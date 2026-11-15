"""Opt-in, pure twichui-pricing-v1 calculations. Never selected by legacy APIs.

No database, network, wall clock, persistence or UI dependencies. Callers retain
original observations; outputs are separately versioned derived evidence.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
import re

ALGORITHM = 'twichui-pricing-v1'
HISTORY_BASIS = 'canonical_complete_scope_close'
MAX_COPPER = 99_999_999_999
MAX_I64 = 2**63 - 1
MAX_COUNT = 2**53 - 1
MAX_LISTINGS = 150_000


def copper(value, *, maximum=MAX_I64, positive=False):
    """Validate before conversion, including strings beyond a double's range."""
    if (type(value) is not str or len(value) > 19
            or re.fullmatch(r'0|[1-9][0-9]*', value, flags=re.ASCII) is None):
        raise ValueError('Noncanonical copper')
    number = int(value)
    if number > maximum or (positive and number == 0):
        raise ValueError('Copper range')
    return number


def integer(value, low=0, high=MAX_COUNT):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Integer range')
    return value


def identity(item_id, variant_key):
    integer(item_id, 1, 2**31-1)
    if type(variant_key) is not str or re.fullmatch('[0-9a-f]{64}', variant_key) is None:
        raise ValueError('Variant identity')


def half_up(numerator, denominator):
    integer(numerator, 0, 2**127-1)
    integer(denominator, 1, 2**127-1)
    return (2 * numerator + denominator) // (2 * denominator)


def lower_median(values):
    """Pairs (positive copper integer, positive integer weight); exact lower tie."""
    ordered = sorted(values)
    if not ordered:
        return None
    for price, weight in ordered:
        integer(price, 1, MAX_COPPER)
        integer(weight, 1)
    total = sum(weight for _, weight in ordered)
    cumulative = 0
    for price, weight in ordered:
        cumulative += weight
        if 2 * cumulative >= total:
            return price
    raise AssertionError('Positive weights must reach the median')


def snapshot(rows, *, item_id, variant_key, source_kind):
    """Rows have exact identity, quantity and nullable decimal-string ask fields.

    All rows must belong to the requested variant. Partial source coverage is
    carried by the caller's observation; arithmetic alone grants no advice.
    """
    identity(item_id, variant_key)
    if source_kind not in ('auctions', 'commodities'):
        raise ValueError('Source kind')
    if type(rows) is not list or len(rows) > MAX_LISTINGS:
        raise ValueError('Listing bound')
    tiers = defaultdict(lambda: [0, 0, 0])
    supply = priced_supply = total = 0
    unsupported = False
    minimum_ratio = None
    for row in rows:
        if type(row) is not dict or set(row) != {'item_id', 'variant_key', 'quantity', 'total_copper', 'unit_copper', 'bid_copper'}:
            raise ValueError('Listing shape')
        identity(row['item_id'], row['variant_key'])
        if (row['item_id'], row['variant_key']) != (item_id, variant_key):
            raise ValueError('Mixed variants')
        quantity = integer(row['quantity'], 1, 2**31-1)
        supply += quantity
        integer(supply)
        buyout = copper(row['total_copper'], positive=True) if row['total_copper'] is not None else None
        unit = copper(row['unit_copper'], positive=True) if row['unit_copper'] is not None else None
        bid = copper(row['bid_copper'], positive=True) if row['bid_copper'] is not None else None
        if source_kind == 'commodities':
            if unit is None or buyout is not None or unit * quantity > MAX_I64:
                raise ValueError('Commodity price semantics')
            numerator, denominator = unit, 1
            amount = unit * quantity
        else:
            if unit is not None or (buyout is None and bid is None):
                raise ValueError('Auction price semantics')
            if buyout is None:
                continue
            numerator, denominator = buyout, quantity
            amount = buyout
        priced_supply += quantity
        total += amount
        if minimum_ratio is None or numerator * minimum_ratio[1] < minimum_ratio[0] * denominator:
            minimum_ratio = (numerator, denominator)
        price = (numerator + denominator - 1) // denominator
        unsupported |= price > MAX_COPPER
        entry = tiers[price]
        entry[0] += quantity
        entry[1] += 1
        entry[2] = max(entry[2], quantity)
    result = {'algorithm': ALGORITHM, 'item_id': item_id, 'variant_key': variant_key,
              'state': 'unsupported' if unsupported else 'priced' if priced_supply else 'unpriced',
              'reason': 'numeric_range' if unsupported else None,
              'supply': supply, 'priced_supply': priced_supply, 'listing_count': len(rows),
              'priced_listing_count': sum(t[1] for t in tiers.values()),
              'quantity_weighted_ask_copper': str(half_up(total, priced_supply)) if priced_supply else None,
              'minimum_ratio': [str(x) for x in minimum_ratio] if minimum_ratio else None,
              'minimum_listing_copper': None, 'recent_copper': None, 'distribution': None}
    if not priced_supply or unsupported:
        return result
    ordered = sorted(tiers.items())
    cumulative = 0
    anchor = q25 = q50 = q75 = None
    for price, (quantity, _, _) in ordered:
        cumulative += quantity
        if q25 is None and 4*cumulative >= priced_supply: q25 = price
        if anchor is None and 4*cumulative > priced_supply: anchor = price
        if q50 is None and 2*cumulative >= priced_supply: q50 = price
        if q75 is None and 4*cumulative >= 3*priced_supply: q75 = price
    eligible = [(p, t[0]) for p, t in ordered if 2*p >= anchor]
    # Integer tenths preserve fractional boundary units without binary floats.
    weight = 3 * sum(q for _, q in eligible)
    remaining = weight
    weighted = 0
    for price, quantity in eligible:
        take = min(10*quantity, remaining)
        weighted += price * take
        remaining -= take
        if remaining == 0: break
    recent = half_up(weighted, weight)
    minimum = ordered[0][0]
    spread = 10 * (q75-q25)
    result.update(minimum_listing_copper=str(minimum), recent_copper=str(recent), distribution={
        'algorithm': ALGORITHM, 'anchor_copper': str(anchor),
        'q25_copper': str(q25), 'q50_copper': str(q50), 'q75_copper': str(q75),
        'high_copper': str(ordered[-1][0]),
        'near_supply': sum(t[0] for p, t in ordered if 10*p <= 11*recent),
        'spread_class': 'tight' if spread < q50 else 'moderate' if spread < 3*q50 else 'wide',
        'cheapoutlier': 2*minimum < recent,
        'farbelow': result['priced_listing_count'] < 5 and len(ordered) > 1 and 2*minimum < ordered[1][0],
        'tiers': [{'unit_copper': str(p), 'quantity': t[0], 'listing_count': t[1], 'largest_listing': t[2]}
                  for p, t in ordered[:6]],
        'tail_quantity': sum(t[0] for _, t in ordered[6:]),
        'tail_listing_count': sum(t[1] for _, t in ordered[6:])})
    return result


def instant(value):
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    return value.astimezone(timezone.utc)


def history(observations, *, market_key, item_id, variant_key, as_of, watermark=None):
    """Select complete market-scope closes, including absence; never fill a date.

    The caller must derive Recent Prices from original eligible inputs under this
    algorithm, not relabel provisional means or old Workshop history strings.
    """
    identity(item_id, variant_key)
    if type(market_key) is not str or not 1 <= len(market_key) <= 320:
        raise ValueError('Market identity')
    as_of = instant(as_of)
    if watermark is not None: watermark = integer(watermark, 1, MAX_I64)
    if type(observations) is not list or len(observations) > 100_000:
        raise ValueError('Observation bound')
    daily, seen = {}, set()
    for observation in observations:
        if type(observation) is not dict or set(observation) != {
                'observation_id', 'market_key', 'item_id', 'variant_key', 'algorithm',
                'observed_at', 'complete', 'state', 'recent_copper', 'synthetic', 'content_id'}:
            raise ValueError('Observation shape')
        if (observation['market_key'], observation['item_id'], observation['variant_key']) != (market_key, item_id, variant_key):
            raise ValueError('Mixed market or variant history')
        identity(observation['item_id'], observation['variant_key'])
        if observation['algorithm'] != ALGORITHM:
            raise ValueError('Unsupported history algorithm')
        oid = integer(observation['observation_id'], 1, MAX_I64)
        if oid in seen: raise ValueError('Duplicate observation identity')
        seen.add(oid)
        stamp = instant(observation['observed_at'])
        if stamp > as_of: raise ValueError('Future observation')
        if type(observation['complete']) is not bool or type(observation['synthetic']) is not bool:
            raise ValueError('Observation flags')
        if observation['state'] not in ('listed', 'absent', 'unknown'):
            raise ValueError('Presence state')
        price = observation['recent_copper']
        if price is not None: copper(price, maximum=MAX_COPPER, positive=True)
        if observation['state'] != 'listed' and price is not None:
            raise ValueError('Price without listed observation')
        if type(observation['content_id']) is not str or not 1 <= len(observation['content_id']) <= 128:
            raise ValueError('Content identity')
        if watermark is not None and oid > watermark: continue
        age = (as_of.date()-stamp.date()).days
        if not observation['complete'] or not 0 <= age < 60: continue
        key = stamp.date()
        if key not in daily or (stamp, oid) > (daily[key]['observed_at'], daily[key]['observation_id']):
            daily[key] = {**observation, 'observed_at': stamp}
    mv, hv, days = [], [], []
    for day, point in sorted(daily.items()):
        age = (as_of.date()-day).days
        price = int(point['recent_copper']) if point['recent_copper'] is not None else None
        if price is not None:
            hv.append((price, 1))
            if age < 14: mv.append((price, 4 if age <= 2 else 2 if age <= 6 else 1))
        days.append({'utc_day': day.isoformat(), 'observation_id': str(point['observation_id']),
                     'observed_at': point['observed_at'].isoformat(), 'state': point['state'],
                     'recent_copper': point['recent_copper'], 'synthetic': point['synthetic'],
                     'content_id': point['content_id'], 'provisional_day': age == 0})
    def wire(value): return str(value) if value is not None else None
    return {'algorithm': ALGORITHM, 'history_basis': HISTORY_BASIS,
            'market_value_copper': wire(lower_median(mv)),
            'historical_value_copper': wire(lower_median(hv)) if len(hv) >= 3 else None,
            'coverage': {'priced_days_14': len(mv), 'priced_days_60': len(hv),
                         'observed_days_60': len(days),
                         'distinct_content_count': len({p['content_id'] for p in daily.values()}),
                         'market_value_status': 'unknown' if not mv else 'single_day' if len(mv) == 1 else 'available' if len(mv) == 14 else 'sparse',
                         'historical_value_status': 'insufficient_days' if len(hv) < 3 else 'available' if len(hv) == 60 else 'sparse',
                         'missing_utc_days': [(as_of.date()-timedelta(days=age)).isoformat()
                                              for age in range(59, -1, -1) if as_of.date()-timedelta(days=age) not in daily]},
            'synthetic': any(p['synthetic'] for p in daily.values()), 'days': days}


def quality(facts):
    """Pure policy projection; this does not authorize an Advisor/Sell action."""
    required = {'has_price', 'complete', 'cut', 'distribution', 'wide_spread', 'mixed_variants',
                'farbelow', 'synthetic', 'mapping_verified', 'age_seconds', 'priced_listings', 'observed_days_30'}
    if type(facts) is not dict or set(facts) != required: raise ValueError('Quality shape')
    for key in required-{'age_seconds', 'priced_listings', 'observed_days_30'}:
        if type(facts[key]) is not bool: raise ValueError('Quality flag')
    integer(facts['priced_listings'], 0, MAX_LISTINGS)
    integer(facts['observed_days_30'], 0, 30)
    age = facts['age_seconds']
    if age is not None: integer(age)
    if not facts['has_price']: return 'none'
    if facts['synthetic'] or not facts['mapping_verified'] or age is None: return 'limited'
    fair = age <= 259200 and facts['priced_listings'] >= 3 and not facts['cut'] and not facts['mixed_variants']
    good = (fair and facts['complete'] and age <= 86400 and facts['priced_listings'] >= 5
            and facts['distribution'] and not facts['wide_spread'] and facts['observed_days_30'] >= 7 and not facts['farbelow'])
    return 'good' if good else 'fair' if fair else 'limited'
