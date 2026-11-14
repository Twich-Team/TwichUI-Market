"""Bounded daily PostgreSQL backups; no Docker socket or host scheduler required."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
from datetime import datetime, timezone

DIRECTORY=Path('/backups')
stopping=False


def write_status(payload):
    public=Path('/status')
    public.mkdir(mode=0o755,exist_ok=True)
    public.chmod(0o755)
    target=public/'status.json'
    if target.exists():
        previous=json.loads(target.read_text())
        for key in ('last_success','last_restoration_verified_at','restored_archive_filename','restored_archive_sha256','restored_archive_created_at'):
            if key not in payload and key in previous:
                payload[key]=previous[key]
    temporary=public/'status.partial'
    fd=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY,0o644)
    with os.fdopen(fd,'w') as stream:
        json.dump(payload,stream)
    temporary.chmod(0o644)
    temporary.replace(target)


def create():
    os.umask(0o077)
    DIRECTORY.mkdir(mode=0o700,exist_ok=True)
    with (DIRECTORY/'.backup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        keep=max(1,min(int(os.environ.get('BACKUP_KEEP','7')),30))
        budget=int(os.environ.get('MAX_BACKUP_BYTES',str(2*1024**3)))
        size=int(subprocess.check_output(['psql','-Atc','SELECT pg_database_size(current_database())']))
        used=sum(path.stat().st_size for path in DIRECTORY.glob('*.dump'))
        if used+size>budget or shutil.disk_usage(DIRECTORY).free<size+2*1024**3:
            raise ValueError('Backup disk budget or reserve reached')
        filename='market-development-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.dump'
        target=DIRECTORY/filename
        temporary=target.with_suffix('.partial')
        try:
            with temporary.open('xb') as stream:
                subprocess.run(['pg_dump','--format=custom','--no-owner','--no-acl'],stdout=stream,check=True)
                stream.flush()
                os.fsync(stream.fileno())
            digest=hashlib.sha256()
            with temporary.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):
                    digest.update(chunk)
            temporary.replace(target)
            manifest={'version':1,'filename':filename,'source':'development','created_at':datetime.now(timezone.utc).isoformat(),
                'bytes':target.stat().st_size,'sha256':digest.hexdigest(),'restoration_verified_at':None}
            target.with_suffix('.json').write_text(json.dumps(manifest,indent=2)+'\n')
            write_status({'status':'ok','last_success':manifest['created_at'],'filename':filename,
                          'bytes':manifest['bytes'],'keep':keep})
            for old in sorted(DIRECTORY.glob('market-development-*.dump'),reverse=True)[keep:]:
                old.unlink()
                old.with_suffix('.json').unlink(missing_ok=True)
        finally:
            temporary.unlink(missing_ok=True)


def stop(*_):
    global stopping
    stopping=True


def main():
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    interval=max(3600,int(os.environ.get('BACKUP_INTERVAL_SECONDS','86400')))
    while not stopping:
        try:
            create()
            print('Backup completed',flush=True)
        except Exception:
            # Do not include transport exceptions/DSNs in output.
            try:
                write_status({'status':'failed','checked_at':datetime.now(timezone.utc).isoformat(),
                              'error':'Backup failed; check database health and disk budgets'})
            except OSError:
                pass
            print('Backup failed; will retry at the next scheduled interval',flush=True)
        for _ in range(interval):
            if stopping:
                break
            time.sleep(1)


if __name__=='__main__':
    main()
