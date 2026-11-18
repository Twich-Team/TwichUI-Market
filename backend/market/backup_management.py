"""Administrator-only proxy to the private backup boundary. No archive/host mounts."""
import json
import os
from pathlib import Path
import re
import urllib.request
import urllib.error
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path as ApiPath, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from .db import session
from .models import User
from .security import admin, audit

router = APIRouter(prefix='/api/v1/admin/backups')
BackupId = Annotated[str, ApiPath(pattern=r'^[a-f0-9]{32}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PolicyValues(Strict):
    enabled: bool
    interval_seconds: int = Field(ge=3600, le=31*86400)
    daily: int = Field(ge=1, le=365)
    weekly: int = Field(ge=0, le=104)
    monthly: int = Field(ge=0, le=120)
    max_bytes: int | None = Field(ge=1024**2, le=1024**5)
    minimum_recovery_points: int = Field(ge=1, le=30)
    warning_free_bytes: int = Field(ge=2*1024**3, le=1024**5)


class Policy(Strict):
    revision: int = Field(ge=1)
    values: PolicyValues


class Deletion(Strict):
    confirmation: str = Field(min_length=1, max_length=190)


class Protection(Strict):
    protected: bool


def connect(actor, path, body=None, *, streaming=False):
    # Fixed service identity: configuration cannot turn this into an arbitrary URL proxy.
    if os.environ.get('BACKUP_MANAGEMENT_ENABLED', 'false') != 'true':
        raise HTTPException(503, 'Backup management is not installed; the existing schedule is unchanged')
    try:
        token = Path(os.environ.get('BACKUP_MANAGER_TOKEN_FILE', '/run/secrets/backup-manager-token')).read_text().strip()
        if not 32 <= len(token) <= 256:
            raise ValueError('Invalid service credential')
        request = urllib.request.Request('http://backup-manager:8091'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Authorization': 'Bearer '+token, 'X-Market-Actor': 'admin:'+str(actor), 'Content-Type': 'application/json'})
        # This internal boundary must not inherit host HTTP proxies or follow redirects.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        response = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(request, timeout=30)
        if streaming:
            return response
        with response:
            return json.loads(response.read(4*1024**2+1))
    except urllib.error.HTTPError as exc:
        # Only documented refusals may cross the boundary; never expose raw exceptions.
        if exc.code in (409, 422):
            try:
                message = json.loads(exc.read(16384)).get('detail')
                if isinstance(message, str) and len(message) <= 300:
                    raise HTTPException(exc.code, message) from None
            finally:
                exc.close()
        exc.close()
        raise HTTPException(503, 'Backup management service is unavailable') from None
    except (OSError, ValueError):
        raise HTTPException(503, 'Backup management service is unavailable') from None


def mutation(db, user, action, path, body):
    # Commit API intent first: the private service maintains the durable result receipt.
    audit(db, user.id, 'backup.'+action+'.requested', path)
    db.commit()
    try:
        result = connect(user.id, path, body)
    except HTTPException:
        audit(db, user.id, 'backup.'+action+'.refused', path)
        db.commit()
        raise
    audit(db, user.id, 'backup.'+action+'.accepted', path)
    db.commit()
    return result


@router.get('')
def inventory(offset: int = Query(0, ge=0, le=100000), limit: int = Query(20, ge=1, le=100), user: User = Depends(admin)):
    return connect(user.id, f'/overview?offset={offset}&limit={limit}')


@router.post('/policy')
def update_policy(body: Policy, user: User = Depends(admin), db: Session = Depends(session)):
    return mutation(db, user, 'policy', '/policy', body.model_dump())


@router.post('/create', status_code=202)
def create_backup(user: User = Depends(admin), db: Session = Depends(session)):
    return mutation(db, user, 'create', '/create', {})


@router.post('/{backup_id}/delete')
def delete_backup(backup_id: BackupId, body: Deletion, user: User = Depends(admin), db: Session = Depends(session)):
    return mutation(db, user, 'delete', f'/backups/{backup_id}/delete', body.model_dump())


@router.post('/{backup_id}/protect')
def protect_backup(backup_id: BackupId, body: Protection, user: User = Depends(admin), db: Session = Depends(session)):
    return mutation(db, user, 'protect', f'/backups/{backup_id}/protect', body.model_dump())


@router.get('/{backup_id}/manifest')
def manifest(backup_id: BackupId, user: User = Depends(admin), db: Session = Depends(session)):
    audit(db, user.id, 'backup.manifest.authorized', backup_id)
    db.commit()
    return connect(user.id, f'/backups/{backup_id}/manifest')


@router.get('/{backup_id}/download')
def download(backup_id: BackupId, user: User = Depends(admin), db: Session = Depends(session)):
    audit(db, user.id, 'backup.download.requested', backup_id)
    db.commit()
    response = connect(user.id, f'/backups/{backup_id}/download', streaming=True)
    disposition = response.headers.get('Content-Disposition', '')
    length = response.headers.get('Content-Length', '')
    if not re.fullmatch(r'attachment; filename="[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\.dump"', disposition) or not length.isdigit():
        response.close()
        raise HTTPException(503, 'Invalid backup download response')
    def chunks():
        try:
            while chunk := response.read(1024**2):
                yield chunk
        finally:
            response.close()
    return StreamingResponse(chunks(), media_type='application/octet-stream', headers={
        'Content-Disposition': disposition, 'Content-Length': length, 'Cache-Control': 'no-store'})
