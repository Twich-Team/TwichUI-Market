from base64 import b64encode
from datetime import timedelta
from hashlib import sha1
import json

import pytest
from sqlalchemy import select

from market.crafting_writs import CACHE_KEY, queue_catalogue_refresh, read_catalogue, refresh_catalogue, validate_catalogue
from market.db import now
from market.metadata_recovery import enqueue_crafting_writ_refresh, schedule_crafting_writ_items, tick
from market.models import CraftingWritReward, Market, MetadataJob, MetadataProvider, MetadataResource, MetadataSource, MetadataTask
from market.writ_catalogue_source import ATT_API, ATT_PATH, FACTION_URL, fetch_writ_export
from test_foreverdb import setup_provider


def export_fixture():
    rows = (
        (2001, 111, 'Journeyman', 'First Delivery', 301, 1, ''),
        (2999, 112, 'Expert', 'Bulk Delivery', 302, 200, 'Horde'),
        (2074, 113, 'Artisan', 'Last Delivery', 303, 1, 'Alliance'),
    )
    quests = ['\t' * 5 + 'prof(ALCHEMY, {']
    envelopes = []
    index = []
    for item, quest, tier, name, delivery, quantity, side in rows:
        quests += [
            '\t' * 6 + f"q({quest}, {{ -- Craftsman's Writ: {name} [{tier}]",
            '\t' * 7 + f'qs = {item},',
            '\t' * 7 + f'cost = {{ {{ "i", {delivery}, {quantity} }} }}, -- {name}',
            '\t' * 7 + 'isDaily = true,',
            '\t' * 6 + '}),',
        ]
        envelopes += [
            '\t' * 4 + f"i(41, {{ -- Sealed {tier}'s Writ",
            '\t' * 5 + f'i({item}), -- validated item',
            '\t' * 4 + '}),',
        ]
        image = f'<img alt="{side}">' if side else ''
        index.append(f'<a href="/quest/{quest}/craftsmans-writ-test">{name}</a><em class="new">New</em></span>'
                     f'<span class="qs-side">{image}</span>')
    raw = '\n'.join([*quests, *envelopes]).encode()
    package = {
        'path': ATT_PATH, 'encoding': 'base64', 'size': len(raw),
        'sha': sha1(f'blob {len(raw)}\0'.encode() + raw, usedforsecurity=False).hexdigest(),
        'content': b64encode(raw).decode(),
    }
    return package, '\n'.join(index).encode()


def catalogue_fetcher(previous=None):
    package, index = export_fixture()

    def transport(url, **_):
        assert url in (ATT_API, FACTION_URL)
        return {'status': 200}, json.dumps(package).encode() if url == ATT_API else index

    return fetch_writ_export(previous, fetcher=transport)


def test_imports_exact_relationships_without_id_arithmetic():
    catalogue = validate_catalogue(catalogue_fetcher())
    writs = {writ['item_id']: writ for writ in catalogue['writs']}
    assert [writs[item]['quest_id'] for item in (2001, 2999, 2074)] == [111, 112, 113]
    assert writs[2999]['objectives'] == [{'item_id': 302, 'name': 'Bulk Delivery', 'quantity': 200, 'buy_allowed': True}]
    assert writs[2999]['allowed_sides'] == ['horde']
    assert writs[2074]['allowed_sides'] == ['alliance']
    assert writs[2001]['allowed_sides'] == []
    assert all('Daily quest' in writ['restrictions'] and writ['provider_reward'] is None for writ in writs.values())


def test_rejects_partial_export_and_incorrect_faction_index():
    package, index = export_fixture()
    bad_package = {**package, 'size': 1}

    def transport(url, **_):
        return {'status': 200}, json.dumps(bad_package).encode() if url == ATT_API else index

    with pytest.raises(ValueError, match='Incomplete writ export'):
        fetch_writ_export(fetcher=transport)
    bad_package = package
    index = b'no faction records'
    with pytest.raises(ValueError, match='Missing writ faction index'):
        fetch_writ_export(fetcher=transport)


def test_validates_quantity_duplicate_and_recipe_cycle():
    catalogue = catalogue_fetcher()
    catalogue['writs'][0]['objectives'][0]['quantity'] = 0
    with pytest.raises(ValueError, match='Invalid ID or quantity'):
        validate_catalogue(catalogue)
    catalogue = catalogue_fetcher()
    catalogue['writs'].append(catalogue['writs'][0])
    with pytest.raises(ValueError, match='Duplicate or invalid writ'):
        validate_catalogue(catalogue)
    catalogue = catalogue_fetcher()
    catalogue['writs'][0]['recipes'] = [{'recipe_id': 31, 'item_id': 301, 'output_quantity': 1,
                                         'ingredients': [{'item_id': 301, 'quantity': 1}]}]
    with pytest.raises(ValueError, match='Cyclic recipe graph'):
        validate_catalogue(catalogue)


def test_reads_last_good_data_through_retry_and_respects_upstream_delay(database):
    at = now()
    assert not read_catalogue(None)[1]
    assert refresh_catalogue(database, at=at, fetcher=catalogue_fetcher)
    with database.begin() as db:
        queue_catalogue_refresh(db, 1, at=at + timedelta(minutes=16))
    calls = []

    def fail(previous):
        assert len(previous['writs']) == 3

        def transport(url, **_):
            calls.append(url)
            return {'status': 429, 'headers': {'Retry-After': '1800'}}, b''

        return fetch_writ_export(previous, fetcher=transport)

    later = at + timedelta(minutes=16)
    assert not refresh_catalogue(database, at=later, fetcher=fail)
    assert not refresh_catalogue(database, at=later + timedelta(minutes=29), fetcher=fail)
    with database() as db:
        row, visible = read_catalogue(db)
        assert row.status == 'error'
        assert len(visible['writs']) == 3
        assert json.loads(row.source_json)['confirmed_at'] == at.isoformat()
        assert row.retry_at == later + timedelta(minutes=30)
    assert calls == [ATT_API]


def test_preserves_existing_recipes_only_for_identical_objectives(database):
    at = now()
    legacy = catalogue_fetcher()
    legacy['writs'][0]['recipes'] = [{'recipe_id': 31, 'item_id': 301, 'output_quantity': 1, 'skill': 100,
                                      'craft_allowed': True, 'ingredients': [{'item_id': 999, 'quantity': 1}]}]
    legacy['writs'][-1]['objectives'][0]['quantity'] = 3
    legacy['writs'][-1]['recipes'] = [{'recipe_id': 32, 'item_id': 302, 'output_quantity': 1, 'skill': 40,
                                       'craft_allowed': True, 'ingredients': [{'item_id': 998, 'quantity': 1}]}]
    with database.begin() as db:
        db.add(MetadataResource(region=CACHE_KEY[0], resource=CACHE_KEY[1], offset=CACHE_KEY[2],
                                status='curated_seed', fields_json=json.dumps(legacy)))
        db.add(CraftingWritReward(scope='tier', key='journeyman', reputation=91, revision=1,
                                  updated_at=at, updated_by=1))
    assert refresh_catalogue(database, at=at, fetcher=catalogue_fetcher)
    with database() as db:
        row, data = read_catalogue(db)
        assert row.status == 'available'
        assert len(json.loads(row.source_json)['sha256']) == 64
        assert data['writs'][0]['recipes'] == legacy['writs'][0]['recipes']
        assert data['writs'][-1]['recipes'] == []
        assert db.get(CraftingWritReward, ('tier', 'journeyman')).reputation == 91


@pytest.fixture
def provider(database, monkeypatch, tmp_path):
    keyring = tmp_path / 'keyring.json'
    keyring.write_text(json.dumps({'active': 'test', 'keys': {'test': b64encode(b'x' * 32).decode()}}))
    keyring.chmod(0o600)
    monkeypatch.setenv('METADATA_KEYRING_FILE', str(keyring))
    at = now()
    with database.begin() as db:
        market_id = setup_provider(db)
        db.get(Market, market_id).verified = True
    return at, market_id


def test_item_backfill_requeues_after_import_and_obeys_cooldown(database, provider):
    at, market_id = provider
    with database.begin() as db:
        db.get(MetadataProvider, 'foreverdb').cooldown_until = at + timedelta(minutes=10)
        db.add(MetadataJob(market_id=market_id, mode='single', state='completed',
                           dedupe_key='crafting-writ-items', providers_json='["foreverdb"]', created_at=at))
    later = at + timedelta(seconds=1)
    assert refresh_catalogue(database, at=later, fetcher=catalogue_fetcher)
    with database.begin() as db:
        schedule_crafting_writ_items(db, later)
        schedule_crafting_writ_items(db, later)
        active, created = enqueue_crafting_writ_refresh(db, at=later)
        assert not created and active.total == 6 and active.request_budget == 12
        active_id = active.id

    def forbidden(*args, **kwargs):
        raise AssertionError('cooldown bypassed')

    tick(database, at=later, automatic=False, fetcher=forbidden)
    with database() as db:
        assert db.get(MetadataJob, active_id).requests_used == 0
        assert db.scalar(select(MetadataTask).where(MetadataTask.job_id == active_id)).attempts == 0
        assert len(read_catalogue(db)[1]['writs']) == 3


def test_item_backfill_success_is_independent_of_rewards(database, provider):
    at, _ = provider
    assert refresh_catalogue(database, at=at, fetcher=catalogue_fetcher)
    with database.begin() as db:
        db.add(CraftingWritReward(scope='tier', key='journeyman', reputation=91, revision=1, updated_at=at, updated_by=1))
        enqueue_crafting_writ_refresh(db, at=at)

    calls = []

    def fetcher(provider, item_id, **kwargs):
        assert provider == 'foreverdb'
        calls.append(item_id)
        body = {'data': {'id': item_id, 'name': 'Fixture'},
                'meta': {'edition': 'forever', 'build': '1.60.1.71091'}}
        return {'status': 200, 'headers': {}}, json.dumps(body).encode()

    tick(database, at=at, automatic=False, fetcher=fetcher)
    with database() as db:
        assert db.get(CraftingWritReward, ('tier', 'journeyman')).reputation == 91
        assert len(read_catalogue(db)[1]['writs']) == 3
        item_id, = calls
        assert db.get(MetadataSource, ('us', item_id, 'en_US', 'foreverdb')).status == 'available'
