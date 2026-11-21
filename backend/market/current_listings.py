"""Bounded exact sorting/pagination of all current variant listings."""
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from sqlalchemy import Numeric,case,cast,func,select
from sqlalchemy.orm import Session
from .db import session
from .market_api import MarketId,latest_observation,money_contract,require_market
from .models import Listing,User
from .security import identity,aware
router=APIRouter(prefix='/api/v1/markets')

@router.get('/{market_id}/items/{item_id}/{variant_key}/listings')
def current_listings(market_id:MarketId,item_id:MarketId,variant_key:str,
        page:int=Query(0,ge=0,le=6000),page_size:int=Query(25,ge=1,le=100),
        sort:Literal['unit','quantity','total','time_left','auction_id','bid']='unit',
        direction:Literal['asc','desc']='asc',expected_snapshot:str|None=None,
        user:User=Depends(identity),db:Session=Depends(session)):
    require_market(db,market_id)
    if len(variant_key)!=64 or any(c not in '0123456789abcdef' for c in variant_key):raise HTTPException(422,'Invalid variant key')
    head=latest_observation(db,market_id)
    snapshot=str(head.snapshot_id) if head else None
    if expected_snapshot and expected_snapshot!=snapshot:raise HTTPException(409,'Current snapshot changed; refresh listings')
    if not head:return {'listings':[],'total':0,'snapshot_id':None,'page':page,'page_size':page_size,'synthetic':False,'observed_at':None}
    predicate=(Listing.snapshot_id==head.snapshot_id)&(Listing.item_id==item_id)&(Listing.variant_key==variant_key)
    unit=func.coalesce(cast(Listing.unit_price,Numeric(80,40)),cast(Listing.buyout,Numeric(80,40))/Listing.quantity)
    total=func.coalesce(cast(Listing.buyout,Numeric),cast(Listing.unit_price,Numeric)*Listing.quantity)
    duration=case({'SHORT':1,'MEDIUM':2,'LONG':3,'VERY_LONG':4},value=Listing.time_left,else_=None)
    field={'unit':unit,'quantity':Listing.quantity,'total':total,'time_left':duration,'auction_id':Listing.auction_id,'bid':Listing.bid}[sort]
    order=(field.desc() if direction=='desc' else field.asc()).nulls_last()
    count=db.scalar(select(func.count()).select_from(Listing).where(predicate))
    rows=db.scalars(select(Listing).where(predicate).order_by(order,Listing.auction_id).offset(page*page_size).limit(page_size))
    return money_contract({'listings':[{'auction_id':str(r.auction_id),'quantity':r.quantity,'buyout':r.buyout,'unit_price':r.unit_price,'bid':r.bid,'time_left':r.time_left,'source_kind':r.source_kind} for r in rows],
        'observed_at':aware(head.retrieved_at).isoformat(),'total':count,'snapshot_id':snapshot,'page':page,'page_size':page_size,'synthetic':head.synthetic,'provenance':'asking_listings_only'})
