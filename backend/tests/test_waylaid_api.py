from datetime import timedelta

import pytest
from sqlalchemy import select

from market.db import now
from market.models import Market, MetadataJob, MetadataProvider, User, WaylaidReward
from market.security import hasher
from market.waylaid_rewards import DEFAULT_REWARDS

MEMBER_ROUTE = '/api/v1/waylaid-crates'
ADMIN_ROUTE = '/api/v1/admin/waylaid-crates'


@pytest.fixture
def waylaid_market(database):
    with database.begin() as db:
        market = Market(region='us', ruleset_id=2, house_id=114, source_kind='auctions',
                        label='US Normal Horde', verified=True)
        db.add(market)
        db.add(User(username='member', role='member', password_hash=hasher.hash('market member password')))
        db.add_all(WaylaidReward(tier=tier, favor=favor, revision=1) for tier, favor in DEFAULT_REWARDS.items())
        db.flush()
        return market.id


def test_signed_out_member_and_admin_access(client, waylaid_market):
    member_url = f'{MEMBER_ROUTE}?market_id={waylaid_market}'
    assert client.get(member_url).status_code == 401
    assert client.get(ADMIN_ROUTE).status_code == 401
    login = client.post('/api/v1/auth/login', json={'username': 'member', 'password': 'market member password'})
    assert login.status_code == 200
    client.headers['x-csrf-token'] = login.json()['csrf_token']
    visible = client.get(member_url)
    assert visible.status_code == 200
    assert visible.json()['rows'] == []
    assert visible.json()['catalogue']['refreshed_at'] is None
    assert client.get(ADMIN_ROUTE).status_code == 403
    assert client.put(ADMIN_ROUTE + '/rewards/apprentice', json={'favor': 6, 'revision': 1}).status_code == 403
    assert client.post(ADMIN_ROUTE + '/refresh').status_code == 403
    assert client.get(f'{MEMBER_ROUTE}?market_id=90001').status_code == 404


@pytest.mark.parametrize('favor', [0, -1, 1.25, 2.0, '3', True, 2**31])
def test_rejects_invalid_reward_inputs(owner, waylaid_market, favor):
    assert owner.put(ADMIN_ROUTE + '/rewards/apprentice', json={'favor': favor, 'revision': 1}).status_code == 422
    assert owner.get(ADMIN_ROUTE).json()['rewards'][0]['favor'] == 5


def test_admin_reward_edit_and_conflict(owner, waylaid_market):
    assert [row['favor'] for row in owner.get(ADMIN_ROUTE).json()['rewards']] == [5, 10, 15, None]
    target = ADMIN_ROUTE + '/rewards/apprentice'
    updated = owner.put(target, json={'favor': 21, 'revision': 1})
    assert updated.status_code == 200
    assert updated.json()['favor'] == 21
    assert updated.json()['revision'] == 2
    assert updated.json()['updated_by'] == 'owner'
    assert owner.put(target, json={'favor': 6, 'revision': 1}).status_code == 409
    assert owner.put(target, json={'favor': None, 'revision': 2}).json()['favor'] is None
    assert owner.put(ADMIN_ROUTE + '/rewards/nonexistent', json={'favor': 6, 'revision': 0}).status_code == 404
    owner.headers.pop('x-csrf-token')
    assert owner.put(target, json={'favor': 8, 'revision': 3}).status_code == 403


def test_admin_refresh_enqueues_once_and_never_reseeds_rewards(owner, database, waylaid_market):
    with database.begin() as db:
        db.add(MetadataProvider(provider='foreverdb', enabled=True, credential_status='connected',
                                expires_at=now() + timedelta(days=1)))
    reward_url = ADMIN_ROUTE + '/rewards/expert'
    assert owner.put(reward_url, json={'favor': 29, 'revision': 1}).status_code == 200
    for _ in range(2):
        queued = owner.post(ADMIN_ROUTE + '/refresh')
        assert queued.status_code == 202
        assert queued.json()['state'] == 'queued'
    with database() as db:
        jobs = list(db.scalars(select(MetadataJob)))
        assert len(jobs) == 1 and jobs[0].requests_used == 0
        assert db.get(WaylaidReward, 'expert').favor == 29


def test_cached_catalogue_and_quality_restrictions_during_outage(owner, database, waylaid_market):
    import json
    from pathlib import Path

    from market.merchants_favor import CACHE_KEY, parse_catalogue
    from market.models import MetadataResource

    at = now() - timedelta(days=3)
    fixture_path = Path(__file__).parent / 'fixtures' / 'foreverdb' / 'merchants-favor.json'
    data, origin = parse_catalogue(fixture_path.read_bytes(), at=at)
    with database.begin() as db:
        db.add(MetadataResource(region=CACHE_KEY[0], resource=CACHE_KEY[1], offset=CACHE_KEY[2],
                                status='upstream_error', fields_json=json.dumps(data),
                                source_json=json.dumps(origin), http_status=503, checked_at=now()))
    result = owner.get(MEMBER_ROUTE, params={'market_id': waylaid_market, 'owned': True}).json()
    assert result['catalogue']['stale']
    assert result['catalogue']['refreshed_at'] == at.isoformat()
    rows = {row['item']['item_id']:row for row in result['rows']}
    common = rows[248682]
    assert common['favor'] == 5 and common['purchase_cost_copper'] == '0'
    assert common['purchase_quote']['item'] == common['item']
    assert [entry['materials'][0]['item']['item_id'] for entry in common['bundles']] == [2447, 765, 2449, 785, 2450]
    uncommon = rows[248702]
    assert uncommon['favor'] is None and uncommon['cost_per_favor'] is None and not uncommon['eligible']
    assert uncommon['reward_unavailable_reason'] == 'unverified_reward_quality'
    assert rows[248699]['favor'] is None
