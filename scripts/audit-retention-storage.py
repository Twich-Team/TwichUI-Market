"""Read-only, project-scoped live audit. Never emits environment or credentials."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ['docker', '--context', 'rootless']


def run(args):
    return subprocess.check_output(args, timeout=90).decode()


def query(sql):
    output = run(DOCKER + ['exec', 'twichui-market-db-1', 'psql', '-XAtq', '-U', 'market', '-d', 'market',
        '-c', "BEGIN READ ONLY; SET LOCAL statement_timeout='20s'; " + sql + '; COMMIT;'])
    return [json.loads(line) for line in output.splitlines() if line.startswith(('{', '['))]


def main():
    result = {'observed_at': datetime.now(timezone.utc).isoformat(), 'provenance': 'read-only live production'}
    ids = run(DOCKER + ['ps', '-aq', '--filter', 'label=com.docker.compose.project=twichui-market']).split()
    containers = json.loads(run(DOCKER + ['inspect', *ids]))
    result['containers'] = [dict(name=c['Name'], image=c['Image'], started=c['State']['StartedAt'],
        status=c['State']['Status'], oom=c['State']['OOMKilled'], restarts=c['RestartCount'],
        revision=c['Config']['Labels'].get('org.opencontainers.image.revision'),
        memory=c['HostConfig']['Memory'], cpus=c['HostConfig']['NanoCpus']/1e9,
        volumes=[dict(name=m.get('Name'), destination=m['Destination'], writable=m['RW']) for m in c['Mounts']]) for c in containers]
    result['database'] = query("SELECT json_build_object('bytes',pg_database_size(current_database()),'schema',(SELECT version_num FROM alembic_version))")[0]
    result['tables'] = query("SELECT row_to_json(t) FROM (SELECT relname,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze,autovacuum_count,pg_table_size(relid) AS table_bytes,pg_indexes_size(relid) AS index_bytes,pg_total_relation_size(relid) AS total_bytes FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC) t")
    result['policies'] = query('SELECT row_to_json(p) FROM retention_policy p')
    result['automation'] = query("SELECT json_build_object('enabled',enabled,'authorized_at',authorized_at,'next_run_at',next_run_at,'execution_hash',\"authorization\"::json->>'execution_hash') FROM retention_automation")
    result['executions'] = query('SELECT row_to_json(t) FROM (SELECT status,reason,count(*),max(finished_at) AS latest FROM retention_executions GROUP BY status,reason) t')
    result['recent_executions'] = query('SELECT row_to_json(t) FROM (SELECT * FROM retention_executions ORDER BY id DESC LIMIT 20) t')
    result['removed'] = query('SELECT row_to_json(t) FROM (SELECT stage,sum(rows_removed),max(created_at) AS latest FROM retention_batches GROUP BY stage) t')
    result['markets'] = query('SELECT row_to_json(t) FROM (SELECT id,house_id,enabled,interval_seconds,last_success,failures,last_error FROM markets) t')
    result['tiers'] = query("SELECT json_build_object('observations',(SELECT json_build_object('count',count(*),'oldest',min(retrieved_at),'newest',max(retrieved_at)) FROM observations),'snapshots',(SELECT json_build_object('count',count(*),'oldest',min(created_at),'newest',max(created_at),'reported_listings',sum(listing_count),'raw_snapshots',count(*) FILTER(WHERE raw_retained),'statistic_snapshots',count(*) FILTER(WHERE statistics_retained)) FROM snapshots),'daily',(SELECT json_build_object('count',count(*),'oldest',min(day),'newest',max(day)) FROM daily_observations),'captures',(SELECT json_build_object('count',count(*),'retained',count(*) FILTER(WHERE compressed_payload IS NOT NULL),'compressed_bytes',sum(octet_length(compressed_payload))) FROM feed_captures))")[0]
    result['ingestion'] = query("SELECT row_to_json(t) FROM (SELECT date_trunc('day',retrieved_at) AS day,count(*),sum(payload_bytes) AS payload_bytes FROM observations WHERE retrieved_at>now()-interval '7 days' GROUP BY 1 ORDER BY 1) t")
    result['backup_state'] = json.loads(run(DOCKER + ['exec','twichui-market-backup-manager-1','python3','-c',"import sqlite3,json; c=sqlite3.connect('file:/state/management.sqlite?mode=ro',uri=True); print(json.dumps({k:json.loads(v) for k,v in c.execute(\"select key,value from settings where key in ('policy','job','next_at')\")}))"]))
    files = list((ROOT.parents[1]/'backups').glob('*')) if ROOT.name == 'backup-nas' else list((ROOT/'backups').glob('*'))
    result['local_backups'] = [dict(name=p.name, bytes=p.lstat().st_size, symlink=p.is_symlink()) for p in files]
    result['disk'] = run(['df','-B1',str(ROOT)])
    # Only this project's named volumes; never inspect unrelated volumes.
    result['volumes'] = run(DOCKER+['system','df','-v']) if False else [m.get('Name') for c in containers for m in c['Mounts'] if m.get('Name')]
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
