"""Durable, bounded server-only enrichment. One request in flight across workers.

Reservations commit before I/O. Leases recover after crashes, budgets are charged
before sending, and controls remain available while the network is slow.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import secrets
from sqlalchemy import and_, func, or_, select, text
from .db import Session, now
from .models import ItemMetadata, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, Observation, SnapshotStatistic
from .metadata_catalog import get_source, import_everloot_page, store_source
from .metadata_providers import PARSERS, PROVIDERS, decode, fetch
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
        query = query.where(or_(ItemMetadata.item_id.is_(None), and_(ItemMetadata.name.is_(None), ItemMetadata.fallback_name.is_(None)), ItemMetadata.catalog_json.is_(None)))
    elif mode == 'stale':
        eligible = select(MetadataSource.item_id).where(MetadataSource.region == ids.c.region,
            MetadataSource.item_id == ids.c.item_id, MetadataSource.provider.in_(providers), MetadataSource.refresh_at <= at).exists()
        query = query.where(eligible)
    else: raise ValueError('Unsupported recovery mode')
    return list(db.execute(query.order_by(ItemMetadata.requested_at.desc().nulls_last(), ids.c.item_id).limit(limit)))


def enqueue(db, market_id, mode, providers, *, actor_id=None, item_id=None, limit=100, budget=100, at=None):
    at = at or now()
    if not providers or any(p not in PROVIDERS for p in providers): raise ValueError('Select known providers')
    providers = sorted(set(providers))
    if not 1 <= limit <= MAX_TASKS or not 1 <= budget <= MAX_TASKS: raise ValueError('Invalid job bounds')
    if mode == 'single' and (type(item_id) is not int or not 1 <= item_id <= 2**31-1): raise ValueError('Invalid item ID')
    if mode == 'bulk' and providers != ['everloot']: raise ValueError('Bulk import currently supports Everloot client attributes only')
    # Serialize enqueue/dedupe independently of the auction collector lock.
    if db.bind.dialect.name == 'postgresql': db.execute(text('SELECT pg_advisory_xact_lock(7140241)'))
    items = candidates(db, market_id, mode, min(limit, MAX_TASKS // len(providers)), providers, item_id=item_id, at=at)
    key = hashlib.sha256(json.dumps([market_id, mode, providers, items, budget], default=list).encode()).hexdigest()
    existing = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == key, MetadataJob.state.in_(ACTIVE)).order_by(MetadataJob.id).limit(1))
    if existing: return existing, False
    job = MetadataJob(actor_id=actor_id, market_id=market_id, mode=mode, providers_json=json.dumps(providers),
        state='queued' if items else 'completed', dedupe_key=key, total=len(items) * len(providers), request_budget=budget, created_at=at, updated_at=at)
    db.add(job); db.flush()
    for region, ident in items:
        for provider in providers: db.add(MetadataTask(job_id=job.id, provider=provider, region=region, item_id=ident, available_at=at, updated_at=at))
    audit(db, actor_id, 'metadata.job.created', f'job={job.id}; mode={mode}; tasks={job.total}')
    return job, True


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


def reserve_budget(row, at):
    hourly_ceiling,daily_ceiling,interval=provider_limits(row,at)
    if row.cooldown_until and aware(row.cooldown_until) > at: return aware(row.cooldown_until)
    if row.next_request_at and aware(row.next_request_at) > at: return aware(row.next_request_at)
    if not row.hour_start or at >= aware(row.hour_start) + timedelta(hours=1): row.hour_start, row.hour_used = at, 0
    if not row.day_start or at >= aware(row.day_start) + timedelta(days=1): row.day_start, row.day_used = at, 0
    if row.hour_used >= min(row.hourly_budget,hourly_ceiling): return aware(row.hour_start) + timedelta(hours=1)
    if row.day_used >= min(row.daily_budget,daily_ceiling): return aware(row.day_start) + timedelta(days=1)
    row.hour_used += 1; row.day_used += 1
    row.next_request_at = at + timedelta(seconds=interval)
    return None


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


def retry_delay(value, at):
    if value is None:return 0
    try:
        seconds=int(value) if str(value).isdigit() else int((aware(parsedate_to_datetime(value))-at).total_seconds())
    except (TypeError,ValueError,OverflowError):return 0
    return max(0,min(seconds,int((datetime.max.replace(tzinfo=timezone.utc)-at).total_seconds())-1))


def cooldown(row, status, headers, at):
    category = error_category(status)
    row.last_error = category
    if status in (401, 402, 403, 429):
        # Respect Retry-After, including dates, with a conservative minimum.
        delay = max(3600 if status != 429 else 60, retry_delay(headers.get('Retry-After'), at))
        row.cooldown_until = at + timedelta(seconds=delay)
    return category


def validate_credential_once(factory, *, at, fetcher):
    with factory.begin() as db:
        row = db.scalar(select(MetadataProvider).where(MetadataProvider.validation_requested.is_(True)).order_by(MetadataProvider.provider).with_for_update(skip_locked=True).limit(1))
        if row is None: return False
        if reserve_budget(row, at): return False
        ident, revision = row.provider, row.validation_revision
        try:
            if ident=='blizzard' and fetcher is fetch and not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):raise SecretUnavailable('OAuth required')
            credential = credential_value(db, row, pending=True, at=at)
        except SecretUnavailable:
            row.validation_requested = False; row.validation_error = 'secret_unavailable'
            return True
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
        status, headers, category = None, {}, 'transport_or_schema'
    with factory.begin() as db:
        row = db.get(MetadataProvider, ident, with_for_update=True)
        if row.validation_revision != revision: return True
        if status in (429, 503) or status is None:
            row.validation_error = category
            row.cooldown_until = at + timedelta(seconds=900)
            if status == 429: cooldown(row, status, headers, at)
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


def schedule_automatic(db, at, *, allow_mock=False):
    # At most one automatic job per provider; a blocked provider cannot stall others.
    for market in db.scalars(select(Market).where(Market.enabled.is_(True), Market.verified.is_(True)).order_by(Market.id)):
        for provider in db.scalars(select(MetadataProvider).where(MetadataProvider.enabled.is_(True), MetadataProvider.automatic.is_(True)).order_by(MetadataProvider.provider)):
            if db.scalar(select(MetadataTask.id).join(MetadataJob).where(MetadataJob.actor_id.is_(None),MetadataJob.state.in_(ACTIVE),MetadataTask.provider==provider.provider,MetadataTask.state.in_(('queued','running'))).limit(1)):continue
            if provider.provider=='blizzard' and not allow_mock and not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):continue
            if provider.provider=='foreverdb' and not provider.credential:continue
            if provider.expires_at and aware(provider.expires_at)<=at:continue
            if provider.cooldown_until and aware(provider.cooldown_until)>at:continue
            if provider.next_request_at and aware(provider.next_request_at)>at:continue
            for current,phase in ((True,'missing'),(True,'priority'),(False,'missing'),(True,'stale'),(False,'stale')):
                ids = observed_query(market.id,current=current).subquery()
                query = select(ids.c.item_id).outerjoin(ItemMetadata, (ItemMetadata.region == ids.c.region) & (ItemMetadata.item_id == ids.c.item_id)).outerjoin(MetadataSource,
                    (MetadataSource.region == ids.c.region) & (MetadataSource.item_id == ids.c.item_id) & (MetadataSource.provider == provider.provider) & (MetadataSource.locale == 'en_US'))
                if phase=='missing':query=query.where(func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).is_(None))
                if phase=='priority':query=query.where(ItemMetadata.requested_at>=at-timedelta(days=7))
                query = query.where(or_(MetadataSource.item_id.is_(None), MetadataSource.retry_at <= at)).order_by(
                    func.coalesce(ItemMetadata.name, ItemMetadata.fallback_name).is_not(None), ItemMetadata.requested_at.desc().nulls_last(), ids.c.item_id)
                ident = db.scalar(query.limit(1))
                if ident:
                    enqueue(db, market.id, 'single', [provider.provider], item_id=ident, limit=1, budget=1, at=at)
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
            for task in tasks:
                job, provider = db.get(MetadataJob, task.job_id), db.get(MetadataProvider, task.provider)
                if not provider.enabled:
                    task.state, task.result_json = 'skipped', json.dumps({'status':'provider_disabled','provider':task.provider})
                    finalize(db, job, at); continue
                src = get_source(db, task.region, task.item_id, task.provider)
                if job.mode != 'bulk' and src.retry_at and aware(src.retry_at) > at:
                    task.state, task.result_json = 'skipped', json.dumps({'status':'cached','provider':task.provider,'retry_at':src.retry_at.isoformat()})
                    finalize(db, job, at); continue
                if job.requests_used >= job.request_budget:
                    task.state, task.result_json = 'skipped', json.dumps({'status':'job_budget','provider':task.provider})
                    finalize(db, job, at); continue
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
                chosen = (task.id, task.lease_token, task.provider, task.region, task.item_id, job.mode, key, src.etag)
                break
        if chosen is None: return bool(tasks or expired)
        task_id, token, ident, region, item_id, mode, key, etag = chosen
        parsed, raw, status, headers, category = None, None, None, {}, None
        try:
            kwargs={'credential':key,'etag':etag,'offset':item_id-1 if mode=='bulk' else None,'region':region}
            if ident=='blizzard' and fetcher is fetch:kwargs['client']=provider_client
            meta, raw = fetcher(ident, item_id, **kwargs)
            status, headers = meta['status'], meta.get('headers', {})
            if status == 200 and ident != 'blizzard' and mode != 'bulk': parsed = PARSERS[ident](raw, item_id, at=at)
            if status not in (200, 304): category = error_category(status)
        except Exception: category = 'transport_or_schema'
        with factory.begin() as db:
            task = db.get(MetadataTask, task_id, with_for_update=True)
            if task.lease_token != token: return True
            job, provider = db.get(MetadataJob, task.job_id), db.get(MetadataProvider, ident)
            src = get_source(db, region, item_id, ident)
            src.checked_at, src.http_status = at, status
            result = {'provider':ident, 'item_id':item_id, 'http_status':status, 'status':category or 'available', 'recovered_fields':[]}
            try:
                if category is None and status == 200:
                    with db.begin_nested():
                        if mode == 'bulk':
                            if decode(raw).get('offset')!=item_id-1:raise ValueError('Bulk response offset mismatch')
                            count, next_offset = import_everloot_page(db, region, raw, at=at)
                            result.update(imported_items=count, recovered_fields=['client_attributes'])
                            if next_offset is not None and job.total < job.request_budget and job.state != 'cancelled':
                                db.add(MetadataTask(job_id=job.id, provider=ident, region=region, item_id=next_offset+1, available_at=at))
                                job.total += 1
                        elif ident == 'blizzard':
                            from .metadata import store_metadata
                            store_metadata(db, region, item_id, raw, at=at, resolved_namespace=headers.get('Battlenet-Namespace'))
                            result['recovered_fields'] = ['name', 'base_attributes']
                        else:
                            fields, origin = parsed
                            store_source(db, region, item_id, ident, fields, origin, at=at, etag=headers.get('ETag'))
                            result.update(recovered_fields=list(fields), source=origin)
                        provider.last_success, provider.last_error = at, None
                        task.state = 'completed'
                        audit(db, job.actor_id, 'metadata.item.recovered', f'job={job.id}; provider={ident}; item={item_id}')
                elif category is None and status == 304 and src.fields_json:
                    src.status = 'available'; src.retry_at = src.refresh_at = at + timedelta(seconds=PROVIDERS[ident].refresh_seconds)
                    task.state = 'completed'; result['status'] = 'not_modified'
                    provider.last_success, provider.last_error = at, None
                else:
                    if category is None: category = 'invalid_not_modified'
            except Exception:
                category = 'transport_or_schema'
                result['recovered_fields']=[]
                result.pop('imported_items',None)
            if category:
                src.status = category
                delay = 604800 if status == 404 else 900
                src.retry_at = at + timedelta(seconds=delay)
                provider.last_error = category
                if ident == 'blizzard':
                    primary=db.get(ItemMetadata,(region,item_id))
                    if primary is None:
                        primary=ItemMetadata(region=region,item_id=item_id,namespace=f'static-forever-{region}')
                        db.add(primary)
                    primary.http_status,primary.checked_at,primary.retry_after=status,at,src.retry_at
                    primary.status='missing' if status==404 else 'error'
                if status in (401, 402, 403, 429):
                    cooldown(provider, status, headers, at)
                    src.retry_at = max(aware(src.retry_at), aware(provider.cooldown_until))
                result['status'] = category
                # Missing is a completed provider result, never a nonexistent item.
                if status == 404: task.state = 'completed'
                elif status == 429 or (status is None or status >= 500) and task.attempts < 3:
                    task.state, task.available_at = 'queued', src.retry_at
                else: task.state = 'failed'
            if job.state == 'cancelled': task.state = 'cancelled'
            task.lease_token = task.lease_until = None
            task.result_json, task.updated_at = json.dumps(result), at
            finalize(db, job, at)
        return True
