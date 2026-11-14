"""Operator-only immutable release import and audited atomic pointer transitions.

No web route imports this module. The approved owner-controlled Windows workflow
must supply its actual CI/visual/Authenticode receipt. This importer independently
checks its pinned identity, bounded bytes and updater signature/signed version.
It cannot independently reproduce Windows trust-chain evaluation on Linux.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from .companion_releases import bounded_json,load

MAX_STORE_BYTES=256*1024*1024
MAX_AUDITS=4096


def sync_directory(directory):
    descriptor=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def atomic_json(path,value):
    encoded=(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
    if len(encoded)>16384:raise ValueError('Release audit document exceeds limit')
    descriptor,name=tempfile.mkstemp(prefix='.publication-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as file:
            file.write(encoded);file.flush();os.fsync(file.fileno());os.fchmod(file.fileno(),0o644)
        os.replace(name,path);sync_directory(path.parent)
    finally:
        Path(name).unlink(missing_ok=True)


@contextmanager
def locked(store):
    store=Path(store)
    if store.is_symlink():raise ValueError('Release store must not be a symlink')
    store.mkdir(mode=0o755,parents=True,exist_ok=True)
    store=store.resolve(strict=True)
    marker=store/'.companion-release-store.json'
    identity={'schema_version':1,'purpose':'companion-release-assets'}
    if marker.exists():
        if bounded_json(marker)!=identity:raise ValueError('Unexpected release store identity')
    elif any(store.iterdir()):
        raise ValueError('Refusing an existing directory without the release-store identity')
    else:atomic_json(marker,identity)
    descriptor=os.open(store/'.publication.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX)
        yield store
    finally:os.close(descriptor)


def usage(store):
    total=0
    for path in store.rglob('*'):
        if path.is_symlink():raise ValueError('Release store contains a symlink')
        if path.is_file():total+=path.stat().st_size
    return total


def verify_installer(manifest_path,asset):
    executable=os.environ.get('COMPANION_RELEASE_VERIFIER','/usr/local/bin/twichui-verify-release')
    result=subprocess.run([executable,str(manifest_path),str(asset)],capture_output=True,timeout=90,check=False)
    if result.returncode or len(result.stdout)>4096:
        raise ValueError('Independent release signature verification failed')
    proof=json.loads(result.stdout)
    manifest=bounded_json(manifest_path)
    if proof!={'signature_verified':True,'signed_version':manifest['version'],'sha256':manifest['sha256']}:
        raise ValueError('Release verifier identity mismatch')


def pointer(store):
    path=store/'current.json'
    if not path.exists():return None
    value=bounded_json(path)
    if set(value)!={'schema_version','version'} or type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('Current release pointer is invalid')
    load(value['version'],store)
    return value['version']


def transition(store,version,actor,operation):
    if not re.fullmatch(r'[A-Za-z0-9_@.-]{1,64}',actor):raise ValueError('An explicit bounded operator identity is required')
    manifest,asset=load(version,store)
    verify_installer(asset.parent/'manifest.json',asset)
    previous=pointer(store)
    if previous==version:return {'changed':False,'version':version}
    audit=store/'audit';audit.mkdir(mode=0o755,exist_ok=True)
    records=sorted(audit.glob('*.json'))
    if len(records)>=MAX_AUDITS:raise ValueError('Release audit capacity reached; preserve records before extending capacity')
    if any(not re.fullmatch(r'[0-9]{8}(\.complete)?\.json',record.name) for record in records):raise ValueError('Unexpected audit record')
    prepared=[record for record in records if re.fullmatch(r'[0-9]{8}\.json',record.name)]
    if any(record.name.endswith('.complete.json') and not (audit/(record.name.removesuffix('.complete.json')+'.json')).is_file() for record in records):
        raise ValueError('Completion record has no durable publication intent')
    event=max((int(record.stem) for record in prepared),default=0)+1
    target=audit/f'{event:08d}.json'
    if target.exists():raise ValueError('Audit sequence collision')
    if usage(store)+32768>MAX_STORE_BYTES:raise ValueError('Release store budget reached; no versions were removed')
    # Durable intent precedes the atomic pointer. A crash after pointer rename is
    # recoverable from this immutable receipt; no asset/history rollback is needed.
    atomic_json(target,{'schema_version':1,'phase':'prepared','operation':operation,'actor':actor,
        'at':datetime.now(timezone.utc).isoformat(),'previous_version':previous,'version':version,
        'source_commit':manifest.source_commit,'workflow_run_id':manifest.workflow_run_id,
        'visual_approval_commit':manifest.visual_approval_commit,'installer_sha256':manifest.sha256,
        'manifest_sha256':hashlib.sha256((asset.parent/'manifest.json').read_bytes()).hexdigest()})
    atomic_json(store/'current.json',{'schema_version':1,'version':version})
    # A completion record is additional evidence, not a prerequisite for deciding
    # the active pointer after interruption. Prepared records are never rewritten.
    atomic_json(audit/f'{event:08d}.complete.json',{'schema_version':1,'phase':'committed','prepared':target.name,
        'at':datetime.now(timezone.utc).isoformat(),'version':version})
    return {'changed':True,'previous_version':previous,'version':version,'audit':target.name}


def publish(store,bundle,actor):
    if not re.fullmatch(r'[A-Za-z0-9_@.-]{1,64}',actor):raise ValueError('An explicit bounded operator identity is required')
    bundle=Path(bundle)
    if bundle.is_symlink():raise ValueError('Release bundle must not be a symlink')
    bundle=bundle.resolve(strict=True)
    manifest,asset=load(bundle.name,bundle.parent)
    verify_installer(bundle/'manifest.json',asset)
    with locked(store) as store:
        destination=store/manifest.version
        if destination.exists():
            existing,old_asset=load(manifest.version,store)
            if (existing!=manifest or (destination/'manifest.json').read_bytes()!=(bundle/'manifest.json').read_bytes()
                    or old_asset.stat().st_size!=manifest.bytes):
                raise ValueError('Published versions are immutable')
        else:
            if usage(store)+manifest.bytes+65536>MAX_STORE_BYTES:raise ValueError('Release store budget reached; no versions were removed')
            staging=Path(tempfile.mkdtemp(prefix='.staging-',dir=store))
            try:
                for source in (bundle/'manifest.json',asset):
                    target=staging/source.name
                    with source.open('rb') as incoming,target.open('xb') as outgoing:
                        shutil.copyfileobj(incoming,outgoing,64*1024);outgoing.flush();os.fsync(outgoing.fileno())
                    target.chmod(0o644)
                # Recheck copied bytes/signature before exposing the version directory.
                verify_installer(staging/'manifest.json',staging/manifest.filename)
                staging.chmod(0o755);sync_directory(staging)
                os.rename(staging,destination);sync_directory(store)
            finally:
                if staging.exists():shutil.rmtree(staging)
        return transition(store,manifest.version,actor,'publish')


def rollback(store,version,actor):
    with locked(store) as store:return transition(store,version,actor,'rollback')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['publish','rollback'])
    parser.add_argument('bundle_or_version')
    parser.add_argument('--actor',required=True)
    args=parser.parse_args()
    store=os.environ.get('COMPANION_RELEASE_DIRECTORY','')
    if not store:raise SystemExit('Configure the dedicated release store first')
    result=(publish(store,args.bundle_or_version,args.actor) if args.operation=='publish'
        else rollback(store,args.bundle_or_version,args.actor))
    print(json.dumps(result))


if __name__=='__main__':main()
