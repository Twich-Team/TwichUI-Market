from fractions import Fraction

import pytest
from sqlalchemy import select

from market import writ_api
from market.models import CraftingWritReward, Market, SecurityEvent, User
from market.security import hasher
from market.waylaid_pricing import ItemQuote, QuoteBook

MEMBER = '/api/v1/crafting-writs'
ADMIN = '/api/v1/admin/crafting-writs'
TIER = ADMIN + '/rewards/tier/journeyman'
OVERRIDE = ADMIN + '/rewards/writ/264018'


@pytest.fixture
def writ_market(database, monkeypatch):
    with database.begin() as db:
        market = Market(region='us', ruleset_id=2, house_id=114, source_kind='auctions',
                        label='US Normal Horde', enabled=True, verified=True)
        db.add(market)
        db.add(User(username='member', role='member', password_hash=hasher.hash('market member password')))
        db.flush()
        market_id = market.id

    datum = {
        'item_id': 264018, 'name': "Craftsman's Writ: Elixir of Defense", 'quest_id': 94218,
        'tier': 'journeyman', 'profession': 'alchemy', 'provider_reward': 60, 'hand_in_allowed': True,
        'objectives': [{'item_id': 8951, 'name': 'Elixir of Defense', 'quantity': 1, 'buy_allowed': True}],
        'recipes': [{'recipe_id': 11450, 'item_id': 8951, 'skill': 195, 'output_quantity': 1,
                     'craft_allowed': True, 'ingredients': [{'item_id': 3355, 'quantity': 1}]}],
        'restrictions': ['Writ required at hand-in', 'Repeatability unknown'],
    }
    other = {
        'item_id': 264027, 'name': "Craftsman's Writ: Big Bronze Knife", 'quest_id': 94227,
        'tier': 'journeyman', 'profession': 'blacksmithing', 'provider_reward': None, 'hand_in_allowed': True,
        'objectives': [{'item_id': 3848, 'name': 'Big Bronze Knife', 'quantity': 1, 'buy_allowed': True}],
        'recipes': [],
    }
    monkeypatch.setattr(writ_api, 'read_catalogue', lambda db: (None, {'writs': [datum, other]}))

    def quotes(_db, _market, names, basis):
        units = {264018: 800, 8951: 400, 3355: 200, 264027: 500, 3848: 125}
        book = QuoteBook(basis, {}, freshness='current', verified=True)
        for item_id in names:
            unit = units[item_id]
            quote = ItemQuote(minimum=unit, unit=unit, status='available', source_kind='commodities',
                              depth_known=True, priced_quantity=10)
            quote.observe(10, 1, Fraction(unit))
            book.items[item_id] = quote
        return book

    monkeypatch.setattr(writ_api, 'load_quotes', quotes)
    return market_id


def test_browser_access_and_filters(client, writ_market):
    assert client.get(MEMBER, params={'market_id': writ_market}).status_code == 401
    assert client.get(ADMIN).status_code == 401
    login = client.post('/api/v1/auth/login', json={'username': 'member', 'password': 'market member password'})
    client.headers['x-csrf-token'] = login.json()['csrf_token']
    assert client.get(ADMIN).status_code == 403
    assert client.put(TIER, json={'reputation': 70, 'revision': 0}).status_code == 403
    assert client.post(ADMIN + '/refresh').status_code == 403
    params = {'market_id': writ_market, 'profession': 'alchemy', 'owned': True, 'method': 'craft',
              'confirmed_recipes': 11450, 'max_skill': 195}
    view = client.get(MEMBER, params=params)
    assert view.status_code == 200 and view.headers['cache-control'] == 'no-store'
    assert {row['slug'] for row in view.json()['professions']} == {'alchemy', 'blacksmithing'}
    row, = view.json()['rows']
    assert row['item']['name'] == "Craftsman's Writ: Elixir of Defense"
    assert row['selected_method'] == 'craft'
    assert row['purchase_cost_copper'] == '0'
    assert row['total_cost_copper'] == '200'
    assert row['cost_per_reputation'] == {'numerator_copper': '10', 'denominator': 3}
    assert row['craft']['materials'][0]['item']['item_id'] == 3355
    assert row['objectives'][0]['item']['item_id'] == 8951
    limited = client.get(MEMBER, params={**params, 'max_skill': 194}).json()['rows'][0]
    assert limited['selected_method'] is None and limited['cost_per_reputation'] is None
    assert 'recipe_skill_above_maximum' in limited['reasons']
    assert client.get(MEMBER, params={**params, 'confirmed_recipes': [11450] * 41}).status_code == 422


def test_reward_precedence_persists_and_recalculates(owner, database, writ_market, monkeypatch):
    def results():
        return owner.get(MEMBER, params={'market_id': writ_market}).json()['rows']

    first, other = results()
    assert (first['reputation'], first['reward_source']) == (60, 'provider')
    assert other['total_cost_copper'] == '625' and other['cost_per_reputation'] is None
    assert not other['eligible']
    assert owner.put(TIER, json={'reputation': 75, 'revision': 0}).json()['revision'] == 1
    assert owner.put(TIER, json={'reputation': 85, 'revision': 0}).status_code == 409
    assert owner.put(OVERRIDE, json={'reputation': 100, 'revision': 0}).json()['revision'] == 1
    first, other = results()
    assert (first['reputation'], first['reward_source'], first['provider_reputation']) == (100, 'writ_override', 60)
    assert first['cost_per_reputation'] == {'numerator_copper': '12', 'denominator': 1}
    assert (other['reputation'], other['reward_source']) == (75, 'tier_setting')
    admin_row = owner.get(ADMIN).json()['writs'][0]
    assert (admin_row['reputation'], admin_row['provider_reputation'], admin_row['effective_reputation']) == (100, 60, 100)
    monkeypatch.setattr(writ_api, 'enqueue_crafting_writ_refresh', lambda *args, **kwargs: None)
    assert owner.post(ADMIN + '/refresh').status_code == 202
    with database() as db:
        assert db.get(CraftingWritReward, ('writ', '264018')).reputation == 100
        assert db.get(CraftingWritReward, ('tier', 'journeyman')).reputation == 75
        assert len(list(db.scalars(select(SecurityEvent).where(
            SecurityEvent.action == 'crafting_writs.reward_changed')))) == 2
    assert owner.put(OVERRIDE, json={'reputation': None, 'revision': 1}).json()['revision'] == 2
    assert results()[0]['reputation'] == 75
    assert owner.put(TIER, json={'reputation': None, 'revision': 1}).json()['revision'] == 2
    assert results()[0]['reputation'] == 60
    assert results()[1]['reputation'] is None


@pytest.mark.parametrize('value', [0, -2, 1.25, 2.0, '3', True, 2**31])
def test_reward_input_validation_and_csrf(owner, writ_market, value):
    assert owner.put(TIER, json={'reputation': value, 'revision': 0}).status_code == 422
    assert owner.put(ADMIN + '/rewards/tier/unverified', json={'reputation': 20, 'revision': 0}).status_code == 404
    owner.headers.pop('x-csrf-token')
    assert owner.put(TIER, json={'reputation': 20, 'revision': 0}).status_code == 403
    assert owner.post(ADMIN + '/refresh').status_code == 403


def test_simultaneous_reward_edits_commit_only_once(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from market.writ_rewards import RewardConflict, save_reward

    with database() as db:
        if db.get_bind().dialect.name != 'postgresql':
            pytest.skip('Concurrent write test requires distinct PostgreSQL sessions')
    ready = Barrier(2, timeout=5)

    def edit(value):
        with database() as db:
            actor = db.scalar(select(User).where(User.username == 'owner'))
            ready.wait()
            try:
                save_reward(db, actor, 'tier', 'journeyman', value, 0)
            except RewardConflict:
                return None
            return value

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(edit, (75, 85))
    assert (first is None) != (second is None)
    with database() as db:
        setting = db.get(CraftingWritReward, ('tier', 'journeyman'))
        assert setting.revision == 1 and setting.reputation == (first or second)
        assert len(list(db.scalars(select(SecurityEvent).where(
            SecurityEvent.action == 'crafting_writs.reward_changed')))) == 1
