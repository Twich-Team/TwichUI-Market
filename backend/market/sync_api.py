"""Versioned data-only synchronization with signed, resumable cursors."""
import base64
import binascii
import hashlib
import hmac
import json
import os
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_, select, text, tuple_
from sqlalchemy.orm import Session
from .db import session
from .market_api import MarketId, money_contract, require_market
from .models import Observation, Snapshot, SnapshotStatistic, User
from .pricing import ALGORITHM, HistoryUnavailable, rounded, values
from .security import aware, identity

router=APIRouter(prefix='/api/v1/sync')


def secret():
    value=os.environ.get('SYNC_CURSOR_SECRET','')
    if len(value)<32:
        raise HTTPException(503,'Operator must configure SYNC_CURSOR_SECRET (at least 32 characters)')
    return value.encode()


def encode_cursor(payload):
    encoded=base64.urlsafe_b64encode(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).decode().rstrip('=')
    signature=hmac.new(secret(),encoded.encode(),hashlib.sha256).hexdigest()
    return encoded+'.'+signature


def decode_cursor(cursor,market_id):
    key=secret()
    try:
        encoded,signature=cursor.split('.')
        expected=hmac.new(key,encoded.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected):
            raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))
        if (set(data)!={'v','market','base','target','after','done'} or data['v']!=1 or data['market']!=market_id
            or type(data['base']) is not int or type(data['target']) is not int
            or not 0<=data['base']<=data['target'] or type(data['done']) is not bool
            or not isinstance(data['after'],list) or len(data['after'])!=2
            or type(data['after'][0]) is not int or not 0<=data['after'][0]<=2**31-1
            or not isinstance(data['after'][1],str) or len(data['after'][1])>64):
            raise ValueError()
        return data
    except (ValueError,TypeError,KeyError,binascii.Error,UnicodeError):
        raise HTTPException(409,'Invalid sync cursor; start a full synchronization')


def compact(db,observation,item_id,variant_key,watermark):
    if not observation:
        return None
    try:
        result=values(db,observation.market_id,item_id,variant_key,at=aware(observation.retrieved_at),
                      through_observation_id=watermark)
    except HistoryUnavailable:
        raise HTTPException(409,'Detailed sync history compacted; start a full synchronization')
    if result['listing_count']==0:
        return None
    return money_contract({key:result[key] for key in ('recent_price','lowest_buyout','market_value','historical_value',
        'supply','priced_supply','listing_count','coverage_days','market_coverage_days','synthetic')})


def compact_many(db, observation, keys, generation):
    """One bounded statistics query for this page, reusing exact daily winners.

    The unchanged asking-v1 implementation above remains the independent reference
    for equivalence checks. At most 100 keys × 61 UTC days are materialized.
    """
    keys=[tuple(key) for key in keys]
    if len(keys)>100:
        raise ValueError('Compact pricing batch exceeds page limit')
    if observation is None or not keys:
        return {key:None for key in keys}
    if generation is None:
        raise HTTPException(409,'Detailed sync history compacted; start a full synchronization')
    snapshots={snapshot_id for _,snapshot_id,_ in generation.daily}
    rows=list(db.scalars(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id.in_(snapshots),
        tuple_(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).in_(keys))))
    if any(row.algorithm!=ALGORITHM for row in rows):
        raise HTTPException(409,'Detailed sync history compacted; start a full synchronization')
    statistics={(row.snapshot_id,row.item_id,row.variant_key):row for row in rows}
    result={}
    for key in keys:
        current=statistics.get((observation.snapshot_id,*key))
        if current is None or not current.listing_count:
            result[key]=None
            continue
        prices=[];recent=[]
        for _,snapshot_id,in_recent_window in generation.daily:
            row=statistics.get((snapshot_id,*key))
            if row is not None and row.recent_price is not None:
                prices.append(Decimal(row.recent_price))
                if in_recent_window:recent.append(Decimal(row.recent_price))
        result[key]=money_contract({**{name:getattr(current,name) for name in
            ('recent_price','lowest_buyout','supply','priced_supply','listing_count')},
            'market_value':rounded(sum(recent)/len(recent)) if recent else None,
            'historical_value':rounded(sum(prices)/len(prices)) if prices else None,
            'coverage_days':len(prices),'market_coverage_days':len(recent),'synthetic':generation.synthetic})
    return result


@router.get('/markets/{market_id}')
def synchronize(market_id: MarketId,request: Request,cursor: str | None = Query(None,max_length=2048),
                limit: int = Query(50,ge=1,le=100),user: User = Depends(identity),db: Session = Depends(session)):
    require_market(db,market_id)
    # No lower observation IDs may commit after selecting this download's watermark.
    if db.bind.dialect.name=='postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
    state=decode_cursor(cursor,market_id) if cursor else {'v':1,'market':market_id,'base':0,'target':0,'after':[0,''],'done':True}
    if state['done']:
        latest=db.scalar(select(Observation).where(Observation.market_id==market_id).order_by(Observation.id.desc()).limit(1))
        state={'v':1,'market':market_id,'base':state['target'],'target':latest.id if latest else 0,'after':[0,''],'done':False}
    target=db.get(Observation,state['target']) if state['target'] else None
    base=db.get(Observation,state['base']) if state['base'] else None
    if ((state['target'] and (not target or target.market_id!=market_id))
        or (state['base'] and (not base or base.market_id!=market_id))):
        raise HTTPException(409,'Sync history unavailable; start a full synchronization')
    def head(watermark):
        return db.scalar(select(Observation).where(Observation.market_id==market_id,Observation.id<=watermark)
            .order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1)) if watermark else None
    # Late historical imports may have a newer ID but must not replace current supply.
    target,base=head(state['target']),head(state['base'])
    from .retention import history_floor
    floor=history_floor(db)
    for observation in (target,base):
        if observation and floor and aware(observation.retrieved_at)<aware(floor):
            raise HTTPException(409,'Historical reference support compacted; start a full synchronization')
        if observation and not db.get(Snapshot,observation.snapshot_id).statistics_retained:
            raise HTTPException(409,'Detailed sync history compacted; start a full synchronization')
    from .sync_generation import signature
    target_signature=signature(db,target,state['target'])
    base_signature=signature(db,base,state['base']) if base else None
    unchanged=(base_signature is not None and target_signature is not None
        and base_signature.digest==target_signature.digest)
    if target_signature is None or (base and base_signature is None):
        raise HTTPException(409,'Detailed sync history compacted; start a full synchronization')
    if state['base']==state['target'] or unchanged:
        state['done']=True
        result = {'contract_version':1,'market_id':market_id,'algorithm':ALGORITHM,'changes':[],
                'cursor':encode_cursor(state),'has_more':False,'target_observation_id':str(state['target']),
                'observed_at':aware(target.retrieved_at).isoformat() if target else None,
                'synthetic':target_signature.synthetic}
        from .companion_devices import record_sync
        record_sync(db,request,market_id,state['target'],True)
        return result
    snapshots=[observation.snapshot_id for observation in (target,base) if observation]
    after_item,after_variant=state['after']
    keys=list(db.execute(select(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).where(SnapshotStatistic.snapshot_id.in_(snapshots),
        or_(SnapshotStatistic.item_id>after_item,and_(SnapshotStatistic.item_id==after_item,SnapshotStatistic.variant_key>after_variant)))
        .distinct().order_by(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).limit(limit+1)))
    changes=[]
    current_values=compact_many(db,target,keys[:limit],target_signature)
    previous_values=compact_many(db,base,keys[:limit],base_signature)
    for item_id,variant_key in keys[:limit]:
        current=current_values[item_id,variant_key]
        previous=previous_values[item_id,variant_key]
        if current==previous:
            continue
        changes.append({'operation':'upsert' if current is not None else 'delete',
                        'item_id':item_id,'variant_key':variant_key,'value':current})
    state['done']=len(keys)<=limit
    if keys:
        state['after']=list(keys[min(len(keys),limit)-1])
    result = {'contract_version':1,'market_id':market_id,'algorithm':ALGORITHM,'changes':changes,
            'cursor':encode_cursor(state),'has_more':not state['done'],'target_observation_id':str(state['target']),
            'observed_at':aware(target.retrieved_at).isoformat() if target else None,
            'synthetic':target_signature.synthetic}
    from .companion_devices import record_sync
    record_sync(db,request,market_id,state['target'],state['done'])
    return result
