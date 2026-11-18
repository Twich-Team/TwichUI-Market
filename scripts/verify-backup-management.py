"""Run INSIDE backup-check against an isolated PostgreSQL 17 market_test only.
Creates and restores actual custom-format archives, exercises keep-two rotation,
and compares the unchanged source rows after deletion. Never accepts production.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,'/app')
from management import Manager, Refused


def sql(statement, database='market_test'):
    return subprocess.check_output(['psql','-d',database,'-Atc',statement],stderr=subprocess.DEVNULL).decode().strip()


assert os.environ['PGDATABASE']=='market_test'
assert sql('SELECT current_database()')=='market_test'
sql('CREATE TABLE IF NOT EXISTS backup_fixture (id integer primary key, value text); INSERT INTO backup_fixture SELECT n, md5(n::text) FROM generate_series(1,200) n ON CONFLICT DO NOTHING')
fingerprint=sql("SELECT md5(string_agg(id::text||value,',' ORDER BY id)) FROM backup_fixture")
manager=Manager()
try:
    assert manager.overview()['total']==0, 'Requires fresh disposable backup fixtures'
    assert not manager.overview()['policy']['enabled']
    policy=manager.overview()['policy'];revision=policy.pop('revision')
    manager.policy('admin:1',revision,{**policy,'daily':2})
    receipts=[]
    for days in (2,1,0):
        job=manager.create('scheduler',origin='scheduled')
        assert job['status']=='succeeded',job
        row=manager.overview()['items'][0]
        # Test clock dates establish different daily buckets; archive bytes remain exact.
        manifest=manager.read_json(row['filename'][:-5]+'.json')
        manifest['created_at']=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        manager.write_json(row['filename'][:-5]+'.json',manifest)
        receipts.append({'id':row['id'],'filename':row['filename'],'sha256':row['sha256']})
    remaining=manager.overview()
    assert remaining['total']==2
    assert not (Path('/backups')/receipts[0]['filename']).exists()
    assert {r['id'] for r in remaining['items']}=={r['id'] for r in receipts[1:]}
    # Restore an actual surviving archive into an explicitly disposable database.
    sql('CREATE DATABASE market_restore')
    newest=remaining['items'][0]
    with (Path('/backups')/newest['filename']).open('rb') as source:
        subprocess.run(['pg_restore','-d','market_restore','--no-owner','--no-acl','--exit-on-error'],stdin=source,check=True,stderr=subprocess.DEVNULL)
    assert sql("SELECT md5(string_agg(id::text||value,',' ORDER BY id)) FROM backup_fixture",'market_restore')==fingerprint
    manifest=manager.read_json(newest['filename'][:-5]+'.json')
    assert manifest['restoration_verified_at'] is None, 'Integrity alone must never claim restore proof'
    manifest.update(restoration_verified_at=datetime.now(timezone.utc).isoformat(),restored={'backup_fixture_rows':200},protected=True,required_by=['isolated-rehearsal'])
    manager.write_json(newest['filename'][:-5]+'.json',manifest)
    with manager.download('admin:1',newest['id']) as (row,stream):
        assert hashlib.sha256(stream.read()).hexdigest()==row['sha256']
    # v2 manifests keep the fields consumed by the existing restoration helper.
    assert all(key in manifest for key in ('version','filename','source','created_at','bytes','sha256','restoration_verified_at','restored'))
    old=next(row for row in remaining['items'] if row['id']!=newest['id'])
    deletion=manager.delete('admin:1',old['id'],old['filename'])
    assert deletion['archive_removed'] and deletion['manifest_removed']
    try:manager.delete('admin:1',newest['id'],newest['filename'])
    except Refused:pass
    else:raise AssertionError('Protected restored recovery point deleted')
    assert sql("SELECT md5(string_agg(id::text||value,',' ORDER BY id)) FROM backup_fixture")==fingerprint
    result=dict(synthetic=True,postgres_major=17,archive_integrity='full pg_restore decode and SHA-256',
        keep_two={'created':[r['filename'] for r in receipts],'removed':receipts[0]['filename'],'remaining_after_rotation':[r['filename'] for r in remaining['items']]},
        isolated_restore_rows=200,source_fingerprint_unchanged=True,manual_deletion=deletion,protected_point_retained=True)
    print(json.dumps(result,indent=2))
finally:
    manager.close()
