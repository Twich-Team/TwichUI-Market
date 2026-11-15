"""Public-only exact-byte updater acceptance preparation; never signs or publishes.

The payload source and later harness source are separate, explicit identities.
Private key material is neither needed nor accepted by this Windows CI tool.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('beta_prepare',ROOT/'scripts/prepare-companion-private-beta.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


def read_proof(path):
    value=prepare.read(path)
    required={'schema_version','version','payload_source_commit','windows_run_id','backend_run_id','website_run_id',
        'installer_artifact_id','installer_sha256','installer_bytes','executable_sha256','updater_public_key_sha256','updater_signature'}
    if set(value)!=required or type(value['schema_version']) is not int or value['schema_version']!=1:raise ValueError('Unexpected signed candidate proof')
    if not re.fullmatch(prepare.VERSION,value['version']):raise ValueError('Exact beta identity required')
    for field,length in [('payload_source_commit',40),('installer_sha256',64),('executable_sha256',64),('updater_public_key_sha256',64)]:
        if not re.fullmatch('[a-f0-9]{'+str(length)+'}',value[field]):raise ValueError('Invalid public candidate identity')
    for field in ('windows_run_id','backend_run_id','website_run_id','installer_artifact_id'):
        if type(value[field]) is not int or value[field]<1:raise ValueError('Exact canonical run/artifact identity required')
    if type(value['installer_bytes']) is not int or not 1024<=value['installer_bytes']<=64*1024*1024:raise ValueError('Invalid candidate size')
    import base64
    if not 32<=len(value['updater_signature'])<=4096:raise ValueError('Missing updater signature')
    base64.b64decode(value['updater_signature'],validate=True)
    key=(ROOT/'desktop/src-tauri/updater-public-key.txt').read_text().strip()
    if hashlib.sha256(key.encode()).hexdigest()!=value['updater_public_key_sha256']:raise ValueError('Candidate uses another compiled verification key')
    return value,key


def preflight(path):
    proof,key=read_proof(path)
    for name,workflow_path in prepare.WORKFLOWS.items():prepare.workflow(proof[name+'_run_id'],workflow_path,proof['payload_source_commit'])
    output=os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output,'a') as file:
            file.write(f"windows_run_id={proof['windows_run_id']}\ninstaller_artifact_id={proof['installer_artifact_id']}\n")
    return proof


def stage(path,incoming):
    proof,key=read_proof(path)
    candidates=list(Path(incoming).rglob('*.exe'))
    if len(candidates)!=1:raise ValueError('Expected one original CI installer')
    asset=candidates[0];prepare.unsigned_pe(asset)
    if asset.stat().st_size!=proof['installer_bytes'] or prepare.sha(asset)!=proof['installer_sha256']:raise ValueError('Original candidate bytes changed')
    # Exact release artifact download is performed by actions/download-artifact,
    # never by a URL carrying account/device credentials.
    # Earlier independent tests preserve their disposable profiles. Move them
    # aside intact before the separate exact-signed-byte SDK test reuses its name.
    temporary=Path(os.environ['RUNNER_TEMP'])
    for name in ('TwichMarket-Upgrade','TwichMarket-Upgrade-RetainedData'):
        previous=temporary/name;retained_profile=temporary/('Harness-'+name)
        if previous.exists():
            if retained_profile.exists():raise ValueError('Refusing to overwrite earlier retained test data')
            shutil.move(previous,retained_profile)
    directory=ROOT/'desktop/src-tauri/target/release/bundle/nsis'
    retained=Path(os.environ['RUNNER_TEMP'])/'TwichMarket-Harness-Bundle'
    if retained.exists():raise ValueError('Refusing to overwrite the harness bundle')
    if directory.exists():shutil.move(directory,retained)
    directory.mkdir(parents=True)
    installer=directory/(proof['version']+'-setup.exe');shutil.copyfile(asset,installer)
    Path(str(installer)+'.sig').write_text(proof['updater_signature'])
    manifest={'version':proof['version'],'filename':f"TwichUI-Market-Companion-{proof['version']}-windows-x64.exe",
        'bytes':proof['installer_bytes'],'sha256':proof['installer_sha256'],'source_commit':proof['payload_source_commit'],
        'notes':'Exact-byte engineering verification; not publication approval','updater_signature':proof['updater_signature']}
    evidence=ROOT/'artifacts/companion-signed-update-test';evidence.mkdir(parents=True,exist_ok=True)
    manifest_path=evidence/'verification-manifest.json';manifest_path.write_text(json.dumps(manifest))
    environment={**os.environ,'COMPANION_UPDATER_PUBLIC_KEY':key}
    subprocess.run([str(ROOT/'desktop/target/release/examples/verify_release.exe'),str(manifest_path),str(installer)],env=environment,check=True,timeout=90)
    with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as file:
        file.write(f"RELEASE_VERSION={proof['version']}\nMARKET_TEST_EXPECTED_EXE_SHA256={proof['executable_sha256']}\nMARKET_TEST_UPDATER_SDK=true\n")
    return proof


def record(path):
    proof,key=read_proof(path)
    upgrade=prepare.read(ROOT/'artifacts/companion-v2/legacy-upgrade.json')
    harness=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if upgrade.get('source_commit')!=harness or upgrade.get('to_version')!=proof['version']:raise ValueError('Signed upgrade harness provenance differs')
    for name in ('actual_old_installer','actual_new_installer','legacy_credentials_preserved','cache_preserved','connection_settings_preserved',
            'new_native_sync','export_contract_preserved','signed_updater_sdk_install','uninstall_data_preservation_verified_by_parent'):
        if upgrade.get(name) is not True:raise ValueError('Signed updater installation/retention acceptance is incomplete')
    receipt={'schema_version':1,'payload_source_commit':proof['payload_source_commit'],'harness_source_commit':harness,
        'version':proof['version'],'installer_sha256':proof['installer_sha256'],'executable_sha256':proof['executable_sha256'],
        'updater_public_key_sha256':proof['updater_public_key_sha256'],'workflow_run_id':int(os.environ['GITHUB_RUN_ID']),
        **dict.fromkeys(('supported_sdk_signature_verified','corrupt_payload_rejected','wrong_signed_version_rejected',
            'actual_sdk_install','installed_executable_verified','reconnect_sync_export','uninstall_data_preserved'),True),
        'tray_actions_verified':False,'publication_approved':False,'deployment_approved':False}
    target=ROOT/'artifacts/companion-signed-update-test';target.mkdir(parents=True,exist_ok=True)
    (target/'signed-update-acceptance.json').write_text(json.dumps(receipt,indent=2))
    shutil.copyfile(ROOT/'artifacts/companion-v2/legacy-upgrade.json',target/'legacy-upgrade.json')
    shutil.copyfile(path,target/'signed-candidate.json')


def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_OS')!='Windows':raise ValueError('Disposable Windows runner only')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['preflight','stage','record']);parser.add_argument('--proof',type=Path,required=True);parser.add_argument('--incoming',type=Path)
    args=parser.parse_args()
    if args.mode=='preflight':preflight(args.proof)
    elif args.mode=='stage':stage(args.proof,args.incoming)
    else:record(args.proof)
    print('Public signed-candidate verification checkpoint complete. No publication or deployment.')


if __name__=='__main__':main()
