"""Bounded item catalogue over compact statistics; parent prices are variant ranges."""
import json
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import Integer,case,cast,func,select
from sqlalchemy.orm import Session
from .db import now,session
from .models import DailyObservation,ItemMedia,ItemMetadata,Listing,Observation,SnapshotStatistic,User
from .market_api import MarketId,identity,latest_observation,market_view,metadata_name,require_market
from .pricing import ALGORITHM

router=APIRouter(prefix='/api/v1')
Sort=Literal['item_id','name','recent_price','market_value','historical_value','supply','listing_count']


def references(market_id,at):
    stat=SnapshotStatistic
    bad=func.sum(case((stat.algorithm!=ALGORITHM,1),else_=0))
    return select(stat.item_id,stat.variant_key,
        case((bad>0,None),else_=func.round(func.avg(stat.recent_price).filter(Observation.retrieved_at>=at-timedelta(days=14)))).label('market_value'),
        case((bad>0,None),else_=func.round(func.avg(stat.recent_price))).label('historical_value'),
        func.count(stat.recent_price).filter(Observation.retrieved_at>=at-timedelta(days=14)).label('coverage_days'),
        func.max(cast(Observation.synthetic,Integer)).label('synthetic')).join(
        Observation,Observation.snapshot_id==stat.snapshot_id).join(DailyObservation,DailyObservation.observation_id==Observation.id).where(
        DailyObservation.market_id==market_id,Observation.retrieved_at>=at-timedelta(days=60),Observation.retrieved_at<=at
        ).group_by(stat.item_id,stat.variant_key).cte('catalogue_references')


def cash(value):return str(int(value)) if value is not None else None


def context(db,market_id,expected_snapshot=None):
    market=require_market(db,market_id)
    latest=latest_observation(db,market_id)
    if expected_snapshot is not None and (latest is None or str(latest.snapshot_id)!=expected_snapshot):
        raise HTTPException(409,"Market snapshot changed; refresh the catalogue before expanding variants")
    if latest and db.scalar(select(SnapshotStatistic.item_id).where(SnapshotStatistic.snapshot_id==latest.snapshot_id,
            SnapshotStatistic.algorithm!=ALGORITHM).limit(1)) is not None:
        raise HTTPException(409,'Current pricing algorithm is not supported')
    return market,latest


@router.get('/markets/{market_id}/catalogue')
def catalogue(market_id: MarketId,q: str=Query('',max_length=64),sort: Sort='item_id',
              direction: Literal['asc','desc']='asc',page: int=Query(0,ge=0,le=100000),
              page_size: int=Query(50,ge=1,le=100),user: User=Depends(identity),db: Session=Depends(session)):
    market,latest=context(db,market_id)
    envelope={'contract_version':1,'market':market_view(market),'algorithm':ALGORITHM,
              'snapshot_id':str(latest.snapshot_id) if latest else None,'observed_at':latest.retrieved_at if latest else None,
              'page':page,'page_size':page_size,'total_items':0,'items':[],'synthetic':bool(latest and latest.synthetic)}
    if not latest:return envelope
    stat=SnapshotStatistic
    base=select(stat.item_id).outerjoin(ItemMetadata,(ItemMetadata.region==market.region)&(ItemMetadata.item_id==stat.item_id)
        ).where(stat.snapshot_id==latest.snapshot_id)
    if q.strip():
        term=q.strip()
        if term.isascii() and term.isdigit():
            if int(term)>2**31-1:return envelope
            base=base.where(stat.item_id==int(term))
        else:base=base.where(func.lower(func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name)).contains(term.lower(),autoescape=True))
    ids=base.distinct().subquery('matching_items')
    envelope['total_items']=db.scalar(select(func.count()).select_from(ids))
    refs=references(market_id,now())
    joined=select(stat.item_id,func.count().label('variant_count'),case((func.count()==1,func.min(stat.variant_key)),else_=None).label('sole_variant_key'),func.sum(stat.supply).label('supply'),
        func.sum(stat.listing_count).label('listing_count'),func.min(stat.recent_price).label('recent_min'),
        func.max(stat.recent_price).label('recent_max'),func.min(refs.c.market_value).label('market_min'),
        func.max(refs.c.market_value).label('market_max'),func.min(refs.c.historical_value).label('historical_min'),
        func.max(refs.c.historical_value).label('historical_max'),func.count(stat.recent_price).label('priced_variants'),
        func.max(refs.c.synthetic).label('historical_synthetic'),func.max(func.coalesce(ItemMetadata.name,ItemMetadata.fallback_name)).label('name'))
    grouped=joined.join(ids,ids.c.item_id==stat.item_id).outerjoin(refs,(refs.c.item_id==stat.item_id)&(refs.c.variant_key==stat.variant_key)
        ).outerjoin(ItemMetadata,(ItemMetadata.region==market.region)&(ItemMetadata.item_id==stat.item_id)
        ).where(stat.snapshot_id==latest.snapshot_id).group_by(stat.item_id).subquery('item_groups')
    sort_column={'item_id':grouped.c.item_id,'name':func.lower(grouped.c.name),
        'recent_price':grouped.c.recent_min,'market_value':grouped.c.market_min,'historical_value':grouped.c.historical_min,
        'supply':grouped.c.supply,'listing_count':grouped.c.listing_count}[sort]
    ordering=(sort_column.desc() if direction=='desc' else sort_column.asc()).nulls_last()
    rows=list(db.execute(select(grouped).order_by(ordering,grouped.c.item_id.asc()).offset(page*page_size).limit(page_size)).mappings())
    metadata={record[0].item_id:record for record in db.execute(select(ItemMetadata,ItemMedia.asset_hash,ItemMedia.source).outerjoin(ItemMedia,(ItemMedia.region==ItemMetadata.region)&(ItemMedia.item_id==ItemMetadata.item_id)).where(ItemMetadata.region==market.region,ItemMetadata.item_id.in_([r['item_id'] for r in rows])))} if rows else {}
    for row in rows:
        envelope['items'].append({'item_id':row['item_id'],**metadata_name(metadata[row['item_id']][0] if row['item_id'] in metadata else None,row['item_id']),
            'icon_attribution':json.loads(metadata[row['item_id']][0].fallback)['source']['attribution'] if row['item_id'] in metadata and metadata[row['item_id']][2]=='thewowdb' and metadata[row['item_id']][0].fallback else None,
            'icon_url':f'/api/v1/items/{market.region}/{row["item_id"]}/icon?v={metadata[row["item_id"]][1]}' if row['item_id'] in metadata and metadata[row['item_id']][1] else None,
            'variant_count':row['variant_count'],'sole_variant_key':row['sole_variant_key'],'priced_variant_count':row['priced_variants'],
            'supply':row['supply'],'listing_count':row['listing_count'],
            'price_ranges':{key:{'minimum':cash(row[prefix+'_min']),'maximum':cash(row[prefix+'_max'])} for key,prefix in
                            [('recent_price','recent'),('market_value','market'),('historical_value','historical')]},
            'synthetic':bool(latest.synthetic or row['historical_synthetic'])})
    envelope['synthetic']=envelope['synthetic'] or any(r['synthetic'] for r in envelope['items'])
    return envelope


@router.get('/markets/{market_id}/catalogue/{item_id}/variants')
def variants(market_id: MarketId,item_id: MarketId,page: int=Query(0,ge=0,le=100000),page_size: int=Query(50,ge=1,le=100),
             expected_snapshot: str | None=Query(None,max_length=64),user: User=Depends(identity),db: Session=Depends(session)):
    market,latest=context(db,market_id,expected_snapshot)
    result={'contract_version':1,'market_id':market_id,'item_id':item_id,'snapshot_id':str(latest.snapshot_id) if latest else None,
            'page':page,'page_size':page_size,'total_variants':0,'variants':[],'algorithm':ALGORITHM,'synthetic':bool(latest and latest.synthetic)}
    if not latest:return result
    stat=SnapshotStatistic
    predicate=(stat.snapshot_id==latest.snapshot_id)&(stat.item_id==item_id)
    result['total_variants']=db.scalar(select(func.count()).select_from(stat).where(predicate))
    refs=references(market_id,now())
    rows=list(db.execute(select(stat,refs.c.market_value,refs.c.historical_value,refs.c.coverage_days,refs.c.synthetic).outerjoin(
        refs,(refs.c.item_id==stat.item_id)&(refs.c.variant_key==stat.variant_key)).where(predicate)
        .order_by(stat.variant_key).offset(page*page_size).limit(page_size)))
    descriptors=dict(db.execute(select(Listing.variant_key,Listing.variant).where(Listing.snapshot_id==latest.snapshot_id,
        Listing.item_id==item_id,Listing.variant_key.in_([r[0].variant_key for r in rows])).distinct()).all()) if rows else {}
    metadata=db.get(ItemMetadata,(market.region,item_id))
    for row,mv,hv,coverage,synthetic in rows:
        result['variants'].append({'item_id':item_id,**metadata_name(metadata,item_id),'variant_key':row.variant_key,
            'variant':json.loads(descriptors[row.variant_key]) if row.variant_key in descriptors else None,
            'recent_price':cash(row.recent_price),'lowest_buyout':cash(row.lowest_buyout),'market_value':cash(mv),
            'historical_value':cash(hv),'supply':row.supply,'priced_supply':row.priced_supply,'listing_count':row.listing_count,
            'coverage_days':coverage or 0,'synthetic':bool(latest.synthetic or synthetic)})
    result['synthetic']=result['synthetic'] or any(r['synthetic'] for r in result['variants'])
    return result
