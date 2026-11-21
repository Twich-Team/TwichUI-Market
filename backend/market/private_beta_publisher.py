"""Operator-only private-beta import. Never writes a stable store; signatures are mandatory for private updates."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from . import companion_private_beta as beta
from . import release_publisher as store_tools

PURPOSE='private-companion-beta-assets'
MAX_STORE_BYTES=128*1024*1024


def actor_name(actor):
    if not re.fullmatch(r'[A-Za-z0-9_@.-]{1,64}',actor):raise ValueError('Explicit bounded private-beta operator required')


def pointer(store):
    path=store/'current.json'
    if not path.exists():return None
    value=beta.bounded_json(path)
    if (not isinstance(value,dict) or set(value)!={'schema_version','version'} or type(value['schema_version']) is not int
            or value['schema_version']!=1):raise ValueError('Invalid private beta pointer')
    return beta.load(value['version'],store)[0].version


def transition(store,version,actor,operation):
    actor_name(actor)
    manifest,asset=beta.load(version,store)
    store_tools.verify_installer(asset.parent/'manifest.json',asset)
    previous=pointer(store)
    if previous==version:return {'changed':False,'channel':'private-beta','version':version}
    audit=store/'audit';audit.mkdir(mode=0o755,exist_ok=True)
    records=sorted(audit.glob('*.json'))
    if len(records)+2>store_tools.MAX_AUDITS:raise ValueError('Private beta audit capacity reached; no records removed')
    if any(not re.fullmatch(r'[0-9]{8}(\.complete)?\.json',record.name) or record.is_symlink() for record in records):
        raise ValueError('Unexpected private beta audit record')
    prepared=[record for record in records if re.fullmatch(r'[0-9]{8}\.json',record.name)]
    if any(record.name.endswith('.complete.json') and not (audit/(record.name.removesuffix('.complete.json')+'.json')).is_file() for record in records):
        raise ValueError('Private beta completion lacks durable intent')
    event=max((int(record.stem) for record in prepared),default=0)+1
    if store_tools.usage(store)+32768>MAX_STORE_BYTES:raise ValueError('Private beta store budget reached; no versions removed')
    intent=audit/f'{event:08d}.json'
    if intent.exists():raise ValueError('Private beta audit sequence collision')
    store_tools.atomic_json(intent,{'schema_version':1,'phase':'prepared','operation':operation,'actor':actor,'channel':'private-beta',
        'at':datetime.now(timezone.utc).isoformat(),'previous_version':previous,'version':version,
        'source_commit':manifest.source_commit,'workflow_run_id':manifest.workflow_run_id,'installer_sha256':manifest.sha256,
        'manifest_sha256':hashlib.sha256((asset.parent/'manifest.json').read_bytes()).hexdigest(),
        'evidence_sha256':manifest.evidence_sha256,'tray_actions_verified':False,'updates':'signed','updater_public_key_sha256':manifest.updater_public_key_sha256,'authenticode_status':'NotSigned'})
    store_tools.atomic_json(store/'current.json',{'schema_version':1,'version':version})
    store_tools.atomic_json(audit/f'{event:08d}.complete.json',{'schema_version':1,'phase':'committed','prepared':intent.name,
        'at':datetime.now(timezone.utc).isoformat(),'channel':'private-beta','version':version})
    return {'changed':True,'channel':'private-beta','previous_version':previous,'version':version,'audit':intent.name}


def publish(store,bundle,actor):
    actor_name(actor);bundle=Path(bundle)
    if bundle.is_symlink():raise ValueError('Private beta bundle must not be a symlink')
    bundle=bundle.resolve(strict=True)
    manifest,asset=beta.load(bundle.name,bundle.parent)
    store_tools.verify_installer(bundle/'manifest.json',asset)
    with store_tools.locked(store,PURPOSE) as store:
        destination=store/manifest.version
        if destination.exists():
            existing,_=beta.load(manifest.version,store)
            if existing!=manifest or (destination/'manifest.json').read_bytes()!=(bundle/'manifest.json').read_bytes():
                raise ValueError('Private beta versions and evidence are immutable')
        else:
            if store_tools.usage(store)+manifest.bytes+256*1024>MAX_STORE_BYTES:
                raise ValueError('Private beta store budget reached; no versions removed')
            temporary=Path(tempfile.mkdtemp(prefix='.beta-staging-',dir=store))
            staging=temporary/manifest.version;staging.mkdir(mode=0o700)
            try:
                for source in [bundle/'manifest.json',asset,*[bundle/name for name in sorted(beta.EVIDENCE)]]:
                    target=staging/source.name
                    with source.open('rb') as incoming,target.open('xb') as outgoing:
                        shutil.copyfileobj(incoming,outgoing,64*1024);outgoing.flush();os.fsync(outgoing.fileno())
                    target.chmod(0o644)
                beta.load(manifest.version,temporary)
                store_tools.verify_installer(staging/'manifest.json',staging/manifest.filename)
                staging.chmod(0o755);store_tools.sync_directory(staging)
                os.rename(staging,destination);store_tools.sync_directory(store)
            finally:
                if temporary.exists():shutil.rmtree(temporary)
        return transition(store,manifest.version,actor,'publish')


def rollback(store,version,actor):
    actor_name(actor)
    with store_tools.locked(store,PURPOSE) as store:return transition(store,version,actor,'rollback')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['publish','rollback']);parser.add_argument('bundle_or_version');parser.add_argument('--actor',required=True)
    args=parser.parse_args();store=os.environ.get('COMPANION_PRIVATE_BETA_DIRECTORY','')
    if not store:raise SystemExit('Configure the separate private-beta store first')
    result=publish(store,args.bundle_or_version,args.actor) if args.operation=='publish' else rollback(store,args.bundle_or_version,args.actor)
    print(json.dumps(result))


if __name__=='__main__':main()
