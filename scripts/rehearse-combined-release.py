"""Restore and migrate only the dedicated market_restore database; fingerprint every original column."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.parse import quote
import backups

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = 'twichui-market-restore-db-1'
COMMAND = ['docker', '--context', 'rootless', 'exec', '-e', 'PGOPTIONS=-c default_transaction_read_only=on',
           CONTAINER, 'psql', '-U', 'market', '-d', 'market_restore', '-Atqc']


def sql(query):
    return subprocess.check_output(COMMAND + [query], text=True).strip()


def fingerprint(columns=None):
    tables = json.loads(sql("SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND tablename<>'alembic_version'"))
    columns = columns or {table: json.loads(sql("SELECT json_agg(column_name ORDER BY ordinal_position) FROM information_schema.columns WHERE table_schema='public' AND table_name='" + table + "'")) for table in tables}
    result = {}
    for table, fields in columns.items():
        assert table in tables and all(field.replace('_', '').isalnum() for field in fields)
        keys = sql("SELECT string_agg(quote_ident(a.attname),',' ORDER BY c.ord) FROM pg_index i CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY c(attnum,ord) JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=c.attnum WHERE i.indrelid='" + table + "'::regclass AND i.indisprimary")
        selected = ','.join('"' + field + '"' for field in fields)
        order = keys or selected
        command = COMMAND + [f'COPY (SELECT {selected} FROM "{table}" ORDER BY {order}) TO STDOUT']
        process = subprocess.Popen(command, stdout=subprocess.PIPE)
        digest = hashlib.sha256(); rows = size = 0
        for chunk in iter(lambda: process.stdout.read(1024 * 1024), b''):
            digest.update(chunk); rows += chunk.count(b'\n'); size += len(chunk)
        assert process.wait() == 0
        result[table] = {'rows': rows, 'bytes': size, 'sha256': digest.hexdigest()}
    return columns, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    archive = args.archive.resolve(); output = args.output.resolve()
    assert archive.parent == ROOT / 'backups' and archive.suffix == '.dump'
    assert output.is_relative_to(ROOT / 'artifacts')
    manifest = json.loads(archive.with_suffix('.json').read_text())
    assert backups.sha256(archive) == manifest['sha256'] and archive.stat().st_size == manifest['bytes']
    compose = backups.compose('restore')
    assert not subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'name=^/' + CONTAINER + '$'], text=True).strip(), 'Dedicated restore project is already in use'
    envfile = None
    try:
        backups.run(compose + ['up', '-d', '--wait', '--wait-timeout', '90'])
        assert sql('SELECT current_database()') == 'market_restore'
        with archive.open('rb') as source:
            backups.run(compose + ['exec', '-T', 'db', 'pg_restore', '-U', 'market', '-d', 'market_restore', '--no-owner', '--no-acl', '--exit-on-error'], stdin=source)
        before_revision = sql('SELECT version_num FROM alembic_version')
        assert before_revision == '0012'
        columns, before = fingerprint()
        config = json.loads(subprocess.check_output(['docker', 'inspect', CONTAINER]))[0]
        env = dict(value.split('=', 1) for value in config['Config']['Env'] if '=' in value)
        fd, name = tempfile.mkstemp(prefix='restore-env-', dir=ROOT / 'artifacts'); envfile = Path(name)
        with os.fdopen(fd, 'w') as stream:
            stream.write('DATABASE_URL=postgresql+psycopg://market:' + quote(env['POSTGRES_PASSWORD'], safe='') + '@db:5432/market_restore\n')
        started = time.monotonic()
        command = ['docker', 'run', '--rm', '--network', 'twichui-market-restore_default', '--memory', '384m', '--cpus', '0.5', '--read-only', '--tmpfs', '/tmp:size=32m', '--env-file', str(envfile), args.image]
        backups.run(command + ['alembic', 'upgrade', 'head'])
        duration = time.monotonic() - started
        backups.run(command + ['alembic', 'check'])
        revision = sql('SELECT version_num FROM alembic_version')
        assert revision == 'meta_20261114'
        _, after = fingerprint(columns)
        assert before == after, 'Original restored data changed during migration'
        assert sql("SELECT extname FROM pg_extension WHERE extname='pg_trgm'") == 'pg_trgm'
        index = sql("SELECT indexdef FROM pg_indexes WHERE indexname='ix_item_metadata_catalog_search'")
        assert 'USING gin' in index and 'gin_trgm_ops' in index
        result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'archive': archive.name,
                  'archive_sha256': manifest['sha256'], 'before_revision': before_revision,
                  'migration_order': ['0012', '0013', 'meta_20261114'], 'revision': revision,
                  'migration_seconds': round(duration, 3), 'schema_drift': False,
                  'original_columns': columns, 'before': before, 'after': after,
                  'all_original_rows_preserved': True, 'pg_trgm': True, 'catalog_index': index,
                  'production_database_touched': False}
        output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'output': str(output.relative_to(ROOT)), 'all_original_rows_preserved': True, 'migration_seconds': result['migration_seconds']}))
    finally:
        if envfile: envfile.unlink(missing_ok=True)
        backups.run(compose + ['down'])


if __name__ == '__main__':
    main()
