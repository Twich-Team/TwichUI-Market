"""Value crate requirements using exact base variants and observed asking prices."""
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
from typing import Literal

from sqlalchemy import Integer, String, and_, column, func, select, true, tuple_, values
from sqlalchemy.orm import aliased

from .db import now
from .ingest import canonical
from .market_api import market_view
from .models import ItemSourceCoverage, Listing, Observation, Snapshot, SnapshotStatistic
from .opportunities import daily_window
from .pricing import ALGORITHM, rounded
from .reference_quality import reference_quality
from .security import aware

Basis = Literal['current', 'regional', '14d']


@dataclass
class ItemQuote:
    minimum: int | None = None
    unit: Fraction | int | None = None
    status: str = 'missing_price'
    quality_reason: str | None = None
    source_kind: str | None = None
    coverage_days: int | None = None
    synthetic: bool = False
    priced_quantity: int | None = None
    depth_known: bool = False
    exact_minimum: Fraction | None = None
    # Whole auction stacks or divisible commodity lots at the exact minimum.
    lots: Counter = field(default_factory=Counter)

    def observe(self, size, count, unit):
        if self.exact_minimum is None or unit < self.exact_minimum:
            self.exact_minimum = unit
            self.lots.clear()
        if unit == self.exact_minimum:
            self.lots[size] += count


@dataclass
class QuoteBook:
    basis: Basis
    items: dict[int, ItemQuote]
    snapshot_id: str | None = None
    observed_at: str | None = None
    freshness: str = 'unknown'
    synthetic: bool = False
    verified: bool = False


def _snapshots(db, market_id, basis, at):
    """Pin the current observation and daily index together in one database read."""
    head = (select(Observation.snapshot_id, Observation.retrieved_at, Observation.synthetic, Observation.upstream_modified)
            .where(Observation.market_id == market_id, Observation.retrieved_at <= at)
            .order_by(Observation.retrieved_at.desc(), Observation.id.desc()).limit(1).subquery())
    q = select(head, Snapshot.raw_retained, Snapshot.statistics_retained).join_from(
        head, Snapshot, Snapshot.id == head.c.snapshot_id)
    if basis == '14d':
        day = daily_window(market_id, at)
        daily_snapshot = aliased(Snapshot)
        q = (q.outerjoin(day, true()).outerjoin(daily_snapshot, daily_snapshot.id == day.c.snapshot_id)
             .add_columns(day.c.snapshot_id.label('day_snapshot'), day.c.synthetic.label('day_synthetic'),
                          day.c.retrieved_at.label('day_observed_at'),
                          daily_snapshot.statistics_retained.label('day_retained')))
    return db.execute(q).mappings().all()


def load_quotes(db, market, item_ids, basis: Basis, *, at=None):
    """Read only requested exact variants in this logical market, with no provider calls."""
    if basis not in ('current', 'regional', '14d'):
        raise ValueError('Unknown price basis')
    at = at or now()
    book = QuoteBook(basis, {i: ItemQuote(status='regional_unavailable' if basis == 'regional' else 'missing_price')
                             for i in item_ids}, verified=market.verified)
    rows = _snapshots(db, market.id, basis, at)
    if not rows:
        return book
    head = rows[0]
    book.snapshot_id = str(head['snapshot_id'])
    book.observed_at = aware(head['retrieved_at']).isoformat()
    view = market_view(market)
    book.freshness = view['freshness']
    if book.freshness == 'current':
        if any(feed['enabled'] and feed['status'] == 'stale' for feed in view['feeds']):
            book.freshness = 'stale'
        elif head['upstream_modified'] != market.last_modified:
            # A newer market check cannot establish the freshness of this pinned observation.
            book.freshness = 'unknown'
    book.synthetic = head['synthetic']
    if not book.items:
        return book
    exact_keys = [(i, sha256(canonical({'id': i}).encode()).hexdigest()) for i in book.items]
    days = [r for r in rows if r.get('day_snapshot') is not None]
    ids = {head['snapshot_id'], *(r['day_snapshot'] for r in days)}
    stat = SnapshotStatistic
    stats = {(r.snapshot_id, r.item_id): r for r in db.scalars(select(stat).where(
        stat.snapshot_id.in_(ids), tuple_(stat.item_id, stat.variant_key).in_(exact_keys)))}
    # Same per-variant coverage floor as pricing.values(), fetched in one batch.
    coverage_starts = {}
    if days:
        source = ItemSourceCoverage
        coverage_starts = {i: aware(timestamp) for i, timestamp in db.execute(
            select(source.item_id, source.first_observed_at).where(source.market_id == market.id,
                tuple_(source.item_id, source.variant_key).in_(exact_keys)))}
    for item_id, quote in book.items.items():
        current = stats.get((head['snapshot_id'], item_id))
        valid_current = head['statistics_retained'] and (not current or current.algorithm == ALGORITHM)
        if valid_current:
            quote.minimum = current.lowest_buyout if current else None
            quote.source_kind = current.source_kind if current else None
            quote.priced_quantity = current.priced_supply if current else 0
            quote.depth_known = head['raw_retained']
        if basis == 'regional':
            # No regional AH price source or definition exists in this edition of Market.
            quote.status = 'regional_unavailable'
        elif not valid_current:
            quote.status = 'unsupported_statistics'
        elif basis == 'current':
            if quote.minimum is not None:
                quote.unit = quote.minimum if quote.minimum > 0 else None
                quote.status = 'rounded_estimate'
                quote.quality_reason = 'Only a rounded snapshot minimum is available for this item.'
        else:
            start = coverage_starts.get(item_id)
            daily_stats = [(r, stats.get((r['day_snapshot'], item_id))) for r in days
                           if start is None or aware(r['day_observed_at']) >= start]
            sources = {s.source_kind for _, s in daily_stats if s}
            if quote.source_kind:
                sources.add(quote.source_kind)
            if len(sources) > 1 or any(not r['day_retained'] or (s and s.algorithm != ALGORITHM)
                                       for r, s in daily_stats):
                quote.status = 'unsupported_statistics'
                continue
            quote.source_kind = next(iter(sources), None)
            prices = [s.recent_price for _, s in daily_stats if s and s.recent_price is not None]
            quote.coverage_days = len(prices)
            quote.synthetic = any(r['day_synthetic'] for r, s in daily_stats if s and s.recent_price is not None)
            if prices:
                # Reuse the provisional market value's positive half-up rounding,
                # exactly once after averaging the priced UTC days.
                quote.unit = rounded(Decimal(sum(prices)) / len(prices))
            quality = reference_quality(quote.unit, current.recent_price if current else None,
                                        min(prices, default=None), max(prices, default=None), len(prices))
            quote.status, quote.quality_reason = quality['state'], quality['reason']
            if quote.unit == 0:
                quote.unit = None

    if head['raw_retained']:
        # Fence the snapshot scan so the planner cannot probe per-variant indexes across retained history.
        snapshot_lots = (
            select(Listing.item_id, Listing.variant_key, Listing.source_kind, Listing.quantity,
                   Listing.buyout, Listing.unit_price)
            .where(Listing.snapshot_id == head['snapshot_id'],
                   Listing.buyout.is_not(None) | Listing.unit_price.is_not(None))
            .cte('waylaid_snapshot_lots').prefix_with('MATERIALIZED', dialect='postgresql')
        )
        variants = values(column('item_id', Integer), column('variant_key', String(64))).data(exact_keys).cte('waylaid_variants')
        raw = snapshot_lots.c
        fields = (raw.item_id, raw.source_kind, raw.quantity, raw.buyout, raw.unit_price)
        lots = (
            select(*fields, func.count())
            .join_from(snapshot_lots, variants, and_(raw.item_id == variants.c.item_id, raw.variant_key == variants.c.variant_key))
            .group_by(*fields)
        )
        seen = Counter()
        for item, kind, qty, buyout, unit_price, count in db.execute(lots):
            quote = book.items[item]
            if quote.source_kind != kind:
                quote.depth_known = False
                continue
            unit = Fraction(buyout, qty) if buyout is not None else Fraction(unit_price)
            quote.observe(qty, count, unit)
            seen[item] += count * qty
        for item, quote in book.items.items():
            # Fail closed on concurrent compaction or an incomplete price/depth source.
            if seen[item] != quote.priced_quantity:
                quote.depth_known = False
            if basis == 'current' and quote.depth_known and quote.exact_minimum is not None:
                if _rounded_copper(quote.exact_minimum) == quote.minimum:
                    quote.unit = quote.exact_minimum
                    quote.status, quote.quality_reason = 'available', None
                else:
                    quote.depth_known = False
    return book


def _can_buy_exact(lots, quantity):
    """Subset sum with multiplicities; the bitset covers only the requested units."""
    if quantity in lots or lots.get(1, 0) >= quantity:
        return True
    if len(lots) == 1:
        size, count = next(iter(lots.items()))
        return quantity % size == 0 and quantity // size <= count
    # Catalog quantities can be untrusted integers. Keep exact-search memory bounded.
    if quantity > 100_000:
        return None
    reachable, target = 1, 1 << quantity
    mask = 2 * target - 1
    for size, count in lots.items():
        count = min(count, quantity // size)
        chunk = 1
        while count:
            used = min(count, chunk)
            reachable |= (reachable << (size * used)) & mask
            if reachable & target:
                return True
            count -= used
            chunk *= 2
    return False


def _exact(value):
    if value is None:
        return None
    denominator = value.denominator
    return {'numerator_copper': str(value.numerator),
            'denominator': denominator if denominator < 2**53 else str(denominator)}


def _rounded_copper(value):
    # All asking prices are nonnegative. Avoid any decimal-context or float rounding.
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _display(value):
    return str(_rounded_copper(value)) if value is not None else None


def _line(item_id, quantity, book):
    quote = book.items.get(item_id) or ItemQuote()
    subtotal = quantity * quote.unit if quote.unit is not None else None
    available = sum(size * count for size, count in quote.lots.items()) if quote.depth_known else None
    if available is None:
        stock = 'unknown'
    elif available < quantity:
        stock = 'insufficient_at_minimum'
    elif quote.source_kind == 'commodities':
        stock = 'sufficient_at_minimum'
    else:
        exact = _can_buy_exact(quote.lots, quantity)
        stock = 'unknown' if exact is None else 'sufficient_at_minimum' if exact else 'whole_stack_overshoot'
    # The valuation can be fractional when a full stack would overshoot the request.
    observed_cost = None
    if stock == 'sufficient_at_minimum':
        observed_cost = int(quote.exact_minimum * quantity)
    return subtotal, {
        'item_id': item_id, 'quantity': quantity, 'minimum_purchase_copper': (
            str(observed_cost) if observed_cost is not None else None),
        'unit_price_exact': _exact(quote.unit), 'unit_price_copper': _display(quote.unit),
        'subtotal_exact': _exact(subtotal), 'subtotal_copper': _display(subtotal),
        'minimum_unit_copper': str(quote.minimum) if quote.minimum is not None else None,
        'available_at_minimum': available, 'current_priced_quantity': quote.priced_quantity,
        'stock_status': stock, 'quote_status': quote.status, 'quality_reason': quote.quality_reason,
        'coverage_days': quote.coverage_days, 'source_kind': quote.source_kind,
        'synthetic': book.synthetic or quote.synthetic,
    }


def _reasons(book, lines):
    reasons = []
    if book.freshness != 'current':
        reasons.append(book.freshness + '_freshness')
    if not book.verified:
        reasons.append('unverified_market')
    if book.synthetic or any(line['synthetic'] for line in lines):
        reasons.append('synthetic_observations')
    for line in lines:
        if line['quote_status'] != 'available':
            reasons.append(line['quote_status'])
        if book.basis == 'current' and line['stock_status'] != 'sufficient_at_minimum':
            reasons.append(line['stock_status'])
    return list(dict.fromkeys(reasons))


def price_crate(crate_item_id, favor, bundles, quotes, owned=False):
    """Choose the cheapest fully valued valid fill; keep incomplete options visible."""
    options, priced = [], []
    for bundle_id, quantities in bundles.items():
        if not quantities or any(type(q) is not int or q < 1 for q in quantities.values()):
            raise ValueError('A bundle requires positive material quantities')
        lines = [_line(i, q, quotes) for i, q in quantities.items()]
        materials = [line for _, line in lines]
        costs = [cost for cost, _ in lines]
        fill = sum(costs, Fraction()) if all(c is not None for c in costs) else None
        reasons = _reasons(quotes, materials)
        option = {'bundle_id': bundle_id, 'materials': materials,
                  'fill_cost_copper': _display(fill), 'fill_cost_exact': _exact(fill),
                  'eligible': not reasons, 'reasons': reasons}
        options.append(option)
        if fill is not None:
            priced.append((fill, option))
    fill, chosen = min(priced, key=lambda entry: (
        entry[0], not entry[1]['eligible'], entry[1]['bundle_id']), default=(None, None))
    purchase, purchase_quote = _line(crate_item_id, 1, quotes)
    if owned:
        purchase = Fraction(0)
    total = fill + purchase if fill is not None and purchase is not None else None
    if chosen:
        lines = list(chosen['materials'])
        if not owned:
            # Repeated crate/material IDs draw on the same observed inventory.
            shared = [m for m in lines if m['item_id'] == crate_item_id]
            if shared:
                lines.remove(shared[0])
                lines.append(_line(crate_item_id, shared[0]['quantity'] + 1, quotes)[1])
            else:
                lines.append(purchase_quote)
        reasons = _reasons(quotes, lines)
    else:
        reasons = ['no_fully_priced_bundle']
        reasons.extend(_reasons(quotes, [] if owned else [purchase_quote]))
    ratio = None
    if type(favor) is not int or favor <= 0:
        reasons.append('unknown_favor')
    elif total is not None:
        ratio = _exact(Fraction(total) / favor)
    return {'bundles': options, 'selected_bundle_id': chosen['bundle_id'] if chosen else None,
            'fill_cost_copper': _display(fill), 'fill_cost_exact': _exact(fill),
            'purchase_cost_copper': _display(purchase), 'purchase_cost_exact': _exact(purchase),
            'purchase_quote': purchase_quote, 'total_cost_copper': _display(total),
            'total_cost_exact': _exact(total), 'cost_per_favor': ratio, 'eligible': not reasons, 'reasons': reasons}
