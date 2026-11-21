"""Project-scoped PostgreSQL dumps and isolated restore rehearsals (no host packages)."""
import argparse
import fcntl
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'backups'
RESERVE_BYTES = 2 * 1024**3
BUDGET_BYTES = 2 * 1024**3


def locked(function):
    @wraps(function)
    def wrapper(*args,**kwargs):
        DIRECTORY.mkdir(mode=0o700,exist_ok=True)
        with os.fdopen(os.open(DIRECTORY/'.backup.lock', os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW, 0o600), 'a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return function(*args,**kwargs)
    return wrapper


def compose(project):
    if project == 'development':
        return ['docker','--context','rootless','compose','-p','twichui-market','-f',str(ROOT/'compose.yaml')]
    if project in ('test','recovery'):
        name='twichui-market-test' if project=='test' else 'twichui-market-recovery'
        return ['docker','--context','rootless','compose','-p',name,
                '-f',str(ROOT/'compose.yaml'),'-f',str(ROOT/'compose.test.yaml')]
    if project == 'restore':
        return ['docker','--context','rootless','compose','-p','twichui-market-restore','-f',str(ROOT/'compose.restore.yaml')]
    raise ValueError('Unknown project')


def run(command, **kwargs):
    return subprocess.run(command,cwd=ROOT,check=True,**kwargs)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


@locked
def backup(project='development', keep=7):
    DIRECTORY.mkdir(mode=0o700,exist_ok=True)
    DIRECTORY.chmod(0o700)
    if not 1<=keep<=30:
        raise ValueError('Keep must be between 1 and 30')
    database = 'market' if project=='development' else 'market_test'
    if project not in ('development','test','recovery'):
        raise ValueError('Invalid backup source')
    size = int(run(compose(project)+['exec','-T','db','psql','-U','market','-d',database,'-Atc',
        'SELECT pg_database_size(current_database())'],stdout=subprocess.PIPE).stdout.strip())
    if shutil.disk_usage(DIRECTORY).free < size + RESERVE_BYTES:
        raise ValueError('Insufficient disk headroom for safe backup')
    used = sum(path.stat().st_size for path in DIRECTORY.glob('*.dump'))
    if used + size > BUDGET_BYTES:
        raise ValueError('Backup disk budget would be exceeded; review archives before retrying')
    filename = f'market-{project}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")}.dump'
    target = DIRECTORY/filename
    temporary = target.with_suffix('.partial')
    try:
        fd = os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as output:
            run(compose(project)+['exec','-T','db','pg_dump','-U','market','-d',database,
                '--format=custom','--no-owner','--no-acl'],stdout=output)
            output.flush()
            os.fsync(output.fileno())
        temporary.rename(target)
        manifest = {'version':1,'filename':filename,'source':project,'created_at':datetime.now(timezone.utc).isoformat(),
                    'bytes':target.stat().st_size,'sha256':sha256(target),'restoration_verified_at':None}
        write_manifest(target,manifest)
        # Retention belongs to the management service. Operator/release archives
        # are retained conservatively; --keep never authorizes filename-only deletion.
        return target
    finally:
        temporary.unlink(missing_ok=True)


def write_manifest(path,manifest):
    target = path.with_suffix('.json')
    temp = target.with_suffix('.json.partial')
    fd = os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(manifest,stream,indent=2)
        stream.write('\n')
    temp.replace(target)


@locked
def restore_check(path):
    if Path(path).is_symlink():
        raise ValueError('Symlink archives are not accepted')
    path = Path(path).resolve()
    if path.parent != DIRECTORY.resolve() or not path.name.startswith('market-') or path.suffix!='.dump':
        raise ValueError('Restore rehearsal accepts only project backup archives')
    manifest = json.loads(path.with_suffix('.json').read_text())
    if manifest.get('version') not in (1,2) or manifest.get('sha256') != sha256(path) or manifest.get('bytes')!=path.stat().st_size:
        raise ValueError('Backup integrity verification failed')
    command = compose('restore')
    # Always disposable; --no-clean restores only into the freshly created database.
    run(command+['down'],stdout=subprocess.DEVNULL)
    try:
        run(command+['up','-d','--wait','--wait-timeout','90'],stdout=subprocess.DEVNULL)
        with path.open('rb') as stream:
            run(command+['exec','-T','db','pg_restore','-U','market','-d','market_restore',
                '--no-owner','--no-acl','--exit-on-error'],stdin=stream)
        sql = "SELECT json_build_object('migration',(SELECT version_num FROM alembic_version),'users',(SELECT count(*) FROM users),'markets',(SELECT count(*) FROM markets),'observations',(SELECT count(*) FROM observations),'listings',(SELECT count(*) FROM listings),'synthetic_observations',(SELECT count(*) FROM observations WHERE synthetic),'buyout_total',(SELECT COALESCE(sum(buyout),0)::text FROM listings))"
        result = run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',sql],stdout=subprocess.PIPE)
        evidence = json.loads(result.stdout)
        present=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
            "SELECT to_regclass('snapshot_statistics') IS NOT NULL"],stdout=subprocess.PIPE).stdout.strip()==b't'
        if present:
            statistics=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
                "SELECT json_build_object('snapshot_statistics',(SELECT count(*) FROM snapshot_statistics),'daily_observations',(SELECT count(*) FROM daily_observations))"],stdout=subprocess.PIPE)
            evidence.update(json.loads(statistics.stdout))
        verification_table=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
            "SELECT to_regclass('market_verifications') IS NOT NULL"],stdout=subprocess.PIPE).stdout.strip()==b't'
        if verification_table:
            receipt_count=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
                'SELECT count(*) FROM market_verifications'],stdout=subprocess.PIPE)
            evidence['market_verifications']=int(receipt_count.stdout.strip())
        preferences_table=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
            "SELECT to_regclass('user_preferences') IS NOT NULL"],stdout=subprocess.PIPE).stdout.strip()==b't'
        if preferences_table:
            preference_count=run(command+['exec','-T','db','psql','-U','market','-d','market_restore','-Atc',
                'SELECT count(*) FROM user_preferences'],stdout=subprocess.PIPE)
            evidence['user_preferences']=int(preference_count.stdout.strip())
        if not evidence['migration']:
            raise ValueError('Restored database has no migration revision')
        # PostgreSQL also restores and validates foreign-key/unique constraints through pg_restore.
        manifest['restoration_verified_at'] = datetime.now(timezone.utc).isoformat()
        manifest['restored'] = evidence
        if manifest.get('version') == 2:
            manifest['protected'] = True  # restore/retention gate points need explicit release
            manifest['required_by'] = sorted(set(manifest.get('required_by', [])) | {'restore-recovery-gate'})
        write_manifest(path,manifest)
        if manifest['source']=='development':
            status_directory=ROOT/'artifacts'/'backup-status'
            status_directory.mkdir(mode=0o755,parents=True,exist_ok=True)
            target=status_directory/'status.json'
            status=json.loads(target.read_text()) if target.exists() else {'status':'manual_backup_verified'}
            status.update({'status':'ok','last_success':manifest['created_at'],'filename':manifest['filename'],
                'bytes':manifest['bytes'],'last_restoration_verified_at':manifest['restoration_verified_at'],
                'restored_archive_filename':manifest['filename'],'restored_archive_sha256':manifest['sha256'],
                'restored_archive_created_at':manifest['created_at']})
            temp=target.with_suffix('.partial')
            temp.write_text(json.dumps(status)+'\n')
            temp.chmod(0o644)
            temp.replace(target)
        return evidence
    finally:
        run(command+['down'],stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest='command',required=True)
    create = subparsers.add_parser('create')
    create.add_argument('--source',choices=['development','test'],default='development')
    create.add_argument('--keep',type=int,default=7)
    restore = subparsers.add_parser('verify-restore')
    restore.add_argument('archive')
    args = parser.parse_args()
    try:
        result = backup(args.source,args.keep) if args.command=='create' else restore_check(args.archive)
    except (ValueError,OSError,subprocess.CalledProcessError,json.JSONDecodeError) as exc:
        parser.exit(1,f'Backup operation failed ({type(exc).__name__}); inspect project service health and disk capacity.\n')
    print(json.dumps(result) if isinstance(result,dict) else str(result))


if __name__=='__main__':
    main()
