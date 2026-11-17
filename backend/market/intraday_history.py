"""Bounded hourly selection from genuine retained observations, never daily relabels."""
from datetime import timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from .db import now, session
from .market_api import MarketId, require_market, money_contract
from .models import Observation, Snapshot, SnapshotStatistic, User
from .pricing import ALGORITHM
from .security import aware, identity
router=APIRouter(prefix='/api/v1/markets')
MAX_OBSERVATIONS=4096


def intraday(db,market_id,item_id,variant_key,hours,*,at=None):
    at=aware(at or now()).astimezone(timezone.utc)
    start=at-timedelta(hours=hours)
    # Header scan and payload are independently bounded. Statistics use their exact PK.
    if db.bind.dialect.name=='postgresql': db.execute(text("SET LOCAL statement_timeout='3s'"))
    observations=list(db.scalars(select(Observation).where(Observation.market_id==market_id,
        Observation.retrieved_at>=start,Observation.retrieved_at<=at)
        .order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(MAX_OBSERVATIONS+1)))
    if len(observations)>MAX_OBSERVATIONS:
        raise HTTPException(503,'Intraday observation limit reached; try 24H or retry later. No partial history was substituted.')
    buckets={};counts={}
    for observation in observations:
        stamp=aware(observation.retrieved_at).astimezone(timezone.utc)
        hour=stamp.replace(minute=0,second=0,microsecond=0)
        counts[hour]=counts.get(hour,0)+1
        buckets.setdefault(hour,observation)
    snapshots={row.id:row for row in db.scalars(select(Snapshot).where(Snapshot.id.in_({r.snapshot_id for r in buckets.values()})))} if buckets else {}
    statistics={row.snapshot_id:row for row in db.scalars(select(SnapshotStatistic).where(
        SnapshotStatistic.snapshot_id.in_(snapshots),SnapshotStatistic.item_id==item_id,
        SnapshotStatistic.variant_key==variant_key))} if snapshots else {}
    points=[]
    for hour,observation in sorted(buckets.items()):
        snapshot=snapshots.get(observation.snapshot_id);stat=statistics.get(observation.snapshot_id)
        status='available'
        if not snapshot or not snapshot.statistics_retained: status='compacted'
        elif stat and stat.algorithm!=ALGORITHM: status='unsupported_algorithm'
        elif not stat: status='not_listed'
        known=status in ('available','not_listed')
        points.append({'bucket_start':hour.isoformat(),'observed_at':aware(observation.retrieved_at).isoformat(),
            'recent_price':stat.recent_price if stat and status=='available' else None,
            'lowest_buyout':stat.lowest_buyout if stat and status=='available' else None,
            'supply':stat.supply if stat and known else 0 if status=='not_listed' else None,
            'priced_supply':stat.priced_supply if stat and known else 0 if status=='not_listed' else None,
            'listing_count':stat.listing_count if stat and known else 0 if status=='not_listed' else None,
            'status':status,'synthetic':observation.synthetic,'observations_in_hour':counts[hour],
            'observation_id':str(observation.id),'snapshot_id':str(observation.snapshot_id),
            'namespace':observation.namespace,'payload_hash':observation.payload_hash,
            'upstream_modified':observation.upstream_modified})
    return {'contract_version':1,'market_id':market_id,'item_id':item_id,'variant_key':variant_key,
        'algorithm':ALGORITHM,'hours':hours,'window_start':start.isoformat(),'window_end':at.isoformat(),
        'bucket_seconds':3600,'selection':'latest_recorded_observation_in_each_utc_hour',
        'source_observation_count':len(observations),'observation_scan_limit':MAX_OBSERVATIONS,
        'points':points,'synthetic':any(p['synthetic'] for p in points),
        'provenance':'observed_asking_prices_only',
        'notice':'Latest recorded observation in each UTC hour within this rolling window. Missing hours are unobserved; prices are asking listings, not completed sales. Compacted or unsupported statistics remain unavailable.'}


@router.get('/{market_id}/items/{item_id}/{variant_key}/intraday-history')
def intraday_history(market_id:MarketId,item_id:MarketId,variant_key:str,hours:int=Query(24,ge=24,le=48),
                     user:User=Depends(identity),db:Session=Depends(session)):
    require_market(db,market_id)
    if hours not in (24,48): raise HTTPException(422,'Choose 24H or 48H')
    if len(variant_key)!=64 or any(c not in '0123456789abcdef' for c in variant_key):
        raise HTTPException(422,'Invalid variant key')
    try:
        return money_contract(intraday(db,market_id,item_id,variant_key,hours))
    except DBAPIError as error:
        if getattr(error.orig,'sqlstate',None)=='57014':
            db.rollback()
            raise HTTPException(503,'Intraday history took too long. Retry this bounded window.') from None
        raise
