"""Resource-bounded isolated restore verification and renewal of recovery evidence."""
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

GIB=1024**3


def target_environment():
    from management import Refused
    result=dict(os.environ)
    target=os.environ.get('RESTORE_PGHOST')
    if not target:
        if os.environ.get('PGDATABASE')!='market_test':
            raise Refused('A separate isolated restore server must be configured')
        target=os.environ.get('PGHOST')
    if target==os.environ.get('PGHOST') and os.environ.get('PGDATABASE')!='market_test':
        raise Refused('Restore verification cannot use the production PostgreSQL server')
    result.update(PGHOST=target,PGPORT=os.environ.get('RESTORE_PGPORT','5432'),
        PGUSER=os.environ.get('RESTORE_PGUSER','market'),PGDATABASE='market_test',PGCONNECT_TIMEOUT='5')
    if os.environ.get('RESTORE_PGPASSWORD_FILE'):
        result['PGPASSWORD']=Path(os.environ['RESTORE_PGPASSWORD_FILE']).read_text().strip()
    elif os.environ.get('RESTORE_PGPASSWORD'):result['PGPASSWORD']=os.environ['RESTORE_PGPASSWORD']
    result['PGOPTIONS']='-c statement_timeout=600000 -c lock_timeout=2000'
    return result


def output(command,env,timeout=20):
    return subprocess.check_output(command,env=env,timeout=timeout,stderr=subprocess.DEVNULL).decode().strip()


def atomic_json(directory,name,value):
    from management import Refused
    root=Path(directory)
    if not root.is_dir() or root.is_symlink():raise Refused('Recovery evidence directory is unavailable')
    temporary=root/('.recovery-'+uuid.uuid4().hex)
    try:
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
        with os.fdopen(fd,'w') as stream:
            json.dump(value,stream);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,root/name)
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temporary.unlink(missing_ok=True)


def restore(manager,actor,job_id,*,automatic=False):
    from management import Refused,stamp
    with manager.lock(),manager.db() as db:
        job=manager.get(db,'restore',{})
        if job.get('id')!=job_id or job.get('status')!='queued':raise Refused('Restore job changed')
        job.update(status='running',started_at=stamp());manager.set(db,'restore',job);db.commit()
        database='market_test_restore_'+uuid.uuid4().hex[:20]
        created=False;env=None
        try:
            if os.environ.get('BACKUP_RESTORE_TEST_ENABLED')!='true':raise Refused('Isolated restore capacity is not configured')
            env=target_environment()
            previous=manager.get(db,'restore_cleanup')
            if previous:
                if not re.fullmatch(r'market_test_restore_[a-f0-9]{20}',previous):raise Refused('Unsafe restore cleanup receipt')
                subprocess.run(['dropdb','--if-exists','--force',previous],env=env,check=True,timeout=30,stderr=subprocess.DEVNULL)
                manager.set(db,'restore_cleanup',None);db.commit()
            row=manager.find(db,job['backup_id'])
            if manager.checksum(row['filename'])!=row['sha256']:raise Refused('Archive checksum failed')
            major=int(output(['psql','-Atc','SHOW server_version_num'],env))//10000
            manifest=manager.read_json(row['filename'][:-5]+'.json')
            if manifest['postgres_major']!=major:raise Refused('Isolated restore PostgreSQL major version must match the archive')
            maximum=int(os.environ.get('RESTORE_MAX_DATABASE_BYTES',str(32*GIB)))
            reserve=int(os.environ.get('RESTORE_MIN_FREE_BYTES',str(2*GIB)))
            filesystem=Path(os.environ.get('RESTORE_FILESYSTEM_PATH','/tmp'))
            size=int(output(['psql','-Atc','SELECT pg_database_size(current_database())'],os.environ))
            disk=os.statvfs(filesystem)
            if size>maximum or disk.f_bavail*disk.f_frsize<2*size+reserve:
                raise Refused('Isolated restore capacity or filesystem safety reserve is insufficient')
            manager.set(db,'restore_cleanup',database);job['database']=database;manager.set(db,'restore',job);db.commit()
            subprocess.run(['createdb',database],env=env,check=True,timeout=30,stderr=subprocess.DEVNULL);created=True
            next_check=0
            def resource_check():
                nonlocal next_check
                if time.monotonic()<next_check:return
                next_check=time.monotonic()+3
                disk=os.statvfs(filesystem)
                measured=int(output(['psql','-Atc',"SELECT pg_database_size('"+database+"')"],env,timeout=10))
                if measured>maximum or disk.f_bavail*disk.f_frsize<reserve:
                    raise Refused('Isolated restore exceeded its storage budget; recovery remains paused')
            with manager.store.open(row['filename']) as source:
                manager.decode(source,database,env=env,check=resource_check)
            # pg_restore validated constraints/index creation. Capture actual schema and table populations.
            tables=output(['psql','-d',database,'-Atc',"SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]') FROM pg_tables WHERE schemaname='public'"],env)
            names=json.loads(tables)
            counts={}
            for name in names:
                if not re.fullmatch('[a-z_][a-z_0-9]{0,62}',name):raise Refused('Unexpected restored schema identifier')
                counts[name]=int(output(['psql','-d',database,'-Atc','SELECT count(*) FROM "'+name+'"'],env,timeout=120))
            evidence=dict(tables=len(names),row_counts=counts,database_bytes=int(output(['psql','-Atc',"SELECT pg_database_size('"+database+"')"],env)))
            if 'alembic_version' in names:
                evidence['migration']=output(['psql','-d',database,'-Atc','SELECT version_num FROM alembic_version'],env)
            manifest.update(restoration_verified_at=stamp(),restored=evidence)
            if automatic:
                # An operation pin is distinct from an administrator's explicit protected flag.
                manifest['recovery_pin']=True
                manifest['required_by']=sorted(set(manifest.get('required_by',[]))|{'automatic-retention'})
            manager.write_json(row['filename'][:-5]+'.json',manifest)
            if automatic:publish_recovery(manager,db,actor,row,manifest)
            job.update(status='succeeded',finished_at=stamp(),restored=evidence,backup_id=row['id'])
            if automatic:manager.set(db,'automatic_restore_retry',None)
            manager.receipt(db,actor,'restore.verified',dict(id=job_id,backup_id=row['id'],automatic=automatic))
        except Exception as exc:
            job.update(status='failed',finished_at=stamp(),error=str(exc) if isinstance(exc,Refused) else 'Isolated restore failed; production and valid recovery copies were preserved')
            manager.receipt(db,actor,'restore.failed',dict(id=job_id))
        finally:
            if created:
                try:
                    subprocess.run(['dropdb','--if-exists','--force',database],env=env,check=True,timeout=30,stderr=subprocess.DEVNULL)
                    manager.set(db,'restore_cleanup',None)
                except Exception:job['cleanup_pending']=True
            manager.set(db,'restore',job)
        return job


def publish_recovery(manager,db,actor,row,manifest):
    from management import Refused,stamp
    directory=os.environ.get('BACKUP_RECOVERY_DIRECTORY')
    approval=os.environ.get('RETENTION_LOCAL_RECOVERY_APPROVAL','')
    if not directory or not approval:raise Refused('Owner-approved recovery evidence destination is unavailable')
    created=datetime.fromisoformat(manifest['created_at'])
    if datetime.now(timezone.utc)-created>=timedelta(hours=24):raise Refused('Archive creation is older than the retention recovery window; a new scheduled backup is needed')
    evidence=dict(backup_id=row['id'],filename=row['filename'],sha256=manifest['sha256'],restored_archive_sha256=manifest['sha256'],
        local_restoration_verified_at=manifest['restoration_verified_at'],archive_created_at=manifest['created_at'],expires_at=(created+timedelta(hours=24)).isoformat(),owner_approval_reference=approval,
        off_vm_verified=False,off_vm_verified_at=None,automatic=True,verified_at=stamp())
    atomic_json(directory,'evidence.json',evidence)
    if os.environ.get('BACKUP_STATUS_DIRECTORY'):
        atomic_json(os.environ['BACKUP_STATUS_DIRECTORY'],'status.json',dict(status='ok',filename=row['filename'],
            last_success=manifest['created_at'],bytes=manifest['bytes'],last_restoration_verified_at=manifest['restoration_verified_at'],
            restored_archive_filename=row['filename'],restored_archive_sha256=manifest['sha256'],restored_archive_created_at=manifest['created_at']))
    # Only release pins that this automation created. Explicit protection is never cleared.
    old=manager.get(db,'automatic_recovery')
    manager.set(db,'automatic_recovery',dict(backup_id=row['id'],storage_id=row['storage_id'],filename=row['filename'],
        verified_at=manifest['restoration_verified_at'],expires_at=(created+timedelta(hours=24)).isoformat(),
        sha256=manifest['sha256'],bytes=manifest['bytes'],file_identity=manifest['file_identity']))
    manager.receipt(db,actor,'recovery.renewed',dict(backup_id=row['id'],expires_at=(created+timedelta(hours=24)).isoformat()))
    db.commit()
    if old and old['backup_id']!=row['id']:
        try:
            with manager.location(old['storage_id']):
                previous=manager.read_json(old['filename'][:-5]+'.json')
                if previous.get('recovery_pin'):
                    previous['recovery_pin']=False
                    previous['required_by']=[v for v in previous['required_by'] if v!='automatic-retention']
                    manager.write_json(old['filename'][:-5]+'.json',previous)
                    manager.receipt(db,actor,'recovery.previous_pin.released',dict(backup_id=old['backup_id']))
        except Exception:
            # Never lose the new proof because an old pin could not be released; fail safe by retaining that copy.
            manager.receipt(db,actor,'recovery.previous_pin.retained',dict(backup_id=old['backup_id']))


def automatic_tick(manager):
    from management import stamp,date
    if os.environ.get('BACKUP_AUTOMATIC_RESTORE')!='true':return False
    with manager.lock(),manager.db() as db:
        manager.idle(db)
        retry=manager.get(db,'automatic_restore_retry')
        if retry and date(retry)>datetime.now(timezone.utc):return False
        rows,_=manager.rows()
        eligible=[r for r in rows if r['verification']=='archive_integrity_verified' and datetime.now(timezone.utc)-date(r['created_at'])<timedelta(hours=24)]
        if not eligible:return False
        newest=eligible[0]
        current=manager.get(db,'automatic_recovery',{})
        if current.get('backup_id')==newest['id'] and current.get('verified_at'):return False
        if newest.get('storage_id')=='local' and newest.get('restoration_verified_at') and datetime.now(timezone.utc)-date(newest['restoration_verified_at'])<timedelta(hours=24):
            manager._location='local'
            manifest=manager.read_json(newest['filename'][:-5]+'.json')
            if manifest.get('restored') and manager.checksum(newest['filename'])==manifest['sha256']:
                manifest['recovery_pin']=True
                manifest['required_by']=sorted(set(manifest.get('required_by',[]))|{'automatic-retention'})
                manager.write_json(newest['filename'][:-5]+'.json',manifest)
                publish_recovery(manager,db,'scheduler',newest,manifest)
                manager.receipt(db,'scheduler','recovery.adopted.verified_local',dict(backup_id=newest['id'],original_verified_at=manifest['restoration_verified_at']))
                return True
        manager.set(db,'automatic_restore_retry',(datetime.now(timezone.utc)+timedelta(minutes=30)).isoformat())
        job=dict(id=uuid.uuid4().hex,status='queued',backup_id=newest['id'],actor='scheduler',requested_at=stamp(),automatic=True)
        manager.set(db,'restore',job);manager.receipt(db,'scheduler','restore.queued',job)
    restore(manager,'scheduler',job['id'],automatic=True)
    return True


def proof(manager,key):
    """Cheap identity check between full daily restore/checksum verifications."""
    from management import Refused
    with manager.lock(),manager.db() as db:
        record=manager.get(db,'automatic_recovery',{})
        if record.get('backup_id')!=key:raise Refused('A current verified recovery record is required')
        row=manager.find(db,key)
        manifest=manager.read_json(row['filename'][:-5]+'.json')
        info=manager.store.info(row['filename'])
        if (record.get('sha256')!=manifest.get('sha256') or record.get('bytes')!=info['bytes'] or
            record.get('file_identity')!=info['identity'] or record.get('verified_at')!=manifest.get('restoration_verified_at') or
            not row['protected'] or 'automatic-retention' not in row['required_by']):
            raise Refused('Recovery archive identity changed; a new complete verification is required')
        return dict(manifest,protected=True,integrity_checked_at=record['verified_at'],identity_checked_at=__import__('management').stamp())
