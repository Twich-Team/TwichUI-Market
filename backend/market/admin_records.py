"""Bounded administration record queries; never contact external providers."""
from datetime import datetime
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import JSON, String, case, cast, func, or_, select, tuple_
from sqlalchemy.orm import Session
from .db import now, session
from .models import CollectionRun, ItemMedia, ItemMetadata, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, SecurityEvent, User
from .metadata_admin import job_view
from .market_api import metadata_name
from .metadata_catalog import FIELDS
from .metadata_recovery import ACTIVE, enqueue, observed_query, provider_limits
from .security import admin, aware

router = APIRouter(prefix='/api/v1/admin/records')
Provider = Literal['blizzard', 'everloot', 'foreverdb', 'thewowdb']
# Historical results did not distinguish returned data from actual gains.
OUTCOMES = ('name_recovered', 'attributes_recovered', 'already_known', 'metadata_returned', 'no_usable_data',
    'missing', 'wrong_identity', 'invalid_response', 'credentials_invalid', 'access_blocked', 'rate_limited',
    'unavailable', 'pending', 'skipped', 'attributes_returned', 'observations_returned', 'name_returned')
RESULTS = cast(MetadataTask.result_json, JSON)
STATUS = RESULTS['status'].as_string()
RECORDED_OUTCOME = func.coalesce(RESULTS['outcome'].as_string(), case(
    (MetadataTask.state.in_(('queued', 'running')), 'pending'),
    (STATUS == 'not_modified', 'already_known'),
    (STATUS == 'metadata_unavailable', 'missing'),
    (STATUS == 'forbidden', 'access_blocked'),
    (STATUS.in_(('authorization', 'credential_unavailable')), 'credentials_invalid'),
    (STATUS == 'rate_limited', 'rate_limited'),
    (STATUS == 'wrong_identity', 'wrong_identity'),
    (STATUS == 'transport_or_schema', 'invalid_response'),
    ((STATUS == 'available') & (cast(RESULTS['recovered_fields'], String) == '[]'), 'no_usable_data'),
    (STATUS == 'available', 'metadata_returned'),
    (MetadataTask.state.in_(('skipped', 'cancelled')), 'skipped'), else_='unavailable'))
OUTCOME = case((STATUS == 'attributes_only', 'attributes_returned'), (STATUS == 'observations_only', 'observations_returned'), ((STATUS == 'named_record') & (RECORDED_OUTCOME == 'metadata_returned'), 'name_returned'), else_=RECORDED_OUTCOME)


def page(db, query, order, offset, limit):
    count = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return count, list(db.execute(query.order_by(*order).offset(offset).limit(limit)))


def dates(query, column, since, until):
    if since and until and aware(since) >= aware(until): raise HTTPException(422, 'End time must follow start time')
    if since: query = query.where(column >= aware(since))
    if until: query = query.where(column < aware(until))
    return query


def retry_permission(db, task, provider, src, active_identities=None):
    at = now()
    if task.state not in ('completed', 'failed', 'skipped'): return False, 'Attempt is still active or cancelled', None
    if not provider or not provider.enabled: return False, 'Provider disabled', None
    times = [aware(t) for t in (provider.cooldown_until, provider.next_request_at, src.retry_at if src else None) if t and aware(t) > at]
    hourly, daily, _ = provider_limits(provider, at)
    from datetime import timedelta
    for start, used, cap, duration in ((provider.hour_start, provider.hour_used, min(hourly,provider.hourly_budget),timedelta(hours=1)),
                                     (provider.day_start, provider.day_used, min(daily,provider.daily_budget),timedelta(days=1))):
        if start and aware(start)+duration > at and used >= cap: times.append(aware(start)+duration)
    if times: return False, 'Retry not yet eligible', max(times)
    if provider.expires_at and aware(provider.expires_at) <= at: return False, 'Credential expired', None
    if provider.provider == 'foreverdb' and not provider.credential: return False, 'Credential unavailable', None
    active = ((task.provider,task.region,task.item_id) in active_identities) if active_identities is not None else db.scalar(select(MetadataTask.id).join(MetadataJob).where(MetadataJob.state.in_(ACTIVE),
        MetadataTask.state.in_(('queued','running')),MetadataTask.provider==task.provider,
        MetadataTask.region==task.region,MetadataTask.item_id==task.item_id).limit(1))
    if active: return False, 'Recovery already queued', None
    return True, None, None


def safe_attempt(db, task, metadata, provider, src, outcome, job, active_identities=None):
    value = json.loads(task.result_json) if task.result_json else {}
    origin = value.get('source') or {}
    scope = 'catalog' if job.mode=='bulk' or value.get('kind') in ('attributes','corpus','corpus_page') else 'item'
    permitted, reason, eligible = retry_permission(db, task, provider, src, active_identities)
    if job and job.mode in ('bulk','diagnostic'): permitted,reason=False,'Preview a bounded recovery job'
    # Explicit allowlist. No payload, URLs, headers, exception text or credentials.
    return {'id':task.id,'job_id':task.job_id,'item_id':task.item_id,'region':task.region,'provider':task.provider,
        'record_scope':scope,'item_name':(metadata.name or metadata.fallback_name) if metadata and scope=='item' else None,'quality':metadata_name(metadata,task.item_id)['quality'] if scope=='item' else None,'state':task.state,
        'at':task.updated_at,'attempts':task.attempts,'http_status':value.get('http_status'),
        'outcome':outcome,'delta_recorded':'new_fields' in value,'fields_returned':[f for f in value.get('fields_returned',value.get('recovered_fields',[])) if f in FIELDS or f in ('base_attributes','client_attributes')],
        'fields_recovered':[f for f in value.get('new_fields',[]) if f in FIELDS],
        'error_category':value.get('status') if value.get('status') in ('authorization','forbidden','rate_limited','metadata_unavailable','transport_or_schema','wrong_identity','upstream_error','invalid_not_modified') else None,
        'source':{'edition':'forever','build':origin.get('build'),'confidence':origin.get('confidence')},
        'next_retry':eligible or (src.retry_at if src else task.available_at if task.state=='queued' else None),
        'retry_allowed':permitted,'retry_reason':reason}


@router.get('/metadata-attempts')
def attempts(market_id: int | None = Query(None, ge=1), provider: Provider | None = None,
             outcome: str | None = None, item_id: int | None = Query(None, ge=1, le=2**31-1),
             since: datetime | None = None, until: datetime | None = None, q: str = Query('',max_length=64),
             offset: int = Query(0, ge=0, le=1000000), limit: int = Query(25, ge=1, le=100),
             sort: Literal['at','item_id','provider','outcome'] = 'at', desc: bool = True,
             user: User = Depends(admin), db: Session = Depends(session)):
    query = select(MetadataTask, ItemMetadata, OUTCOME.label('outcome'), MetadataJob).join(MetadataJob).outerjoin(ItemMetadata,
        (ItemMetadata.region==MetadataTask.region)&(ItemMetadata.item_id==MetadataTask.item_id))
    if market_id: query = query.where(MetadataJob.market_id==market_id)
    if provider: query = query.where(MetadataTask.provider==provider)
    if item_id: query = query.where(MetadataTask.item_id==item_id)
    if q.strip():
        term=q.strip()
        query=query.where(or_(cast(MetadataTask.item_id,String)==term,ItemMetadata.name.icontains(term,autoescape=True),ItemMetadata.fallback_name.icontains(term,autoescape=True)))
    query = dates(query, MetadataTask.updated_at, since, until)
    if outcome:
        if outcome not in OUTCOMES: raise HTTPException(422, 'Unknown attempt outcome')
        query = query.where(OUTCOME==outcome)
    filtered=query.subquery()
    summary=dict(db.execute(select(filtered.c.outcome,func.count()).group_by(filtered.c.outcome)).all())
    column={'at':MetadataTask.updated_at,'item_id':MetadataTask.item_id,'provider':MetadataTask.provider,'outcome':OUTCOME}[sort]
    count, rows = page(db,query,((column.desc() if desc else column.asc()),MetadataTask.id.desc()),offset,limit)
    providers={p.provider:p for p in db.scalars(select(MetadataProvider))}
    identities = [(r[0].region,r[0].item_id,r[0].locale,r[0].provider) for r in rows]
    sources = {(s.region,s.item_id,s.locale,s.provider):s for s in db.scalars(select(MetadataSource).where(tuple_(MetadataSource.region,MetadataSource.item_id,MetadataSource.locale,MetadataSource.provider).in_(identities)))} if identities else {}
    active_identities = set(db.execute(select(MetadataTask.provider,MetadataTask.region,MetadataTask.item_id).join(MetadataJob).where(MetadataJob.state.in_(ACTIVE), MetadataTask.state.in_(('queued','running')),tuple_(MetadataTask.region,MetadataTask.item_id,MetadataTask.locale,MetadataTask.provider).in_(identities))).all()) if identities else set()
    records=[]
    for task,metadata,result_outcome,job in rows:
        src=sources.get((task.region,task.item_id,task.locale,task.provider))
        records.append(safe_attempt(db,task,metadata,providers.get(task.provider),src,result_outcome,job,active_identities))
    return {'rows':records,'total':count,'summary':summary}


@router.post('/metadata-attempts/{task_id}/retry', status_code=202)
def retry(task_id: int, user: User = Depends(admin), db: Session = Depends(session)):
    task=db.get(MetadataTask,task_id)
    if not task: raise HTTPException(404,'Attempt not found')
    provider=db.get(MetadataProvider,task.provider,with_for_update=True)
    src=db.get(MetadataSource,(task.region,task.item_id,task.locale,task.provider))
    allowed,reason,_=retry_permission(db,task,provider,src)
    if not allowed: raise HTTPException(409,reason)
    original=db.get(MetadataJob,task.job_id)
    if original.mode=='diagnostic': raise HTTPException(409,'Diagnostic attempts require an explicit operator window')
    if original.mode=='bulk': raise HTTPException(409,'Preview a bounded bulk job instead')
    job,_=enqueue(db,original.market_id,'single',[task.provider],actor_id=user.id,item_id=task.item_id,limit=1,budget=1)
    db.commit()
    return {'job_id':job.id,'state':job.state}


@router.get('/jobs')
def jobs(offset: int = Query(0,ge=0,le=1000000), limit: int = Query(25,ge=1,le=100),
         market_id: int | None = Query(None,ge=1), q: str = Query('',max_length=64), state: str | None = None,
         sort: Literal['id','mode','state','created_at','updated_at'] = 'id', desc: bool = True,
         user: User = Depends(admin), db: Session = Depends(session)):
    query=select(MetadataJob)
    if market_id: query=query.where(MetadataJob.market_id==market_id)
    if q: query=query.where(cast(MetadataJob.id,String).contains(q,autoescape=True))
    if state: query=query.where(MetadataJob.state==state)
    column=getattr(MetadataJob,sort)
    count,rows=page(db,query,((column.desc() if desc else column.asc()),MetadataJob.id.desc()),offset,limit)
    return {'rows':[job_view(db,row[0]) for row in rows],'total':count}


@router.get('/security')
def security(q: str = Query('',max_length=64), category: str = Query('',max_length=64),
             since: datetime | None = None, until: datetime | None = None,
             offset: int = Query(0,ge=0,le=1000000),limit: int = Query(25,ge=1,le=100),
             sort: Literal['created_at','action','actor_id'] = 'created_at',desc: bool = True,
             user: User = Depends(admin), db: Session = Depends(session)):
    query=select(SecurityEvent,User.username).outerjoin(User,User.id==SecurityEvent.actor_id)
    if q: query=query.where(or_(User.username.icontains(q,autoescape=True),SecurityEvent.action.icontains(q,autoescape=True)))
    if category: query=query.where(SecurityEvent.action.startswith(category,autoescape=True))
    query=dates(query,SecurityEvent.created_at,since,until)
    column=getattr(SecurityEvent,sort)
    count,rows=page(db,query,((column.desc() if desc else column.asc()),SecurityEvent.id.desc()),offset,limit)
    return {'total':count,'rows':[{'id':r.id,'actor_id':r.actor_id,'account':name,'action':r.action,'at':r.created_at,
        'detail':r.detail} for r,name in rows]}


@router.get('/collection')
def collection(market_id: int | None = Query(None,ge=1),status: str = Query('',max_length=32),
               offset: int = Query(0,ge=0,le=1000000),limit: int = Query(25,ge=1,le=100),
               sort: Literal['checked_at','market_id','status','http_status','duration_seconds','payload_bytes']='checked_at',desc: bool=True,
               user: User = Depends(admin),db: Session = Depends(session)):
    query=select(CollectionRun)
    if market_id: query=query.where(CollectionRun.market_id==market_id)
    if status=='failures': query=query.where(or_(CollectionRun.status=='failed',CollectionRun.error.is_not(None)))
    elif status: query=query.where(CollectionRun.status==status)
    column=getattr(CollectionRun,sort)
    count,rows=page(db,query,((column.desc() if desc else column.asc()),CollectionRun.id.desc()),offset,limit)
    return {'total':count,'rows':[{k:getattr(r[0],k) for k in ('id','market_id','checked_at','status','http_status','duration_seconds','payload_bytes','error')} for r in rows]}


@router.get('/unresolved')
def unresolved(market_id: int = Query(ge=1),item_id: int | None = Query(None,ge=1,le=2**31-1),
               primary: Literal['missing','pending'] | None=None,
               offset: int = Query(0,ge=0,le=1000000),limit: int = Query(25,ge=1,le=100),
               sort: Literal['item_id','checked_at','retry_after']='item_id',desc: bool=False,
               user: User = Depends(admin),db: Session = Depends(session)):
    ids=observed_query(market_id).subquery()
    supplemental_checked=select(func.max(MetadataSource.checked_at)).where(MetadataSource.region==ids.c.region,MetadataSource.item_id==ids.c.item_id,MetadataSource.provider!='blizzard').correlate(ids).scalar_subquery()
    supplemental_retry=select(func.min(MetadataSource.retry_at)).where(MetadataSource.region==ids.c.region,MetadataSource.item_id==ids.c.item_id,MetadataSource.provider!='blizzard').correlate(ids).scalar_subquery()
    primary_checked=case((ItemMetadata.http_status.is_not(None),ItemMetadata.checked_at),else_=None)
    last_attempt=case((primary_checked.is_(None),supplemental_checked),(supplemental_checked.is_(None),primary_checked),(primary_checked>supplemental_checked,primary_checked),else_=supplemental_checked)
    next_retry=case((ItemMetadata.retry_after.is_(None),supplemental_retry),(supplemental_retry.is_(None),ItemMetadata.retry_after),(ItemMetadata.retry_after<supplemental_retry,ItemMetadata.retry_after),else_=supplemental_retry)
    query=select(ids.c.region,ids.c.item_id,ItemMetadata,ItemMedia.asset_hash,last_attempt.label('last_attempt'),next_retry.label('next_retry')).outerjoin(ItemMetadata,
        (ItemMetadata.region==ids.c.region)&(ItemMetadata.item_id==ids.c.item_id)).outerjoin(ItemMedia,
        (ItemMedia.region==ids.c.region)&(ItemMedia.item_id==ids.c.item_id)).where(func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).is_(None))
    if item_id: query=query.where(ids.c.item_id==item_id)
    if primary=='missing': query=query.where(ItemMetadata.http_status==404)
    elif primary=='pending': query=query.where(or_(ItemMetadata.http_status.is_(None),ItemMetadata.http_status!=404))
    column={'item_id':ids.c.item_id,'checked_at':last_attempt,'retry_after':next_retry}[sort]
    count,rows=page(db,query,((column.desc().nulls_last() if desc else column.asc().nulls_last()),ids.c.item_id),offset,limit)
    identities=[(r[0],r[1]) for r in rows]
    sources={}
    if identities:
        for source in db.scalars(select(MetadataSource).where(tuple_(MetadataSource.region,MetadataSource.item_id).in_(identities),MetadataSource.provider!='blizzard')):
            sources.setdefault((source.region,source.item_id),[]).append(source)
    result=[]
    for region,ident,metadata,icon,checked,retry_at in rows:
        records=sources.get((region,ident),[])
        result.append({'id':f'{region}-{ident}','item_id':ident,'region':region,'market_presence':'Current snapshot',
            'blizzard_status':'Provider reports missing' if metadata and metadata.http_status==404 else 'Pending or unavailable',
            'supplemental_status':', '.join(f'{s.provider}: {s.status}' for s in records) or 'Not attempted',
            'checked_at':checked,'retry_after':retry_at,
            'icon_available':bool(icon),'icon_url':f'/api/v1/items/{region}/{ident}/icon?v={icon}' if icon else None})
    return {'rows':result,'total':count}
