"""Synthetic prices; item IDs/names were independently verified in Forever."""
import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import func, select
from market.db import now
from market.feed_collection import coverage_start
from market.ingest import canonical, ingest
from market.models import (CollectionRun, FeedCapture, FeedCheck, ItemSourceCoverage, Listing,
                           Market, MarketFeed, Observation, Snapshot, SnapshotStatistic)
from market.worker import collect_once
from test_bridge_export import contract_bundle  # Frozen bundle for installed-package CI.


def payload(kind, rows):
    path = '/data/wow/ruleset/2/auctions/114' + ('/commodities' if kind == 'commodities' else '')
    value = {'_links': {'self': {'href': 'https://us.api.blizzard.com' + path + '?namespace=dynamic-forever-us'}},
             'auctions': rows}
    if kind == 'auctions': value['id'] = 114
    return json.dumps(value).encode()


def row(item, aid, *, quantity=1, price=100, kind='commodities'):
    return {'id': aid, 'item': {'id': item}, 'quantity': quantity,
            'unit_price' if kind == 'commodities' else 'buyout': price}


def configure(factory):
    at = now() - timedelta(minutes=1)
    with factory.begin() as db:
        market = Market(id=2, region='us', ruleset_id=2, house_id=114, source_kind='auctions',
            label='US — Normal — Horde', unified_coverage=True, enabled=True, verified=True, interval_seconds=300, next_check=at)
        db.add(market)
        db.flush()
        for kind in ('auctions', 'commodities'):
            proof = {'identity': {'region': 'us', 'ruleset_id': 2, 'house_id': 114, 'source_kind': kind,
                'namespace': 'dynamic-forever-us', 'scope': 'ruleset_house'}, 'evidence_sha256': 'a'*64}
            db.add(MarketFeed(market_id=2, source_kind=kind, enabled=True, verification=canonical(proof)))
    return at


class Client:
    def __init__(self, commodities=None, auctions=None, statuses=None):
        self.commodities = commodities if commodities is not None else [
            row(4306, 10, quantity=20, price=123), row(14342, 11, quantity=3, price=4567), row(6657, 12, quantity=4, price=890)]
        self.auctions = auctions if auctions is not None else [row(25, 1, quantity=2, price=999, kind='auctions')]
        self.statuses = statuses or {}
        self.calls = []

    def fetch(self, market):
        kind = market.source_kind
        self.calls.append((kind, market.house_id, market.ruleset_id, market.etag, market.last_modified))
        status = self.statuses.get(kind, 200)
        body = payload(kind, getattr(self, kind)) if status == 200 else b''
        return {'status': status, 'headers': {'Battlenet-Namespace': 'dynamic-forever-us',
            'Last-Modified': 'Tue, 17 Nov 2026 12:00:00 GMT', 'ETag': '"'+kind+'"'}}, body


def test_unified_prices_provenance_and_idempotent_snapshots(database):
    at = configure(database)
    client = Client()
    assert collect_once(database, client, at=at)
    assert [c[0] for c in client.calls] == ['auctions', 'commodities']
    assert all(c[1:3] == (114, 2) for c in client.calls)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Market)) == 1
        obs = db.scalar(select(Observation))
        assert len(json.loads(obs.source_manifest)) == 2
        assert db.scalar(select(func.count()).select_from(Listing)) == 4
        cloth = db.scalar(select(Listing).where(Listing.item_id == 4306))
        assert (cloth.unit_price, cloth.buyout, cloth.quantity, cloth.source_kind) == (123, None, 20, 'commodities')
        stat = db.scalar(select(SnapshotStatistic).where(SnapshotStatistic.item_id == 4306))
        assert (stat.recent_price, stat.supply, stat.listing_count) == (123, 20, 1)
        equipment = db.scalar(select(SnapshotStatistic).where(SnapshotStatistic.item_id == 25))
        assert equipment.recent_price == 500  # Existing half-up stack/unit behavior.
        assert coverage_start(db, 2, 4306, cloth.variant_key) == at
        snapshot = obs.snapshot_id
    # A process restart has no Python state; persisted validators and captures suffice.
    unchanged = Client(statuses={'auctions': 304, 'commodities': 304})
    assert collect_once(database, unchanged, at=at+timedelta(seconds=300))
    assert all(c[3] for c in unchanged.calls)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Snapshot)) == 1
        assert db.scalar(select(func.count()).select_from(Observation)) == 2
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 2
        assert db.scalar(select(Observation.payload_bytes).order_by(Observation.id.desc()).limit(1)) == 0
        assert db.scalar(select(Observation.snapshot_id).order_by(Observation.id.desc()).limit(1)) == snapshot


@pytest.mark.parametrize('failed', ['auctions', 'commodities'])
def test_partial_retains_success_without_false_empty_or_stale_observation(database, failed):
    at = configure(database)
    assert collect_once(database, Client(), at=at)
    original = Client(commodities=[row(4306, 20, quantity=100, price=200)],
                      auctions=[row(25, 2, price=2000, kind='auctions')], statuses={failed: 503})
    assert collect_once(database, original, at=at+timedelta(seconds=300))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 1
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 3
        assert db.scalar(select(CollectionRun.status).order_by(CollectionRun.id.desc()).limit(1)) == 'partial'
        assert db.get(Market, 2).last_error
        assert db.get(MarketFeed, (2, failed)).failures == 1
    recovered = Client(commodities=original.commodities, auctions=original.auctions)
    assert collect_once(database, recovered, at=at+timedelta(seconds=600))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 2
        assert db.get(Market, 2).last_error is None


def test_missing_304_capture_does_not_publish_empty(database):
    at = configure(database)
    assert collect_once(database, Client(statuses={'commodities': 304}), at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 1
        assert db.get(MarketFeed, (2, 'commodities')).etag is None


@pytest.mark.parametrize('overlap', ['listing', 'variant'])
def test_cross_feed_overlap_fails_closed_and_retains_captures(database, overlap):
    at = configure(database)
    commodities = [row(25 if overlap == 'variant' else 4306, 1 if overlap == 'listing' else 10)]
    assert collect_once(database, Client(commodities=commodities), at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 2
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
        assert db.scalar(select(func.count()).select_from(Listing)) == 0
        assert db.get(Market, 2).last_error


def test_wrong_response_house_is_rejected(database):
    at = configure(database)
    class WrongHouse(Client):
        def fetch(self, market):
            meta, body = super().fetch(market)
            if market.source_kind == 'auctions':
                value = json.loads(body)
                value['id'] = 113
                body = json.dumps(value).encode()
            return meta, body
    assert collect_once(database, WrongHouse(), at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 1


def test_genuine_empty_commodities_after_success_is_zero_supply(database):
    at = configure(database)
    assert collect_once(database, Client(), at=at)
    assert collect_once(database, Client(commodities=[]), at=at+timedelta(seconds=300))
    with database() as db:
        head = db.scalar(select(Observation).order_by(Observation.id.desc()).limit(1))
        assert db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id == head.snapshot_id)) == 1
        assert db.scalar(select(func.count()).select_from(ItemSourceCoverage)) == 3


def test_history_before_commodity_coverage_is_unobserved(database):
    at = configure(database)
    with database.begin() as db:
        ingest(db, 2, payload('auctions', [row(25, 1, kind='auctions')]),
               request_key='old-regular', retrieved_at=at-timedelta(days=3))
    assert collect_once(database, Client(), at=at)
    from market.pricing import values, daily_history
    from market.intraday_history import intraday
    with database() as db:
        key = db.scalar(select(Listing.variant_key).where(Listing.item_id == 4306))
        v = values(db, 2, 4306, key, at=at)
        assert len(v['history']) == 1 and v['history'][0]['supply'] == 20
        h = daily_history(db, 2, 4306, key, at=at)
        assert len(h['points']) == 1
        assert all(p['status'] == 'available' for p in intraday(db, 2, 4306, key, 48, at=at)['points'])


def test_catalogue_details_history_deals_and_incremental_sync(owner, database, monkeypatch):
    from market.models import ItemMetadata
    monkeypatch.setenv('SYNC_CURSOR_SECRET', 'coverage-fixture-secret-that-is-long-enough')
    at = configure(database)
    with database.begin() as db:
        for item, name in ((4306, 'Silk Cloth'), (14342, 'Mooncloth'), (6657, 'Savory Deviate Delight')):
            db.add(ItemMetadata(region='us', item_id=item, name=name, status='available',
                namespace='static-forever-us', quality='COMMON', synthetic=True))
    assert collect_once(database, Client(), at=at)
    for item, name in ((4306, 'Silk Cloth'), (14342, 'Mooncloth'), (6657, 'Savory Deviate Delight')):
        a = owner.get('/api/v1/markets/2/catalogue', params={'q': name}).json()
        b = owner.get('/api/v1/markets/2/catalogue', params={'q': str(item)}).json()
        assert [r['item_id'] for r in a['items']] == [item]
        assert a['items'] == b['items']
        key = a['items'][0]['sole_variant_key']
        detail = owner.get(f'/api/v1/markets/2/items/{item}/{key}').json()
        assert detail['market']['id'] == 2
        assert detail['listings'][0]['buyout'] is None
        assert detail['listings'][0]['source_kind'] == 'commodities'
        assert detail['valuation']['coverage_days'] == 1
    page = owner.get('/api/v1/markets/2/catalogue?page_size=2&sort=item_id').json()
    next_page = owner.get('/api/v1/markets/2/catalogue?page_size=2&sort=item_id&page=1').json()
    assert len(page['items']) == len(next_page['items']) == 2
    assert set(r['item_id'] for r in page['items']).isdisjoint(r['item_id'] for r in next_page['items'])
    # Missing metadata cannot suppress exact ID search.
    with database.begin() as db:
        db.delete(db.get(ItemMetadata, ('us', 4306)))
    assert owner.get('/api/v1/markets/2/catalogue?q=4306').json()['total_items'] == 1
    sync = owner.get('/api/v1/sync/markets/2').json()
    assert {r['item_id'] for r in sync['changes']} == {25, 4306, 14342, 6657}
    cloth = next(r for r in sync['changes'] if r['item_id'] == 4306)
    assert cloth['value']['recent_price'] == '123'
    assert cloth['value']['supply'] == 20
    assert cloth['value']['coverage_days'] == 1
    # A one-day fixture is insufficient for normal three-day deal eligibility.
    deals = owner.get('/api/v1/markets/2/deals?minimum_coverage=3').json()
    assert not deals['deals']


def test_canonical_derivation_uses_each_feed_price_contract(database):
    from market.bridge_api import prepare_snapshot, record_batch
    from market.canonical_pricing import ALGORITHM
    at = configure(database)
    assert collect_once(database, Client(), at=at)
    with database.begin() as db:
        snapshot = db.scalar(select(Snapshot))
        prepare_snapshot(db, snapshot, ALGORITHM, 'auctions')
        key = db.scalar(select(Listing.variant_key).where(Listing.item_id == 4306))
        records = record_batch(db, [(4306, key)], [snapshot.id], ALGORITHM)
        assert records[snapshot.id, 4306, key]['summary']['recent_copper'] == '123'


def test_archive_v1_stays_regular_only_and_v2_carries_coverage(client, database, monkeypatch):
    from pathlib import Path
    import jsonschema
    from market.models import User
    from market.security import issue
    monkeypatch.setenv('SYNC_CURSOR_SECRET', 'coverage-archive-secret-that-is-long-enough')
    at = configure(database)
    with database.begin() as db:
        token, _, _ = issue(db, db.get(User, 1), 'device')
        ingest(db, 2, payload('auctions', [row(25, 1, kind='auctions')]), request_key='archive-old-regular',
               retrieved_at=at-timedelta(days=3), synthetic=True)
    client.headers['Authorization'] = 'Bearer ' + token
    assert collect_once(database, Client(), at=at)
    all_rows = {}
    envelopes = {}
    for protocol in (1, 2):
        schema = json.loads((Path(__file__).resolve().parents[2]/f'contracts/archive/v{protocol}/archive.schema.json').read_bytes())
        validate = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate
        for _ in range(5):
            response = client.get('/api/v1/archive/markets/2/checkpoint', params={'protocol': protocol})
            if response.status_code != 202: break
        assert response.status_code == 200, response.text
        envelope = response.json()
        validate(envelope)
        envelopes[protocol] = envelope
        cursor = envelope['cursor']
        rows = []
        while cursor:
            response = client.get('/api/v1/archive/markets/2/pages', params={
                'checkpoint': envelope['header']['checkpoint_id'], 'cursor': cursor, 'limit': 2})
            assert response.status_code == 200, response.text
            page = response.json()
            validate(page)
            rows.extend(page['entries'])
            cursor = page['next_cursor']
        all_rows[protocol] = rows
    old_schema = json.loads((Path(__file__).resolve().parents[2]/'contracts/archive/v1/archive.schema.json').read_bytes())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(old_schema).validate(envelopes[2])
    ordinary = [r for r in all_rows[1] if r['kind'] == 'variant']
    assert {r['item_id'] for r in ordinary} == {25}
    assert all('coverage_started_at' not in r['value'] for r in ordinary)
    unified = [r for r in all_rows[2] if r['kind'] == 'variant']
    assert {r['item_id'] for r in unified} == {25, 4306, 14342, 6657}
    assert all(r['value']['source_kind'] == 'commodities' and r['value']['coverage_started_at']
               for r in unified if r['item_id'] != 25)
    assert client.get('/api/v1/archive/markets/2/checkpoint', params={
        'protocol': 2, 'base': envelopes[1]['header']['checkpoint_id']}).status_code == 409


def test_retry_after_survives_restart_and_does_not_refetch_deferred_feed(database):
    at = configure(database)
    class Limited(Client):
        def fetch(self, market):
            meta, body = super().fetch(market)
            if market.source_kind == 'commodities':
                meta['status'] = 429
                meta['headers']['Retry-After'] = '900'
                body = b''
            return meta, body
    assert collect_once(database, Limited(), at=at)
    restarted = Client()
    assert collect_once(database, restarted, at=at+timedelta(seconds=300))
    assert [c[0] for c in restarted.calls] == ['auctions']
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
        assert db.get(MarketFeed, (2, 'commodities')).retry_after
        assert db.scalar(select(FeedCheck.status).where(FeedCheck.source_kind=='commodities')
            .order_by(FeedCheck.id.desc()).limit(1)) == 'deferred'
    assert collect_once(database, Client(), at=at+timedelta(seconds=900))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 1


def test_compacted_identical_snapshot_is_reconstructed_without_new_snapshot_identity(database):
    from sqlalchemy import delete
    at = configure(database)
    assert collect_once(database, Client(), at=at)
    with database.begin() as db:
        snapshot = db.scalar(select(Snapshot))
        sid = snapshot.id
        db.execute(delete(Listing).where(Listing.snapshot_id==sid))
        snapshot.raw_retained=False
    assert collect_once(database, Client(statuses={'auctions':304,'commodities':304}), at=at+timedelta(seconds=300))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Snapshot)) == 1
        assert db.get(Snapshot, sid).raw_retained
        assert db.scalar(select(func.count()).select_from(Listing)) == 4
        assert db.scalar(select(func.count()).select_from(Observation)) == 2


def test_global_lock_protects_unified_collection_before_network_io(database):
    from sqlalchemy import text
    with database() as db:
        if db.bind.dialect.name != 'postgresql': pytest.skip('PostgreSQL advisory-lock behavior')
    at = configure(database)
    client = Client()
    with database.begin() as holder:
        holder.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        assert collect_once(database, client, at=at) is False
        assert not client.calls
    assert collect_once(database, client, at=at)


def test_wrong_commodity_self_link_is_not_silently_substituted(database):
    at = configure(database)
    class OtherHouse(Client):
        def fetch(self, market):
            meta, body = super().fetch(market)
            if market.source_kind=='commodities': body=body.replace(b'/114/', b'/113/')
            return meta, body
    assert collect_once(database, OtherHouse(), at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
        assert db.scalar(select(func.count()).select_from(FeedCapture)) == 1
        assert db.get(MarketFeed,(2,'commodities')).failures == 1


def test_commodity_deals_require_three_actual_priced_days_even_with_low_requested_coverage(owner,database):
    at=configure(database)
    start=at-timedelta(days=2)
    with database.begin() as db: db.get(Market,2).next_check=start
    client=Client(commodities=[row(4306,10,quantity=20,price=100),row(4306,11,quantity=20,price=400)])
    assert collect_once(database,client,at=start)
    path='/api/v1/markets/2/deals?minimum_coverage=1&minimum_discount=1'
    assert owner.get(path).json()['deals']==[]
    assert collect_once(database,client,at=start+timedelta(days=1))
    assert owner.get(path).json()['deals']==[]
    assert collect_once(database,client,at=at)
    response=owner.get(path)
    assert response.status_code==200,response.text
    deals=response.json()['deals']
    assert len(deals)==1 and deals[0]['item_id']==4306
    assert deals[0]['quantity']==20 and deals[0]['total_buyout']=='2000'


@pytest.mark.parametrize('malformed',[[],None,{'auctions':[],'_links':None},{'auctions':[],'_links':{'self':None}}])
def test_malformed_commodity_envelope_preserves_successful_peer_capture(database,malformed):
    at=configure(database)
    class Malformed(Client):
        def fetch(self,market):
            meta,body=super().fetch(market)
            if market.source_kind=='commodities': body=json.dumps(malformed).encode()
            return meta,body
    assert collect_once(database,Malformed(),at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(FeedCapture))==1
        assert db.scalar(select(func.count()).select_from(Observation))==0
        assert db.get(MarketFeed,(2,'commodities')).failures==1
        assert db.get(Market,2).last_error


def test_historical_source_transition_requires_review_without_hiding_real_history(database):
    at=configure(database)
    with database.begin() as db:
        ingest(db,2,payload('auctions',[row(4306,100,quantity=20,price=2460,kind='auctions')]),
               request_key='synthetic-previous-source',retrieved_at=at-timedelta(days=1),synthetic=True)
    assert collect_once(database,Client(),at=at)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert db.scalar(select(func.count()).select_from(ItemSourceCoverage))==0
        assert db.scalar(select(func.count()).select_from(FeedCapture))==2
        assert 'historical source transition' in db.get(Market,2).last_error
        previous=db.scalar(select(SnapshotStatistic).where(SnapshotStatistic.item_id==4306))
        assert previous.recent_price==123 and previous.supply==20


def test_clearing_unified_flag_cannot_publish_regular_only_false_zero(owner,database):
    at=configure(database)
    assert collect_once(database,Client(),at=at)
    with database.begin() as db: db.get(Market,2).unified_coverage=False
    client=Client()
    assert collect_once(database,client,at=at+timedelta(seconds=300))
    assert not client.calls
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert 'compatible collector' in db.get(Market,2).last_error
    view=owner.get('/api/v1/markets').json()['markets'][0]
    assert view['coverage_status']=='partial' and view['freshness']=='stale'
