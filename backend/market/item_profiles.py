"""Private rich item facts and safe locally cached artwork."""
import json
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import now,session
from .models import ItemMedia,ItemMetadata,SnapshotStatistic,User
from .market_api import MarketId,identity,latest_observation,metadata_name,require_market
from .security import admin
router=APIRouter(prefix='/api/v1')


@router.get('/markets/{market_id}/item-profiles/{item_id}')
def profile(market_id: MarketId,item_id: MarketId,user: User=Depends(identity),db: Session=Depends(session)):
    market=require_market(db,market_id)
    row=db.get(ItemMetadata,(market.region,item_id))
    media=db.get(ItemMedia,(market.region,item_id))
    fallback=json.loads(row.fallback) if row and row.fallback else None
    primary=bool(row and row.details)
    attributes=json.loads(row.details) if primary else (fallback.get('attributes') if fallback else None)
    source={'provider':'blizzard','namespace':row.resolved_namespace or row.namespace,'observed_at':row.resolved_at,
            'payload_hash':row.payload_hash,'confidence':'synthetic' if row.synthetic else 'blizzard_base_item','status':row.status} if primary else (fallback.get('source') if fallback else None)
    return {'contract_version':1,'item_id':item_id,'region':market.region,**metadata_name(row,item_id),
        'attributes':attributes,'source':source,'variant_notice':'Base item attributes; variant bonuses and enchantments are not inferred.',
        'icon_url':f'/api/v1/items/{market.region}/{item_id}/icon?v={media.asset_hash}' if media and media.asset_hash else None,
        'icon_source':{'provider':media.source,'url':media.source_url,'namespace':media.namespace,'observed_at':media.resolved_at,'payload_hash':media.asset_hash,'attribution':fallback['source']['attribution'] if fallback and media.source=='thewowdb' else None} if media and media.asset_hash else None,
        'media_status':media.status if media else 'pending','metadata_status':row.status if row else 'unresolved'}


@router.get('/items/{region}/{item_id}/icon')
def icon(region: Literal['us','eu','kr','tw'],item_id: MarketId,request: Request,user: User=Depends(identity),db: Session=Depends(session)):
    row=db.get(ItemMedia,(region,item_id))
    if row is None or not row.data or not row.asset_hash:raise HTTPException(404,'Item artwork is unavailable')
    etag='"'+row.asset_hash+'"'
    headers={'ETag':etag,'Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff','Vary':'Cookie, Authorization'}
    if request.headers.get('if-none-match')==etag:return Response(status_code=304,headers=headers)
    return Response(content=row.data,media_type=row.content_type,headers=headers)


class MetadataRequest(BaseModel):
    item_ids: list[int]=Field(min_length=1,max_length=50)


@router.post('/markets/{market_id}/item-metadata-requests',status_code=202)
def prioritize(market_id: MarketId,body: MetadataRequest,user: User=Depends(identity),db: Session=Depends(session)):
    market=require_market(db,market_id)
    latest=latest_observation(db,market_id)
    if not latest:return {'queued':0}
    wanted=set(body.item_ids)
    if any(type(ident) is not int or not 1<=ident<=2**31-1 for ident in wanted):raise HTTPException(422,'Invalid item identity')
    observed=list(db.scalars(select(SnapshotStatistic.item_id).where(SnapshotStatistic.snapshot_id==latest.snapshot_id,
        SnapshotStatistic.item_id.in_(wanted)).distinct()))
    at=now()
    existing={r.item_id:r for r in db.scalars(select(ItemMetadata).where(ItemMetadata.region==market.region,ItemMetadata.item_id.in_(observed)))}
    for ident in observed:
        row=existing.get(ident)
        if row is None:
            row=ItemMetadata(region=market.region,item_id=ident,namespace=f'static-forever-{market.region}',retry_after=at)
            db.add(row)
        row.requested_at=at
    db.commit()
    return {'queued':len(observed)}


@router.get('/admin/item-enrichment')
def enrichment_status(user: User=Depends(admin),db: Session=Depends(session)):
    import os
    from sqlalchemy import func
    facts=db.scalar(select(func.count()).select_from(ItemMetadata).where(ItemMetadata.details.is_not(None)))
    community=db.scalar(select(func.count()).select_from(ItemMetadata).where(ItemMetadata.fallback.is_not(None)))
    media=list(db.execute(select(ItemMedia.status,func.count(),func.coalesce(func.sum(ItemMedia.byte_count),0)).group_by(ItemMedia.status)))
    failures=db.execute(select(ItemMedia.region,ItemMedia.item_id,ItemMedia.status,ItemMedia.http_status,ItemMedia.checked_at,ItemMedia.retry_after).where(ItemMedia.status.in_(['error','missing','budget'])).order_by(ItemMedia.checked_at.desc()).limit(100))
    from .models import Market, Observation, SnapshotStatistic
    ranked=select(Observation.market_id,Observation.snapshot_id,func.row_number().over(partition_by=Observation.market_id,order_by=(Observation.retrieved_at.desc(),Observation.id.desc())).label('position')).subquery()
    ids=select(Market.region,SnapshotStatistic.item_id).join(ranked,ranked.c.market_id==Market.id).join(SnapshotStatistic,SnapshotStatistic.snapshot_id==ranked.c.snapshot_id).where(ranked.c.position==1).distinct().subquery()
    coverage=db.execute(select(func.count(),func.count(ItemMetadata.name),func.count(ItemMetadata.fallback_name).filter(ItemMetadata.name.is_(None))).select_from(ids).outerjoin(ItemMetadata,(ItemMetadata.region==ids.c.region)&(ItemMetadata.item_id==ids.c.item_id))).one()
    total,primary,supplemental=coverage
    return {'name_coverage':{'item_ids':total,'primary_names':primary,'supplemental_names':supplemental,'unresolved':total-primary-supplemental,'percent':round(100*(primary+supplemental)/total,2) if total else None},'rich_items':facts,'community_items':community,'icon_states':[{'status':status,'count':count,'bytes':size} for status,count,size in media],
            'icon_cache_budget_bytes':32*1024*1024,'community_enabled':os.environ.get('ITEM_COMMUNITY_FALLBACK_ENABLED','false').lower()=='true',
            'media_failures':[{'region':r.region,'item_id':r.item_id,'status':r.status,'http_status':r.http_status,'checked_at':r.checked_at,'retry_after':r.retry_after} for r in failures]}
