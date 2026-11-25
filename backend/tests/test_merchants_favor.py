"""Merchant's Favor endpoint contract, cache safety and shared quota tests."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from market.db import now
from market.merchants_favor import RESOURCE, parse_catalogue, read_catalogue
from market.metadata_providers import fetch
from market.metadata_recovery import enqueue_merchant_favor_refresh, schedule_merchant_favor, tick
from market.models import ItemMetadata, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask
from test_foreverdb import setup_provider, test_keyring


FIXTURE = Path(__file__).parent / 'fixtures' / 'foreverdb' / 'merchants-favor.json'


def test_catalogue_fetch_uses_exact_authenticated_conditional_endpoint():
    def transport(url, **kwargs):
        return url, kwargs

    url, kwargs = fetch('foreverdb', 1, credential='fixtures-only', etag='"catalogue"',
                        offset=0, resource=RESOURCE, transport=transport)
    assert url == 'https://foreverdb.net/api/v1/merchants-favor'
    assert kwargs['authorization'] == 'Bearer fixtures-only'
    assert kwargs['conditional'] == {'If-None-Match': '"catalogue"'}
    assert kwargs['max_bytes'] == 1048576
    with pytest.raises(ValueError):
        fetch('foreverdb', 1, credential='fixtures-only', offset=1, resource=RESOURCE, transport=transport)


def test_catalogue_refresh_is_deduped_and_uses_shared_cooldown(database):
    at = now()
    with database.begin() as db:
        setup_provider(db)
        provider = db.get(MetadataProvider, 'foreverdb')
        provider.cooldown_until = at + timedelta(minutes=10)
        scheduled, created = enqueue_merchant_favor_refresh(db, at=at)
        assert created
        manual, created = enqueue_merchant_favor_refresh(db, actor_id=1, at=at)
        assert not created and manual.id == scheduled.id
    def unexpected(*_args, **_kwargs):
        pytest.fail('Provider cooldown bypassed')
    tick(database, at=at, automatic=False, fetcher=unexpected)
    with database() as db:
        slot = db.scalar(select(MetadataTask).where(MetadataTask.resource == RESOURCE))
        assert slot.attempts == 0
        assert json.loads(slot.result_json)['status'] == 'quota_deferred'
        assert db.get(MetadataProvider, 'foreverdb').day_used == 0


def test_daily_schedule_can_be_disabled_without_blocking_admin_enqueue(database, monkeypatch):
    at = now()
    with database.begin() as db:
        setup_provider(db)
        monkeypatch.setenv('FOREVERDB_MERCHANTS_FAVOR_REFRESH_SECONDS', '0')
        schedule_merchant_favor(db, at)
        assert not db.scalar(select(MetadataJob.id))
        job, created = enqueue_merchant_favor_refresh(db, actor_id=1, at=at)
        assert created and job.state == 'queued'


def test_authenticated_response_subset_keeps_choices_exact_and_sealed_mapping_unknown():
    raw = FIXTURE.read_bytes()
    catalogue, origin = parse_catalogue(raw)
    assert origin['edition'] == 'forever' and origin['build'] == '1.60.1.71091'
    assert origin['payload_hash'] == hashlib.sha256(raw).hexdigest()
    assert origin['attribution']['url'] == 'https://foreverdb.net'
    assert catalogue['currency']['id'] == 3402
    assert catalogue['upstream_reward_note']
    crates = {crate['item_id']: crate for crate in catalogue['crates']}
    apprentice = crates[248682]
    assert apprentice['tier'] == 'apprentice' and apprentice['required_level'] == 10
    assert apprentice['sealed_item_id'] is None
    assert apprentice['reward_unavailable_reason'] is None
    assert apprentice['unavailable_reason'] is None
    assert [(bundle['bundle_id'], bundle['materials'][0]['quantity'])
            for bundle in apprentice['bundles']] == [(2447, 20), (765, 20), (2449, 10), (785, 10), (2450, 10)]
    assert all(len(bundle['materials']) == 1 for bundle in apprentice['bundles'])
    assert crates[248686]['tier'] == 'journeyman' and crates[248686]['required_level'] == 10
    assert crates[248699]['tier'] == 'artisan' and crates[248699]['required_level'] == 35
    uncommon = crates[248702]
    assert uncommon['quality'] == 'UNCOMMON'
    assert uncommon['reward_unavailable_reason'] == 'unverified_reward_quality'
    assert uncommon['unavailable_reason'] is None and uncommon['bundles']
    assert {row['item_id'] for row in catalogue['sealed_crates'] if row['name'] == 'Sealed Apprentice Crate'} == {
        248765, 248770, 248775,
    }


def test_unsupported_tier_or_missing_choices_are_explicit():
    mutation = json.loads(FIXTURE.read_bytes())
    mutation['data']['crates'][0]['name'] = 'Waylaid Crate: Other Herbs'
    mutation['data']['crates'][1]['bundles'] = []
    catalogue, _ = parse_catalogue(json.dumps(mutation).encode())
    unsupported, missing = catalogue['crates'][:2]
    assert unsupported['tier'] is None and unsupported['unavailable_reason'] == 'unsupported_tier'
    assert unsupported['bundles']
    assert missing['unavailable_reason'] == 'no_supported_bundles'


def test_future_tier_uses_matching_provider_tier_word_with_no_exact_relationship():
    mutation = json.loads(FIXTURE.read_bytes())
    mutation['data']['crates'][0]['name'] = 'Waylaid Crate: Master Herbs'
    mutation['data']['sealedCrates'][0]['name'] = 'Sealed Master Crate'
    mutation['data']['crates'][1]['name'] = 'Waylaid Crate: Master Journeyman Herbs'
    catalogue, _ = parse_catalogue(json.dumps(mutation).encode())
    new_tier, ambiguous = catalogue['crates'][:2]
    assert new_tier['tier'] == 'master' and new_tier['sealed_item_id'] is None
    assert new_tier['unavailable_reason'] is None and new_tier['reward_unavailable_reason'] is None
    assert ambiguous['tier'] is None and ambiguous['unavailable_reason'] == 'unsupported_tier'


@pytest.mark.parametrize('mutation', [
    'crate_count', 'sealed_count', 'build', 'duplicate_choice', 'duplicate_crate',
    'crate_as_material', 'sealed_as_material', 'false_quantity', 'wrong_item_url',
])
def test_malformed_responses_cannot_replace_last_catalogue(mutation):
    value = json.loads(FIXTURE.read_bytes())
    crate = value['data']['crates'][0]
    if mutation == 'crate_count':
        value['data']['counts']['crates'] += 1
    elif mutation == 'sealed_count':
        value['data']['counts']['sealedCrates'] = len(value['data']['sealedCrates']) + 1
    elif mutation == 'build':
        value['meta']['build'] = '12.1.0.0'
    elif mutation == 'duplicate_choice':
        crate['bundles'].append(crate['bundles'][0])
    elif mutation == 'duplicate_crate':
        value['data']['crates'][1] = crate
    elif mutation in ('crate_as_material', 'sealed_as_material'):
        forbidden = crate if mutation == 'crate_as_material' else value['data']['sealedCrates'][0]
        crate['bundles'][0] = {**forbidden, 'count': 1}
    elif mutation == 'false_quantity':
        crate['bundles'][0]['count'] = True
    else:
        crate['bundles'][0]['url'] = 'https://foreverdb.net/item/1'
    with pytest.raises(ValueError):
        parse_catalogue(json.dumps(value).encode())


def test_refresh_persists_good_catalogue_confirmations_and_bounded_exact_backfill(database, monkeypatch):
    at = now()
    monkeypatch.setenv('FOREVERDB_MERCHANTS_FAVOR_REFRESH_SECONDS', '43200')
    with database.begin() as db:
        market_id = setup_provider(db)
        db.get(Market, market_id).verified = True
        db.add(ItemMetadata(region='us', item_id=248682, namespace='static-forever-us',
                            name='Known fixture item'))
        db.add(MetadataSource(region='us', item_id=248686, locale='en_US', provider='foreverdb',
                              status='metadata_unavailable', retry_at=at + timedelta(days=2)))
        schedule_merchant_favor(db, at)
    raw = FIXTURE.read_bytes()
    responses = iter([
        ({'status': 200, 'headers': {'ETag': '"sheet-1"'}}, raw),
        ({'status': 304, 'headers': {}}, b''),
        ({'status': 200, 'headers': {}}, b'{"data":{"crates":[]}}'),
    ])
    requested_etags = []

    def fetcher(_provider, _item_id, **kwargs):
        assert kwargs['resource'] == RESOURCE and kwargs['offset'] == 0
        requested_etags.append(kwargs['etag'])
        return next(responses)

    assert tick(database, at=at, automatic=False, fetcher=fetcher)
    with database.begin() as db:
        resource, good = read_catalogue(db)
        assert resource.status == 'available'
        origin = json.loads(resource.source_json)
        assert origin['payload_hash'] == hashlib.sha256(raw).hexdigest()
        assert resource.refresh_at.replace(tzinfo=at.tzinfo) == at + timedelta(hours=12)
        backfill = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == 'merchants-favor-items'))
        assert backfill.total == backfill.request_budget == 12
        item_ids = set(db.scalars(select(MetadataTask.item_id).where(MetadataTask.job_id == backfill.id)))
        exact_ids = {crate['item_id'] for crate in good['crates']} | {
            material['item_id'] for crate in good['crates'] for bundle in crate['bundles'] for material in bundle['materials']
        }
        assert item_ids <= exact_ids
        assert item_ids.isdisjoint({248682, 248686})
        schedule_merchant_favor(db, at + timedelta(hours=1))
        assert len(list(db.scalars(select(MetadataJob).where(MetadataJob.dedupe_key == RESOURCE)))) == 1
        enqueue_merchant_favor_refresh(db, actor_id=1, at=at + timedelta(minutes=5))
    assert tick(database, at=at + timedelta(minutes=5), automatic=False, fetcher=fetcher)
    with database.begin() as db:
        resource, after_304 = read_catalogue(db)
        assert after_304 == good
        confirmed = json.loads(resource.source_json)
        assert confirmed['retrieved_at'] == origin['retrieved_at']
        assert confirmed['confirmed_at'] > origin['confirmed_at']
        enqueue_merchant_favor_refresh(db, actor_id=1, at=at + timedelta(minutes=10))
    assert tick(database, at=at + timedelta(minutes=10), automatic=False, fetcher=fetcher)
    with database() as db:
        resource, after_failure = read_catalogue(db)
        assert resource.status == 'wrong_identity' and resource.http_status == 200
        assert json.loads(resource.source_json) == confirmed and after_failure == good
        assert db.get(MetadataProvider, 'foreverdb').day_used == 3
    assert requested_etags == [None, '"sheet-1"', '"sheet-1"']


def test_refresh_retries_under_shared_backoff_with_finite_request_budget(database):
    at = now()
    with database.begin() as db:
        setup_provider(db)
        job, _ = enqueue_merchant_favor_refresh(db, actor_id=1, at=at)
        job_id = job.id
    attempts = []

    def limited(_provider, _item, **_kwargs):
        attempts.append(True)
        return {'status': 429, 'headers': {'Retry-After': '60'}}, b''

    due = at
    for count in (1, 2, 3):
        assert tick(database, at=due, automatic=False, fetcher=limited)
        with database() as db:
            resource, data = read_catalogue(db)
            assert data is None and resource.status == 'rate_limited'
            assert db.get(MetadataProvider, 'foreverdb').day_used == count
            assert db.get(MetadataJob, job_id).requests_used == count
            task = db.scalar(select(MetadataTask).where(MetadataTask.job_id == job_id))
            assert task.state == ('queued' if count < 3 else 'failed')
            waiting = resource.retry_at.replace(tzinfo=at.tzinfo)
        assert waiting >= due + timedelta(minutes=1)
        assert not tick(database, at=due + timedelta(seconds=1), automatic=False, fetcher=limited)
        due = waiting + timedelta(seconds=1)
    assert len(attempts) == 3
