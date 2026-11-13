import json
from datetime import timedelta
from types import SimpleNamespace
import pytest
from sqlalchemy import func, select
from market.db import now
from market.models import CollectionRun, Listing, Market, Observation, Snapshot
from market.security import aware
from market.worker import BlizzardClient, UpstreamFailure, collect_once, retry_seconds

BODY = b'{"auctions":[{"id":1,"item":{"id":12363},"quantity":5,"buyout":1000}]}'


class Client:
    def __init__(self, status=200, body=BODY, headers=None):
        self.status, self.body, self.headers = status, body, headers or {}
        self.calls = 0
    def fetch(self, market):
        self.calls += 1
        return {'status':self.status,'headers':self.headers}, self.body


@pytest.fixture
def scheduled(database):
    with database.begin() as db:
        market = Market(region='eu', ruleset_id=2, house_id=113, source_kind='auctions',
                        label='Test only',enabled=True,verified=True,next_check=now()-timedelta(seconds=1))
        db.add(market)
        db.flush()
        return market.id


def test_scheduled_collection_conditional_and_dedup(database, scheduled):
    at = now()
    client = Client(headers={'Last-Modified':'Thu, 12 Nov 2026 12:00:00 GMT','ETag':'"a"'})
    assert collect_once(database,client,at=at)
    assert not collect_once(database,client,at=at+timedelta(seconds=1))
    assert client.calls == 1
    assert collect_once(database,Client(304,b''),at=at+timedelta(minutes=31))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Snapshot)) == 1
        assert db.scalar(select(func.count()).select_from(Observation)) == 2
        assert list(db.scalars(select(CollectionRun.status).order_by(CollectionRun.id))) == ['collected','unchanged']
        row = db.get(Market,scheduled)
        assert row.etag == '"a"'
        assert row.last_modified == 'Thu, 12 Nov 2026 12:00:00 GMT'
        assert row.failures == 0


def test_unverified_disabled_and_future_are_never_requested(database, scheduled):
    with database.begin() as db:
        db.get(Market,scheduled).verified = False
    client = Client()
    assert not collect_once(database,client)
    with database.begin() as db:
        row = db.get(Market,scheduled)
        row.verified, row.enabled = True, False
    assert not collect_once(database,client)
    assert client.calls == 0


def test_rate_limit_backoff_failure_and_recovery(database, scheduled, monkeypatch):
    at = now()
    assert collect_once(database,Client(429,b'',{'Retry-After':'7200'}),at=at)
    with database() as db:
        market = db.get(Market,scheduled)
        assert market.failures == 1
        assert aware(market.next_check) == at+timedelta(hours=2)
        assert market.last_success is None
        assert db.scalar(select(func.count()).select_from(Observation)) == 0
    assert not collect_once(database,Client(),at=at+timedelta(hours=1))
    monkeypatch.setattr('market.ingest.now',lambda:at+timedelta(hours=2))
    assert collect_once(database,Client(),at=at+timedelta(hours=2))
    with database() as db:
        assert db.get(Market,scheduled).last_error is None
        assert db.get(Market,scheduled).failures == 0


def test_malformed_payload_preserves_last_good_snapshot(database, scheduled):
    at = now()
    collect_once(database,Client(),at=at)
    collect_once(database,Client(200,b'{"auctions":[{}]}'),at=at+timedelta(minutes=31))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Observation)) == 1
        assert db.scalar(select(func.count()).select_from(Listing)) == 1
        assert db.get(Market,scheduled).failures == 1
        assert db.scalar(select(CollectionRun).order_by(CollectionRun.id.desc()).limit(1)).status == 'failed'


def test_304_without_snapshot_clears_conditionals(database, scheduled):
    with database.begin() as db:
        db.get(Market,scheduled).etag = 'old'
    collect_once(database,Client(304,b''))
    with database() as db:
        assert db.get(Market,scheduled).etag is None
        assert db.get(Market,scheduled).failures == 1


def test_database_budget_stops_fetch(database, scheduled):
    with database() as db:
        if db.bind.dialect.name != 'postgresql':
            pytest.skip('PostgreSQL disk budget')
    client = Client()
    collect_once(database,client,max_database_bytes=1)
    assert client.calls == 0
    with database() as db:
        assert 'disk budget' in db.get(Market,scheduled).last_error


def test_oauth_cache_conditional_and_invalidated_token(monkeypatch):
    monkeypatch.setenv('BLIZZARD_CLIENT_ID','test-id')
    monkeypatch.setenv('BLIZZARD_CLIENT_SECRET','test-secret')
    calls = []
    def transport(url,**kwargs):
        calls.append((url,kwargs))
        if url.endswith('/token'):
            return {'status':200,'headers':{}}, json.dumps({'access_token':'secret-token','expires_in':3600}).encode()
        return {'status':401,'headers':{}}, b''
    client = BlizzardClient(transport)
    assert client.authenticate() == client.authenticate() == 'secret-token'
    assert len(calls) == 1
    market = SimpleNamespace(region='eu',ruleset_id=2,house_id=113,source_kind='commodities',etag='x',last_modified='y')
    client.fetch(market)
    assert '/113/commodities?' in calls[-1][0]
    assert calls[-1][1]['conditional'] == {'If-None-Match':'x','If-Modified-Since':'y'}
    assert client.token is None


def test_credentials_and_retry_safety(monkeypatch):
    monkeypatch.delenv('BLIZZARD_CLIENT_ID',raising=False)
    monkeypatch.delenv('BLIZZARD_CLIENT_SECRET',raising=False)
    with pytest.raises(UpstreamFailure,match='credentials missing'):
        BlizzardClient().authenticate()
    at = now()
    assert retry_seconds('9999999',at) == 86400
    assert retry_seconds('invalid',at) == 0
    assert retry_seconds('-5',at) == 0


def test_global_collector_lock_prevents_duplicate_fetch(database, scheduled):
    from sqlalchemy import text
    with database.begin() as db:
        if db.bind.dialect.name != 'postgresql':
            pytest.skip('PostgreSQL advisory lock')
        db.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        client = Client()
        assert not collect_once(database,client)
        assert client.calls == 0
