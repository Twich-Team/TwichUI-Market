"""Set-based, explainable asking-price and supply signals. Never infers sales."""
from datetime import timedelta,timezone
from sqlalchemy import Integer,Numeric,and_,case,cast,func,select,true,or_
from sqlalchemy.orm import aliased
from .db import now
from .models import DailyObservation,ItemMetadata,Listing,Observation,SnapshotStatistic,ItemSourceCoverage
from .pricing import ALGORITHM


def evidence(coverage,freshness,verified,synthetic):
    if freshness!='current' or not verified or synthetic: return 'limited'
    return 'strong' if coverage>=7 else 'moderate' if coverage>=3 else 'limited'


def admissible(freshness,verified,minimum):
    return minimum=='limited' or (freshness=='current' and verified)


def daily_window(market_id,at,*,prior=False):
    query=select(DailyObservation.day,Observation.snapshot_id,Observation.synthetic,Observation.retrieved_at).join(
        Observation,Observation.id==DailyObservation.observation_id).where(
        DailyObservation.market_id==market_id,Observation.retrieved_at>=at-timedelta(days=14),Observation.retrieved_at<=at)
    if prior: query=query.where(DailyObservation.day<at.astimezone(timezone.utc).date())
    return query.subquery()


def below_reference(db,market,latest,*,minimum_discount,maximum_spend,minimum_coverage,minimum_confidence,freshness,at=None):
    at=at or now()
    if not admissible(freshness,market.verified,minimum_confidence): return [],False
    daily=daily_window(market.id,at)
    references=select(SnapshotStatistic.item_id,SnapshotStatistic.variant_key,
        func.round(func.avg(SnapshotStatistic.recent_price)).label('reference_price'),
        func.count(SnapshotStatistic.recent_price).label('coverage'),
        func.max(cast(daily.c.synthetic,Integer)).label('synthetic')).select_from(daily).join(
        SnapshotStatistic,SnapshotStatistic.snapshot_id==daily.c.snapshot_id).where(
        SnapshotStatistic.algorithm==ALGORITHM).group_by(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).subquery()
    total=case((Listing.buyout.is_not(None),Listing.buyout),else_=Listing.unit_price*Listing.quantity)
    price=case((Listing.buyout.is_not(None),cast(Listing.buyout,Numeric)/Listing.quantity),else_=cast(Listing.unit_price,Numeric))
    discount=(1-price/func.nullif(references.c.reference_price,0))*100
    query=select(Listing,references.c.reference_price,references.c.coverage,references.c.synthetic,ItemMetadata,
        discount.label('discount'),total.label('total')).join(references,and_(references.c.item_id==Listing.item_id,
        references.c.variant_key==Listing.variant_key)).outerjoin(ItemMetadata,and_(ItemMetadata.region==market.region,
        ItemMetadata.item_id==Listing.item_id)).where(Listing.snapshot_id==latest.snapshot_id,
        references.c.reference_price>0,references.c.coverage>=minimum_coverage,total<=maximum_spend,discount>=minimum_discount)
    if minimum_confidence!='limited':
        if latest.synthetic: return [],False
        query=query.where(references.c.synthetic==0,references.c.coverage>=(7 if minimum_confidence=='strong' else 3))
    rows=list(db.execute(query.order_by(discount.desc(),Listing.auction_id).limit(101)))
    return rows[:100],len(rows)>100


def change_signals(db,market,latest,*,kind,minimum_change,minimum_coverage,minimum_confidence,direction,freshness,at=None):
    at=at or now()
    if not admissible(freshness,market.verified,minimum_confidence): return [],False
    daily=daily_window(market.id,at,prior=True)
    old=aliased(SnapshotStatistic)
    current=select(SnapshotStatistic.item_id,SnapshotStatistic.variant_key,SnapshotStatistic.recent_price,
        SnapshotStatistic.supply).where(SnapshotStatistic.snapshot_id==latest.snapshot_id,
            SnapshotStatistic.algorithm==ALGORITHM).subquery()
    historical_keys=select(old.item_id,old.variant_key).join(daily,old.snapshot_id==daily.c.snapshot_id).where(old.algorithm==ALGORITHM)
    keys=select(current.c.item_id,current.c.variant_key).union(historical_keys).subquery()
    baseline=select(keys.c.item_id,keys.c.variant_key,
        func.max(current.c.recent_price).label('current_price'),func.coalesce(func.max(current.c.supply),0).label('current_supply'),
        func.round(func.avg(old.recent_price)).label('reference_price'),
        func.avg(cast(func.coalesce(old.supply,0),Numeric)).label('reference_supply'),
        func.count(old.recent_price).label('price_days'),func.count(old.supply).label('supply_days'),
        func.count(daily.c.day).label('market_days'),func.max(cast(daily.c.synthetic,Integer)).label('synthetic'))
    baseline=baseline.select_from(keys).outerjoin(ItemSourceCoverage,and_(
        ItemSourceCoverage.market_id==market.id,ItemSourceCoverage.item_id==keys.c.item_id,
        ItemSourceCoverage.variant_key==keys.c.variant_key)).join(daily,or_(
        ItemSourceCoverage.first_observed_at.is_(None), daily.c.retrieved_at>=ItemSourceCoverage.first_observed_at)).outerjoin(old,and_(old.snapshot_id==daily.c.snapshot_id,
        old.item_id==keys.c.item_id,old.variant_key==keys.c.variant_key,old.algorithm==ALGORITHM)).outerjoin(
        current,and_(current.c.item_id==keys.c.item_id,current.c.variant_key==keys.c.variant_key))
    baseline=baseline.group_by(keys.c.item_id,keys.c.variant_key).subquery()
    reference=baseline.c.reference_price if kind=='price' else baseline.c.reference_supply
    current_value=baseline.c.current_price if kind=='price' else baseline.c.current_supply
    coverage=baseline.c.price_days if kind=='price' else baseline.c.supply_days
    change=(cast(current_value,Numeric)/func.nullif(reference,0)-1)*100
    query=select(baseline,ItemMetadata,change.label('change')).outerjoin(ItemMetadata,and_(
        ItemMetadata.region==market.region,ItemMetadata.item_id==baseline.c.item_id)).where(
        reference>0,coverage>=minimum_coverage,func.abs(change)>=minimum_change)
    if kind=='price': query=query.where(current_value.is_not(None),current_value>0)
    if direction=='increase': query=query.where(change>0)
    elif direction=='decrease': query=query.where(change<0)
    if minimum_confidence!='limited':
        if latest.synthetic:return [],False
        query=query.where(baseline.c.synthetic==0,coverage>=(7 if minimum_confidence=='strong' else 3))
    rows=list(db.execute(query.order_by(func.abs(change).desc(),baseline.c.item_id,baseline.c.variant_key).limit(101)))
    return rows[:100],len(rows)>100
