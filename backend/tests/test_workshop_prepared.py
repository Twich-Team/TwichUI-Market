"""Synthetic source/attestation tests; no provider or live installation access."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
import jsonschema
from market import workshop_prepared as prepared, workshop_summary as summary
from market.models import BridgeGeneration, BridgeRecord
from test_workshop_summary import source, download, bridge


def synthetic():
    root = Path(__file__).resolve().parents[2]
    value = json.loads((root / 'contracts/workshop-summary/v3/fixtures/synthetic.json').read_text())
    return value['manifest'], {int(k): v.encode() for k, v in value['parts'].items()}


def test_shared_vectors_remain_source_bound_and_schema_valid():
    root = Path(__file__).resolve().parents[2] / 'contracts/workshop-prepared/v1'
    vectors = json.loads((root / 'fixtures/synthetic.json').read_text())
    schema = json.loads((root / 'attestation.schema.json').read_text())
    for count in prepared.COUNTS:
        result, payloads = prepared.prepare(vectors['manifest'], {int(k): v for k, v in vectors['parts'].items()}, count)
        jsonschema.Draft202012Validator(schema).validate(result)
        assert result == vectors['layouts'][str(count)]['attestation']
        assert {str(k): list(v) for k, v in payloads.items()} == vectors['layouts'][str(count)]['payloads']


def test_exact_source_identity_portable_records_and_empty_buckets():
    manifest, parts = synthetic()
    for count in (16, 32):
        attestation, payloads = prepared.prepare(manifest, parts, count)
        assert attestation['source_generation_id'] == manifest['generation_id']
        assert len(attestation['partitions']) == count
        assert attestation['record_count'] == manifest['record_count']
        body = {k: v for k, v in attestation.items() if k != 'attestation_id'}
        assert summary.digest(body) == attestation['attestation_id']
        for p in attestation['partitions']:
            data, proof = payloads[p['bucket']]
            assert len(data) == 135 * p['record_count']
            assert proof[:64] == p['merkle_root']
            if not p['record_count']:
                assert p['sha256'] == hashlib.sha256(b'[]').hexdigest()
                assert proof == hashlib.sha256(b'empty\0').hexdigest()
            assert not set(data) - set('0123456789abcdefz')


def test_source_corruption_invalid_routes_counts_order_and_layout_are_rejected():
    h, parts = synthetic()
    bucket = h['partitions'][0]['bucket']
    for damage in ('bytes', 'price', 'missing', 'count', 'order'):
        altered, changed = copy.deepcopy(h), dict(parts)
        if damage == 'bytes': changed[bucket] += b' '
        elif damage == 'price': changed[bucket] = changed[bucket].replace(b'"120"', b'"121"', 1)
        elif damage == 'missing': changed.pop(bucket)
        elif damage == 'count': altered['record_count'] += 1
        else: altered['partitions'] += copy.deepcopy(altered['partitions'])
        if damage in ('count', 'order'):
            altered.pop('generation_id');altered['generation_id'] = summary.digest(altered)
        with pytest.raises(ValueError): prepared.prepare(altered, changed)
    for count in (1, 8, 64, True, '16'):
        with pytest.raises(ValueError): prepared.prepare(h, parts, count)


def test_fixed_encoder_refuses_injection_and_preserves_maximum_integers():
    h, parts = synthetic()
    row = json.loads(parts[h['partitions'][0]['bucket']])[0]
    row[3:6] = ['99999999999', '99999999998', '99999999997']
    row[6] = 2**53 - 1
    encoded = prepared.fixed([row])
    assert len(encoded) == prepared.WIDTH
    assert int(encoded[73:83], 16) == 99999999999
    assert int(encoded[103:117], 16) == 2**53 - 1
    for evil in ('";bad();--', '0', 1.5, True):
        changed = copy.deepcopy(row);changed[3] = evil
        with pytest.raises(ValueError): prepared.fixed([changed])


def test_content_is_generation_independent_but_attestation_is_not():
    h, parts = synthetic()
    first, payloads = prepared.prepare(h, parts)
    h = copy.deepcopy(h);h['source_watermark'] = str(int(h['source_watermark']) + 1)
    h.pop('generation_id');h['generation_id'] = summary.digest(h)
    second, reused = prepared.prepare(h, parts)
    assert first['attestation_id'] != second['attestation_id']
    assert first['partitions'] == second['partitions'] and payloads == reused


def test_prepared_bound_refuses_whole_projection_without_pruning(monkeypatch):
    h, parts = synthetic()
    monkeypatch.setattr(prepared, 'MAX_TOTAL_BYTES', 1)
    with pytest.raises(ValueError, match='generation bound'): prepared.prepare(h, parts)


def test_opt_in_api_account_generation_binding_etag_legacy_and_corruption(source, database):
    client, mid, _, _ = source
    h, _, _ = download(source, 3)
    path = f"/api/v1/workshop/markets/{mid}/summary/{h['generation_id']}/prepared/1/16"
    response = client.get(path)
    assert response.status_code == 200, response.text
    value = response.json();assert value['account_id'] > 0
    assert value['attestation']['source_generation_id'] == h['generation_id']
    assert client.get(path, headers={'If-None-Match': response.headers['etag']}).status_code == 304
    assert client.get(path.replace('/16', '/32')).status_code == 200
    assert client.get(path.replace('/16', '/8')).status_code == 422
    assert client.get(path.replace(h['generation_id'], 'f' * 64)).status_code == 410
    assert client.get(path.replace(f'markets/{mid}', 'markets/99999')).status_code == 404
    old, _, _ = download(source, 2)
    assert client.get(path.replace(h['generation_id'], old['generation_id'])).status_code == 410
    assert download(source, 3)[0] == h
    with database.begin() as db:
        part = db.get(BridgeRecord, (h['generation_id'], h['partitions'][0]['bucket']))
        part.record_json += ' '
    assert client.get(path).status_code == 409
    client.headers.pop('Authorization')
    assert client.get(path).status_code == 401


def test_scoped_companion_capability_is_read_only(source, owner):
    from test_companion_auth import authorize
    client, mid, _, _ = source
    h, _, _ = download(source, 3)
    client.headers.pop('Authorization', None)
    token = authorize(owner)['access_token'];client.headers['Authorization'] = 'Bearer ' + token
    path = f"/api/v1/workshop/markets/{mid}/summary/{h['generation_id']}/prepared/1/16"
    assert client.get(path).status_code == 200
    assert client.post(path).status_code == 405  # No write handler exists.
    assert client.get(path.replace('/16', '/8')).status_code == 403
    assert client.get('/api/v1/admin/users').status_code == 403
