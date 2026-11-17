"""Administrator-only local recovery views. GET never contacts a provider."""
from datetime import timedelta
import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import JSON, and_, cast, func, or_, select, String, tuple_, literal
from sqlalchemy.orm import Session, aliased
from .db import now, session
from .models import ItemMetadata, ItemMedia, Market, MetadataAttempt, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, MetadataRecoveryItem, User
from .metadata_recovery import observed_query, latest_foreverdb_build
from .recovery_planner import provider_context, load_items, plan_item, essential_missing_sql, source_due_sql, fields_sql
from .recovery_policy import known_fields, CAPABILITIES
from .security import admin

router = APIRouter(prefix='/api/v1/admin/item-metadata/tracker')
Provider = Literal['blizzard','foreverdb','everloot','thewowdb']


def tracker_query(market_id):
    ids = observed_query(market_id).subquery()
    return ids, select(ids.c.region,ids.c.item_id,func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).label('name')).select_from(ids).outerjoin(
        ItemMetadata,(ItemMetadata.region==ids.c.region)&(ItemMetadata.item_id==ids.c.item_id)).outerjoin(
        ItemMedia,(ItemMedia.region==ids.c.region)&(ItemMedia.item_id==ids.c.item_id))


def eligibility_sql(ids, context, at, build, provider=None, *, facts=None, name=None, legacy_quality=None, no_icon=None, icon_retry=None):
    choices=[]
    for ident,(row,due,credentials) in context.items():
        if provider and ident != provider: continue
        if not row.enabled or not row.automatic or not credentials or row.expires_at and row.expires_at <= at or row.last_error in ('authorization','forbidden','subscription_required','credential_unavailable','secret_unavailable') or due > at: continue
        s=aliased(MetadataSource)
        capable=func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).is_(None) if name is None else name.is_(None)
        if ident != 'everloot': capable=or_(capable,essential_missing_sql(CAPABILITIES[ident],facts=facts,legacy_quality=legacy_quality))
        if ident in ('foreverdb','thewowdb'):
            missing_icon=ItemMedia.data.is_(None) if no_icon is None else no_icon
            retry=ItemMedia.retry_after if icon_retry is None else icon_retry
            capable=or_(capable,and_(missing_icon,or_(retry.is_(None),retry<=at)))
        if ident=='foreverdb':capable=or_(capable,(fields_sql() if facts is None else facts)['class'].as_string().in_(('Weapon','Armor')))
        source=and_(s.region==ids.c.region,s.item_id==ids.c.item_id,s.locale=='en_US',s.provider==ident)
        untried=~select(s.item_id).where(source).exists()
        due_source=select(s.item_id).where(source,source_due_sql(s,at,build=build),or_(capable,s.fields_json.is_not(None))).exists()
        choices.append(or_(and_(capable,untried),due_source))
    return or_(*choices) if choices else False


def tracker_states(db,ids,base,context,at,build):
    """Decode rich catalog text once and evaluate each provider once per item.

    Repeating correlated eligibility inside multiple COUNT FILTERs reparses
    TOASTed catalog/source JSON many times. Materialized narrow booleans keep
    the summary and eligibility-filter page counts bounded on rich records.
    """
    from sqlalchemy.dialects.postgresql import JSONB
    facts=base.with_only_columns(ids.c.region,ids.c.item_id,
        func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).label('name'),
        (func.jsonb_extract_path(cast(ItemMetadata.catalog_json,JSONB),'fields',type_=JSONB) if db.bind.dialect.name=='postgresql' else cast(ItemMetadata.catalog_json,JSON)['fields']).label('facts'),
        ItemMetadata.quality.label('legacy_quality'),ItemMedia.data.is_(None).label('no_icon'),
        ItemMedia.retry_after.label('icon_retry')).cte('tracker_facts')
    if db.bind.dialect.name=='postgresql':facts=facts.prefix_with('MATERIALIZED')
    kwargs=dict(facts=facts.c.facts,name=facts.c.name,legacy_quality=facts.c.legacy_quality,no_icon=facts.c.no_icon,icon_retry=facts.c.icon_retry)
    values=[facts.c.region,facts.c.item_id,facts.c.name,facts.c.name.is_(None).label('unnamed'),facts.c.no_icon,
        essential_missing_sql(facts=facts.c.facts,legacy_quality=facts.c.legacy_quality).label('missing_essential')]
    for ident,(row,due,credentials) in context.items():
        # Exactly one source eligibility expression/provider, assigned to its
        # current pool state. Disabled/access-blocked sources remain false.
        available=eligibility_sql(facts,{ident:(row,at,credentials)},at,build,**kwargs)
        if available is False:available=literal(False)
        values.extend([(available if due<=at else literal(False)).label('ready_'+ident),
                       (available if due>at else literal(False)).label('cooling_'+ident)])
    states=select(*values).select_from(facts).cte('tracker_states')
    if db.bind.dialect.name=='postgresql':states=states.prefix_with('MATERIALIZED')
    return states


def provider_status(row, source, action, attempt=None):
    reason=action.get('reason') if action else None
    if not row.enabled: status='provider_disabled'
    elif reason in ('credential_unavailable','access_blocked','provider_cooldown'): status=reason
    elif not source or not source.checked_at: status='never_attempted'
    elif source.http_status == 404: status='missing'
    elif source.http_status == 429: status='rate_limited'
    elif source.http_status in (401,402,403): status='access_blocked'
    elif source.http_status not in (200,304): status='temporarily_unavailable'
    else:
        evidence=json.loads(source.recovery_json) if source.recovery_json else {}
        fields=evidence.get('new_fields',[])
        status='name_recovered' if 'name' in fields else 'attributes_recovered' if fields else 'metadata_updated' if evidence.get('updated_fields') else 'already_known' if source.http_status==304 or evidence else 'historical_incomplete'
    if attempt and attempt.kind in ('media','artwork') and 'icon' in json.loads(attempt.new_json or '[]') and row.enabled:status='icon_recovered'
    return {'status':status,'checked_at':source.checked_at if source else None,
            'next_at':action.get('next_at') if action else source.retry_at if source else None,
            'waiting':reason if reason not in ('eligible','incapable') else None}


def item_view(identity, metadata, media, sources, context, at, build,attempts=None):
    plan=plan_item(metadata,media,sources,context,at,automatic=True,build=build)
    actions={a['provider']:a for a in plan['actions']}
    waiting=[a['next_at'] for a in plan['actions'] if a['next_at'] and not a['eligible']]
    gap=plan['missing']
    missing=(['Name'] if gap['name'] else [])+(['Icon'] if gap['icon'] else [])+[f.replace('_',' ').title() for f in gap['essential']]+(['Equipment detail verification'] if gap['details'] else [])
    useful=[json.loads(s.recovery_json).get('last_useful_at') for s in sources.values() if s.recovery_json]
    chosen=plan['chosen']
    return {'region':identity[0],'item_id':identity[1], 'name':known_fields(metadata).get('name'),
        'icon':f'/api/v1/items/{identity[0]}/{identity[1]}/icon' if media and media.data else None,
        'missing':missing,'providers':{ident:provider_status(row,sources.get(ident),actions.get(ident),(attempts or {}).get(ident)) for ident,(row,_,_) in context.items()},
        'last_useful_at':max([u for u in useful if u],default=None),
        'next_provider':chosen['provider'] if chosen else None,'next_at':chosen['next_at'] if chosen else min(waiting,default=None),
        'status':'eligible' if chosen else 'complete' if not missing else 'waiting' if waiting else 'no_eligible_provider',
        'explanation':plan['explanation'],'decision':plan}


def latest_attempts(db,identities):
    if not identities:return {}
    a=MetadataAttempt
    ranked=select(a.id,func.row_number().over(partition_by=(a.region,a.item_id,a.provider),order_by=(a.started_at.desc(),a.id.desc())).label('position')).where(tuple_(a.region,a.item_id).in_(identities),a.kind.in_(('metadata','media','artwork'))).subquery()
    result={}
    for a in db.scalars(select(a).join(ranked,ranked.c.id==a.id).where(ranked.c.position==1)):
        result.setdefault((a.region,a.item_id),{})[a.provider]=a
    return result


@router.get('')
def tracker(market_id:int=Query(ge=1),q:str=Query('',max_length=64),
    missing:Literal['all','name','icon','attributes']='all',provider:Provider|None=None,
    eligibility:Literal['all','eligible','waiting','unavailable']='all',
    outcome:str=Query('',max_length=32),offset:int=Query(0,ge=0,le=1000000),limit:int=Query(25,ge=1,le=100),
    sort:Literal['item_id','name']='item_id',desc:bool=False,
    user:User=Depends(admin),db:Session=Depends(session)):
    if not db.get(Market,market_id): raise HTTPException(404,'Market not found')
    at=now();context=provider_context(db,at);build=latest_foreverdb_build(db)
    ids,base=tracker_query(market_id)
    states=tracker_states(db,ids,base,context,at,build)
    ready_all=or_(*[states.c['ready_'+p] for p in context]) if context else literal(False)
    cooling_all=or_(*[states.c['cooling_'+p] for p in context]) if context else literal(False)
    absent_state=or_(states.c.unnamed,states.c.no_icon,states.c.missing_essential)
    measurements=db.execute(select(func.count(),func.count().filter(states.c.unnamed),func.count().filter(states.c.no_icon),
        func.count().filter(states.c.missing_essential),func.count().filter(ready_all),
        func.count().filter(and_(absent_state,~ready_all)),func.count().filter(and_(absent_state,~ready_all,cooling_all))).select_from(states)).one()
    summary=dict(zip(('observed','missing_names','missing_icons','missing_essential','eligible','no_eligible','waiting_cooldowns'),measurements))
    unnamed=func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name).is_(None)
    no_icon=ItemMedia.data.is_(None)
    essentials=essential_missing_sql()
    ready=states.c['ready_'+provider] if provider and provider in context else ready_all
    cooling=states.c['cooling_'+provider] if provider and provider in context else cooling_all
    cooldown_items=and_(absent_state,~ready,cooling)
    query=base
    if q.strip(): query=query.where(or_(cast(ids.c.item_id,String)==q.strip(),ItemMetadata.name.icontains(q.strip(),autoescape=True),ItemMetadata.fallback_name.icontains(q.strip(),autoescape=True)))
    if missing!='all': query=query.where({'name':unnamed,'icon':no_icon,'attributes':essentials}[missing])
    if eligibility!='all':query=query.join(states,(states.c.region==ids.c.region)&(states.c.item_id==ids.c.item_id))
    if eligibility=='eligible': query=query.where(ready)
    elif eligibility=='waiting': query=query.where(cooldown_items)
    elif eligibility=='unavailable': query=query.where(absent_state,~ready)
    if provider or outcome:
        conditions=[MetadataSource.region==ids.c.region,MetadataSource.item_id==ids.c.item_id,MetadataSource.locale=='en_US']
        if provider: conditions.append(MetadataSource.provider==provider)
        if outcome: conditions.append(cast(MetadataSource.recovery_json,JSON)['outcome'].as_string()==outcome)
        query=query.where(select(MetadataSource.item_id).where(*conditions).exists())
    total=db.scalar(select(func.count()).select_from(query.subquery()))
    column=ids.c.item_id if sort=='item_id' else func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name)
    records=list(db.execute(query.order_by(column.desc().nulls_last() if desc else column.asc().nulls_last(),ids.c.item_id).offset(offset).limit(limit)))
    identities=[(r.region,r.item_id) for r in records]
    metadata,media,sources=load_items(db,identities)
    latest=latest_attempts(db,identities)
    rows=[item_view(i,metadata.get(i),media.get(i),sources.get(i,{}),context,at,build,latest.get(i)) for i in identities]
    useful=dict(( (region,item_id),stamp) for region,item_id,stamp in db.execute(select(MetadataAttempt.region,MetadataAttempt.item_id,func.max(MetadataAttempt.completed_at)).where(tuple_(MetadataAttempt.region,MetadataAttempt.item_id).in_(identities),MetadataAttempt.new_json.is_not(None),MetadataAttempt.new_json!='[]',MetadataAttempt.state=='finished').group_by(MetadataAttempt.region,MetadataAttempt.item_id))) if identities else {}
    for r in rows:
        if (r['region'],r['item_id']) in useful:r['last_useful_at']=useful[(r['region'],r['item_id'])]
    return {'rows':rows,'total':total,'summary':summary,'measured_at':at,
        'definition':'Distinct regional base items in the selected market’s latest recorded snapshot; en_US Forever. Essentials: quality/class, plus level/slot for known Weapon/Armor. Missing does not imply recoverable.'}


@router.get('/efficiency')
def efficiency(days:int=Query(7),user:User=Depends(admin),db:Session=Depends(session)):
    if days not in (1,7,30):raise HTTPException(422,"Select 1, 7 or 30 days")
    since=now()-timedelta(days=days)
    # New evidence is per invocation, not per task. Reserved requests interrupted
    # by a crash remain unknown and are never silently counted as real requests.
    a=MetadataAttempt
    new=cast(a.new_json,String)
    from .metadata_catalog import FIELDS
    attribute_gain=or_(*[or_(new.contains('\"'+field+'\"'),a.updated_json.contains('\"'+field+'\"')) for field in sorted(FIELDS-{'name','icon_reference'})])
    useful=and_(a.kind.in_(('metadata','media','bulk','related')),a.state=='finished',or_(and_(a.new_json.is_not(None),new!='[]'),and_(a.updated_json.is_not(None),a.updated_json!='[]')))
    rows=db.execute(select(a.provider,func.count().filter(a.state=='finished'),func.count().filter(useful),
        func.count().filter(and_(useful,new.contains('"name"'))),
        func.count().filter(and_(a.kind.in_(('artwork','media')),a.new_json.is_not(None),new!='[]',a.state=='finished')),
        func.count().filter(and_(useful,attribute_gain)),
        func.count().filter(a.outcome=='already_known'),func.count().filter(a.outcome.in_(('missing','no_usable_data'))),
        func.count().filter(a.outcome.in_(('invalid_response','unavailable','credentials_invalid','access_blocked','wrong_identity'))),
        func.count().filter(a.outcome=='rate_limited'),func.count().filter(a.state=='reserved'),func.count().filter(and_(a.state=='finished',a.kind.in_(('metadata','media','bulk','related')))))
        .where(a.started_at>=since).group_by(a.provider)).all()
    keys=['provider','external_requests','useful_requests','names','icons','attributes','already_known','missing_no_data','errors','rate_limits','unknown_reservations','metadata_requests']
    providers=[dict(zip(keys,r)) for r in rows]
    # Metadata efficiency excludes image downloads/validation from denominator.
    metadata_requests=db.scalar(select(func.count()).select_from(a).where(a.started_at>=since,a.state=='finished',a.kind.in_(('metadata','media','bulk','related'))))
    recovered=sum(r['useful_requests'] for r in providers)
    historic=db.scalar(select(func.count()).select_from(MetadataTask).where(MetadataTask.updated_at>=since,MetadataTask.attempts>0,~select(a.id).where(a.task_id==MetadataTask.id).exists()))
    deferred=db.scalar(select(func.count()).select_from(MetadataTask).where(MetadataTask.state=='queued',cast(MetadataTask.result_json,JSON)['status'].as_string().in_(('provider_cooldown','quota_deferred','rate_limited'))))
    return {'queued_quota_deferrals':deferred,'days':days,'providers':providers,'metadata_requests':metadata_requests,'useful_requests':recovered,
            'useful_rate':recovered/metadata_requests if metadata_requests else None,'historical_task_records':historic,
            'notice':'Exact forward ledger counts completed network invocations. Crash reservations remain unknown. Historical task records have incomplete request/gain evidence and are excluded. Image requests are shown separately; validation cannot recover fields. Useful means a newly filled field or a verified changed value; returned unchanged fields are excluded. Recoveries may include more than one field per request.'}


@router.get('/{item_id}')
def journey(item_id:int,market_id:int=Query(ge=1),before:int|None=Query(None,ge=1),user:User=Depends(admin),db:Session=Depends(session)):
    market=db.get(Market,market_id)
    if not market or not 1<=item_id<=2**31-1: raise HTTPException(404,'Item or market not found')
    identity=(market.region,item_id);at=now()
    metadata,media,sources=load_items(db,[identity]);row=metadata.get(identity)
    result=item_view(identity,row,media.get(identity),sources.get(identity,{}),provider_context(db,at),at,latest_foreverdb_build(db),latest_attempts(db,[identity]).get(identity))
    catalog=json.loads(row.catalog_json) if row and row.catalog_json else {}
    stored_decision=db.get(MetadataRecoveryItem,(*identity,'en_US'))
    result['last_scheduler_decision']={'at':stored_decision.decided_at,'status':stored_decision.status,'next_at':stored_decision.next_at,'decision':json.loads(stored_decision.decision_json)} if stored_decision else None
    result['known_fields']=known_fields(row)
    result['provenance']={f:{k:v for k,v in src.items() if k in ('provider','edition','build','retrieved_at','confidence')} for f,src in catalog.get('provenance',{}).items()}
    query=select(MetadataAttempt).where(MetadataAttempt.region==market.region,MetadataAttempt.item_id==item_id,MetadataAttempt.kind.not_in(('bulk','related')))
    if before: query=query.where(MetadataAttempt.id<before)
    attempts=list(db.scalars(query.order_by(MetadataAttempt.id.desc()).limit(51)))
    result['attempts']=[{'id':a.id,'provider':a.provider,'at':a.started_at,'completed_at':a.completed_at,'http_status':a.http_status,'outcome':a.outcome or 'reservation_unknown',
        'kind':a.kind,'returned_fields':json.loads(a.returned_json or '[]'),'new_fields':json.loads(a.new_json or '[]'),'updated_fields':json.loads(a.updated_json or '[]'),'decision':json.loads(a.decision_json) if a.decision_json else None} for a in attempts[:50]]
    result['next_before']=attempts[49].id if len(attempts)>50 else None
    history=db.execute(select(MetadataTask).join(MetadataJob).where(MetadataTask.region==market.region,MetadataTask.item_id==item_id,MetadataJob.mode.not_in(('bulk','related','diagnostic')),
        ~select(MetadataAttempt.id).where(MetadataAttempt.task_id==MetadataTask.id).exists()).order_by(MetadataTask.updated_at.desc(),MetadataTask.id.desc()).limit(50)).scalars()
    result['historical']=[{'provider':t.provider,'at':t.updated_at,'attempts':t.attempts,'outcome':json.loads(t.result_json or '{}').get('outcome','unrecorded'),'evidence':'Historical record with incomplete evidence'} for t in history]
    return result
