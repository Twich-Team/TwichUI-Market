"""Real authenticated archive routes; independent listing-price expectations."""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import delete, select
from market import archive_api as archive
from market.db import now
from market.ingest import ingest
from market.models import ArchiveCheckpoint, ArchiveDigest, ArchiveMember, BridgeDerivedRecord, Market, User
from market.security import issue
from test_bridge_export import bridge, contract_bundle, key


def start(client, mid, **query):
    for _ in range(20):
        r = client.get(f'/api/v1/archive/markets/{mid}/checkpoint', params=query)
        if r.status_code != 202:
            assert r.status_code == 200, r.text
            return r.json()
    pytest.fail('preparation never completed')


def page(client, mid, e, cursor=None, limit=2):
    return client.get(f'/api/v1/archive/markets/{mid}/pages', params={
        'checkpoint': e['header']['checkpoint_id'], 'cursor': cursor or e['cursor'], 'limit': limit})


def download(client, mid, e):
    rows = []
    cursor = e['cursor']
    chain = '0' * 64
    while True:
        r = page(client, mid, e, cursor)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p['offset'] == len(rows) and p['previous_sha256'] == chain
        assert hashlib.sha256(archive.canonical(p['entries'])).hexdigest() == p['page_sha256']
        chain = hashlib.sha256(bytes.fromhex(chain) + archive.canonical(p['entries'])).hexdigest()
        assert p['chain_sha256'] == chain
        rows.extend(p['entries'])
        if not p['has_more']:
            assert p['next_cursor'] is None
            break
        cursor = p['next_cursor']
    return rows


def test_bootstrap_sparse_absence_historical_bid_only_and_resume(bridge):
    client, mid, _, _ = bridge
    e = start(client, mid)
    first = page(client, mid, e)
    assert first.json() == page(client, mid, e).json(), 'repeat must be deterministic'
    rows = download(client, mid, e)
    obs = [r['observation'] for r in rows if r['kind'] == 'observation']
    snapshots = {r['snapshot_id']: r for r in rows if r['kind'] == 'snapshot'}
    records = [r for r in rows if r['kind'] == 'variant']
    assert len(obs) == 2 and len(snapshots) == 2 and len(records) == 7
    assert (archive.bridge.utc(__import__('datetime').datetime.fromisoformat(obs[1]['observed_at'].replace('Z','+00:00'))).date()
            - __import__('datetime').date.fromisoformat(obs[0]['utc_day'])).days == 2
    assert e['header']['total_records'] == 7 and e['header']['archive_complete']
    for sid, meta in snapshots.items():
        group = [r for r in records if r['snapshot_id'] == sid]
        assert len(group) == meta['record_count']
        assert hashlib.sha256(b''.join(archive.canonical(r) + b'\n' for r in group)).hexdigest() == meta['records_sha256']
    priced = [r['value']['summary']['recent_copper'] for r in records if r['item_id'] == 2589 and r['variant_key'] == key({'id': 2589})]
    assert priced == ['100', '120']
    assert len([r for r in records if r['item_id'] == 2]) == 1, 'absence represented by complete snapshot membership, not invented listing'
    assert all(r['value']['summary']['recent_copper'] is None for r in records if r['item_id'] == 123)
    meta_hash = hashlib.sha256(b''.join(archive.canonical(r) + b'\n' for r in rows if r['kind'] != 'variant')).hexdigest()
    assert meta_hash == e['header']['metadata_sha256']


def test_watermark_freezes_pages_and_incremental_is_only_new_evidence(bridge, database):
    client, mid, _, _ = bridge
    old = start(client, mid)
    first = page(client, mid, old).json()
    with database.begin() as db:
        ingest(db, mid, b'{"auctions":[{"id":1,"item":{"id":99},"quantity":1,"buyout":777}]}', request_key='archive-next', synthetic=True)
    rows = download(client, mid, old)
    assert not any(r.get('item_id') == 99 for r in rows)
    assert first == page(client, mid, old).json()
    new = start(client, mid, base=old['header']['checkpoint_id'])
    changes = download(client, mid, new)
    assert new['header']['base_checkpoint_id'] == old['header']['checkpoint_id']
    assert [r['value']['summary']['recent_copper'] for r in changes if r['kind'] == 'variant'] == ['777']
    assert new['header']['total_observations'] == 3 and new['header']['transfer_observations'] == 1


def test_reused_snapshot_sends_only_observation(bridge, database):
    client, mid, _, _ = bridge
    old = start(client, mid)
    with database.begin() as db:
        from market.models import Observation
        o = db.scalar(select(Observation).where(Observation.market_id == mid).order_by(Observation.id.desc()))
        db.add(Observation(market_id=mid, snapshot_id=o.snapshot_id, request_key='repeat-observation',
            retrieved_at=now(), namespace=o.namespace, payload_hash=o.payload_hash, payload_bytes=o.payload_bytes, synthetic=True))
    new = start(client, mid, base=old['header']['checkpoint_id'])
    rows = download(client, mid, new)
    assert len(rows) == 1 and rows[0]['kind'] == 'observation'
    assert new['header']['transfer_records'] == 0


def test_auth_cursor_market_expiry_and_versions(bridge, database):
    client, mid, _, _ = bridge
    e = start(client, mid)
    assert page(client, mid, e, e['cursor'] + 'x').status_code == 409
    assert client.get(f'/api/v1/archive/markets/{mid}/checkpoint', params={'algorithm': 'future'}).status_code == 422
    with database.begin() as db:
        u = User(username='archive-other', password_hash='unused', role='member')
        db.add(u); db.flush(); token, _, _ = issue(db, u, 'device')
    original = client.headers['Authorization']
    client.headers['Authorization'] = 'Bearer ' + token
    assert page(client, mid, e).status_code == 409
    client.headers['Authorization'] = original
    assert page(client, mid + 1, e).status_code == 409
    with database.begin() as db:
        db.get(ArchiveCheckpoint, e['header']['checkpoint_id']).expires_at = now() - timedelta(seconds=1)
    assert page(client, mid, e).status_code == 409
    client.headers.pop('Authorization')
    assert client.get(f'/api/v1/archive/markets/{mid}/checkpoint').status_code == 401


def test_loss_of_evidence_is_not_complete_and_exact_copper_preserved(bridge, database):
    client, mid, _, _ = bridge
    with database.begin() as db:
        ingest(db, mid, b'{"auctions":[{"id":1,"item":{"id":99},"quantity":1,"buyout":9223372036854775807}]}', request_key='archive-large', synthetic=True)
    e = start(client, mid)
    rows = download(client, mid, e)
    large = next(r for r in rows if r.get('item_id') == 99)
    assert large['value']['summary']['quantity_weighted_ask_copper'] == '9223372036854775807'
    assert large['value']['summary']['recent_copper'] is None
    with database.begin() as db:
        db.execute(delete(BridgeDerivedRecord))
    cursor = e['cursor']
    for _ in range(20):
        r = page(client, mid, e, cursor)
        if r.status_code == 409:
            break
        assert r.json()['has_more'], 'must not claim complete after evidence loss'
        cursor = r.json()['next_cursor']
    else:
        pytest.fail('missing evidence not detected')


def selection_for(e, variants):
    h=e['header']
    return {'format':'twichui-market-selection','contract_version':1,'expected_schema_version':3,
        'issuer_id':h['issuer_id'],'market':h['market'],'scope_type':'explicit_variants',
        'variants':[{'item_id':i,'variant_key':v} for i,v in sorted(variants)],
        'history_from_day':(archive.bridge.utc(now()).date()-timedelta(days=2)).isoformat(),
        'history_through_day':archive.bridge.utc(now()).date().isoformat(),
        'pricing_algorithm':h['pricing_algorithm'],'history_basis':h['history_basis'],'profile':'daily_research_v1'}


def test_scoped_schema3_selection_gap_exact_values_and_refusals(bridge, monkeypatch):
    client,mid,_,_=bridge;e=start(client,mid)
    request=selection_for(e,[(2,key({'id':2})),(123,key({'id':123})),(2589,key({'id':2589}))])
    url=f'/api/v1/archive/markets/{mid}/scoped?checkpoint='+e['header']['checkpoint_id']
    response=client.post(url,json=request)
    assert response.status_code==200,response.text
    g=response.json();archive.scoped_contract().validate(g,request)
    assert g['schema_version']==3 and g['coverage']['generation_complete'] is False and g['scope']['scope_complete'] is True
    assert g['records'][0]['current']['state']=='absent'
    assert g['records'][1]['current']['supply']==2 and g['records'][1]['current']['metrics']['recent_copper'] is None
    assert [d['recent_copper'] for d in g['records'][2]['daily']]==['100','120']
    assert g['scope']['date_coverage'][1]['state']=='no_observation'
    bad=json.loads(json.dumps(request));bad['variants'].append(bad['variants'][0])
    assert client.post(url,json=bad).status_code==422
    bad=json.loads(json.dumps(request));bad['market']['house_id']=110
    assert client.post(url,json=bad).status_code==409
    bad=json.loads(json.dumps(request));bad['expected_schema_version']=999
    assert client.post(url,json=bad).status_code==422
    bad=json.loads(json.dumps(request));bad['variants'][0]['variant_key']='0'*64
    assert client.post(url,json=bad).status_code==409
    original=archive.scoped_contract().preflight
    def tiny(g,r,budget):return original(g,r,{'canonical_bytes':1})
    monkeypatch.setattr(archive.scoped_contract(),'preflight',tiny)
    refused=client.post(url,json=request)
    assert refused.status_code==413 and 'canonical_bytes' in refused.json()['exceeded']


def test_companion_rotation_resumes_same_device_and_revocation_stops_it(owner, database, monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET', 'synthetic-archive-device-rotation-'+'a'*32)
    from test_companion_auth import authorize, refresh_form, seed_market
    seed_market(database)
    tokens = authorize(owner)
    owner.headers['Authorization'] = 'Bearer ' + tokens['access_token']
    envelope = start(owner, 2)
    first = page(owner, 2, envelope).json()
    owner.headers.pop('Authorization')
    refreshed = owner.post('/api/v1/companion/token', data=refresh_form(tokens))
    assert refreshed.status_code == 200, refreshed.text
    renewed = refreshed.json()
    owner.headers['Authorization'] = 'Bearer ' + renewed['access_token']
    assert page(owner, 2, envelope).json() == first
    owner.headers.pop('Authorization')
    other_device = authorize(owner)
    owner.headers['Authorization'] = 'Bearer ' + other_device['access_token']
    assert page(owner, 2, envelope).status_code == 409
    owner.headers['Authorization'] = 'Bearer ' + renewed['access_token']
    assert owner.post('/api/v1/companion/devices/self/revoke').status_code == 204
    assert page(owner, 2, envelope).status_code == 401


def test_equivalent_checkpoint_reuse_and_capacity_never_evicts_pending_peer(bridge, database, monkeypatch):
    client, mid, _, _ = bridge
    envelope = start(client, mid)
    assert start(client, mid) == envelope
    monkeypatch.setattr(archive, 'MAX_CHECKPOINTS', 1)
    with database.begin() as db:
        ingest(db, mid, b'{"auctions":[{"id":1,"item":{"id":99},"quantity":1,"buyout":777}]}', request_key='archive-storage-next', synthetic=True)
    response = client.get(f'/api/v1/archive/markets/{mid}/checkpoint')
    assert response.status_code == 503
    assert download(client, mid, envelope)


def test_retention_change_requires_full_bootstrap_and_old_exact_descriptor_is_preserved(bridge, database):
    from market.models import Observation
    client, mid, oids, _ = bridge
    with database.begin() as db:
        ingest(db, mid, b'{"auctions":[{"id":1,"item":{"id":77},"quantity":1,"buyout":700}]}', request_key='archive-old-only', retrieved_at=now()-timedelta(days=90), synthetic=True)
    envelope = start(client, mid)
    request = selection_for(envelope, [(77,key({'id':77}))])
    response = client.post(f'/api/v1/archive/markets/{mid}/scoped', params={'checkpoint':envelope['header']['checkpoint_id']}, json=request)
    assert response.status_code == 200, response.text
    assert response.json()['records'][0]['variant_json'] == '{"id":77}'
    assert response.json()['records'][0]['current']['state'] == 'absent'
    with database.begin() as db:
        db.execute(delete(Observation).where(Observation.id == oids[0]))
    assert client.get(f'/api/v1/archive/markets/{mid}/checkpoint', params={'base':envelope['header']['checkpoint_id']}).status_code == 409
    # Genuine retained-source changes need a new pinned full checkpoint. The old
    # frozen metadata is not silently reused just because the watermark matches.
    replacement = start(client, mid)
    assert replacement['header']['checkpoint_id'] != envelope['header']['checkpoint_id']
    assert replacement['header']['total_observations'] == 2
    assert len([e for e in download(client, mid, replacement) if e['kind']=='observation']) == 2
