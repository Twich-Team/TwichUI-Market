"""Synthetic crate recipes, quotes and isolated snapshot observations."""
import json
from collections import Counter
from datetime import timedelta
from email.utils import format_datetime
from fractions import Fraction

from market.db import now
from market.ingest import ingest
from market.models import ItemSourceCoverage, Listing, Market, Snapshot
from market.pricing import values
from sqlalchemy import select
from market.waylaid_pricing import ItemQuote, QuoteBook, load_quotes, price_crate


def market(db, *, house=100, kind='auctions'):
    row = Market(region='us', ruleset_id=1, house_id=house, source_kind=kind,
                 verified=True, label='Synthetic test market')
    db.add(row)
    db.flush()
    return row


def snapshot(db, scope, at, entries, key):
    body = {'auctions': [dict(id=i, **row) for i, row in enumerate(entries, 1)]}
    return ingest(db, scope.id, json.dumps(body).encode(), request_key=key,
                  synthetic=True, retrieved_at=at, modified=format_datetime(at, usegmt=True))


def auction(item, size, buyout):
    return {'item': {'id': item}, 'quantity': size, 'buyout': buyout}


def test_minimum_depth_exact_stack_sizes_bids_variants_and_market_isolation(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        head = snapshot(db, scope, at, [
            auction(10, 2, 20), auction(10, 2, 20), auction(10, 3, 30), auction(10, 5, 100),
            {'item': {'id': 10}, 'quantity': 50, 'bid': 1},
            {'item': {'id': 10, 'bonus_lists': [1]}, 'quantity': 100, 'buyout': 100},
        ], 'stack-depth')
        snapshot(db, market(db, house=101), at, [auction(10, 100, 100)], 'other-house')
        book = load_quotes(db, scope, [10, 999], 'current', at=at)
        assert book.snapshot_id == str(head.snapshot_id)
        options = price_crate(999, 5, {
            'overshoot': {10: 6}, 'exact': {10: 4}, 'too_few': {10: 9}, 'mixed_stacks': {10: 5},
        }, book, owned=True)['bundles']
        overshoot, exact, too_few, mixed_stacks = [b['materials'][0] for b in options]
        assert exact['available_at_minimum'] == 7 and exact['current_priced_quantity'] == 12
        assert exact['minimum_purchase_copper'] == '40' and exact['stock_status'] == 'sufficient_at_minimum'
        assert mixed_stacks['minimum_purchase_copper'] == '50'
        assert overshoot['subtotal_copper'] == '60' and overshoot['minimum_purchase_copper'] is None
        assert overshoot['stock_status'] == 'whole_stack_overshoot'
        assert too_few['stock_status'] == 'insufficient_at_minimum'
        assert all('synthetic_observations' in b['reasons'] for b in options)


def test_exact_minimum_uses_unrounded_asks_and_never_underquotes_stack_spend(database):
    with database.begin() as db:
        scope = market(db)
        at = now() - timedelta(seconds=1)
        snapshot(db, scope, at, [auction(10, 3, 31), auction(10, 5, 51)], 'near-minimum')
        book = load_quotes(db, scope, [10], 'current')
        result = price_crate(999, 5, {'fill': {10: 5}}, book, owned=True)
        line = result['bundles'][0]['materials'][0]
        # Both unit asks round to 10. Only 51/5 is the actual lowest.
        assert line['minimum_unit_copper'] == '10' and line['available_at_minimum'] == 5
        assert line['unit_price_exact'] == {'numerator_copper': '51', 'denominator': 5}
        assert line['subtotal_copper'] == '51' and line['minimum_purchase_copper'] == '51'
        assert result['fill_cost_exact'] == result['total_cost_exact'] == line['subtotal_exact']
        assert result['reasons'] == ['synthetic_observations']


def test_commodity_partial_lots_and_raw_compaction(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db, kind='commodities')
        head = snapshot(db, scope, at, [
            {'item': {'id': 5}, 'quantity': 50, 'unit_price': 3},
            {'item': {'id': 5}, 'quantity': 10, 'unit_price': 4},
        ], 'commodity-depth')
        def material():
            book = load_quotes(db, scope, [5, 90], 'current')
            return price_crate(90, 5, {'base': {5: 21}}, book, owned=True)['bundles'][0]['materials'][0]
        line = material()
        assert line['source_kind'] == 'commodities' and line['available_at_minimum'] == 50
        assert line['minimum_purchase_copper'] == '63'
        db.get(Snapshot, head.snapshot_id).raw_retained = False
        line = material()
        assert line['stock_status'] == 'unknown' and line['available_at_minimum'] is None
        assert line['subtotal_copper'] == '63' and line['minimum_purchase_copper'] is None
        assert line['quote_status'] == 'rounded_estimate'


def test_reference_basis_changes_cheapest_bundle_and_crate_preserving_daily_semantics(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        # Three UTC days, including two observations on the first day. Only its last price counts.
        for time, costs, key in [
            (at - timedelta(days=15), [300, 400, 2], 'expired'),
            (at - timedelta(days=2, seconds=1), [99, 95, 10], 'replaced'),
            (at - timedelta(days=2), [45, 10, 4], 'day1'),
            (at - timedelta(days=1), [45, 10, 4], 'day2'),
            (at, [5, 20, 4], 'day3'),
        ]:
            snapshot(db, scope, time, [auction(item, 1, c) for item, c in zip([1, 2, 3], costs)], key)
        current = load_quotes(db, scope, [1, 2, 3], 'current', at=at)
        history = load_quotes(db, scope, [1, 2, 3], '14d', at=at)
        assert history.items[1].coverage_days == 3 and history.items[1].unit == 32
        assert history.items[1].status == 'available'
        for book, expected in [(current, 'ore'), (history, 'cloth')]:
            choice = price_crate(3, 10, {'ore': {1: 1}, 'cloth': {2: 1}, 'incomplete': {99: 1}}, book)
            assert choice['selected_bundle_id'] == expected and choice['purchase_cost_copper'] == '4'
            crates = [price_crate(3, 10, {'fill': {item: 1}}, book) for item in [1, 2]]
            def rate(crate):
                r = crate['cost_per_favor']
                return Fraction(int(r['numerator_copper']), r['denominator'])
            assert min(range(2), key=lambda i: rate(crates[i])) == (0 if book is current else 1)
        regional = load_quotes(db, scope, [1, 3], 'regional', at=at)
        unavailable = price_crate(3, 10, {'ore': {1: 1}}, regional)
        assert unavailable['total_cost_copper'] is None and not unavailable['eligible']
        assert unavailable['bundles'][0]['materials'][0]['quote_status'] == 'regional_unavailable'


def test_limited_stale_prices_and_bid_only_supply_remain_explicit(database):
    at = now() - timedelta(days=3)
    with database.begin() as db:
        scope = market(db)
        snapshot(db, scope, at, [auction(1, 1, 23), {'item': {'id': 2}, 'bid': 39, 'quantity': 11}], 'stale')
        history = load_quotes(db, scope, [1, 2], '14d')
        known = price_crate(2, 5, {'fill': {1: 2}}, history, owned=True)
        assert known['fill_cost_copper'] == '46' and known['purchase_cost_copper'] == '0'
        assert 'limited' in known['reasons'] and 'stale_freshness' in known['reasons']
        assert 'insufficient_at_minimum' not in known['reasons']
        current = load_quotes(db, scope, [1, 2], 'current')
        unknown = price_crate(2, None, {'fill': {1: 1}}, current)
        assert unknown['purchase_quote']['current_priced_quantity'] == 0
        assert unknown['purchase_cost_copper'] is None and unknown['total_cost_copper'] is None
        assert unknown['cost_per_favor'] is None and 'unknown_favor' in unknown['reasons']


def test_exact_large_costs_owned_crates_and_shared_inventory():
    # Pure arithmetic example with explicit test quotes and no database observations.
    price = 2**53 + 7
    material = ItemQuote(minimum=price, unit=price, status='available', source_kind='commodities',
                         priced_quantity=5, depth_known=True, exact_minimum=Fraction(price), lots=Counter({5: 1}))
    book = QuoteBook('current', {1: material}, freshness='current', verified=True)
    bought = price_crate(1, 3, {'same': {1: 5}}, book)
    assert bought['total_cost_copper'] == str(price * 6)
    assert not bought['eligible'] and bought['reasons'] == ['insufficient_at_minimum']
    owned = price_crate(1, 3, {'same': {1: 5}}, book, owned=True)
    assert owned['cost_per_favor'] == {'numerator_copper': str(price * 5 // 3), 'denominator': 1}
    assert owned['eligible'] and owned['purchase_cost_copper'] == '0'
    missing = price_crate(9, 3, {'same': {1: 5}}, book)
    assert missing['fill_cost_copper'] == str(price * 5) and missing['purchase_cost_copper'] is None
    assert missing['total_cost_copper'] is None and not missing['eligible']


def test_rounded_zero_unit_never_becomes_free_unowned_crate(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        snapshot(db, scope, at, [auction(1, 10, 1), auction(2, 1, 50)], 'sub-copper')
        book = load_quotes(db, scope, [1, 2], 'current')
        result = price_crate(1, 5, {'fill': {2: 1}}, book)
        assert result['purchase_quote']['minimum_unit_copper'] == '0'
        assert result['purchase_quote']['quote_status'] == 'available'
        assert result['purchase_cost_exact'] == {'numerator_copper': '1', 'denominator': 10}
        assert result['cost_per_favor'] == {'numerator_copper': '501', 'denominator': 50}
        assert result['purchase_quote']['minimum_purchase_copper'] is None
        assert 'whole_stack_overshoot' in result['reasons']
        whole = price_crate(2, 5, {'fill': {1: 10}}, book, owned=True)
        assert whole['fill_cost_copper'] == '1' and whole['reasons'] == ['synthetic_observations']
        assert price_crate(1, 5, {'fill': {2: 1}}, book, owned=True)['total_cost_copper'] == '50'


def test_quality_and_provenance_follow_the_priced_snapshot(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        for offset, cost in [(2, 2), (1, 2), (0, 202)]:
            snapshot(db, scope, at - timedelta(days=offset), [auction(1, 1, cost)], f'quality-{offset}')
        book = load_quotes(db, scope, [1], '14d', at=at)
        line = price_crate(2, 5, {'fill': {1: 1}}, book, owned=True)['bundles'][0]['materials'][0]
        assert line['quote_status'] == 'needs_review' and '100×' in line['quality_reason']
        assert line['subtotal_copper'] == '69' and line['coverage_days'] == 3 and line['synthetic']
        assert load_quotes(db, scope, [1], 'current', at=at - timedelta(days=1)).freshness == 'unknown'
        empty = load_quotes(db, market(db, house=102), [1], 'regional')
        assert empty.snapshot_id is None and empty.items[1].status == 'regional_unavailable'


def test_round_only_after_exact_bundle_choice_and_combined_total(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        snapshot(db, scope, at, [auction(1, 10, 104), auction(2, 5, 51), auction(3, 10, 3)], 'round-last')
        book = load_quotes(db, scope, [1, 2, 3], 'current')
        # Both alternatives display 10c, and lexical tie-breaking would have selected the dearer one.
        result = price_crate(3, 7, {'dearer': {1: 1}, 'lower': {2: 1}}, book)
        assert result['selected_bundle_id'] == 'lower'
        assert result['total_cost_exact'] == {'numerator_copper': '21', 'denominator': 2}
        assert result['total_cost_copper'] == '11' and result['cost_per_favor'] == {
            'numerator_copper': '3', 'denominator': 2}
        both = price_crate(3, 4, {'fill': {1: 1, 2: 1}}, book, owned=True)
        assert both['fill_cost_exact'] == {'numerator_copper': '103', 'denominator': 5}
        assert both['fill_cost_copper'] == '21'


def test_rate_denominator_above_javascript_integer_precision(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db)
        size = 2**30 - 1
        snapshot(db, scope, at, [auction(1, size, 2)], 'large-denominator')
        book = load_quotes(db, scope, [1], 'current')
        favor = 2**30 + 1
        result = price_crate(2, favor, {'fill': {1: 1}}, book, owned=True)
        assert result['cost_per_favor'] == {'numerator_copper': '2', 'denominator': str(size * favor)}


def test_coverage_floor_matches_native_market_value(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        scope = market(db, kind='commodities')
        for days, unit in [(5, 1000), (3, 900), (2, 19), (1, 21), (0, 26)]:
            head = snapshot(db, scope, at - timedelta(days=days), [
                {'item': {'id': 1}, 'unit_price': unit, 'quantity': 2}], f'floor-{days}')
        key = db.scalar(select(Listing.variant_key).where(Listing.snapshot_id == head.snapshot_id))
        db.add(ItemSourceCoverage(market_id=scope.id, item_id=1, variant_key=key,
                                  first_observed_at=at - timedelta(days=2), source_kind='commodities'))
        native = values(db, scope.id, 1, key, at=at)
        book = load_quotes(db, scope, [1], '14d', at=at)
        assert book.items[1].unit == native['market_value'] == 22
        assert book.items[1].coverage_days == native['market_coverage_days'] == 3
