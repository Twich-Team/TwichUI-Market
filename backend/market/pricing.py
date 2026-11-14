"""Version 1 provisional asking-price references; Workshop compatibility pending."""
from datetime import timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from .db import now
from .models import DailyObservation, Observation, Snapshot, SnapshotStatistic
from .security import aware

ALGORITHM = 'asking-v1-provisional'


class HistoryUnavailable(ValueError):
    pass


def summarize(listings):
    priced = [row for row in listings if row.buyout is not None or row.unit_price is not None]
    quantity = sum(row.quantity for row in priced)
    total = sum((row.buyout if row.buyout is not None else row.unit_price * row.quantity) for row in priced)
    unit_prices = [(Decimal(row.buyout) / row.quantity if row.buyout is not None else Decimal(row.unit_price)) for row in priced]
    return {'recent_price': rounded(Decimal(total) / quantity) if quantity else None,
            'lowest_buyout': rounded(min(unit_prices)) if unit_prices else None,
            'supply': sum(row.quantity for row in listings), 'priced_supply': quantity,
            'listing_count': len(listings)}


def rounded(value):
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def values(db, market_id, item_id, variant_key, *, at=None, through_observation_id=None):
    at = at or now()
    query = select(Observation).where(
        Observation.market_id == market_id, Observation.retrieved_at <= at,
        Observation.retrieved_at >= at - timedelta(days=60))
    if through_observation_id is not None:
        query = query.where(Observation.id <= through_observation_id)
    observations = list(db.scalars(query.order_by(Observation.retrieved_at, Observation.id)))
    if not observations:
        return {'algorithm': ALGORITHM, 'recent_price': None, 'market_value': None, 'historical_value': None,
                'supply': 0, 'priced_supply': 0, 'listing_count': 0, 'lowest_buyout': None,
                'coverage_days': 0, 'market_coverage_days': 0, 'observed_at': None, 'synthetic': False, 'history': []}
    # Last observation each UTC day: polling frequency does not overweight a day.
    days = {}
    for observation in observations:
        days[aware(observation.retrieved_at).astimezone(timezone.utc).date()] = observation
    snapshot_ids = {observation.snapshot_id for observation in days.values()}
    retained=list(db.scalars(select(Snapshot.statistics_retained).where(Snapshot.id.in_(snapshot_ids))))
    if not all(retained):
        raise HistoryUnavailable('Detailed history compacted; restart synchronization')
    cache={snapshot_id:summarize([]) for snapshot_id in snapshot_ids}
    for row in db.scalars(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id.in_(snapshot_ids),
        SnapshotStatistic.item_id == item_id, SnapshotStatistic.variant_key == variant_key)):
        if row.algorithm!=ALGORITHM:
            raise HistoryUnavailable('Historical reference algorithm is not supported by this version')
        cache[row.snapshot_id]={key:getattr(row,key) for key in ('recent_price','lowest_buyout','supply','priced_supply','listing_count')}
    def summary(observation):
        return cache[observation.snapshot_id]
    history = [{'date': day.isoformat(), **summary(observation)} for day, observation in sorted(days.items())]
    def average(window):
        prices = [Decimal(summary(obs)['recent_price']) for day, obs in days.items()
                  if aware(obs.retrieved_at) >= at - timedelta(days=window) and summary(obs)['recent_price'] is not None]
        return rounded(sum(prices) / len(prices)) if prices else None
    latest = observations[-1]
    return {**summary(latest), 'algorithm': ALGORITHM, 'market_value': average(14), 'historical_value': average(60),
            'coverage_days': sum(row['recent_price'] is not None for row in history),
            'market_coverage_days': sum(aware(obs.retrieved_at) >= at-timedelta(days=14)
                and summary(obs)['recent_price'] is not None for obs in days.values()),
            'observed_at': aware(latest.retrieved_at).isoformat(),
            'synthetic': any(obs.synthetic for obs in observations), 'history': history}


def daily_history(db,market_id,item_id,variant_key,days=365,*,at=None):
    at=at or now()
    observations=list(db.execute(select(DailyObservation.day,Observation).join(Observation,
        Observation.id==DailyObservation.observation_id).where(DailyObservation.market_id==market_id,
        DailyObservation.day>=(at-timedelta(days=days)).date(),DailyObservation.day<=at.date())
        .order_by(DailyObservation.day)))
    ids={observation.snapshot_id for _,observation in observations}
    statistics={row.snapshot_id:row for row in db.scalars(select(SnapshotStatistic).where(
        SnapshotStatistic.snapshot_id.in_(ids),SnapshotStatistic.item_id==item_id,SnapshotStatistic.variant_key==variant_key))}
    points=[]
    for day,observation in observations:
        row=statistics.get(observation.snapshot_id)
        points.append({'date':day.isoformat(),**({key:getattr(row,key) for key in
            ('recent_price','lowest_buyout','supply','priced_supply','listing_count')} if row else summarize([])),
            'observed_at':aware(observation.retrieved_at).isoformat(),'synthetic':observation.synthetic,
            'algorithm':row.algorithm if row else ALGORITHM,
            'observation_id':str(observation.id),'namespace':observation.namespace,
            'payload_hash':observation.payload_hash,'upstream_modified':observation.upstream_modified})
    return {'algorithm':ALGORITHM,'points':points,'synthetic':any(row['synthetic'] for row in points)}
