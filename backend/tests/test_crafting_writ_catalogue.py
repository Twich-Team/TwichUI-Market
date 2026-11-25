from market.crafting_writs import read_catalogue, refresh_seconds


def test_curated_relationships_and_offline_copy():
    row, data = read_catalogue(None)
    assert row is None
    writs = {w['item_id']: w for w in data['writs']}
    assert len(writs) == 9
    assert writs[264018]['quest_id'] == 94218
    assert writs[264018]['objectives'][0]['item_id'] == 8951
    assert writs[264037]['quest_id'] == 94237
    assert writs[264037]['objectives'][0]['quantity'] == 200
    assert all(w['provider_reward'] is None for w in writs.values())
    data['writs'].clear()
    assert len(read_catalogue(None)[1]['writs']) == 9
    assert refresh_seconds() == 0


def test_relationship_validation_rejects_bad_data():
    from copy import deepcopy
    import pytest
    from market.crafting_writs import validate_catalogue
    _, good = read_catalogue(None)
    invalid = deepcopy(good)
    invalid['writs'][0]['objectives'][0]['quantity'] = 0
    with pytest.raises(ValueError):
        validate_catalogue(invalid)
    invalid = deepcopy(good)
    invalid['writs'].append(deepcopy(invalid['writs'][0]))
    with pytest.raises(ValueError):
        validate_catalogue(invalid)
    invalid = deepcopy(good)
    invalid['writs'][0]['recipes'][0]['ingredients'][0]['item_id'] = 8951
    with pytest.raises(ValueError):
        validate_catalogue(invalid)


def test_invalid_cached_catalogue_falls_back_to_seed():
    class Row:
        fields_json = '{"schema_version":1,"writs":[]}'
    class DB:
        def get(self, model, key):
            return Row()
    row, data = read_catalogue(DB())
    assert row is not None
    assert len(data['writs']) == 9


def test_item_backfill_dedupes_and_obeys_cooldown(database, monkeypatch, tmp_path):
    import json
    from base64 import b64encode
    from datetime import timedelta
    from sqlalchemy import select
    from market.db import now
    from market.metadata_recovery import enqueue_crafting_writ_refresh, tick
    from market.models import Market, MetadataJob, MetadataProvider, MetadataTask
    from test_foreverdb import setup_provider
    keyring = tmp_path / 'keyring.json'
    keyring.write_text(json.dumps({'active': 'test', 'keys': {'test': b64encode(b'x' * 32).decode()}}))
    keyring.chmod(0o600)
    monkeypatch.setenv('METADATA_KEYRING_FILE', str(keyring))
    at = now()
    with database.begin() as db:
        market_id = setup_provider(db)
        db.get(Market, market_id).verified = True
        db.get(MetadataProvider, 'foreverdb').cooldown_until = at + timedelta(minutes=10)
        first, created = enqueue_crafting_writ_refresh(db, at=at)
        assert created
        duplicate, created = enqueue_crafting_writ_refresh(db, at=at)
        assert not created and first.id == duplicate.id
        assert first.request_budget == first.total * 2
    def forbidden(*args, **kwargs):
        raise AssertionError('cooldown bypassed')
    tick(database, at=at, automatic=False, fetcher=forbidden)
    with database() as db:
        job = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == 'crafting-writ-items'))
        assert job.requests_used == 0
        assert db.scalar(select(MetadataTask).where(MetadataTask.job_id == job.id)).attempts == 0
        _, data = read_catalogue(db)
        assert len(data['writs']) == 9


def test_backfill_failure_retains_seed(database, monkeypatch, tmp_path):
    import json
    from base64 import b64encode
    from sqlalchemy import select
    from market.db import now
    from market.metadata_recovery import enqueue_crafting_writ_refresh, tick
    from market.models import Market, MetadataJob
    from test_foreverdb import setup_provider
    keyring = tmp_path / 'keyring.json'
    keyring.write_text(json.dumps({'active': 'test', 'keys': {'test': b64encode(b'x' * 32).decode()}}))
    keyring.chmod(0o600)
    monkeypatch.setenv('METADATA_KEYRING_FILE', str(keyring))
    at = now()
    with database.begin() as db:
        market_id = setup_provider(db)
        db.get(Market, market_id).verified = True
        enqueue_crafting_writ_refresh(db, at=at)
    tick(database, at=at, automatic=False, fetcher=lambda *a, **k: ({'status': 503, 'headers': {}}, b''))
    with database() as db:
        job = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == 'crafting-writ-items'))
        assert job.requests_used == 1
        assert len(read_catalogue(db)[1]['writs']) == 9
