"""Prepare a frozen PRIVATE native test from a COPY of a completed DEV cache.

Runs the real proposed prepared endpoint in-process against disposable SQLite.
No listening socket, production database, provider, account, or credential access.
Real market records must never be committed or uploaded as CI artifacts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]


def need(ok, message):
    if not ok:
        raise ValueError(message)


def bounded(path, maximum):
    need(not any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
                 for p in [path, *path.parents]), 'No linked snapshot inputs')
    need(path.stat().st_size <= maximum, 'Snapshot file exceeds bound')
    return path.read_bytes()


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-copy', type=Path, required=True)
    parser.add_argument('--configuration-copy', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--repo-root', type=Path, help='Exact pinned source checkout when running the packaged adapter')
    args = parser.parse_args()
    if args.repo_root:
        ROOT = args.repo_root.resolve()
    need((ROOT / 'backend/market/workshop_prepared.py').is_file(), 'Exact Market source checkout required')
    need(args.cache_copy.name.startswith('private-market-source-'), 'Use an explicit private-market-source-* COPY, never live AppData')
    need(not args.out.exists(), 'Output must be new; preserve prior snapshots')
    need(not any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
                 for p in args.out.parents), 'No linked output parents')
    state = json.loads(bounded(args.cache_copy / 'current.json', 65536 + 128))
    need(set(state) == {'bank', 'manifest'} and state['bank'] in ('A', 'B'), 'Completed cache state required')
    config = json.loads(bounded(args.configuration_copy, 65536))
    scope = config['scope']
    h = state['manifest']
    need(h['contract_version'] == h['schema_version'] == 3, 'Contract 3 source required; no re-labeling legacy data')
    need(h['market']['server_market_id'] == scope['market_id'] and scope['algorithm'] == h['pricing_algorithm'], 'Source scope mismatch')
    need({p['bucket'] for p in h['partitions']} == {p['bucket'] for p in h['history_partitions']} == set(range(64)), 'All 64 current/history source partitions required')
    parts = {}
    for history in (False, True):
        for descriptor in h['history_partitions' if history else 'partitions']:
            position = descriptor['bucket'] + (64 if history else 0)
            raw = bounded(args.cache_copy / state['bank'] / f'{position:02}.json', 1048576)
            need(len(raw) == descriptor['bytes'] and hashlib.sha256(raw).hexdigest() == descriptor['sha256'], 'Source partition integrity')
            parts[position] = raw
    # Override this subprocess's database BEFORE importing any backend modules.
    with tempfile.TemporaryDirectory(prefix='private-prepared-endpoint-') as temporary:
        os.environ.update(DATABASE_URL='sqlite:///' + str(Path(temporary) / 'market_test.sqlite'),
                          APP_ORIGIN='http://127.0.0.1', TRUSTED_INGRESS_TOKEN='',
                          SYNC_CURSOR_SECRET='private-snapshot-fixture-' + secrets.token_hex(24),
                          BRIDGE_CONTRACT_ROOT=str(ROOT / 'contracts/bridge/v1'))
        sys.path.insert(0, str(ROOT / 'backend'))
        from fastapi.testclient import TestClient
        from market.app import app
        from market.db import Base, engine, Session, now
        from market.models import User, Market, CompanionDevice, BridgeGeneration, BridgeRecord
        from market.companion_auth import _access
        from market import workshop_summary as summary
        need(engine.url.database.endswith('market_test.sqlite'), 'Disposable database required')
        for descriptor in h['history_partitions']:
            bucket = descriptor['bucket']
            rows = json.loads(parts[64 + bucket])
            need(summary.canonical(rows) == parts[64 + bucket] and len(rows) == descriptor['record_count'], 'History canonical/count')
            for row in rows:
                summary.validate_row(row, bucket, version=2, observations=h['observations'])
            need(summary.canonical([r[:13] for r in rows]) == parts[bucket], 'History/current identity and price binding')
        Base.metadata.create_all(engine)
        token = secrets.token_urlsafe(32)  # Temporary isolated-db token only; never exported.
        with Session.begin() as db:
            db.add(User(id=scope['account_id'], username='private_snapshot_only', password_hash='no-login', role='member'))
            market = h['market']
            db.add(Market(id=scope['market_id'], region=market['region'], ruleset_id=market['transport_ruleset_id'],
                          house_id=market['house_id'], source_kind=market['source_kind'],
                          label='Isolated frozen snapshot', verified=True, enabled=True))
            db.flush()
            device = CompanionDevice(user_id=scope['account_id'], name='In-process snapshot test', platform='Windows',
                                     app_version='2.0.0-beta.11', issuer_origin='http://127.0.0.1',
                                     expires_at=now()+timedelta(hours=1), refresh_expires_at=now()+timedelta(hours=1),
                                     refresh_hash=hashlib.sha256(secrets.token_bytes(32)).hexdigest())
            db.add(device); db.flush(); _access(db, device, token)
            db.add(BridgeGeneration(generation_id=h['generation_id'], market_id=scope['market_id'],
                                   algorithm='workshop-summary-v3:' + h['pricing_algorithm'],
                                   source_signature=h['generation_id'], manifest_json=summary.canonical(h).decode()))
            db.flush()
            db.add_all(BridgeRecord(generation_id=h['generation_id'], position=k, record_json=raw.decode()) for k, raw in parts.items())
        attestations = {}
        with TestClient(app) as client:
            for count in (16, 32):
                route = f'/api/v1/workshop/markets/{scope["market_id"]}/summary/{h["generation_id"]}/prepared/1/{count}'
                need(client.get(route).status_code == 401, 'Endpoint authentication must remain enforced')
                response = client.get(route, headers={'Authorization': 'Bearer ' + token})
                need(response.status_code == 200 and response.json()['account_id'] == scope['account_id'], 'Proposed prepared endpoint refused source')
                attestations[count] = response.json()['attestation']
                unchanged = client.get(route, headers={'Authorization': 'Bearer ' + token, 'If-None-Match': response.headers['etag']})
                need(unchanged.status_code == 304, 'Prepared conditional integrity response')
        engine.dispose()
    # Publish output only after both complete endpoint checks; no credential files.
    args.out.mkdir(mode=0o700)
    (args.out / 'parts').mkdir(mode=0o700)
    (args.out / 'manifest.json').write_bytes(summary.canonical(h))
    (args.out / 'scope.json').write_bytes(summary.canonical(scope))
    for position, raw in parts.items():
        (args.out / 'parts' / f'{position:02}.json').write_bytes(raw)
    for count, attestation in attestations.items():
        (args.out / f'prepared-{count}.json').write_bytes(summary.canonical(attestation))
    receipt = {'source_generation': h['generation_id'], 'source_synthetic': h['synthetic'],
               'layouts': [16, 32], 'history_partitions': 64, 'endpoint': 'isolated in-process production route',
               'authentication': [401, 200, 304], 'production_changes': False,
               'input_current_sha256': hashlib.sha256((args.cache_copy / 'current.json').read_bytes()).hexdigest(),
               'files': {str(p.relative_to(args.out)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in args.out.rglob('*.json')}}
    (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'files'}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        sys.exit('PRIVATE SNAPSHOT REFUSED: ' + str(error))
