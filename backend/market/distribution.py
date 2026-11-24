"""Set-based all-listing price distribution, independently bounded from display rows."""
from fastapi import APIRouter,Depends,Query
from sqlalchemy import Numeric,case,cast,func,literal,select
from sqlalchemy.orm import Session
from .db import session
from .market_api import MarketId,identity,latest_observation,require_market
from .models import Listing,User
router=APIRouter(prefix='/api/v1')


@router.get('/markets/{market_id}/distribution/{item_id}/{variant_key}')
def distribution(market_id: MarketId,item_id: MarketId,variant_key: str,bins: int=Query(12,ge=5,le=32),user: User=Depends(identity),db: Session=Depends(session)):
    require_market(db,market_id)
    latest=latest_observation(db,market_id)
    result={'contract_version':1,'bands':[],'priced_supply':0,'unpriced_supply':0,'listing_count':0,'priced_listing_count':0,'unpriced_listing_count':0,'synthetic':bool(latest and latest.synthetic),'basis':'current_asking_listings','cheapest':None}
    if not latest:return result
    from fastapi import HTTPException
    if len(variant_key)!=64 or any(c not in '0123456789abcdef' for c in variant_key):raise HTTPException(422,'Invalid variant identity')
    numerator=func.coalesce(Listing.buyout,Listing.unit_price)
    denominator=case((Listing.buyout.is_not(None),Listing.quantity),else_=1)
    # Keep distinct per-unit prices distinct even for large stack buyouts.
    unit=cast(numerator,Numeric(60,30))/denominator
    prices=select(unit.label('price'),numerator.label('numerator'),denominator.label('denominator'),
        Listing.quantity,Listing.auction_id).where(Listing.snapshot_id==latest.snapshot_id,
        Listing.item_id==item_id,Listing.variant_key==variant_key).cte('distribution_prices')
    bounds=select(func.min(prices.c.price).label('low'),func.max(prices.c.price).label('high')).cte('price_bounds')
    bucket=case((bounds.c.high==bounds.c.low,0),else_=func.floor((prices.c.price-bounds.c.low)/func.nullif(bounds.c.high-bounds.c.low,0)*bins))
    bucket=case((bucket>=bins,bins-1),else_=bucket)
    rows=db.execute(select(bucket.label('bucket'),func.round(func.min(prices.c.price)),func.round(func.max(prices.c.price)),
        func.sum(prices.c.quantity),func.count()).select_from(prices.join(bounds,literal(True)))
        .where(prices.c.price.is_not(None)).group_by(bucket).order_by(bucket))
    for band,low,high,supply,count in rows:
        result['bands'].append({'bucket':int(band),'minimum':str(int(low)),'maximum':str(int(high)),'supply':supply,'listing_count':count})
        result['priced_supply']+=supply;result['priced_listing_count']+=count
    if result['priced_supply']:
        cheapest=select(prices.c.numerator,prices.c.denominator).where(prices.c.price.is_not(None)).order_by(
            prices.c.price,prices.c.auction_id).limit(1).cte('cheapest_unit_price')
        exact_match=cast(prices.c.numerator,Numeric)*cheapest.c.denominator==cast(cheapest.c.numerator,Numeric)*prices.c.denominator
        low,quantity,supply,count=db.execute(select(cheapest.c.numerator,cheapest.c.denominator,
            func.sum(prices.c.quantity),func.count()).select_from(prices.join(cheapest,exact_match)
            ).group_by(cheapest.c.numerator,cheapest.c.denominator)).one()
        result['cheapest']={'numerator':str(low),'denominator':quantity,'supply':supply,'listing_count':count}
    unpriced=db.execute(select(func.coalesce(func.sum(prices.c.quantity),0),func.count()).where(prices.c.price.is_(None))).one()
    result['unpriced_supply'],result['unpriced_listing_count']=unpriced
    result['listing_count']=result['priced_listing_count']+result['unpriced_listing_count']
    return result
