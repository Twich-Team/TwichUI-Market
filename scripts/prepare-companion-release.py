"""Owner-controlled Windows release preparation. Never publishes a live pointer.

Modes: preflight verifies source/CI/visual provenance and prepares public signing config;
candidate verifies signed bytes and writes a deliberately incomplete candidate;
approve admits only an exact-hash manual owner record, then completes the receipt.
No private key is read, serialized or printed by this script.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
REPO='Twich-Team/TwichUI-Market'
WORKFLOWS={'windows':'.github/workflows/desktop.yml','backend':'.github/workflows/backend.yml','website':'.github/workflows/web.yml'}
REQUIRED={'windows_core','installed_ui','native_browser_approval','hidden_sync','tray','autostart','restart','upgrade','uninstall','no_release_debug','preferences','revocation','offline_cache','performance'}


def read(path,maximum=65536):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size>maximum:raise ValueError('Invalid bounded release document')
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        while chunk:=file.read(65536):digest.update(chunk)
    return digest.hexdigest()


def owner():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_OS')!='Windows':raise ValueError('Owner Windows release runner only')
    if os.environ.get('GITHUB_REPOSITORY')!=REPO:raise ValueError('Release repository mismatch')
    expected=os.environ.get('COMPANION_RELEASE_OWNER','')
    actor=os.environ.get('GITHUB_ACTOR','')
    if not expected or actor.lower()!=expected.lower():raise ValueError('The configured owner must explicitly dispatch this release')
    return actor


def identity():
    version=os.environ['RELEASE_VERSION'];source=os.environ['RELEASE_SOURCE_COMMIT'];approved=os.environ['RELEASE_VISUAL_COMMIT']
    if not re.fullmatch(r'2\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})',version):raise ValueError('Release version must be stable 2.x SemVer')
    if not all(re.fullmatch(r'[a-f0-9]{40}',value) for value in (source,approved)):raise ValueError('Exact source and visual approval commits are required')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if actual!=source:raise ValueError('Checked-out release source differs')
    return version,source,approved


def workflow(run_id,path,source):
    if not re.fullmatch(r'[1-9][0-9]{0,19}',run_id):raise ValueError('Explicit CI run identifiers are required')
    token=os.environ.get('GITHUB_TOKEN','')
    if not token:raise ValueError('Read-only CI provenance access is required')
    request=urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/runs/{run_id}',headers={
        'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    with urllib.request.urlopen(request,timeout=20) as response:
        data=response.read(262145)
    if len(data)>262144:raise ValueError('CI provenance response exceeds limit')
    result=json.loads(data)
    if ((source is not None and result.get('head_sha')!=source) or result.get('status')!='completed' or result.get('conclusion')!='success'
            or result.get('path','').split('@')[0]!=path or result.get('repository',{}).get('full_name')!=REPO):
        raise ValueError('Required exact-source CI workflow did not pass')
    return {'id':int(run_id),'path':path,'source_commit':result.get('head_sha'),'conclusion':'success','run_attempt':result.get('run_attempt'),'actor':result.get('actor',{}).get('login'),'event':result.get('event')}


def preflight(output):
    actor=owner();version,source,approved=identity()
    # A later documentation/version-only commit may retain an earlier visual approval.
    subprocess.run(['git','diff','--exit-code',approved,source,'--','desktop/ui','desktop/src-tauri/src','web/src','web/public'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    import tomllib
    for path in ('desktop/core/Cargo.toml','desktop/src-tauri/Cargo.toml'):
        if tomllib.loads((ROOT/path).read_text())['package']['version']!=version:raise ValueError('Commit the consistent stable version before preparing a release')
    for path in ('desktop/package.json','desktop/src-tauri/tauri.conf.json'):
        if read(ROOT/path)['version']!=version:raise ValueError('Desktop version sources differ')
    runs={name:workflow(os.environ[f'RELEASE_{name.upper()}_RUN_ID'],path,source) for name,path in WORKFLOWS.items()}
    key=os.environ.get('COMPANION_UPDATER_PUBLIC_KEY','').strip()
    if not key or len(key)>4096:raise ValueError('Configure the public updater trust key before signing')
    config={'plugins':{'updater':{'pubkey':key,'requireSignedVersion':True,'allowDowngrades':False,'windows':{'installMode':'basicUi'}}}}
    output.mkdir(parents=True,exist_ok=True)
    (output/'tauri-signing.json').write_text(json.dumps(config),encoding='utf-8')
    (output/'source-provenance.json').write_text(json.dumps({'schema_version':1,'owner':actor,'source_commit':source,'version':version,'visual_approval_commit':approved,'runs':runs},indent=2),encoding='utf-8')


def accepted_workflows(acceptance,source):
    installed=read(acceptance/'installed-smoke.json');upgrade=read(acceptance/'legacy-upgrade.json');performance=read(acceptance/'performance.json')
    if installed.get('source_commit')!=source or upgrade.get('source_commit')!=source:raise ValueError('Installed acceptance source differs')
    for name in ('native_browser_approval_ui','native_thread_hidden_sync','single_instance_restore','preferences_saved','credential_and_cache_restart',
            'hidden_startup','current_user_autostart_enable_disable','native_minimize_close_to_tray','export_valid','server_revocation',
            'offline_cache_preserved','website_approval_ui_verified','uninstall_settings_and_cache_preserved'):
        if installed.get(name) is not True:raise ValueError('Installed acceptance is incomplete')
    for name in ('actual_old_installer','actual_new_installer','legacy_credentials_preserved','cache_preserved','connection_settings_preserved',
            'legacy_metadata_migrated','new_native_sync','export_contract_preserved','signed_updater_sdk_install','uninstall_data_preservation_verified_by_parent'):
        if upgrade.get(name) is not True:raise ValueError('Upgrade/uninstall acceptance is incomplete')
    network=performance.get('idle_market_api_requests',{})
    if (performance.get('source_commit')!=source or not performance.get('resources') or not network.get('before')
            or network.get('before')!=network.get('after')):raise ValueError('Source-bound idle performance evidence is missing or has unexpected API traffic')
    config=read(ROOT/'desktop/src-tauri/tauri.conf.json')
    if any(window.get('devtools') is True for window in config['app']['windows']):raise ValueError('Release configuration contains developer tools')
    return {name:name!='tray' for name in REQUIRED}


def candidate(output,acceptance,signing):
    actor=owner();version,source,approved=identity()
    provenance=read(output/'source-provenance.json')
    if provenance['source_commit']!=source or provenance['owner']!=actor:raise ValueError('Prepared source provenance differs')
    acceptance_flags=accepted_workflows(acceptance,source)
    files=list((ROOT/'desktop/src-tauri/target/release/bundle/nsis').glob('*-setup.exe'))
    if len(files)!=1:raise ValueError('Expected one signed NSIS installer')
    installer=files[0];proof=read(signing)
    thumb=proof.get('thumbprint','')
    if (proof.get('status') not in ('NotSigned','Valid') or proof.get('sha256')!=sha(installer)
            or (proof['status']=='NotSigned' and thumb) or (proof['status']=='Valid' and not re.fullmatch(r'[A-F0-9]{40}',thumb))):
        raise ValueError('Actual Windows publisher observation differs')
    signature=Path(str(installer)+'.sig')
    if signature.is_symlink() or not 32<=signature.stat().st_size<=4096:raise ValueError('Version-bound updater signature is missing')
    if not 1024<=installer.stat().st_size<=64*1024*1024:raise ValueError('Installer exceeds controlled delivery limits')
    destination=output/'bundle'/version;destination.mkdir(parents=True,exist_ok=False)
    filename=f'TwichUI-Market-Companion-{version}-windows-x64.exe';shutil.copyfile(installer,destination/filename)
    key=os.environ['COMPANION_UPDATER_PUBLIC_KEY'].strip()
    notes=os.environ.get('RELEASE_NOTES','').strip()
    if len(notes)>4000:raise ValueError('Release notes exceed limit')
    receipt={'schema_version':2,'channel':'stable','version':version,'filename':filename,'bytes':installer.stat().st_size,'sha256':sha(installer),
        'source_commit':source,'workflow_run_id':int(os.environ['GITHUB_RUN_ID']),'published_at':datetime.now(timezone.utc).isoformat(),
        'publisher_thumbprint':thumb,'authenticode_status':proof['status'],'updater_public_key_sha256':hashlib.sha256(key.encode()).hexdigest(),
        'updater_signature':signature.read_text().strip(),'visual_approval_commit':approved,'acceptance':acceptance_flags,'notes':notes}
    (destination/'manifest.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    (output/'candidate-provenance.json').write_text(json.dumps({**provenance,'producer_run_id':int(os.environ['GITHUB_RUN_ID']),
        'installer_sha256':receipt['sha256'],'status':'signed-candidate-awaiting-manual-tray-acceptance','stable_publication_permitted':False,
        'installed_acceptance_sha256':{name:sha(acceptance/name) for name in ('installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json')}},indent=2),encoding='utf-8')
    saved=output/'installed-acceptance';saved.mkdir(exist_ok=False)
    for name in ('installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json'):shutil.copyfile(acceptance/name,saved/name)


def approve(output,manual_path):
    actor=owner();version,source,approved=identity()
    manifest=output/'bundle'/version/'manifest.json';receipt=read(manifest,16384)
    provenance=read(output/'candidate-provenance.json')
    manual_ref=os.environ.get('RELEASE_MANUAL_COMMIT','')
    relative=str(manual_path).replace('\\','/')
    if not re.fullmatch(r'[a-f0-9]{40}',manual_ref) or not re.fullmatch(r'docs/evidence/[A-Za-z0-9_.-]+\.json',relative):
        raise ValueError('An exact committed owner acceptance record is required')
    data=subprocess.check_output(['git','show',f'{manual_ref}:{relative}'],cwd=ROOT)
    if len(data)>16384:raise ValueError('Owner acceptance record exceeds limit')
    manual=json.loads(data)
    local_manual=output/'owner-manual-record.json';local_manual.write_bytes(data)
    manual_path=local_manual
    producer=workflow(os.environ.get('RELEASE_CANDIDATE_RUN_ID',''),'.github/workflows/companion-release.yml',None)
    if (producer.get('actor') or '').lower()!=actor.lower() or producer.get('event')!='workflow_dispatch' or provenance.get('producer_run_id')!=producer['id']:
        raise ValueError('Candidate did not come from the configured owner release workflow')
    if (receipt['source_commit']!=source or receipt['version']!=version or receipt['visual_approval_commit']!=approved
            or provenance.get('installer_sha256')!=receipt['sha256']):raise ValueError('Candidate identity differs')
    if set(provenance.get('installed_acceptance_sha256',{}))!={'installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json'}:
        raise ValueError('Signed candidate acceptance provenance is incomplete')
    for name,digest in provenance['installed_acceptance_sha256'].items():
        if name not in ('installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json') or sha(output/'installed-acceptance'/name)!=digest:
            raise ValueError('Signed candidate installed acceptance changed')
    accepted_workflows(output/'installed-acceptance',source)
    if (manual.get('schema_version')!=1 or manual.get('owner','').lower()!=actor.lower() or manual.get('source_commit')!=source
            or manual.get('installer_sha256')!=receipt['sha256'] or manual.get('version')!=version or not manual.get('observations')
            or not re.fullmatch(r'[a-f0-9]{64}',manual.get('tray_screenshot_sha256',''))
            or manual.get('owner_approved_publication') is not True or manual.get('owner_approved_deployment') is not True
            or not manual.get('windows_version') or not manual.get('display_scaling') or manual.get('tray_actions_verified') is not True):
        raise ValueError('Exact-installer owner PC acceptance is missing')
    checks=manual.get('checks',{})
    required={'notification_menu','open','settings','sync','pause_resume','close_restore','minimize_restore','hidden_sync','startup','single_instance','quit'}
    if set(checks)!=required or not all(value is True for value in checks.values()):raise ValueError('Manual tray acceptance is incomplete')
    key=os.environ.get('COMPANION_UPDATER_PUBLIC_KEY','').strip()
    if receipt['updater_public_key_sha256']!=hashlib.sha256(key.encode()).hexdigest():
        raise ValueError('Candidate public trust identity differs')
    installer=manifest.parent/receipt['filename']
    if sha(installer)!=receipt['sha256']:raise ValueError('Candidate bytes changed')
    receipt['acceptance']['tray']=True
    if set(receipt['acceptance'])!=REQUIRED or not all(receipt['acceptance'].values()):raise ValueError('Release acceptance remains incomplete')
    manifest.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    acceptance={'schema_version':1,'owner':actor,'source_commit':source,'version':version,
        'installer_sha256':receipt['sha256'],'manual_receipt_sha256':sha(manual_path),'approved_at':datetime.now(timezone.utc).isoformat(),
        'approval_run_id':int(os.environ['GITHUB_RUN_ID']),'stable_publication_permitted':True,
        'owner_approved_publication':True,'owner_approved_deployment':True,'updater_public_key_sha256':receipt['updater_public_key_sha256']}
    (output/'owner-acceptance.json').write_text(json.dumps(acceptance,indent=2),encoding='utf-8')
    (manifest.parent/'publication-proof.json').write_text(json.dumps({'source_provenance':provenance,'owner_acceptance':acceptance},indent=2),encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['preflight','candidate','approve'])
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts'/'companion-signed-release')
    parser.add_argument('--acceptance',type=Path)
    parser.add_argument('--signing',type=Path)
    parser.add_argument('--manual',type=Path)
    args=parser.parse_args()
    if args.mode=='preflight':preflight(args.output)
    elif args.mode=='candidate':candidate(args.output,args.acceptance,args.signing)
    else:approve(args.output,args.manual)
    print(f'Owner release {args.mode} checks passed; no live store or production service was changed.')


if __name__=='__main__':main()
