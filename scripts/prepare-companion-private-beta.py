"""Prepare an unsigned private-beta bundle from passed exact-source Windows CI.

No publication, credentials or paid service. An explicit owner private-beta record
is required; design approval alone cannot authorize this distribution policy.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
REPO='Twich-Team/TwichUI-Market'
WORKFLOWS={'windows':'.github/workflows/desktop.yml','backend':'.github/workflows/backend.yml','website':'.github/workflows/web.yml'}
EVIDENCE={'installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json','windows-signature.json'}
ACCEPTANCE={'windows_core','installed_ui','native_browser_approval','hidden_sync','tray','autostart','restart','upgrade','uninstall','no_release_debug','preferences','revocation','offline_cache','performance'}
VERSION=r'2\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})-beta\.[1-9][0-9]{0,3}'


def read(path):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>16384:raise ValueError('Invalid bounded beta evidence')
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value,dict):raise ValueError('Invalid beta evidence document')
    return value


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        while chunk:=file.read(65536):digest.update(chunk)
    return digest.hexdigest()


def unsigned_pe(path):
    """Independent PE security-directory check; Windows trust proof is also required."""
    path=Path(path)
    if path.is_symlink() or not 1024<=path.stat().st_size<=64*1024*1024:raise ValueError('Invalid bounded beta installer')
    with path.open('rb') as file:
        dos=file.read(64)
        if dos[:2]!=b'MZ':raise ValueError('Expected a Windows PE installer')
        offset=struct.unpack_from('<I',dos,60)[0]
        if not 64<=offset<=65536:raise ValueError('Invalid PE header offset')
        file.seek(offset);header=file.read(24)
        if len(header)!=24 or header[:4]!=b'PE\0\0':raise ValueError('Invalid PE header')
        size=struct.unpack_from('<H',header,20)[0]
        if not 136<=size<=1024:raise ValueError('Invalid PE optional header')
        optional=file.read(size)
        if len(optional)!=size:raise ValueError('Incomplete PE optional header')
        magic=struct.unpack_from('<H',optional)[0]
        directory=96 if magic==0x10b else 112 if magic==0x20b else None
        if directory is None or len(optional)<directory+40:raise ValueError('Invalid PE signature directory')
        count=struct.unpack_from('<I',optional,directory-4)[0]
        if count<5:raise ValueError('Missing PE signature directory')
        if struct.unpack_from('<II',optional,directory+32)!=(0,0):raise ValueError('Private beta installer is not unsigned')


def workflow(run_id,path,source):
    run_id=str(run_id)
    if not re.fullmatch(r'[1-9][0-9]{0,19}',run_id):raise ValueError('Explicit CI run identity required')
    headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'}
    # Public source metadata needs no account. Private repositories can supply the
    # protected read-only GITHUB_TOKEN; it is never serialized or printed.
    token=os.environ.get('GITHUB_TOKEN','')
    if token:headers['Authorization']='Bearer '+token
    request=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/runs/{run_id}',headers=headers)
    with urllib.request.urlopen(request,timeout=20) as response:raw=response.read(262145)
    if len(raw)>262144:raise ValueError('CI evidence exceeds bound')
    result=json.loads(raw)
    if (result.get('head_sha')!=source or result.get('path','').split('@')[0]!=path or result.get('status')!='completed'
            or result.get('conclusion')!='success' or result.get('repository',{}).get('full_name')!=REPO):
        raise ValueError('Canonical exact-source CI did not pass')
    return {'id':int(run_id),'source_commit':source,'repository':REPO,'path':path,'status':'completed','conclusion':'success'}


def source_config(source,visual):
    if not all(re.fullmatch(r'[a-f0-9]{40}',value) for value in (source,visual)):raise ValueError('Exact source and approved visual commits required')
    subprocess.run(['git','diff','--exit-code',visual,source,'--','desktop/ui','desktop/src-tauri/src','web/src','web/public'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    raw=subprocess.check_output(['git','show',source+':desktop/src-tauri/tauri.conf.json'],cwd=ROOT)
    if len(raw)>16384:raise ValueError('Source configuration exceeds bound')
    config=json.loads(raw)
    if not re.fullmatch(VERSION,config['version']):raise ValueError('Private beta requires a committed beta version')
    if any(window.get('devtools') is True for window in config['app']['windows']):raise ValueError('Beta must use ordinary release settings')
    return config


def prepare(installer,acceptance,owner_record,source,runs,output,notes=''):
    owner=read(owner_record)
    if (type(owner.get('schema_version')) is not int or owner.get('schema_version')!=1 or owner.get('owner_authorized_private_beta') is not True
            or owner.get('scope')!='private-unsigned-beta-with-manual-updates' or not owner.get('owner_statement')):
        raise ValueError('Explicit owner private-beta authorization required; design approval is insufficient')
    visual=owner.get('visual_approval_commit','');config=source_config(source,visual);version=config['version']
    if len(notes)>4000:raise ValueError('Beta notes exceed bound')
    if set(runs)!=set(WORKFLOWS):raise ValueError('All three canonical CI runs required')
    ci={name:workflow(runs[name],path,source) for name,path in WORKFLOWS.items()}
    installer=Path(installer);unsigned_pe(installer);size=installer.stat().st_size;digest=sha(installer)
    for name in EVIDENCE:read(Path(acceptance)/name)
    # The service's shared admission policy validates all original receipts after
    # staging; importing it does not start an API or connect to a database.
    import sys
    sys.path.insert(0,str(ROOT/'backend'))
    from market import companion_private_beta as beta
    filename=f'TwichUI-Market-Companion-{version}-windows-x64.exe'
    manifest={'schema_version':1,'channel':'private-beta','version':version,'filename':filename,'bytes':size,'sha256':digest,
        'source_commit':source,'visual_approval_commit':visual,'workflow_run_id':ci['windows']['id'],
        'published_at':datetime.now(timezone.utc).isoformat(),'authenticode_status':'NotSigned','updates':'manual',
        'acceptance':{name:name!='tray' for name in ACCEPTANCE},'unverified_requirements':sorted(beta.GAPS),'ci':ci,
        'evidence_sha256':{name:sha(Path(acceptance)/name) for name in EVIDENCE},'notes':notes}
    manifest['evidence_sha256']['owner-private-beta-approval.json']=sha(owner_record)
    output=Path(output)
    if output.is_symlink():raise ValueError('Private beta output must not be a symlink')
    output.mkdir(parents=True,exist_ok=True);destination=output/version
    if destination.exists():raise ValueError('Private beta preparation never overwrites a version')
    temporary=Path(tempfile.mkdtemp(prefix='.beta-preparation-',dir=output))
    try:
        staged=temporary/version;staged.mkdir()
        shutil.copyfile(installer,staged/filename)
        for name in EVIDENCE:shutil.copyfile(Path(acceptance)/name,staged/name)
        shutil.copyfile(owner_record,staged/'owner-private-beta-approval.json')
        (staged/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        beta.load(version,temporary)
        os.rename(staged,destination)
    finally:shutil.rmtree(temporary)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer',type=Path,required=True);parser.add_argument('--acceptance',type=Path,required=True)
    parser.add_argument('--owner-record',type=Path,required=True);parser.add_argument('--source-commit',required=True)
    parser.add_argument('--windows-run',required=True);parser.add_argument('--backend-run',required=True);parser.add_argument('--website-run',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts'/'companion-private-beta-incoming');parser.add_argument('--notes',default='')
    args=parser.parse_args()
    prepare(args.installer,args.acceptance,args.owner_record,args.source_commit,
        {'windows':args.windows_run,'backend':args.backend_run,'website':args.website_run},args.output,args.notes)
    print('Private unsigned beta bundle prepared; tray actions remain unverified. No live store or production service changed.')


if __name__=='__main__':main()
