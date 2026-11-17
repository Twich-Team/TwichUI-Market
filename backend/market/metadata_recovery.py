"""Durable, bounded server-only enrichment. One request in flight across workers.

Reservations commit before I/O. Leases recover after crashes, budgets are charged
before sending, and controls remain available while the network is slow.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from time import monotonic
import hashlib
import json
import os
import secrets
from sqlalchemy import JSON, and_, cast, func, or_, select, text
from .db import Session, now
from .provider_rates import reserve_budget, retry_delay, cooldown, observe, effective
from .models import ItemMetadata, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, MetadataResource, MetadataAttempt, ItemMedia, Observation, SnapshotStatistic
from .metadata_catalog import get_source, import_everloot_page, store_source
from .metadata_providers import IdentityMismatch, PARSERS, PROVIDERS, decode, fetch
from .provider_secrets import SecretUnavailable, decrypt
from .security import audit, aware

ACTIVE = ('queued', 'running', 'paused')
TERMINAL = ('completed', 'skipped', 'failed', 'cancelled')
LEASE_SECONDS = 120
MAX_TASKS = 1000


def ensure_providers(db):
    if db.bind.dialect.name == 'postgresql': db.execute(text('SELECT pg_advisory_xact_lock(7140242)'))
    for ident, spec in PROVIDERS.items():
        if db.get(MetadataProvider, ident) is None:
            db.add(MetadataProvider(provider=ident, enabled=ident == 'blizzard', automatic=ident == 'blizzard',
                hourly_budget=spec.hourly_limit, daily_budget=spec.daily_limit))
    db.flush()


def observed_query(market_id=None, *, current=True):
    if current:
        ranked = select(Observation.market_id, Observation.snapshot_id,
            func.row_number().over(partition_by=Observation.market_id, order_by=(Observation.retrieved_at.desc(), Observation.id.desc())).label('pos')).subquery()
        query = select(Market.region.label('region'), SnapshotStatistic.item_id.label('item_id')).join(ranked, ranked.c.market_id == Market.id).join(SnapshotStatistic, SnapshotStatistic.snapshot_id == ranked.c.snapshot_id).where(ranked.c.pos == 1)
    else:
        query = select(Market.region.label('region'), SnapshotStatistic.item_id.label('item_id')).join(Observation, Observation.market_id == Market.id).join(SnapshotStatistic, SnapshotStatistic.snapshot_id == Observation.snapshot_id)
    if market_id: query = query.where(Market.id == market_id)
    return query.distinct()


def candidates(db, market_id, mode, limit, providers, *, item_id=None, at=None):
    at = at or now()
    market = db.get(Market, market_id)
    if market is None: raise ValueError('Market not found')
    if mode == 'single': return [(market.region, item_id)]
    if mode == 'bulk': return [(market.region, 1)]
    ids = observed_query(market_id).subquery()
    query = select(ids.c.region, ids.c.item_id).outerjoin(ItemMetadata,
        (ItemMetadata.region == ids.c.region) & (ItemMetadata.item_id == ids.c.item_id))
    if mode == 'missing':
        facts=cast(ItemMetadata.catalog_json,JSON)['fields']
        basic_absent=and_(facts['quality'].as_string().is_(None),facts['class'].as_string().is_(None),facts['level'].as_integer().is_(None))
        query = query.where(or_(ItemMetadata.item_id.is_(None), and_(ItemMetadata.name.is_(None), ItemMetadata.fallback_name.is_(None)), ItemMetadata.catalog_json.is_(None),basic_absent))
    elif mode == 'stale':
        eligible = select(MetadataSource.item_id).where(MetadataSource.region == ids.c.region,
            MetadataSource.item_id == ids.c.item_id, MetadataSource.provider.in_(providers), MetadataSource.refresh_at <= at).exists()
        query = query.where(eligible)
    else: raise ValueError('Unsupported recovery mode')
    return list(db.execute(query.order_by(ItemMetadata.requested_at.desc().nulls_last(), ids.c.item_id).limit(limit)))


def enqueue(db, market_id, mode, providers, *, actor_id=None, item_id=None, limit=100, budget=100, at=None, force_refresh=False, decision=None):
    at = at or now()
    if not providers or any(p not in PROVIDERS for p in providers): raise ValueError('Select known providers')
    providers = sorted(set(providers))
    if not 1 <= limit <= MAX_TASKS or not 1 <= budget <= MAX_TASKS: raise ValueError('Invalid job bounds')
    if mode == 'single' and (type(item_id) is not int or not 1 <= item_id <= 2**31-1): raise ValueError('Invalid item ID')
    if mode == 'bulk' and providers != ['everloot']: raise ValueError('Bulk import currently supports Everloot client attributes only')
    # Serialize enqueue/dedupe independently of the auction collector lock.
    if db.bind.dialect.name == 'postgresql': db.execute(text('SELECT pg_advisory_xact_lock(7140241)'))
    items = candidates(db, market_id, mode, min(limit, MAX_TASKS // len(providers)), providers, item_id=item_id, at=at)
    key = hashlib.sha256(json.dumps([market_id, mode, providers, items, budget, force_refresh], default=list).encode()).hexdigest()
    existing = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == key, MetadataJob.state.in_(ACTIVE)).order_by(MetadataJob.id).limit(1))
    if existing: return existing, False
    job = MetadataJob(actor_id=actor_id, market_id=market_id, mode=mode, providers_json=json.dumps(providers),
        state='queued' if items else 'completed', dedupe_key=key, total=len(items) * len(providers), request_budget=budget, created_at=at, updated_at=at)
    db.add(job); db.flush()
    for region, ident in items:
        for provider in providers: db.add(MetadataTask(job_id=job.id, provider=provider, region=region, item_id=ident, available_at=at, updated_at=at, force_refresh=force_refresh, decision_json=json.dumps(decision) if decision else None))
    audit(db, actor_id, 'metadata.job.created', f'job={job.id}; mode={mode}; tasks={job.total}')
    return job, True



def enqueue_related(db, market_id, resource, *, actor_id=None, pages=1, offset=0, at=None):
    from .foreverdb import RELATED
    if not RELATED.fullmatch(resource) or not 1 <= pages <= 10 or not 0 <= offset <= offset+20*(pages-1) <= 100000:
        raise ValueError('Select a documented bounded profession, vendor or item set resource')
    market = db.get(Market, market_id)
    if market is None: raise ValueError('Market not found')
    if not resource.startswith('professions/') and (pages != 1 or offset != 0): raise ValueError('Only professions are paginated')
    at=at or now()
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(7140241)'))
    key=hashlib.sha256(json.dumps(['related',market_id,resource,pages,offset]).encode()).hexdigest()
    existing=db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key==key,MetadataJob.state.in_(ACTIVE)).limit(1))
    if existing:return existing,False
    job=MetadataJob(actor_id=actor_id,market_id=market_id,mode='related',state='queued',dedupe_key=key,
        providers_json='["foreverdb"]',total=pages,request_budget=pages,created_at=at,updated_at=at)
    db.add(job);db.flush()
    for page in range(pages):
        db.add(MetadataTask(job_id=job.id,provider='foreverdb',region=market.region,item_id=offset+20*page+1,resource=resource,available_at=at))
    audit(db,actor_id,'metadata.related.created',f'job={job.id}; resource={resource}; pages={pages}')
    return job,True


def task_source(db,task,job):
    if job.mode!='related':return get_source(db,task.region,task.item_id,task.provider)
    key=(task.region,task.resource,task.item_id-1)
    row=db.get(MetadataResource,key)
    if row is None:
        row=MetadataResource(region=key[0],resource=key[1],offset=key[2]);db.add(row);db.flush()
    return row

def job_counts(db, job_id):
    return dict(db.execute(select(MetadataTask.state, func.count()).where(MetadataTask.job_id == job_id).group_by(MetadataTask.state)).all())


def finalize(db, job, at):
    db.flush()
    counts = job_counts(db, job.id)
    if sum(counts.get(s, 0) for s in TERMINAL) == job.total and job.state not in ('cancelled',):
        job.state = 'completed'
    job.updated_at = at


def provider_limits(row, at=None):
    spec=PROVIDERS[row.provider]
    keyed=row.provider=='everloot' and row.credential and row.validated_at and (not row.expires_at or aware(row.expires_at)>(at or now()))
    # Even validated Everloot keys remain far below the documented 2,000/hour.
    return (240,2000,15) if keyed else (spec.hourly_limit,spec.daily_limit,spec.interval)


def credential_value(db, row, *, pending=False, at=None):
    if pending and row.pending_credential:
        if row.pending_expires_at and aware(row.pending_expires_at)<=(at or now()):raise SecretUnavailable('Candidate expired')
        value = decrypt(row.provider, row.pending_key_id, row.pending_credential)
    elif row.credential:
        if row.expires_at and aware(row.expires_at) <= (at or now()): raise SecretUnavailable('Credential expired')
        value = decrypt(row.provider, row.credential_key_id, row.credential)
    else:
        value = None
    if value: audit(db, None, 'metadata.credential.used', f'provider={row.provider}; purpose={"validation" if pending else "recovery"}')
    return value


def error_category(status):
    return {401: 'authorization', 402: 'subscription_required', 403: 'forbidden', 404: 'metadata_unavailable',
        429: 'rate_limited'}.get(status, 'upstream_error')


def validate_credential_once(factory, *, at, fetcher):
    with factory.begin() as db:
        row = next((candidate for candidate in db.scalars(select(MetadataProvider).where(MetadataProvider.validation_requested.is_(True)).order_by(MetadataProvider.provider).with_for_update(skip_locked=True)) if reserve_budget(candidate, at) is None), None)
        if row is None: return False
        ident, revision = row.provider, row.validation_revision
        try:
            if ident=='blizzard' and fetcher is fetch and not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):raise SecretUnavailable('OAuth required')
            credential = credential_value(db, row, pending=True, at=at)
        except SecretUnavailable:
            observe(row, None, {}, at)
            row.validation_requested = False; row.validation_error = 'secret_unavailable'
            return True
        attempt=MetadataAttempt(provider=ident,region='us',item_id=25,kind='validation',started_at=at,state='reserved')
        db.add(attempt);db.flush();validation_attempt=attempt.id
    started = monotonic()
    status, headers = None, {}
    try:
        meta, body = fetcher(ident, 25, credential=credential, validate=True)
        status, headers = meta['status'], meta.get('headers', {})
        if status == 200:
            payload = decode(body)
            # Require a real provider contract response, never a generic HTML 200.
            if ident == 'everloot':
                from .metadata_providers import parse_everloot_page
                parse_everloot_page(body, at=at)
            elif ident == 'blizzard':
                from .metadata_providers import plain
                from .item_attributes import attributes,valid_namespace
                if type(payload.get('id')) is not int or payload['id']!=25:raise ValueError('Blizzard validation identity')
                plain(payload.get('name').get('en_US') if isinstance(payload.get('name'),dict) else payload.get('name'))
                attributes(payload)
                if headers.get('Battlenet-Namespace') and not valid_namespace(headers['Battlenet-Namespace'],'us'):raise ValueError('Blizzard validation edition')
            elif ident == 'thewowdb':
                PARSERS[ident](body,25,at=at)
            elif ident == 'foreverdb':
                from .metadata_providers import build_identity
                build_identity(payload.get('meta', {}).get('build') or payload.get('data', {}).get('build'))
        category = None if status == 200 else error_category(status)
    except Exception:
        category = 'transport_or_schema'
    with factory.begin() as db:
        row = db.get(MetadataProvider, ident, with_for_update=True)
        received = at + timedelta(seconds=max(0,monotonic()-started))
        observe(row, status, headers, received, reserved_at=at)
        attempt=db.get(MetadataAttempt,validation_attempt)
        attempt.state,attempt.completed_at,attempt.http_status,attempt.outcome='finished',received,status,category or 'validation_confirmed'
        attempt.returned_json=attempt.new_json='[]'
        if status in (401, 402, 403, 429, 503): cooldown(row, status, headers, received)
        if row.validation_revision != revision: return True
        if status in (429, 503) or status is None or category == 'transport_or_schema':
            row.validation_error = category
            row.cooldown_until = max(aware(row.cooldown_until) if row.cooldown_until else received, received + timedelta(seconds=900 if status is None or category == 'transport_or_schema' else 60))
            return True  # Retry the still-encrypted candidate after cooldown.
        row.validation_requested = False
        row.validation_error = category
        if status == 200:
            if row.pending_credential:
                row.credential, row.credential_key_id = row.pending_credential, row.pending_key_id
                row.expires_at = row.pending_expires_at
            row.validated_at, row.credential_status = at, 'oauth_connected' if ident=='blizzard' else ('connected' if row.credential else 'keyless')
            row.last_error = None
            audit(db, None, 'metadata.credential.validated', f'provider={ident}')
        else:
            # Failed replacement preserves the old active ciphertext and expiry.
            if not row.credential: row.credential_status = 'not_configured'
            row.last_error = category
            audit(db, None, 'metadata.credential.rejected', f'provider={ident}; category={category}')
        row.pending_credential = row.pending_key_id = row.pending_expires_at = None
    return True


@contextmanager
def worker_lock(factory):
    """Session advisory lock protects all worker I/O; no auction locks or long SQL tx."""
    with factory() as db:
        engine = db.get_bind()
    if engine.dialect.name != 'postgresql':
        yield True
        return
    with engine.connect() as connection:
        locked = connection.scalar(text('SELECT pg_try_advisory_lock(7140240)'))
        connection.commit()
        try: yield locked
        finally:
            if locked:
                connection.execute(text('SELECT pg_advisory_unlock(7140240)')); connection.commit()



def latest_foreverdb_build(db):
    return db.scalar(select(cast(MetadataSource.source_json,JSON)['current_build'].as_string()).where(
        MetadataSource.provider=='foreverdb',MetadataSource.fields_json.is_not(None),
        cast(MetadataSource.source_json,JSON)['current_build'].as_string().is_not(None))
        .order_by(MetadataSource.retrieved_at.desc().nulls_last()).limit(1))

def schedule_automatic(db, at, *, allow_mock=False):
    from .recovery_planner import provider_context, load_items, plan_item, phase_sql, source_due_sql
    from sqlalchemy.orm import aliased
    context = provider_context(db, at, execution=True, allow_mock=allow_mock)
    eligible = {ident: values for ident, values in context.items() if values[0].enabled and values[0].automatic and values[2] and values[1] <= at}
    if not eligible: return
    build = latest_foreverdb_build(db)
    last = db.scalar(select(MetadataJob.id).where(MetadataJob.actor_id.is_(None)).order_by(MetadataJob.id.desc()).limit(1)) or 0
    # Four reserved maintenance turns per twenty automatic jobs; missing names
    # otherwise lead. Fallback to the normal order when that tier has no work.
    fair = {0:5, 4:4, 8:3, 12:2}.get(last % 20, 1) if last else 1
    priorities = list(dict.fromkeys([fair,1,2,3,4,5]))
    for current in (True,False):
        for priority in priorities:
            if not current and priority in (2,4): continue
            for market in db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)):
                ids = observed_query(market.id,current=current).subquery()
                src = aliased(MetadataSource)
                possible = select(src.item_id).where(src.region==ids.c.region, src.item_id==ids.c.item_id,
                    src.locale=='en_US', src.provider.in_(eligible), source_due_sql(src,at,build=build)).exists()
                never = select(func.count()).select_from(src).where(src.region==ids.c.region,src.item_id==ids.c.item_id,src.locale=='en_US',src.provider.in_(eligible)).scalar_subquery() < len(eligible)
                query = select(ids.c.region,ids.c.item_id).outerjoin(ItemMetadata,(ItemMetadata.region==ids.c.region)&(ItemMetadata.item_id==ids.c.item_id)).outerjoin(ItemMedia,(ItemMedia.region==ids.c.region)&(ItemMedia.item_id==ids.c.item_id)).where(phase_sql(priority),or_(possible,never)).order_by(ItemMetadata.requested_at.desc().nulls_last(),ids.c.item_id).limit(64)
                identities = list(db.execute(query))
                metadata, media, sources = load_items(db,identities)
                for identity in identities:
                    plan = plan_item(metadata.get(identity),media.get(identity),sources.get(identity,{}),context,at,automatic=True,build=build,priority=priority)
                    chosen = plan['chosen']
                    if not chosen: continue
                    # A pending manual/automatic task in any market owns this
                    # regional provider lookup. The global worker lock still
                    # protects reservation/I/O and crash leases.
                    if db.scalar(select(MetadataTask.id).join(MetadataJob).where(MetadataJob.state.in_(ACTIVE),MetadataTask.state.in_(('queued','running')),
                        MetadataTask.region==identity[0],MetadataTask.item_id==identity[1],MetadataTask.provider==chosen['provider'],MetadataTask.locale=='en_US').limit(1)): continue
                    enqueue(db,market.id,'single',[chosen['provider']],item_id=identity[1],limit=1,budget=1,at=at,decision=plan)
                    return



def tick(factory=Session, *, at=None, fetcher=fetch, automatic=True, provider_client=None):
    at = at or now()
    with worker_lock(factory) as locked:
        if not locked: return False
        with factory.begin() as db:
            ensure_providers(db)
            from .metadata_catalog import backfill_legacy
            backfill_legacy(db)
        if validate_credential_once(factory, at=at, fetcher=fetcher): return True
        with factory.begin() as db:
            # Recover committed leases after process death; requests remain budgeted.
            expired = list(db.scalars(select(MetadataTask).where(MetadataTask.state == 'running', MetadataTask.lease_until <= at)))
            for task in expired:
                job = db.get(MetadataJob, task.job_id)
                task.state = 'cancelled' if job.state == 'cancelled' else ('failed' if task.attempts >= 3 else 'queued')
                task.lease_token = task.lease_until = None
                task.result_json = json.dumps({'status': 'lease_expired', 'provider': task.provider})
                finalize(db, job, at)
            if automatic: schedule_automatic(db, at, allow_mock=fetcher is not fetch)
            # Limit local skips per tick as well as outbound work.
            tasks = list(db.scalars(select(MetadataTask).join(MetadataJob).where(MetadataJob.state.in_(('queued','running')),
                MetadataTask.state == 'queued', MetadataTask.available_at <= at).order_by(MetadataJob.actor_id.is_(None), MetadataTask.id).limit(30)))
            chosen = None
            from .recovery_planner import provider_context, load_items, plan_item
            context=provider_context(db,at,execution=True,allow_mock=fetcher is not fetch) if tasks else {}
            batch=load_items(db,list({(t.region,t.item_id) for t in tasks}))
            build=latest_foreverdb_build(db) if tasks else None
            for task in tasks:
                job, provider = db.get(MetadataJob, task.job_id), db.get(MetadataProvider, task.provider, with_for_update=True)
                if not provider.enabled:
                    task.state, task.result_json = 'skipped', json.dumps({'status':'provider_disabled','provider':task.provider})
                    finalize(db, job, at); continue
                src = task_source(db, task, job)
                if task.force_refresh and task.attempts==0 and src.checked_at and aware(src.checked_at)>=aware(job.created_at) and src.http_status in (200,304):
                    task.state,task.result_json='skipped',json.dumps({'status':'fulfilled_by_other_request','provider':task.provider})
                    finalize(db,job,at);continue
                if job.mode not in ('bulk','related'):
                    identity = (task.region,task.item_id)
                    metadata, media, sources = batch
                    previous = json.loads(task.decision_json) if task.decision_json else None
                    plan = plan_item(metadata.get(identity),media.get(identity),sources.get(identity,{}),
                        context,at,
                        automatic=bool(previous and previous.get('automatic')),force=task.force_refresh,build=build,
                        providers=[task.provider],priority=previous.get('priority') if previous else None,
                        allow_refresh=job.mode=='stale' or task.force_refresh)
                    if previous and previous.get('automatic'):
                        plan['selection']=previous.get('selection',previous)
                        plan['revalidation_explanation']=plan['explanation']
                        if plan['chosen']:plan['explanation']=plan['selection']['explanation']
                    task.decision_json=json.dumps(plan)
                    if not plan['chosen']:
                        action=next(iter(plan['actions']),{})
                        if action.get('next_at') and action['reason'] in ('provider_cooldown','temporarily_unavailable'):
                            task.available_at=datetime.fromisoformat(action['next_at'])
                            task.result_json=json.dumps({'status':action['reason'],'provider':task.provider,'retry_at':action['next_at']})
                        else:
                            task.state,task.result_json='skipped',json.dumps({'status':action.get('reason') or 'no_remaining_goal','provider':task.provider})
                            finalize(db,job,at)
                        continue
                from .foreverdb import needs_detail
                upgrade_detail = job.mode!='related' and needs_detail(src,latest_foreverdb_build(db) if task.provider=='foreverdb' else None)
                if job.mode != 'bulk' and src.retry_at and aware(src.retry_at) > at and not upgrade_detail and not (task.force_refresh and src.status=='available'):
                    if src.status in ('rate_limited', 'upstream_error', 'transport_or_schema'):
                        task.available_at = src.retry_at
                    else:
                        task.state, task.result_json = 'skipped', json.dumps({'status':'cached','provider':task.provider,'retry_at':src.retry_at.isoformat()})
                        finalize(db, job, at)
                    continue
                if job.requests_used >= job.request_budget:
                    if task.result_json and json.loads(task.result_json).get('status') == 'rate_limited':
                        # A 429 consumes quota, but is not a permanently failed item.
                        # Do not silently exceed the owner's finite campaign budget.
                        job.state = 'paused'
                    else:
                        task.state, task.result_json = 'skipped', json.dumps({'status':'job_budget','provider':task.provider})
                        finalize(db, job, at)
                    continue
                try:
                    key = credential_value(db, provider, at=at)
                    if task.provider == 'foreverdb' and not key: raise SecretUnavailable('Key required')
                    if task.provider == 'blizzard' and not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')) and fetcher is fetch:
                        raise SecretUnavailable('OAuth required')
                except SecretUnavailable:
                    provider.last_error = 'credential_unavailable'
                    task.state, task.result_json = 'skipped', json.dumps({'status':'credential_unavailable','provider':task.provider})
                    finalize(db, job, at); continue
                waiting = reserve_budget(provider, at)
                if waiting:
                    task.available_at = waiting; continue
                task.state, task.lease_token, task.lease_until = 'running', secrets.token_urlsafe(24), at + timedelta(seconds=LEASE_SECONDS)
                task.attempts += 1; job.requests_used += 1; job.state = 'running'; job.updated_at = at
                attempt=MetadataAttempt(task_id=task.id,provider=task.provider,region=task.region,item_id=task.item_id,
                    kind='bulk' if job.mode=='bulk' else 'related' if job.mode=='related' else 'metadata',
                    started_at=at,state='reserved',decision_json=task.decision_json)
                db.add(attempt);db.flush()
                attempt_id=attempt.id
                chosen = (task.id, task.lease_token, task.provider, task.region, task.item_id, job.mode, key, None if upgrade_detail else src.etag, effective(provider, at)['page_size'], task.resource)
                break
        if chosen is None: return bool(tasks or expired)
        task_id, token, ident, region, item_id, mode, key, etag, page_size, resource = chosen
        parsed, raw, status, headers, category = None, None, None, {}, None
        started = monotonic()
        try:
            kwargs={'credential':key,'etag':etag,'offset':item_id-1 if mode in ('bulk','related') else None,'region':region}
            if mode=='related':kwargs['resource']=resource
            if fetcher is fetch:
                kwargs['page_size'] = page_size
                if ident=='blizzard':kwargs['client']=provider_client
            meta, raw = fetcher(ident, item_id, **kwargs)
            status, headers = meta['status'], meta.get('headers', {})
            if status == 200 and ident != 'blizzard' and mode not in ('bulk','related'): parsed = PARSERS[ident](raw, item_id, at=at)
            if status not in (200, 304): category = error_category(status)
        except IdentityMismatch: category = 'wrong_identity'
        except Exception: category = 'transport_or_schema'
        with factory.begin() as db:
            task = db.get(MetadataTask, task_id, with_for_update=True)
            if task.lease_token != token: return True
            job, provider = db.get(MetadataJob, task.job_id), db.get(MetadataProvider, ident, with_for_update=True)
            received = at + timedelta(seconds=max(0,monotonic()-started))
            observe(provider, status, headers, received, reserved_at=at)
            src = task_source(db, task, job)
            src.checked_at, src.http_status = at, status
            result = {'provider':ident, 'item_id':item_id, 'http_status':status, 'status':category or 'available', 'recovered_fields':[]}
            if mode=='related':result.update(resource=resource,record_scope='catalog')
            before_row = db.get(ItemMetadata, (region, item_id)) if mode!='related' else None
            before_fields = json.loads(before_row.catalog_json).get('fields', {}) if before_row and before_row.catalog_json else {}
            if before_row and before_row.name: before_fields['name'] = before_row.name
            elif before_row and before_row.fallback_name: before_fields['name'] = before_row.fallback_name
            try:
                if category is None and status == 200:
                    with db.begin_nested():
                        if mode == 'related':
                            from .metadata_catalog import import_foreverdb_resource
                            payload=decode(raw);metadata=payload.get('meta',{})
                            if resource.startswith('professions/') and metadata.get('offset')!=item_id-1:raise ValueError('Resource page offset mismatch')
                            changes={}
                            count,origin=import_foreverdb_resource(db,region,resource,raw,at=at,changes=changes)
                            src.fields_json=json.dumps(payload['data']);src.source_json=json.dumps(origin)
                            src.status='available';src.etag=headers.get('ETag')
                            src.refresh_at=src.retry_at=at+timedelta(days=1)
                            result.update(imported_items=count,recovered_fields=[{'professions':'crafting','vendors':'vendors','itemsets':'item_sets'}[resource.split('/')[0]]],source=origin)
                        elif mode == 'bulk':
                            if decode(raw).get('offset')!=item_id-1:raise ValueError('Bulk response offset mismatch')
                            changes = {}
                            count, next_offset = import_everloot_page(db, region, raw, at=at, changes=changes)
                            result.update(imported_items=count, recovered_fields=['client_attributes'])
                            if next_offset is not None and job.total < job.request_budget and job.state != 'cancelled':
                                db.add(MetadataTask(job_id=job.id, provider=ident, region=region, item_id=next_offset+1, available_at=at))
                                job.total += 1
                        elif ident == 'blizzard':
                            from .metadata import store_metadata
                            store_metadata(db, region, item_id, raw, at=at, resolved_namespace=headers.get('Battlenet-Namespace'))
                            stored=db.get(ItemMetadata,(region,item_id))
                            result['recovered_fields']=list(json.loads(stored.details or '{}').keys()-{'scope'})+(['name'] if stored.name else [])
                        else:
                            fields, origin = parsed
                            store_source(db, region, item_id, ident, fields, origin, at=at, etag=headers.get('ETag'))
                            result.update(recovered_fields=list(fields), source={k:v for k,v in origin.items() if k!='record'})
                        after_row = db.get(ItemMetadata, (region, item_id)) if mode!='related' else None
                        after_fields = json.loads(after_row.catalog_json).get('fields', {}) if after_row and after_row.catalog_json else {}
                        result['new_fields'] = list(changes) if mode in ('related','bulk') else [field for field, value in after_fields.items() if value is not None and value != [] and before_fields.get(field) in (None, [])]
                        result['outcome'] = ('name_recovered' if 'name' in result['new_fields'] else 'attributes_recovered' if result['new_fields']
                            else 'already_known' if result['recovered_fields'] else 'no_usable_data')
                        provider.last_success, provider.last_error = at, None
                        if result.get('new_fields'): provider.last_recovery = at
                        task.state = 'completed'
                        audit(db, job.actor_id, 'metadata.item.recovered', f'job={job.id}; provider={ident}; item={item_id}')
                elif category is None and status == 304 and src.fields_json:
                    src.status = 'available'; src.retry_at = src.refresh_at = at + timedelta(seconds=PROVIDERS[ident].refresh_seconds)
                    task.state = 'completed'; result['status'] = 'not_modified'
                    result['outcome'] = 'already_known'
                    provider.last_success, provider.last_error = at, None
                else:
                    if category is None: category = 'invalid_not_modified'
            except Exception:
                category = 'transport_or_schema'
                result['recovered_fields']=[]
                result.pop('imported_items',None)
                result.pop('new_fields',None)
                result.pop('outcome',None)
            if category:
                src.status = category
                delay = 604800 if status == 404 else 900
                src.retry_at = at + timedelta(seconds=max(delay,retry_delay(headers.get('Retry-After'),at)))
                provider.last_error = category
                if status is not None and status >= 500 and status != 503 and headers.get('Retry-After'):
                    provider.cooldown_until = max(aware(provider.cooldown_until) if provider.cooldown_until else at,src.retry_at)
                if ident == 'blizzard':
                    primary=db.get(ItemMetadata,(region,item_id))
                    if primary is None:
                        primary=ItemMetadata(region=region,item_id=item_id,namespace=f'static-forever-{region}')
                        db.add(primary)
                    primary.http_status,primary.checked_at,primary.retry_after=status,at,src.retry_at
                    primary.status='missing' if status==404 else 'error'
                if status in (401, 402, 403, 429, 503):
                    cooldown(provider, status, headers, received)
                    src.retry_at = (aware(provider.cooldown_until) if status in (429, 503) else max(aware(src.retry_at), aware(provider.cooldown_until)))
                result['status'] = category
                result['outcome'] = {'wrong_identity':'wrong_identity','transport_or_schema':'invalid_response','metadata_unavailable':'missing','forbidden':'access_blocked','authorization':'credentials_invalid','rate_limited':'rate_limited'}.get(category,'unavailable')
                # Missing is a completed provider result, never a nonexistent item.
                if status == 404: task.state = 'completed'
                elif status == 429 or (status is None or status >= 500) and task.attempts < 3:
                    task.state, task.available_at = 'queued', src.retry_at
                else: task.state = 'failed'
            if job.state == 'cancelled': task.state = 'cancelled'
            task.lease_token = task.lease_until = None
            task.result_json, task.updated_at = json.dumps(result), at
            attempt=db.get(MetadataAttempt,attempt_id)
            attempt.state,attempt.completed_at,attempt.http_status='finished',received,status
            attempt.outcome=result.get('outcome',result['status'])
            attempt.returned_json=json.dumps(result.get('recovered_fields',[]))
            attempt.new_json=json.dumps(result.get('new_fields',[]))
            if mode not in ('bulk','related'):
                previous_evidence=json.loads(src.recovery_json) if src.recovery_json else {}
                src.recovery_json=json.dumps({'policy_version':1,'returned_fields':result.get('recovered_fields',[]),
                    'new_fields':result.get('new_fields',[]),'outcome':attempt.outcome,
                    'last_useful_at':at.isoformat() if result.get('new_fields') else previous_evidence.get('last_useful_at')})
            finalize(db, job, at)
        return True
