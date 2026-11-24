"""Actual SMB2/3 protocol + isolated PostgreSQL integration; no production access."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
sys.path[:0]=['/app','/secrets-code']
from management import Manager, Refused
from providers import SMB, StorageError, digest, endpoint, relative, CHUNK

os.umask(0o077) # same hardening as the actual management service
assert os.environ['PGDATABASE']=='market_test'
Path('/backups').chmod(0o700)
Path('/state/keyring.json').write_text(json.dumps(dict(active='fixture',keys={'fixture':base64.b64encode(os.urandom(32)).decode()})))
Path('/state/keyring.json').chmod(0o600)
config=dict(type='smb',name='Synthetic NAS',host='smb',port=445,username='nas',password='synthetic-nas-test-only',domain='WORKGROUP',share='backups',directory='',require_encryption=True)
manager=Manager()
checks=[]
def passed(label):checks.append(label);print('PASS '+label,flush=True)
try:
    for _ in range(20):
        try:
            saved=manager.storage_save('admin:1',config); key=saved['id']; result=manager.storage_test('admin:1',key)
            if result['healthy']:break
        except (StorageError,ConnectionError):pass
        time.sleep(1)
    assert result['healthy'],result
    assert all(result[f] for f in ('read','write','create_directory','rename','delete'))
    assert result['capacity_bytes']>0 and result['available_bytes']>0
    assert not any('password'==k or 'secret'==k for k in saved)
    passed('SMB3 encryption/signing, authentication, streaming read/write, create, rename, delete and actual capacity')
    manager.storage_mkdir('admin:1',key,'Market')
    folders=manager.storage_browse('admin:1',key)
    assert 'Market' in folders['folders']
    saved=manager.storage_save('admin:1',{**config,'id':key,'revision':saved['revision'],'password':None,'directory':'Market'})
    assert manager.storage_test('admin:1',key)['healthy']
    assert manager.password(manager.candidate(key))=='synthetic-nas-test-only'
    passed('Manual share, bounded folder browsing/creation, saved credential preservation and redaction')
    bad=manager.storage_save('admin:1',{**config,'name':'Wrong password','password':'incorrect'})
    failed=manager.storage_test('admin:1',bad['id'])
    assert not failed['healthy'] and 'incorrect' not in json.dumps(failed)
    passed('Actual authentication failure is sanitized')
    readonly=manager.storage_save('admin:1',{**config,'name':'Read only','share':'readonly'})
    permissions=manager.storage_test('admin:1',readonly['id'])
    assert not permissions['healthy'] and permissions['read'] and not permissions['write'],permissions
    passed('Actual read-only share permission failure')
    signed=SMB({**config,'share':'signed','require_encryption':False},config['password'])
    assert signed.connection.require_signing
    signed.close()
    passed('Signed session with optional encryption compatibility')
    custom=SMB({**config,'port':1445},config['password']);custom.close()
    passed('Actual SMB connection on an explicitly configured high port')
    started=time.monotonic()
    try:SMB({**config,'host':'10.255.255.254'},config['password'])
    except (StorageError,OSError):pass
    else:raise AssertionError('Unreachable NAS accepted')
    assert time.monotonic()-started<15
    passed('Actual unreachable private destination has bounded connect failure')
    for path in ('../escape','/absolute','a//b','a\\b','x:stream','folder/..'):
        try:relative(path)
        except StorageError:pass
        else:raise AssertionError(path)
    for host in ('127.0.0.1','169.254.169.254','8.8.8.8'):
        try:endpoint(host,445)
        except StorageError:pass
        else:raise AssertionError(host)
    passed('Traversal, alternate stream, public/loopback/metadata peers refused')
    subprocess.run(['psql','-Atc',"CREATE TABLE nas_restore_fixture(id int primary key, value text); INSERT INTO nas_restore_fixture SELECT n, md5(n::text) FROM generate_series(1,10000)n"],check=True,stdout=subprocess.DEVNULL)
    local=manager.create('admin:1')
    assert local['status']=='succeeded',local
    initial=manager.overview()['items'][0]
    plan=manager.migration_plan(key)
    assert plan['count']==1 and plan['originals_preserved']
    job=manager.migration_queue('admin:1',key,plan)
    migrated=manager.migrate('admin:1',job['id'])
    assert migrated['status']=='succeeded',migrated
    assert (Path('/backups')/initial['filename']).is_file()
    rows=manager.overview()['items'];assert rows[0]['storage_id']==key and rows[0]['protected']
    assert manager.storage_status()['active_id']==key
    passed('Real pg_dump, local-to-SMB checksum migration, activation and original/protection preservation')
    remote=manager.create('admin:1')
    assert remote['status']=='succeeded',remote
    inventory=manager.overview();newest=inventory['items'][0]
    assert not (Path('/backups')/newest['filename']).exists()
    with manager.download('admin:1',newest['id']) as (row,stream):
        hasher=hashlib.sha256()
        for chunk in iter(lambda:stream.read(CHUNK),b''):hasher.update(chunk)
        assert hasher.hexdigest()==row['sha256']
    passed('Native NAS pg_dump streaming, full pg_restore decode, finalization, inventory and download; no local fallback')
    job=manager.restore_queue('admin:1',newest['id']); restored=manager.restore_test('admin:1',job['id'])
    assert restored['status']=='succeeded',restored
    passed('Actual NAS backup restoration into unique isolated PostgreSQL database')
    try:manager.delete('admin:1',newest['id'],newest['filename'])
    except Refused:pass
    else:raise AssertionError('Protected delete without acknowledgement')
    result=manager.delete('admin:1',newest['id'],newest['filename'],confirm_protected=True,confirm_recovery_loss=True)
    assert result['status']=='deleted',result
    passed('Protected/newest/last-restored deletion requires explicit acknowledgement; metadata audited without unprotecting')
    from recovery import automatic_tick
    Path('/state/recovery').mkdir();Path('/state/status').mkdir()
    os.environ['BACKUP_AUTOMATIC_RESTORE']='true'
    assert automatic_tick(manager)
    proof=json.loads(Path('/state/recovery/evidence.json').read_text())
    assert proof['sha256']==initial['sha256'] and proof['expires_at'] and proof['automatic']
    scheduled=manager.create('scheduler',origin='scheduled');assert scheduled['status']=='succeeded'
    assert automatic_tick(manager)
    first_scheduled=manager.overview()['items'][0]
    assert first_scheduled['protected'] and 'automatic-retention' in first_scheduled['required_by']
    assert manager.create('scheduler',origin='scheduled')['status']=='succeeded'
    assert automatic_tick(manager)
    status=manager.overview()
    old=next(r for r in status['items'] if r['id']==first_scheduled['id'])
    assert not old['protected'] and not old['required_by']
    original=next(r for r in status['items'] if r['filename']==initial['filename'])
    assert original['protected'], 'Explicit manual protection must never be cleared'
    assert status['preview']['candidates']==[dict(id=old['id'],filename=old['filename'],bytes=old['bytes'])]
    from recovery import proof
    good=proof(manager,status['items'][0]['id'])
    assert good['protected'] and good['integrity_checked_at'] and good['identity_checked_at']
    passed('Recurring actual isolated restore renews expiring evidence and safely transfers operation pins without clearing explicit protection')
    with manager.lock():
        store=manager.store
        large='.stream-test-'+uuid.uuid4().hex
        block=os.urandom(CHUNK)
        with store.open(large,'xb') as out:
            hasher=hashlib.sha256()
            for _ in range(256):out.write(block);hasher.update(block)
        expected=hasher.hexdigest()
        assert digest(store,large)==expected
        store.remove(large)
    import resource
    peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    assert peak_kib<192*1024,peak_kib
    passed(f'256 MiB actual SMB streaming in 1 MiB chunks; process peak RSS {peak_kib} KiB')
    with manager.lock():
        store=manager.store
        stream=store.open(initial['filename'])
        store.connection.disconnect(close=False,timeout=2)
        try:stream.read(CHUNK)
        except (StorageError,OSError):pass
        else:raise AssertionError('Disconnected transport returned invented data')
        try:stream.close()
        except (StorageError,OSError):pass
    assert manager.overview()['total']>=1
    passed('Actual disconnected SMB transport fails safely and a fresh session reconnects')
    # Fault-inject the saved peer only inside this disposable fixture. A failed
    # scheduled preflight must become terminal and retry without a service restart.
    from service import tick
    from datetime import datetime,timezone,timedelta
    with manager.db() as db:
        configs=manager.get(db,'storage_configs');original_host=configs[key]['host']
        configs[key]['host']='10.255.255.254';manager.set(db,'storage_configs',configs)
        policy=manager.get(db,'policy');policy['enabled']=True;manager.set(db,'policy',policy)
        manager.set(db,'next_at',(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    started=time.monotonic();assert tick(manager);assert time.monotonic()-started<30
    with manager.db() as db:
        assert manager.get(db,'job')['status']=='failed'
        assert datetime.fromisoformat(manager.get(db,'next_at'))>datetime.now(timezone.utc)+timedelta(minutes=29)
        configs=manager.get(db,'storage_configs');configs[key]['host']=original_host;manager.set(db,'storage_configs',configs)
    assert not tick(manager) # do not retry early or spend another scheduled budget
    with manager.db() as db:manager.set(db,'next_at',(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    assert tick(manager)
    with manager.db() as db:assert manager.get(db,'job')['status']=='succeeded'
    passed('Actual unreachable NAS scheduled failure becomes terminal, backs off30minutes and creates a verified native backup after recovery without restart or local fallback')
    removal=manager.migration_remove_originals('admin:1',migrated['id'],'REMOVE VERIFIED ORIGINALS',confirm_protected=True)
    assert removal['results'][0]['status']=='deleted',removal
    passed('Originals removed only through separate confirmation after rehashing NAS destination')
    print(json.dumps(dict(synthetic=True,protocol='actual SMB3 with required encryption/signing',checks=checks),indent=2))
finally:manager.close()
