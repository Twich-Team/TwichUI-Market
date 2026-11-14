"""Read-only, controlled installer delivery. No web endpoint can publish a release.

The owner-controlled publisher must verify Windows CI, Authenticode and updater
signatures before writing an immutable version directory and atomic current.json.
The API verifies its trusted receipt, pinned publisher/key identity and file digest.
Native automatic updates additionally verify the pinned updater signature themselves.
Missing configuration, approvals, tests or assets fail closed; CI previews are never stable.
"""
import base64
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from typing import Annotated, Literal

router=APIRouter(prefix='/api/v1/companion/releases')
VERSION=r'2\.[0-9]{1,4}\.[0-9]{1,4}'
REQUIRED_TESTS={'windows_core','installed_ui','native_browser_approval','hidden_sync','tray','autostart','restart','upgrade','uninstall','no_release_debug','preferences','revocation','offline_cache','performance'}

class Manifest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version:Literal[1]
    channel:Literal['stable']
    version:Annotated[str,Field(pattern='^'+VERSION+'$')]
    filename:str
    bytes:Annotated[int,Field(ge=1024,le=64*1024*1024)]
    sha256:Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
    source_commit:Annotated[str,Field(pattern=r'^[a-f0-9]{40}$')]
    workflow_run_id:Annotated[int,Field(ge=1)]
    published_at:str
    publisher_thumbprint:Annotated[str,Field(pattern=r'^[A-F0-9]{40}$')]
    authenticode_status:Literal['Valid']
    updater_public_key_sha256:Annotated[str,Field(pattern=r'^[a-f0-9]{64}$')]
    updater_signature:Annotated[str,Field(min_length=32,max_length=4096)]
    visual_approval_commit:Annotated[str,Field(pattern=r'^[a-f0-9]{40}$')]
    acceptance:dict[str,bool]
    notes:Annotated[str,Field(max_length=4000)]


def root():
    value=os.environ.get('COMPANION_RELEASE_DIRECTORY','')
    if not value:raise ValueError('Release store not configured')
    return Path(value).resolve(strict=True)


def bounded_json(path):
    if path.is_symlink() or path.stat().st_size>16384:raise ValueError('Invalid release receipt')
    with path.open('rb') as file:
        content=file.read(16385)
    if len(content)>16384:raise ValueError('Invalid release receipt')
    return json.loads(content)


@lru_cache(maxsize=8)
def file_digest(path,device,inode,size,modified):
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        while chunk:=file.read(64*1024):digest.update(chunk)
    return digest.hexdigest()


def load(version, store=None):
    if not re.fullmatch(VERSION,version):raise ValueError('Invalid release version')
    directory=(Path(store).resolve(strict=True) if store is not None else root())/version
    if directory.is_symlink():raise ValueError('Invalid release directory')
    manifest=Manifest.model_validate(bounded_json(directory/'manifest.json'))
    if manifest.version!=version or manifest.filename!=f'TwichUI-Market-Companion-{version}-windows-x64.exe':raise ValueError('Invalid release identity')
    stamp=datetime.fromisoformat(manifest.published_at)
    if stamp.tzinfo is None:raise ValueError('Release time needs timezone')
    if set(manifest.acceptance)!=REQUIRED_TESTS or not all(manifest.acceptance.values()):raise ValueError('Incomplete acceptance')
    publisher=os.environ.get('COMPANION_PUBLISHER_THUMBPRINT','').upper()
    key=os.environ.get('COMPANION_UPDATER_PUBLIC_KEY','')
    if (not publisher or manifest.publisher_thumbprint!=publisher or not key
            or hashlib.sha256(key.encode()).hexdigest()!=manifest.updater_public_key_sha256):raise ValueError('Release trust is not configured')
    base64.b64decode(manifest.updater_signature,validate=True)
    asset=directory/manifest.filename
    stat=asset.stat()
    if asset.is_symlink() or not asset.is_file() or stat.st_size!=manifest.bytes:raise ValueError('Invalid installer size')
    if file_digest(str(asset),stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)!=manifest.sha256:raise ValueError('Installer digest mismatch')
    return manifest,asset


@router.get('/current')
def current():
    try:
        manifest=latest()
        return {'contract_version':1,'ready':True,'version':manifest.version,'platform':'windows-x64',
            'download_url':f'/api/v1/companion/releases/{manifest.version}/windows-x64','bytes':manifest.bytes,
            'sha256':manifest.sha256,'published_at':manifest.published_at,'message':'Verified Windows release',
            'source_commit':manifest.source_commit,'notes':manifest.notes}
    except (OSError,ValueError,KeyError,TypeError):
        return {'contract_version':1,'ready':False,'version':None,'platform':'windows-x64','download_url':None,
            'bytes':None,'sha256':None,'published_at':None,
            'message':'The Windows download will appear after release verification and signing are complete. Existing connections keep working.'}


def latest():
    pointer=bounded_json(root()/'current.json')
    if set(pointer)!={'schema_version','version'} or type(pointer['schema_version']) is not int or pointer['schema_version']!=1 or not isinstance(pointer['version'],str):raise ValueError('Invalid release pointer')
    manifest,_=load(pointer['version'])
    return manifest


@router.get('/update/windows-x86_64/{installed}')
def update_metadata(installed:str):
    # Tauri also compares SemVer and cryptographically verifies the signed version.
    match=re.fullmatch(r'(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})\.(0|[1-9][0-9]{0,3})(-[a-zA-Z0-9.-]{1,32})?',installed)
    if not match:raise HTTPException(404,'Verified update not available')
    try:manifest=latest()
    except (OSError,ValueError,KeyError,TypeError):return Response(status_code=204,headers={'Cache-Control':'no-store'})
    current=tuple(int(match[index]) for index in (1,2,3))
    release=tuple(map(int,manifest.version.split('.')))
    if current>release or (current==release and not match[4]):return Response(status_code=204,headers={'Cache-Control':'no-store'})
    return {'version':manifest.version,'pub_date':manifest.published_at,'notes':manifest.notes,
        'url':f'https://market.twich.gg/api/v1/companion/releases/{manifest.version}/windows-x64',
        'signature':manifest.updater_signature,'bytes':manifest.bytes,'sha256':manifest.sha256,'source_commit':manifest.source_commit}


@router.get('/{version}/windows-x64')
def download(version:str):
    try:manifest,asset=load(version)
    except (OSError,ValueError,KeyError,TypeError):raise HTTPException(404,'Verified installer not available')
    return FileResponse(asset,filename=manifest.filename,media_type='application/vnd.microsoft.portable-executable',
        headers={'X-Installer-SHA256':manifest.sha256})
