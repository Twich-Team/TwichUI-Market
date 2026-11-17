import ipaddress
import json
import math
import secrets
from . import environment as settings
import os
import re
import secrets
from typing import Literal
from datetime import timedelta
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from pydantic import BaseModel, Field
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .db import now, session
from .models import CompanionDevice, Credential, Invitation, LoginAttempt, SecurityEvent, User
from .security import DUMMY_HASH, admin, audit, aware, digest, hasher, identity, issue, verify

app = FastAPI(title="TwichUI Market", version="0.1.0", docs_url=None, redoc_url=None)
from .market_api import router as market_router
app.include_router(market_router)
from .catalogue import router as catalogue_router
app.include_router(catalogue_router)
from .item_profiles import router as profile_router
app.include_router(profile_router)
from .metadata_admin import router as metadata_admin_router
app.include_router(metadata_admin_router)
from .admin_records import router as admin_records_router
app.include_router(admin_records_router)
from .metadata_api import router as metadata_catalog_router
app.include_router(metadata_catalog_router)
from .distribution import router as distribution_router
app.include_router(distribution_router)
from .sync_api import router as sync_router
app.include_router(sync_router)
from .retention import router as retention_router
app.include_router(retention_router)
from .market_configuration import router as configuration_router
app.include_router(configuration_router)
from .current_listings import router as listings_router
app.include_router(listings_router)
from .intraday_history import router as intraday_router
app.include_router(intraday_router)
from .preferences import router as preferences_router
app.include_router(preferences_router)
from .companion_auth import router as companion_auth_router
app.include_router(companion_auth_router)
from .companion_devices import DeviceId, Rename, router as companion_devices_router
from .companion_releases import router as companion_releases_router
from .companion_private_beta import router as companion_private_beta_router
app.include_router(companion_devices_router)
app.include_router(companion_releases_router)
app.include_router(companion_private_beta_router)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
ORIGIN = os.environ.get("APP_ORIGIN", "https://localhost")

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request, error):
    if request.url.path.startswith('/api/v1/admin/metadata-providers'):
        return Response(status_code=422, content='{"detail":"Invalid provider settings or credential input"}', media_type='application/json')
    return await request_validation_exception_handler(request, error)


def finite_json_number(value):
    number=float(value)
    if not math.isfinite(number):
        raise ValueError('Nonfinite JSON number')
    return number


def reject_json_constant(value):
    raise ValueError('Invalid JSON constant')


@app.middleware("http")
async def security_headers(request, call_next):
    if settings.INGRESS_TOKEN and request.url.path!='/api/v1/health':
        if not secrets.compare_digest(request.headers.get('x-market-proxy-token',''),settings.INGRESS_TOKEN):
            return Response(status_code=403)
        try:client=str(ipaddress.ip_address(request.headers.get('x-market-client-ip','')))
        except ValueError:return Response(status_code=400)
        request.scope['client']=(client,0)
        request.scope['scheme']='https'
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin != ORIGIN:
            return Response(status_code=403)
        personal_preference = ((request.method=='PATCH' and request.url.path=='/api/v1/me/preferences')
            or (request.method=='POST' and request.url.path=='/api/v1/me/preferences/reset'))
        native_personal = request.url.path in ('/api/v1/companion/authorizations', '/api/v1/companion/token',
            '/api/v1/companion/activity', '/api/v1/companion/devices/self/revoke') or bool(re.fullmatch(
                r'/api/v1/companion/authorizations/[A-Za-z0-9_-]{43}/decision', request.url.path))
        native_personal = native_personal or bool(request.method in ('PATCH','DELETE') and
            re.fullmatch(r'/api/v1/companion/devices/[0-9]+', request.url.path))
        if settings.READ_ONLY and request.url.path not in ('/api/v1/auth/login','/api/v1/auth/logout') and not personal_preference and not native_personal:
            return Response(status_code=403,content='{"detail":"Interactive preview is read-only; use production for changes."}',media_type='application/json')
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 16384:
            return Response(status_code=413)
        native_body = request.url.path.startswith('/api/v1/companion/')
        if personal_preference or native_body or request.url.path.startswith('/api/v1/admin/metadata-providers'):
            chunks=[]
            size=0
            async for chunk in request.stream():
                size+=len(chunk)
                if size>(8192 if native_body else 4096):
                    return Response(status_code=413)
                chunks.append(chunk)
            request._body=b''.join(chunks)
            if request._body and request.url.path != '/api/v1/companion/token':
                try:
                    json.loads(request._body,parse_float=finite_json_number,parse_constant=reject_json_constant)
                except (ValueError,UnicodeDecodeError):
                    return Response(status_code=422,content='{"detail":"Use valid JSON with finite numbers."}',media_type='application/json')
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    artwork=request.method=="GET" and response.status_code in (200,304) and re.fullmatch(r"/api/v1/items/(?:us|eu|kr|tw)/[0-9]+/icon",request.url.path)
    if not artwork:response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


class Login(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=128)


class Registration(Login):
    invitation: str = Field(min_length=20, max_length=128)


class DeviceInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class UserUpdate(BaseModel):
    role: Literal["member", "admin"]
    active: bool


def user_view(user):
    return {"id": user.id, "username": user.username, "role": user.role, "active": user.active}


@app.get("/api/v1/health")
def health(db: Session = Depends(session)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "contract_version": 1}


@app.post("/api/v1/auth/register", status_code=201)
def register(body: Registration, db: Session = Depends(session)):
    username = body.username.lower().strip()
    if not re.fullmatch(r"[a-z0-9_]{3,64}", username):
        raise HTTPException(422, "Use 3–64 lowercase letters, digits or underscores")
    # Atomic claim prevents simultaneous redemption; rollback restores on duplicate username.
    claimed = db.execute(update(Invitation).where(
        Invitation.token_hash == digest(body.invitation), Invitation.used.is_(False),
        Invitation.expires_at > now()).values(used=True))
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, "Invitation invalid or expired")
    user = User(username=username, password_hash=hasher.hash(body.password), role="member")
    db.add(user)
    try:
        db.flush()
        audit(db, user.id, "user.registered")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username unavailable")
    return user_view(user)


@app.post("/api/v1/auth/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(session)):
    # Fixed windows stored in the database, shared across API processes.
    key = digest(f"{request.client.host if request.client else 'unknown'}:{body.username.lower()}")
    attempt = db.get(LoginAttempt, key, with_for_update=True)
    if not attempt:
        attempt = LoginAttempt(key=key, count=0, window_start=now())
        db.add(attempt)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(429, "Try again later")
    if aware(attempt.window_start) < now() - timedelta(minutes=15):
        attempt.count, attempt.window_start = 0, now()
    if attempt.count >= 10:
        raise HTTPException(429, "Try again later")
    attempt.count += 1
    user = db.scalar(select(User).where(User.username == body.username.lower()))
    valid = verify(user.password_hash if user else DUMMY_HASH, body.password)
    if not valid or not user or not user.active:
        audit(db, None, "login.failed")
        db.commit()
        raise HTTPException(401, "Invalid credentials")
    attempt.count = 0
    token, csrf, _ = issue(db, user, "session")
    audit(db, user.id, "login.succeeded")
    db.commit()
    response.set_cookie(settings.SESSION_COOKIE_NAME, token, httponly=True, secure=COOKIE_SECURE,
                        samesite="strict", max_age=86400, path="/api")
    return {"user": user_view(user), "csrf_token": csrf}


@app.get('/api/v1/environment')
def environment(user: User=Depends(identity)):
    return {'read_only':settings.READ_ONLY,'origin':ORIGIN}


@app.get("/api/v1/auth/me")
def me(user: User = Depends(identity)):
    return user_view(user)


@app.get('/api/v1/auth/session')
def browser_session(request: Request,user: User = Depends(identity)):
    if request.state.credential.kind!='session':
        raise HTTPException(403,'Browser session required')
    return {'user':user_view(user),'csrf_token':digest('csrf:'+request.cookies[settings.SESSION_COOKIE_NAME])}


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=12,max_length=128)
    new_password: str = Field(min_length=12,max_length=128)


@app.post('/api/v1/auth/password',status_code=204)
def change_password(body: PasswordChange,request: Request,user: User = Depends(identity),db: Session = Depends(session)):
    if request.state.credential.kind!='session':
        raise HTTPException(403,'Browser session required')
    if not verify(user.password_hash,body.current_password):
        raise HTTPException(403,'Current password incorrect')
    user.password_hash=hasher.hash(body.new_password)
    db.execute(update(CompanionDevice).where(CompanionDevice.user_id==user.id).values(revoked=True))
    db.execute(update(Credential).where(Credential.user_id==user.id).values(revoked=True))
    audit(db,user.id,'password.changed')
    db.commit()


@app.post("/api/v1/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(identity), db: Session = Depends(session)):
    request.state.credential.revoked = True
    audit(db, user.id, "logout")
    db.commit()
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/api")


@app.post("/api/v1/devices", status_code=201)
def create_device(body: DeviceInput, request: Request, user: User = Depends(identity), db: Session = Depends(session)):
    if request.state.credential.kind != "session":
        raise HTTPException(403, "Browser session required")
    token, _, row = issue(db, user, "device", body.name)
    audit(db, user.id, "device.created")
    db.commit()
    return {"id": row.id, "token": token, "expires_at": row.expires_at}


@app.get("/api/v1/devices")
def devices(user: User = Depends(identity), db: Session = Depends(session)):
    rows = db.scalars(select(Credential).where(Credential.kind == "device", Credential.user_id == user.id))
    return [{"id": r.id, "name": r.name, "revoked": r.revoked, "expires_at": r.expires_at} for r in rows]


@app.delete("/api/v1/devices/{device_id}", status_code=204)
def revoke_device(device_id: int, user: User = Depends(identity), db: Session = Depends(session)):
    row = db.get(Credential, device_id)
    if not row or row.kind != "device" or (row.user_id != user.id and user.role != "admin"):
        raise HTTPException(404, "Device not found")
    row.revoked = True
    if row.companion_device_id is not None:
        from .companion_auth import _revoke
        device = db.get(CompanionDevice, row.companion_device_id)
        if device is not None:
                _revoke(db, device, 'account_revocation', actor_id=user.id)
    audit(db, user.id, "device.revoked", str(device_id))
    db.commit()


@app.patch('/api/v1/devices/{device_id}')
def rename_legacy_device(device_id: DeviceId, body: Rename, request: Request,
                         user: User = Depends(identity), db: Session = Depends(session)):
    if request.state.credential.kind != 'session':
        raise HTTPException(403, 'Website session required')
    row = db.get(Credential, device_id)
    if row is None or row.kind != 'device' or row.user_id != user.id:
        raise HTTPException(404, 'Device not found')
    row.name = body.name
    audit(db, user.id, 'device.renamed', str(row.id))
    db.commit()
    return {'id': row.id, 'name': row.name, 'revoked': row.revoked, 'expires_at': row.expires_at}


@app.post("/api/v1/admin/invitations", status_code=201)
def invite(user: User = Depends(admin), db: Session = Depends(session)):
    token = secrets.token_urlsafe(32)
    invitation = Invitation(token_hash=digest(token), created_by=user.id, expires_at=now() + timedelta(days=7))
    db.add(invitation)
    audit(db, user.id, "invitation.created")
    db.commit()
    return {"token": token, "expires_at": invitation.expires_at}


@app.get("/api/v1/admin/users")
def users(include_archived: bool = False, user: User = Depends(admin), db: Session = Depends(session)):
    return [{**user_view(row), "archived_at": row.archived_at} for row in db.scalars(select(User).where(True if include_archived else User.archived_at.is_(None)).order_by(User.id))]


@app.get('/api/v1/admin/invitations')
def invitations(user: User = Depends(admin),db: Session = Depends(session)):
    rows=db.scalars(select(Invitation).order_by(Invitation.id.desc()).limit(200))
    return [{'id':row.id,'expires_at':row.expires_at,'used':row.used} for row in rows]


@app.delete('/api/v1/admin/invitations/{invitation_id}',status_code=204)
def revoke_invitation(invitation_id: int,user: User = Depends(admin),db: Session = Depends(session)):
    row=db.get(Invitation,invitation_id)
    if not row:
        raise HTTPException(404,'Invitation not found')
    row.used=True
    audit(db,user.id,'invitation.revoked',str(row.id))
    db.commit()


@app.get('/api/v1/admin/devices')
def all_devices(user: User = Depends(admin),db: Session = Depends(session)):
    rows=db.scalars(select(Credential).where(Credential.kind=='device').order_by(Credential.id.desc()).limit(200))
    return [{'id':row.id,'user_id':row.user_id,'name':row.name,'revoked':row.revoked,'expires_at':row.expires_at} for row in rows]


@app.patch("/api/v1/admin/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, user: User = Depends(admin), db: Session = Depends(session)):
    # Serialize administrator changes to preserve at least one active administrator.
    administrators = list(db.scalars(select(User).where(User.role == "admin").order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    # Authentication may precede another administrator's committed access change.
    # Refresh cached ORM identities after acquiring the administrator locks.
    db.refresh(user)
    if not user.active or user.role != 'admin' or user.archived_at is not None:
        raise HTTPException(403, 'Administrator access changed; sign in again')
    target = db.get(User, user_id, populate_existing=True)
    if not target:
        raise HTTPException(404, "User not found")
    if target.role == "admin" and target.active and (body.role != "admin" or not body.active):
        if sum(row.active for row in administrators) <= 1:
            raise HTTPException(409, "Keep at least one active administrator")
    if target.id == user.id and not body.active:
        raise HTTPException(409, "You cannot disable your own account")
    if target.archived_at is not None and body.active:
        raise HTTPException(409, "Restore the archived account before enabling access")
    target.role, target.active = body.role, body.active
    if not body.active:
        db.execute(update(CompanionDevice).where(CompanionDevice.user_id == target.id).values(revoked=True))
        db.execute(update(Credential).where(Credential.user_id == target.id).values(revoked=True))
    audit(db, user.id, "user.updated", str(target.id))
    db.commit()
    return user_view(target)


class ArchiveMember(BaseModel):
    confirmation: str = Field(min_length=1, max_length=64)


@app.post('/api/v1/admin/users/{user_id}/archive')
def archive_member(user_id: int, body: ArchiveMember, user: User = Depends(admin), db: Session = Depends(session)):
    administrators = list(db.scalars(select(User).where(User.role == 'admin').order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    # Authentication may precede another administrator's committed access change.
    # Refresh cached ORM identities after acquiring the administrator locks.
    db.refresh(user)
    if not user.active or user.role != 'admin' or user.archived_at is not None:
        raise HTTPException(403, 'Administrator access changed; sign in again')
    target = db.get(User, user_id, populate_existing=True)
    if target is None:
        raise HTTPException(404, 'User not found')
    if body.confirmation != target.username:
        raise HTTPException(409, 'Type the exact account name to confirm archival')
    if target.id == user.id:
        raise HTTPException(409, 'You cannot archive your own account')
    if target.active and target.role == 'admin' and sum(row.active for row in administrators) <= 1:
        raise HTTPException(409, 'Keep at least one active administrator')
    target.active = False
    target.archived_at = target.archived_at or now()
    db.execute(update(Credential).where(Credential.user_id == target.id).values(revoked=True))
    db.execute(update(CompanionDevice).where(CompanionDevice.user_id == target.id).values(revoked=True))
    audit(db, user.id, 'user.archived', f'user={target.id}; access revoked; audit and owned records retained')
    db.commit()
    return user_view(target)


@app.post('/api/v1/admin/users/{user_id}/restore')
def restore_member(user_id: int, user: User = Depends(admin), db: Session = Depends(session)):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'User not found')
    target.archived_at = None
    audit(db, user.id, 'user.archive.restored', f'user={target.id}; access remains disabled')
    db.commit()
    return user_view(target)


@app.get("/api/v1/admin/security-events")
def events(user: User = Depends(admin), db: Session = Depends(session)):
    return [{"id": r.id, "actor_id": r.actor_id, "action": r.action, "detail": r.detail,
             "created_at": r.created_at} for r in db.scalars(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(200))]

# Separate, opt-in bridge API. Existing synchronization and collector behavior stay unchanged.
from .bridge_api import router as bridge_router
app.include_router(bridge_router)

from .archive_api import router as archive_router
app.include_router(archive_router)
