"""Inactive-by-default private unsigned beta delivery; never an update source.

The dedicated operator store is trusted to admit actual CI/owner receipts. These
routes recheck identity, original evidence and bytes, and require an allowlisted
active browser session on every request. Stable release policy stays separate.
"""
from datetime import datetime
import hashlib
import os
from pathlib import Path
import re
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from .companion_releases import REQUIRED_TESTS, bounded_json, file_digest
from .models import User
from .security import identity

router=APIRouter(prefix='/api/v1/companion/private-beta')
VERSION=r'2\.(?:0|[1-9][0-9]{0,3})\.(?:0|[1-9][0-9]{0,3})-beta\.[1-9][0-9]{0,3}'
SHA=Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
COMMIT=Annotated[str,Field(pattern=r'^[a-f0-9]{40}$')]
WORKFLOWS={'windows':'.github/workflows/desktop.yml','backend':'.github/workflows/backend.yml','website':'.github/workflows/web.yml'}
EVIDENCE={'installed-smoke.json','legacy-upgrade.json','performance.json','launch-metrics.json','windows-signature.json','owner-private-beta-approval.json'}
GAPS={'tray_actions','authenticode','signed_update_install'}


class CI(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    id:Annotated[int,Field(ge=1)]
    source_commit:COMMIT
    repository:Literal['Twich-Team/TwichUI-Market']
    path:str
    status:Literal['completed']
    conclusion:Literal['success']


class Manifest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version:Literal[1]
    channel:Literal['private-beta']
    version:Annotated[str,Field(pattern='^'+VERSION+'$')]
    filename:str
    bytes:Annotated[int,Field(ge=1024,le=64*1024*1024)]
    sha256:SHA
    source_commit:COMMIT
    visual_approval_commit:COMMIT
    workflow_run_id:Annotated[int,Field(ge=1)]
    published_at:str
    authenticode_status:Literal['NotSigned']
    updates:Literal['manual']
    acceptance:dict[str,bool]
    unverified_requirements:list[str]
    ci:dict[str,CI]
    evidence_sha256:dict[str,SHA]
    notes:Annotated[str,Field(max_length=4000)]


def root():
    value=os.environ.get('COMPANION_PRIVATE_BETA_DIRECTORY','')
    if not value:raise ValueError('Private beta store is not configured')
    path=Path(value)
    if path.is_symlink():raise ValueError('Invalid private beta store')
    return path.resolve(strict=True)


def reader(request:Request,user:User=Depends(identity)):
    if request.state.credential.kind!='session':raise HTTPException(403,'Website sign-in required')
    configured=os.environ.get('COMPANION_PRIVATE_BETA_USER_IDS','')
    entries=configured.split(',')
    # This is explicitly a three-person pilot, not an implicit all-account feed.
    if (len(configured)>128 or not 1<=len(entries)<=3 or len(set(entries))!=len(entries)
            or not all(re.fullmatch(r'[1-9][0-9]{0,9}',entry) for entry in entries)
            or str(user.id) not in entries):
        raise HTTPException(404,'Private beta not available')
    return user


def digest_file(path):
    if path.is_symlink() or not path.is_file():raise ValueError('Invalid private beta evidence')
    raw=bounded_json(path)
    if not isinstance(raw,dict):raise ValueError('Invalid private beta evidence document')
    return hashlib.sha256(path.read_bytes()).hexdigest(),raw


def validate_evidence(manifest,directory):
    if set(manifest.evidence_sha256)!=EVIDENCE:raise ValueError('Private beta evidence is incomplete')
    documents={}
    for name in sorted(EVIDENCE):
        digest,value=digest_file(directory/name)
        if digest!=manifest.evidence_sha256[name]:raise ValueError('Private beta evidence changed')
        documents[name]=value
    installed=documents['installed-smoke.json'];upgrade=documents['legacy-upgrade.json']
    if (installed.get('source_commit')!=manifest.source_commit or upgrade.get('source_commit')!=manifest.source_commit
            or installed.get('version')!=manifest.version or upgrade.get('to_version')!=manifest.version):
        raise ValueError('Installed beta acceptance source/version differs')
    for name in ('native_browser_approval_ui','native_thread_hidden_sync','single_instance_restore','preferences_saved',
            'credential_and_cache_restart','hidden_startup','current_user_autostart_enable_disable','native_minimize_close_to_tray',
            'export_valid','server_revocation','offline_cache_preserved','website_approval_ui_verified','uninstall_settings_and_cache_preserved','updater_disabled'):
        if installed.get(name) is not True:raise ValueError('Private beta installed acceptance is incomplete')
    if installed.get('tray_acceptance')!='unverified' or installed.get('tray_settings_sync_pause_open_quit') is not False:
        raise ValueError('Private beta tray status must remain explicit')
    for name in ('actual_old_installer','actual_new_installer','legacy_credentials_preserved','cache_preserved',
            'connection_settings_preserved','legacy_metadata_migrated','new_native_sync','export_contract_preserved','uninstall_data_preservation_verified_by_parent'):
        if upgrade.get(name) is not True:raise ValueError('Private beta upgrade/uninstall evidence is incomplete')
    if upgrade.get('signed_updater_sdk_install') is not False:raise ValueError('Private beta is manual-update only')
    perf=documents['performance.json'];network=perf.get('idle_market_api_requests',{})
    if (perf.get('source_commit')!=manifest.source_commit or not perf.get('resources') or not network.get('before')
            or network.get('before')!=network.get('after')):raise ValueError('Private beta idle performance evidence differs')
    launch=documents['launch-metrics.json']
    if launch.get('installer_bytes')!=manifest.bytes:raise ValueError('Private beta installer size differs from installed acceptance')
    signature=documents['windows-signature.json']
    if (signature.get('source_commit')!=manifest.source_commit or signature.get('status')!='NotSigned'
            or signature.get('sha256')!=manifest.sha256 or signature.get('bytes')!=manifest.bytes):
        raise ValueError('Actual Windows signature evidence differs')
    owner=documents['owner-private-beta-approval.json']
    if (type(owner.get('schema_version')) is not int or owner.get('schema_version')!=1 or owner.get('owner_authorized_private_beta') is not True
            or owner.get('scope')!='private-unsigned-beta-with-manual-updates' or not owner.get('owner_statement')
            or owner.get('visual_approval_commit')!=manifest.visual_approval_commit):
        raise ValueError('Explicit owner private-beta authorization is missing')


def load(version,store=None):
    if not isinstance(version,str) or not re.fullmatch(VERSION,version):raise ValueError('Invalid private beta version')
    directory=(Path(store).resolve(strict=True) if store is not None else root())/version
    if directory.is_symlink():raise ValueError('Invalid private beta directory')
    raw=bounded_json(directory/'manifest.json')
    if not isinstance(raw,dict) or type(raw.get('schema_version')) is not int:raise ValueError('Invalid private beta schema')
    manifest=Manifest.model_validate(raw)
    if manifest.version!=version or manifest.filename!=f'TwichUI-Market-Companion-{version}-windows-x64.exe':
        raise ValueError('Invalid private beta identity')
    if datetime.fromisoformat(manifest.published_at).tzinfo is None:raise ValueError('Private beta time needs timezone')
    if (set(manifest.acceptance)!=REQUIRED_TESTS or manifest.acceptance.get('tray') is not False
            or not all(value for name,value in manifest.acceptance.items() if name!='tray')):
        raise ValueError('Non-tray beta acceptance is incomplete')
    if len(manifest.unverified_requirements)!=len(GAPS) or set(manifest.unverified_requirements)!=GAPS:
        raise ValueError('Private beta verification gaps must remain explicit')
    if set(manifest.ci)!=set(WORKFLOWS):raise ValueError('Private beta CI evidence is incomplete')
    for name,path in WORKFLOWS.items():
        run=manifest.ci[name]
        if run.source_commit!=manifest.source_commit or run.path!=path:raise ValueError('Canonical exact-source CI is required')
    if manifest.ci['windows'].id!=manifest.workflow_run_id:raise ValueError('Windows beta build provenance differs')
    validate_evidence(manifest,directory)
    asset=directory/manifest.filename;stat=asset.stat()
    if asset.is_symlink() or not asset.is_file() or stat.st_size!=manifest.bytes:raise ValueError('Invalid private beta installer')
    if file_digest(str(asset),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)!=manifest.sha256:raise ValueError('Private beta digest mismatch')
    return manifest,asset


def latest():
    pointer=bounded_json(root()/'current.json')
    if set(pointer)!={'schema_version','version'} or type(pointer['schema_version']) is not int or pointer['schema_version']!=1:
        raise ValueError('Invalid private beta pointer')
    return load(pointer['version'])[0]


@router.get('/current')
def current(user:User=Depends(reader)):
    try:manifest=latest()
    except (OSError,ValueError,KeyError,TypeError):
        return {'contract_version':1,'ready':False,'channel':'private-beta','version':None,'download_url':None,
            'message':'The private Windows beta is not available yet.'}
    return {'contract_version':1,'ready':True,'channel':'private-beta','version':manifest.version,
        'download_url':f'/api/v1/companion/private-beta/{manifest.version}/windows-x64','bytes':manifest.bytes,'sha256':manifest.sha256,
        'source_commit':manifest.source_commit,'published_at':manifest.published_at,'updates':'manual','signed':False,
        'tray_actions_verified':False,'notes':manifest.notes,
        'message':'Private Windows beta. Unsigned installer; manual updates. Tray actions are still being checked.'}


@router.get('/{version}/windows-x64')
def download(version:str,user:User=Depends(reader)):
    try:manifest,asset=load(version)
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(404,'Private beta installer not available')
    return FileResponse(asset,filename=manifest.filename,media_type='application/vnd.microsoft.portable-executable',
        headers={'X-Installer-SHA256':manifest.sha256,'Cache-Control':'private, no-store'})
