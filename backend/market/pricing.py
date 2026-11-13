"""Version 1 provisional asking-price references; Workshop compatibility pending."""
from datetime import timedelta, timezone
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from .db import now
from .models import Listing, Observation
from .security import aware

ALGORITHM = 'asking-v1-provisional'


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
    grouped = defaultdict(list)
    for row in db.scalars(select(Listing).where(Listing.snapshot_id.in_(snapshot_ids),
        Listing.item_id == item_id, Listing.variant_key == variant_key)):
        grouped[row.snapshot_id].append(row)
    cache = {snapshot_id:summarize(grouped[snapshot_id]) for snapshot_id in snapshot_ids}
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
