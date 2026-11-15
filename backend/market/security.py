import hashlib
import secrets
import re
from datetime import timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import now, session
from .models import CompanionDevice, Credential, SecurityEvent, User
from . import environment as settings

hasher = PasswordHasher(time_cost=3, memory_cost=19456, parallelism=1)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def verify(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def audit(db, actor, action, detail=""):
    db.add(SecurityEvent(actor_id=actor, action=action, detail=detail))


def issue(db, user, kind, name="browser"):
    token = secrets.token_urlsafe(32)
    csrf = digest('csrf:'+token)
    row = Credential(user_id=user.id, token_hash=digest(token), kind=kind, name=name, audience=settings.SESSION_ORIGIN if kind=="session" else None,
                     csrf_hash=digest(csrf) if kind == "session" else None,
                     expires_at=now() + timedelta(days=1 if kind == "session" else 90))
    db.add(row)
    return token, csrf, row


def identity(request: Request, db: Session = Depends(session)):
    authorization = request.headers.get("authorization", "")
    bearer = authorization.startswith("Bearer ")
    token = authorization[7:] if bearer else request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token or len(token) > 256:
        raise HTTPException(401, "Authentication required")
    credential = db.scalar(select(Credential).where(Credential.token_hash == digest(token)))
    if (not credential or credential.revoked or aware(credential.expires_at) <= now()
            or credential.kind not in (("device", "companion") if bearer else ("session",))):
        raise HTTPException(401, "Authentication required")
    if (credential.kind == 'companion') != (credential.companion_device_id is not None):
        raise HTTPException(401, 'Invalid desktop authorization')
    if not bearer and credential.audience != settings.SESSION_ORIGIN:
        if not (credential.audience is None and settings.ALLOW_LEGACY_SESSIONS):
            raise HTTPException(401,"Session belongs to another application origin")
    user = db.get(User, credential.user_id)
    if not user or not user.active:
        raise HTTPException(401, "Authentication required")
    if credential.kind == 'companion':
        device = db.get(CompanionDevice, credential.companion_device_id)
        if (device is None or device.user_id != user.id or device.issuer_origin != settings.SESSION_ORIGIN or device.revoked
                or aware(device.expires_at) <= now()):
            raise HTTPException(401, 'Desktop authorization expired or revoked')
        path = request.url.path
        read = request.method == 'GET' and (path in ('/api/v1/auth/me', '/api/v1/markets', '/api/v1/companion/bootstrap')
            or re.fullmatch(r'/api/v1/sync/markets/[0-9]+', path)
            or re.fullmatch(r'/api/v1/companion/markets/[0-9]+/observations/[0-9]+', path)
            or re.fullmatch(r'/api/v1/companion/private-beta/update/windows-x86_64/[0-9A-Za-z.-]{1,64}',path)
            or re.fullmatch(r'/api/v1/companion/private-beta/2\.[0-9]{1,4}\.[0-9]{1,4}-beta\.[1-9][0-9]{0,3}/windows-x64',path))
        write = request.method == 'POST' and path in ('/api/v1/companion/activity', '/api/v1/companion/devices/self/revoke')
        if not (read or write):
            raise HTTPException(403, 'This desktop connection only permits market synchronization')
        request.state.companion_device = device
    if not bearer and request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(digest(csrf), credential.csrf_hash or ""):
            raise HTTPException(403, "CSRF token required")
    request.state.credential = credential
    return user


def admin(request: Request, user: User = Depends(identity)):
    if user.role != "admin":
        raise HTTPException(403, "Administrator required")
    if request.state.credential.kind != "session":
        raise HTTPException(403, "Administrator browser session required")
    return user
