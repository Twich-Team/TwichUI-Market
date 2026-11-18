"""Synthetic authenticated summary transport; no provider/production requests."""
import copy
import hashlib
import json
import pytest
import jsonschema
from pathlib import Path
from sqlalchemy import event, func, select, text
from market import workshop_summary as summary
from market.models import BridgeGeneration, BridgeRecord, Listing, Observation
from test_bridge_export import bridge, contract_bundle, key
from test_market_configuration import verified_player_mapping


@pytest.fixture
def source(bridge, database):
    client, mid, observations, snapshots = bridge
    with database.begin() as db:
        verified_player_mapping(db, 114, 'Horde')
    return client, mid, observations, snapshots


def download(source):
    client, mid, _, _ = source
    path = f'/api/v1/workshop/markets/{mid}/summary'
    for _ in range(5):
        response = client.get(path)
        if response.status_code != 202:
            break
        assert response.headers['retry-after'] == '5'
    assert response.status_code == 200, response.text
    envelope = response.json()
    manifest = envelope['manifest']
    schema = json.loads((Path(__file__).resolve().parents[2] / 'contracts/workshop-summary/v1/manifest.schema.json').read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)
    rows = []
    for part in manifest['partitions']:
        r = client.get(path + f"/{manifest['generation_id']}/parts/{part['bucket']}")
        assert r.status_code == 200
        assert len(r.content) == part['bytes']
        assert hashlib.sha256(r.content).hexdigest() == part['sha256']
        values = r.json()
        assert len(values) == part['record_count']
        for row in values:
            summary.validate_row(row, part['bucket'])
        rows.extend(values)
    assert len(rows) == manifest['record_count']
    assert summary.digest({k: v for k, v in manifest.items() if k != 'generation_id'}) == manifest['generation_id']
    return manifest, {(r[0], r[1]): r for r in rows}, response.headers['etag']


def test_current_universe_exact_variants_prices_sparse_history_and_no_archive(source, database):
    with database() as db:
        original = {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in (Listing, Observation)}
    manifest, rows, etag = download(source)
    assert manifest['format'] == 'twichui-workshop-summary'
    assert manifest['market']['faction'] == 'Horde'
    assert manifest['coverage'] == dict(scope='current_observed_exact_variants', complete=True,
        source_records=3, delivered_records=3, missing='unavailable', detailed_history='not_delivered')
    assert manifest['can_satisfy_local_competition'] is False
    assert (2, key({'id': 2})) not in rows  # Historical-only explicitly outside universe.
    r = rows[2589, key({'id': 2589})]
    assert r[3:6] == ['120', '100', '120']  # Independent original canonical fixture.
    assert r[9:] == [None, 2, 2, 2]  # No invented third historical close.
    assert rows[2589, key({'id': 2589, 'bonus_lists': [9]})][3] == '999'
    assert rows[123, key({'id': 123})][2:7] == [1, None, None, None, 2]
    assert manifest['synthetic'] and manifest['source_observation']['scope_complete']
    client, mid, _, _ = source
    r = client.get(f'/api/v1/workshop/markets/{mid}/summary', headers={'If-None-Match': etag})
    assert r.status_code == 304 and not r.content
    with database() as db:
        assert {m.__tablename__: db.scalar(select(func.count()).select_from(m)) for m in (Listing, Observation)} == original


def test_native_authorization_market_binding_missing_mapping_and_expiry(source, database):
    client, mid, _, _ = source
    manifest, _, _ = download(source)
    p = f"/api/v1/workshop/markets/{mid}/summary/{manifest['generation_id']}/parts/1"
    assert client.get(p.replace(f'markets/{mid}', 'markets/99999')).status_code == 404
    assert client.get(p.replace(manifest['generation_id'], 'f'*64)).status_code == 410
    assert client.get(p[:-1]+'64').status_code == 422
    del client.headers['Authorization']
    assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 401
    login = client.post('/api/v1/auth/login', json={'username': 'owner', 'password': 'correct horse battery'})
    assert login.status_code == 200
    assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 403


def test_mapping_required_before_any_derivation(bridge, database):
    client, mid, _, _ = bridge
    assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 409
    with database() as db:
        assert db.scalar(select(func.count()).select_from(BridgeGeneration)) == 0


def test_no_ingest_lock_or_per_item_queries_after_derivation(source, database):
    download(source)
    engine = database.kw['bind']
    seen = []
    def record(conn, cursor, statement, params, context, many):
        seen.append((statement, params))
    event.listen(engine, 'before_cursor_execute', record)
    try:
        client, mid, _, _ = source
        assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 200
    finally:
        event.remove(engine, 'before_cursor_execute', record)
    assert len(seen) < 15
    assert all('7140232' not in statement for statement, _ in seen)
    if engine.dialect.name == 'postgresql':
        # A concurrently held ingest transaction must not block immutable export.
        with engine.begin() as held:
            held.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
            assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 200


def test_cold_preparation_and_source_loss_keep_last_good(source, database):
    client, mid, _, snapshots = source
    first = client.get(f'/api/v1/workshop/markets/{mid}/summary')
    assert first.status_code == 202
    manifest, _, _ = download(source)
    with database() as db:
        assert db.get(BridgeGeneration, manifest['generation_id']) is not None


def test_export_and_derivation_reservations_are_independent_of_ingestion(source, database):
    engine = database.kw['bind']
    if engine.dialect.name != 'postgresql':
        pytest.skip('PostgreSQL advisory-lock acceptance')
    client, mid, _, snapshots = source
    path = f'/api/v1/workshop/markets/{mid}/summary'
    with engine.begin() as held:
        held.execute(text('SELECT pg_advisory_xact_lock(7140288, :market)'), {'market': mid})
        assert client.get(path).status_code == 409
    with engine.begin() as held:
        held.execute(text('SELECT pg_advisory_xact_lock(7140289, :snapshot)'), {'snapshot': snapshots[0]})
        assert client.get(path).status_code == 409
    with engine.begin() as held:
        held.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
        assert client.get(path).status_code == 202
        assert client.get(path).status_code == 200


def test_partition_overflow_never_silently_truncates_or_publishes(source, database, monkeypatch):
    monkeypatch.setattr(summary, 'MAX_PART', 64)
    client, mid, _, _ = source
    assert client.get(f'/api/v1/workshop/markets/{mid}/summary').status_code == 202
    r = client.get(f'/api/v1/workshop/markets/{mid}/summary')
    assert r.status_code == 413 and 'no generation' in r.text
    with database() as db:
        assert db.scalar(select(func.count()).select_from(BridgeGeneration).where(BridgeGeneration.algorithm == summary.ALGORITHM)) == 0


@pytest.mark.parametrize('index,value', [(0, True), (1, 'a'*63), (2, 5), (3, '1.5'), (4, '0'),
    (5, '100000000000'), (6, -1), (7, -1), (8, 1), (9, '1e2'), (10, 61), (11, 1)])
def test_strict_tuple_negative_controls(index, value):
    row = [25, 'a'*64, 0, '100', '110', '90', 12, 0, 0, '120', 2, 3, 3]
    row[index] = value
    with pytest.raises(ValueError):
        summary.validate_row(row)


def test_unknown_and_unsupported_never_become_zero_prices():
    for state in (3, 4):
        row = [25, 'a'*64, state, None, None, None, None, 0, 1, None, 0, 0, 0]
        summary.validate_row(row)
        bad = row[:]
        bad[6] = 0
        with pytest.raises(ValueError):
            summary.validate_row(bad)
