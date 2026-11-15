"""Read-only, project-scoped fingerprints before/after a frontend/API deployment.

Raw rows (including credential hashes) are streamed into SHA-256, never printed.
Mutable collector cursors, current daily pointers and authentication audit events
are intentionally outside the immutable-history comparison.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def artifact(path):
    path = path.resolve()
    if not path.is_relative_to(ROOT / 'artifacts'):
        raise ValueError('Audit files must stay in project artifacts')
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


command = ['docker', '--context', 'rootless', 'exec', '-e',
           'PGOPTIONS=-c default_transaction_read_only=on', 'twichui-market-db-1',
           'psql', '-U', 'market', '-d', 'market', '-Atqc']


def sql(query):
    return subprocess.check_output(command + [query], text=True).strip()


def original_projection(current, original=None):
    """Pin all original columns; additive columns cannot change the old row digest."""
    if not isinstance(current, list) or not current or len(current) != len(set(current)):
        raise ValueError('Invalid database columns')
    selected = current if original is None else original
    if (not isinstance(selected, list) or not selected or len(selected) != len(set(selected))
            or not all(isinstance(name, str) and re.fullmatch(r'[a-z_][a-z0-9_]*', name) for name in selected)
            or not set(selected).issubset(current)):
        raise ValueError('Original columns are missing or invalid')
    return ','.join('"' + name + '"' for name in selected), list(selected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['capture', 'verify'])
    parser.add_argument('baseline', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-revision', choices=['0012', '0013', 'meta_20261114'], default='0012')
    args = parser.parse_args()
    baseline = artifact(args.baseline)
    previous = json.loads(baseline.read_text()) if args.action == 'verify' else None
    if previous and previous.get('format_version') != 2:
        raise ValueError('Capture a fresh schema-aware baseline before deployment')
    cutoffs = previous['cutoffs'] if previous else json.loads(sql("""
    SELECT json_build_object('snapshot',(SELECT COALESCE(max(id),0) FROM snapshots),
     'observation',(SELECT COALESCE(max(id),0) FROM observations),
     'user',(SELECT COALESCE(max(id),0) FROM users),
     'credential',(SELECT COALESCE(max(id),0) FROM credentials))
    """))
    assert all(type(value) is int and value >= 0 for value in cutoffs.values())
    tables = {
        'observations': (f"id<={cutoffs['observation']}", 'id'),
        'snapshots': (f"id<={cutoffs['snapshot']}", 'id'),
        'listings': (f"snapshot_id<={cutoffs['snapshot']}", 'id'),
        'snapshot_statistics': (f"snapshot_id<={cutoffs['snapshot']}", 'snapshot_id,item_id,variant_key'),
        'users': (f"id<={cutoffs['user']}", 'id'),
        'credentials': (f"id<={cutoffs['credential']}", 'id'),
        'user_preferences': (f"user_id<={cutoffs['user']}", 'user_id'),
        'market_verifications': ('TRUE', 'id'),
        'player_market_mappings': ('TRUE', 'id'),
        'retention_policy': ('TRUE', 'id'),
    }
    fingerprints = {}
    columns = {}
    for table, (where, order) in tables.items():
        current_columns = json.loads(sql(f"SELECT json_agg(column_name ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND table_name='{table}'"))
        projection, columns[table] = original_projection(current_columns, previous['columns'][table] if previous else None)
        process = subprocess.Popen(command + [f'COPY (SELECT {projection} FROM {table} WHERE {where} ORDER BY {order}) TO STDOUT'],
                                   stdout=subprocess.PIPE)
        digest = hashlib.sha256()
        size = rows = 0
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b''):
            digest.update(chunk)
            size += len(chunk)
            rows += chunk.count(b'\n')
        if process.wait() != 0:
            raise RuntimeError('Project database fingerprint failed')
        fingerprints[table] = {'rows': rows, 'bytes_hashed': size, 'sha256': digest.hexdigest()}

    configuration = json.loads(sql("""SELECT json_agg(row_to_json(m)) FROM
     (SELECT id,region,ruleset_id,house_id,source_kind,enabled,verified,interval_seconds
     FROM markets ORDER BY id) m"""))
    assert [(m['id'], m['house_id'], m['interval_seconds']) for m in configuration if m['enabled']] == [(2, 114, 300)]
    assert sql('SELECT count(*) FROM retention_batches') == '0'
    assert sql('SELECT count(*) FROM retention_policy WHERE approved_hash IS NOT NULL OR approved_at IS NOT NULL') == '0'
    revision = sql('SELECT version_num FROM alembic_version')
    if revision != args.expected_revision:
        raise ValueError('Database revision differs from the explicit deployment expectation')
    if previous:
        assert fingerprints == previous['fingerprints'], 'Pre-existing row fingerprints changed; inspect before acceptance'
        assert configuration == previous['collection_configuration'], 'Collection configuration changed'
    result = {'format_version': 2, 'columns': columns, 'schema_revision': revision,
              'original_schema_revision': previous['original_schema_revision'] if previous else revision,
              'checked_at': datetime.now(timezone.utc).isoformat(), 'cutoffs': cutoffs,
              'fingerprints': fingerprints, 'collection_configuration': configuration,
              'all_preexisting_rows_identical': bool(previous), 'historical_retention_authorized': False,
              'historical_retention_batches': 0,
              'database_bytes': int(sql('SELECT pg_database_size(current_database())')),
              'recent_collection_runs': json.loads(sql("""SELECT json_agg(row_to_json(r)) FROM
     (SELECT id,market_id,checked_at,status,http_status,duration_seconds,error
     FROM collection_runs WHERE market_id=2 ORDER BY id DESC LIMIT 6) r"""))}
    output = artifact(args.output) if args.output else baseline
    if args.action == 'verify' and output == baseline:
        raise ValueError('Verify requires a separate --output to retain the original baseline')
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'output': str(output.relative_to(ROOT)), 'cutoffs': cutoffs,
                      'all_preexisting_rows_identical': bool(previous),
                      'only_enabled_house': 114, 'historical_retention_authorized': False}))


if __name__ == '__main__':
    main()
