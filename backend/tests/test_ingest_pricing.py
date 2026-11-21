import json
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import func, select
from market.db import now
from market.ingest import ingest, normalize
from market.models import Listing, Market, Observation, Snapshot
from market.pricing import summarize, values


@pytest.fixture
def market_id(database):
    with database.begin() as db:
        market = Market(region='eu', ruleset_id=2, house_id=113, source_kind='auctions', label='Synthetic test')
        db.add(market)
        db.flush()
        return market.id


def payload(buyout=1000, quantity=10):
    return json.dumps({'auctions': [{'id': 1, 'item': {'id': 12363}, 'quantity': quantity, 'buyout': buyout}]}).encode()


def test_deduplication_idempotency_provenance(database, market_id):
    with database.begin() as db:
        first = ingest(db, market_id, payload(), request_key='first', synthetic=True)
        assert ingest(db, market_id, payload(), request_key='first').id == first.id
        second = ingest(db, market_id, payload(), request_key='second', synthetic=True)
        assert first.snapshot_id == second.snapshot_id
        assert first.namespace == 'dynamic-forever-eu'
        assert first.payload_bytes == len(payload())
        with pytest.raises(ValueError, match='conflict'):
            ingest(db, market_id, payload(1200), request_key='first')
        assert db.scalar(select(func.count()).select_from(Snapshot)) == 1
        assert db.scalar(select(func.count()).select_from(Listing)) == 1
        assert db.scalar(select(func.count()).select_from(Observation)) == 2


def test_order_independent_content_hash_and_market_isolation(database, market_id):
    data = {'auctions': json.loads(payload())['auctions'] + [{'id': 2, 'item': {'id': 10}, 'quantity': 1, 'bid': 50}]}
    with database.begin() as db:
        first = ingest(db, market_id, json.dumps(data).encode(), request_key='a')
        data['auctions'].reverse()
        second = ingest(db, market_id, json.dumps(data, indent=2).encode(), request_key='b')
        assert first.snapshot_id == second.snapshot_id
        other = Market(region='eu', ruleset_id=1, house_id=113, source_kind='auctions', label='Different ruleset')
        db.add(other)
        db.flush()
        third = ingest(db, other.id, json.dumps(data).encode(), request_key='c')
        assert third.snapshot_id != first.snapshot_id


@pytest.mark.parametrize('body', [b'{}', b'[]', b'null', b'{"auctions":[{}]}',
    b'{"auctions":[{"id":true,"item":{"id":1},"quantity":1,"buyout":1}]}'])
def test_invalid_payload_atomic(database, market_id, body):
    with database() as db:
        with pytest.raises(ValueError):
            ingest(db, market_id, body, request_key='bad')
        db.rollback()
        assert db.scalar(select(func.count()).select_from(Observation)) == 0


def test_commodity_semantics_and_bid_only():
    rows = normalize({'auctions':[{'id':1,'item':{'id':2},'quantity':10,'unit_price':123}]}, 'commodities')
    summary = summarize([SimpleNamespace(**row) for row in rows])
    assert summary['recent_price'] == 123
    assert summary['priced_supply'] == 10
    rows = normalize({'auctions':[{'id':1,'item':{'id':2},'quantity':10,'bid':100}]}, 'auctions')
    assert summarize([SimpleNamespace(**row) for row in rows])['recent_price'] is None
    assert summarize([SimpleNamespace(**row) for row in rows])['supply'] == 10
    with pytest.raises(ValueError):
        normalize({'auctions':[{'id':1,'item':{'id':2},'quantity':10,'buyout':123}]}, 'commodities')


def test_quantity_weighting_stack_total_and_rounding():
    rows = [SimpleNamespace(quantity=2, buyout=201, unit_price=None),
            SimpleNamespace(quantity=8, buyout=1600, unit_price=None)]
    assert summarize(rows)['recent_price'] == 180
    assert summarize(rows)['lowest_buyout'] == 101


def test_windows_daily_sampling_no_sales_inference(database, market_id):
    at = now().replace(hour=12, minute=0, second=0, microsecond=0)-timedelta(days=1)
    with database.begin() as db:
        ingest(db, market_id, payload(1000), request_key='old', retrieved_at=at-timedelta(days=30), synthetic=True)
        ingest(db, market_id, payload(2000), request_key='week', retrieved_at=at-timedelta(days=7), synthetic=True)
        ingest(db, market_id, payload(5000), request_key='early', retrieved_at=at-timedelta(hours=2), synthetic=True)
        latest = ingest(db, market_id, payload(3000), request_key='latest', retrieved_at=at, synthetic=True)
        variant = db.scalar(select(Listing.variant_key).where(Listing.snapshot_id == latest.snapshot_id))
        result = values(db, market_id, 12363, variant, at=at)
        assert result['recent_price'] == 300
        assert result['market_value'] == 250
        assert result['historical_value'] == 200
        assert result['coverage_days'] == 3
        assert result['synthetic']
        # Explicit empty current snapshot removes asking prices, does not invent a sale.
        ingest(db, market_id, b'{"auctions":[]}', request_key='empty', retrieved_at=at+timedelta(minutes=1), synthetic=True)
        result = values(db, market_id, 12363, variant, at=at+timedelta(minutes=1))
        assert result['recent_price'] is None
        assert result['supply'] == 0


def test_item_variants_are_not_mixed(database, market_id):
    data = {'auctions':[{'id':1,'item':{'id':2,'bonus_lists':[10]},'quantity':1,'buyout':100},
                        {'id':2,'item':{'id':2,'bonus_lists':[20]},'quantity':1,'buyout':900}]}
    with database.begin() as db:
        obs = ingest(db, market_id, json.dumps(data).encode(), request_key='variants')
        variants = list(db.scalars(select(Listing.variant_key).where(Listing.snapshot_id == obs.snapshot_id)))
        assert len(set(variants)) == 2
        assert sorted(values(db,market_id,2,key)['recent_price'] for key in variants) == [100,900]
