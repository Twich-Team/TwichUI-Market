"""Stage public-only signing inputs after canonical CI; no signing/publication.

Original installed receipts identify the exact unsigned Windows candidate. The
owner strategy authorizes engineering signing, not live publication/deployment.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('beta_prepare',ROOT/'scripts/prepare-companion-private-beta.py')
prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)


def stage(installer,acceptance,source,runs,artifact_id,output):
    config=prepare.source_config(source,'e55807c58c4cf68560729471019b88cc518fb5b0')
    version=config['version'];key=(ROOT/'desktop/src-tauri/updater-public-key.txt').read_text().strip()
    committed=subprocess.check_output(['git','show',source+':desktop/src-tauri/updater-public-key.txt'],cwd=ROOT,text=True).strip()
    if key!=committed:raise ValueError('Signing host and exact payload source public keys differ')
    key_hash=hashlib.sha256(key.encode()).hexdigest()
    if set(runs)!=set(prepare.WORKFLOWS):raise ValueError('All canonical source CI runs required')
    ci={name:prepare.workflow(runs[name],path,source) for name,path in prepare.WORKFLOWS.items()}
    if type(artifact_id) is not int or artifact_id<1:raise ValueError('Exact original installer artifact required')
    installer=Path(installer);prepare.unsigned_pe(installer);size=installer.stat().st_size;digest=prepare.sha(installer)
    signature=prepare.read(Path(acceptance)/'windows-signature.json')
    installed=prepare.read(Path(acceptance)/'installed-smoke.json');upgrade=prepare.read(Path(acceptance)/'legacy-upgrade.json')
    launch=prepare.read(Path(acceptance)/'launch-metrics.json');performance=prepare.read(Path(acceptance)/'performance.json')
    import re
    if (signature.get('source_commit')!=source or signature.get('status')!='NotSigned' or signature.get('sha256')!=digest
            or signature.get('bytes')!=size or signature.get('updater_public_key_sha256')!=key_hash
            or signature.get('executable_reference')!='actual-installed-windows-executable'
            or installed.get('installed_executable_sha256')!=signature.get('executable_sha256')
            or not re.fullmatch(r'[a-f0-9]{64}',signature.get('executable_sha256',''))):raise ValueError('Original Windows candidate identity differs')
    if (installed.get('source_commit')!=source or installed.get('version')!=version or installed.get('updater_disabled') is not False
            or installed.get('updater_public_key_sha256')!=key_hash or launch.get('installer_bytes')!=size):raise ValueError('Installed key/version/size differs')
    for name in ('native_browser_approval_ui','native_thread_hidden_sync','single_instance_restore','preferences_saved','credential_and_cache_restart',
            'hidden_startup','current_user_autostart_enable_disable','native_minimize_close_to_tray','export_valid','server_revocation',
            'offline_cache_preserved','website_approval_ui_verified','uninstall_settings_and_cache_preserved','update_checks_blocked_for_custom_server'):
        if installed.get(name) is not True:raise ValueError('Native installed candidate acceptance incomplete')
    if upgrade.get('source_commit')!=source or upgrade.get('to_version')!=version:raise ValueError('Upgrade provenance differs')
    for name in ('actual_old_installer','actual_new_installer','legacy_credentials_preserved','cache_preserved','connection_settings_preserved',
            'legacy_metadata_migrated','new_native_sync','export_contract_preserved','uninstall_data_preservation_verified_by_parent'):
        if upgrade.get(name) is not True:raise ValueError('Upgrade/uninstall acceptance incomplete')
    network=performance.get('idle_market_api_requests',{})
    if performance.get('source_commit')!=source or not performance.get('resources') or not network.get('before') or network.get('before')!=network.get('after'):
        raise ValueError('Idle resource/network acceptance incomplete')
    candidate={'schema_version':1,'version':version,'payload_source_commit':source,**{name+'_run_id':int(run) for name,run in runs.items()},
        'installer_artifact_id':artifact_id,'installer_sha256':digest,'installer_bytes':size,'executable_sha256':signature['executable_sha256'],
        'updater_public_key_sha256':key_hash,'ci':ci}
    output=Path(output)
    if output.is_symlink() or output.exists():raise ValueError('Never overwrite signing inputs')
    output.mkdir(mode=0o700,parents=True)
    shutil.copyfile(installer,output/'installer.exe');os.chmod(output/'installer.exe',0o600)
    (output/'candidate.json').write_text(json.dumps(candidate,indent=2));os.chmod(output/'candidate.json',0o600)
    return candidate


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installer',type=Path,required=True);parser.add_argument('--acceptance',type=Path,required=True)
    parser.add_argument('--source-commit',required=True);parser.add_argument('--installer-artifact-id',type=int,required=True)
    parser.add_argument('--windows-run',required=True);parser.add_argument('--backend-run',required=True);parser.add_argument('--website-run',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();stage(args.installer,args.acceptance,args.source_commit,
        {'windows':args.windows_run,'backend':args.backend_run,'website':args.website_run},args.installer_artifact_id,args.output)
    print('Exact passed Windows candidate staged for local Tauri signing. No private key read, publication or deployment.')


if __name__=='__main__':main()
