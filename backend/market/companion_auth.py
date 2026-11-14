"""Public-native-client approval with PKCE, one-time codes and rotating device grants.

No account password or access/refresh token appears in a browser redirect.
Legacy device credentials keep their existing meaning and lifetime.
"""
import base64
from datetime import timedelta
import hashlib
import hmac
import re
import secrets
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import environment
from .db import now, session
from .models import CompanionAuthorization, CompanionDevice, CompanionRefreshHistory, Credential, LoginAttempt, User
from .preferences import browser_member
from .security import audit, aware, digest

router = APIRouter(prefix='/api/v1/companion')
CLIENT_ID = 'twichui-market-companion'
ACCESS_SECONDS = 3600
ROTATION_RETRY_SECONDS = 300
SCOPE = 'market:read sync:read device:self'
Opaque = Annotated[str, Field(strict=True, pattern=r'^[A-Za-z0-9_-]{43}$')]
State = Annotated[str, Field(strict=True, pattern=r'^[A-Za-z0-9_-]{43,128}$')]
AppVersion = Annotated[str, Field(strict=True, pattern=r'^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:-[A-Za-z0-9.-]{1,24})?$', max_length=48)]
RequestID = Annotated[str, Path(pattern=r'^[A-Za-z0-9_-]{43}$')]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


def redirect(value):
    try:
        uri = urlsplit(value)
        port = uri.port
        if (uri.scheme != 'http' or uri.netloc != f'127.0.0.1:{port}'
                or not port or not 1024 <= port <= 65535
                or uri.path != '/companion/callback' or uri.query or uri.fragment):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError('Use the exact temporary IPv4 loopback callback')


def display_name(value):
    if value != value.strip() or not value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('Choose a readable device name')
    return value


class AuthorizationInput(Strict):
    client_id: Literal['twichui-market-companion']
    redirect_uri: Annotated[str, Field(min_length=1, max_length=128)]
    state: State
    code_challenge: Opaque
    code_challenge_method: Literal['S256']
    device_name: Annotated[str, Field(min_length=1, max_length=80)]
    platform: Literal['Windows']
    app_version: AppVersion
    _redirect = field_validator('redirect_uri')(redirect)
    _name = field_validator('device_name')(display_name)


class Decision(Strict):
    decision: Literal['approve', 'deny']
    consent_token: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class CodeExchange(Strict):
    grant_type: Literal['authorization_code']
    client_id: Literal['twichui-market-companion']
    code: Opaque
    redirect_uri: Annotated[str, Field(min_length=1, max_length=128)]
    state: State
    code_verifier: Annotated[str, Field(pattern=r'^[A-Za-z0-9._~-]{43,128}$')]
    _redirect = field_validator('redirect_uri')(redirect)


class RefreshExchange(Strict):
    grant_type: Literal['refresh_token']
    client_id: Literal['twichui-market-companion']
    refresh_token: Opaque
    rotation_nonce: Opaque


def _key():
    from .sync_api import secret
    try:
        key = secret()
    except HTTPException as error:
        if error.status_code == 503:
            raise HTTPException(503, 'Desktop sign-in is temporarily unavailable; please try again later')
        raise
    return hmac.new(key, b'TwichUI companion authorization v2', hashlib.sha256).digest()


def _consent(row, user, request):
    message = f'consent:{row.id}:{row.state_hash}:{user.id}:{request.state.credential.id}:{aware(row.expires_at).isoformat()}'
    return hmac.new(_key(), message.encode(), hashlib.sha256).hexdigest()


def _throttle(db, operation, request, limit, seconds, *, global_bucket=False):
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    peer = 'all' if global_bucket else (request.client.host if request.client else 'unknown')
    key = digest(f'companion-v2:{operation}:{peer}')
    stamp = now()
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    db.execute(insert(LoginAttempt).values(key=key, count=0, window_start=stamp)
        .on_conflict_do_nothing(index_elements=['key']))
    row = db.scalar(select(LoginAttempt).where(LoginAttempt.key == key).with_for_update())
    if aware(row.window_start) <= stamp - timedelta(seconds=seconds):
        row.count, row.window_start = 0, stamp
    if row.count >= limit:
        db.commit()
        raise HTTPException(429, 'Please wait before trying this connection again', headers={'Retry-After': str(seconds)})
    row.count += 1
    db.commit()


@router.post('/authorizations', status_code=201)
def begin(body: AuthorizationInput, request: Request, db: Session = Depends(session)):
    _key()  # Missing signing configuration fails before creating an unusable transaction.
    _throttle(db, 'begin', request, 10, 300)
    _throttle(db, 'begin-total', request, 10000, 86400, global_bucket=True)
    # Only these new, short-lived protocol transactions expire here; never market
    # observations, account/session history or existing audit/security records.
    expired = list(db.scalars(select(CompanionAuthorization.id)
        .where(CompanionAuthorization.expires_at < now() - timedelta(days=1))
        .order_by(CompanionAuthorization.expires_at).limit(100)))
    if expired:
        db.execute(delete(CompanionAuthorization).where(CompanionAuthorization.id.in_(expired)))
    # The transaction state is not a credential. Codes/tokens are stored only as hashes.
    row = CompanionAuthorization(id=secrets.token_urlsafe(32), device_name=body.device_name,
        platform=body.platform, app_version=body.app_version, redirect_uri=body.redirect_uri, issuer_origin=environment.SESSION_ORIGIN,
        state_value=body.state, state_hash=digest(body.state), code_challenge=body.code_challenge,
        expires_at=now() + timedelta(minutes=5))
    if db.scalar(select(func.count()).select_from(CompanionAuthorization)
            .where(CompanionAuthorization.expires_at > now())) >= 5000:
        raise HTTPException(503, 'Connection approval is busy; please try again later', headers={'Retry-After': '60'})
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, 'Start a new connection from the companion')
    return {'request_id': row.id, 'authorization_url': environment.SESSION_ORIGIN + '/companion/authorize?' + urlencode({'request': row.id}),
            'expires_at': row.expires_at}


def _request(db, request_id, *, lock=False):
    query = select(CompanionAuthorization).where(CompanionAuthorization.id == request_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None or row.issuer_origin != environment.SESSION_ORIGIN:
        raise HTTPException(404, 'Connection request not found')
    if aware(row.expires_at) <= now():
        raise HTTPException(410, 'Connection request expired; start again in the companion')
    return row


@router.get('/authorizations/{request_id}')
def inspect(request_id: RequestID, request: Request, user: User = Depends(browser_member), db: Session = Depends(session)):
    row = _request(db, request_id)
    if row.user_id is not None and row.user_id != user.id:
        raise HTTPException(404, 'Connection request not found')
    return {'request_id': row.id, 'application': 'TwichUI Market Companion',
            'device_name': row.device_name, 'platform': row.platform, 'app_version': row.app_version,
            'expires_at': row.expires_at, 'status': row.status,
            'account': {'id': user.id, 'username': user.username},
            'consent_token': _consent(row, user, request) if row.status == 'pending' else None}


@router.post('/authorizations/{request_id}/decision')
def decide(request_id: RequestID, body: Decision, request: Request,
           user: User = Depends(browser_member), db: Session = Depends(session)):
    row = _request(db, request_id, lock=True)
    if row.status != 'pending':
        raise HTTPException(409, 'This connection request has already been answered')
    # A consent screen from another account/session cannot approve under a changed cookie.
    if not hmac.compare_digest(body.consent_token, _consent(row, user, request)):
        raise HTTPException(403, 'Your sign-in changed; reload the approval screen')
    row.user_id = user.id
    row.approved_credential_id = request.state.credential.id
    if body.decision == 'deny':
        row.status = 'denied'
        query = {'error': 'access_denied', 'state': row.state_value}
    else:
        code = secrets.token_urlsafe(32)
        row.code_hash = digest(code)
        row.code_expires_at = min(aware(row.expires_at), now() + timedelta(seconds=60))
        row.status = 'approved'
        query = {'code': code, 'state': row.state_value}
    audit(db, user.id, 'companion.authorization.' + row.status, f'request={row.id}')
    db.commit()
    return {'redirect_uri': row.redirect_uri + '?' + urlencode(query), 'status': row.status}


def _revoke(db, device, reason, *, actor_id=None):
    device.revoked = True
    db.execute(update(Credential).where(Credential.companion_device_id == device.id).values(revoked=True))
    audit(db, actor_id, 'companion.device.revoked', f'device={device.id} reason={reason}')


def _access(db, device, token):
    stamp = now()
    # Older APIs only recognize kind=device and therefore reject these scoped
    # credentials after rollback instead of accidentally treating them as legacy tokens.
    row = Credential(user_id=device.user_id, token_hash=digest(token), kind='companion', name=device.name,
        companion_device_id=device.id, audience=device.issuer_origin,
        expires_at=min(aware(device.expires_at), stamp + timedelta(seconds=ACCESS_SECONDS)))
    db.add(row)
    db.flush()
    device.access_credential_id = row.id
    device.last_connection_at = stamp
    return row


def _tokens(device, credential, access, refresh):
    return {'issuer': device.issuer_origin, 'access_token': access, 'token_type': 'Bearer',
            'expires_in': max(0, int((aware(credential.expires_at) - now()).total_seconds())),
            'refresh_token': refresh, 'refresh_expires_at': device.refresh_expires_at,
            'authorization_expires_at': device.expires_at, 'scope': SCOPE,
            'device': {'id': device.id, 'name': device.name, 'platform': device.platform, 'app_version': device.app_version}}


class InvalidGrant(Exception):
    pass


def _invalid():
    raise InvalidGrant()


def _token_error(code, message):
    return JSONResponse(status_code=400, content={'error': code, 'error_description': message},
        headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


def _exchange(db, body):
    row = db.scalar(select(CompanionAuthorization).where(CompanionAuthorization.code_hash == digest(body.code)).with_for_update())
    if (row is None or row.issuer_origin != environment.SESSION_ORIGIN or row.status != 'approved' or aware(row.expires_at) <= now()
            or row.code_expires_at is None or aware(row.code_expires_at) <= now() or row.invalid_attempts >= 5):
        _invalid()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(body.code_verifier.encode()).digest()).decode().rstrip('=')
    if (not hmac.compare_digest(body.redirect_uri, row.redirect_uri)
            or not hmac.compare_digest(body.state, row.state_value)
            or not hmac.compare_digest(challenge, row.code_challenge)):
        row.invalid_attempts += 1
        if row.invalid_attempts >= 5:
            row.status = 'invalid'
        db.commit()
        _invalid()
    user = db.scalar(select(User).where(User.id == row.user_id).with_for_update())
    if user is None or not user.active:
        _invalid()
    approved_session = db.get(Credential, row.approved_credential_id) if row.approved_credential_id else None
    if (approved_session is None or approved_session.user_id != user.id or approved_session.kind != 'session'
            or approved_session.revoked or aware(approved_session.expires_at) <= now()
            or not (approved_session.audience == row.issuer_origin
                or approved_session.audience is None and environment.ALLOW_LEGACY_SESSIONS)):
        _invalid()
    if db.scalar(select(func.count()).select_from(CompanionDevice)
            .where(CompanionDevice.user_id == user.id, CompanionDevice.revoked.is_(False), CompanionDevice.expires_at > now())) >= 20:
        raise HTTPException(429, 'Revoke an unused desktop connection before adding another')
    refresh, access = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    device = CompanionDevice(user_id=user.id, name=row.device_name, platform=row.platform,
        app_version=row.app_version, issuer_origin=row.issuer_origin, expires_at=now() + timedelta(days=90),
        refresh_expires_at=now() + timedelta(days=30), refresh_hash=digest(refresh))
    db.add(device)
    db.flush()
    credential = _access(db, device, access)
    row.status, row.device_id = 'consumed', device.id
    audit(db, user.id, 'companion.device.authorized', f'device={device.id} request={row.id}')
    db.commit()
    return _tokens(device, credential, access, refresh)


def _derived(label, refresh, nonce):
    return base64.urlsafe_b64encode(hmac.new(_key(), f'{label}:{refresh}:{nonce}'.encode(), hashlib.sha256).digest()).decode().rstrip('=')


def _refresh(db, body):
    hashed = digest(body.refresh_token)
    device = db.scalar(select(CompanionDevice).where(
        (CompanionDevice.refresh_hash == hashed) | (CompanionDevice.previous_refresh_hash == hashed)).with_for_update())
    if device is None:
        previous = db.get(CompanionRefreshHistory, hashed)
        if previous is not None:
            device = db.scalar(select(CompanionDevice).where(CompanionDevice.id == previous.device_id).with_for_update())
            if device is not None and device.issuer_origin == environment.SESSION_ORIGIN and not device.revoked:
                _revoke(db, device, 'older_refresh_reuse')
                db.commit()
        _invalid()
    if (device is None or device.issuer_origin != environment.SESSION_ORIGIN or device.revoked
            or aware(device.expires_at) <= now() or aware(device.refresh_expires_at) <= now()):
        _invalid()
    user = db.get(User, device.user_id)
    if user is None or not user.active:
        _invalid()
    access = _derived('access', body.refresh_token, body.rotation_nonce)
    refresh = _derived('refresh', body.refresh_token, body.rotation_nonce)
    if device.previous_refresh_hash == hashed:
        # Exactly the same pending operation can recover a lost response/vault-write
        # crash for five minutes. Any different nonce is reuse and revokes the family.
        if (device.rotated_at is not None and aware(device.rotated_at) >= now() - timedelta(seconds=ROTATION_RETRY_SECONDS)
                and hmac.compare_digest(device.rotation_nonce_hash or '', digest(body.rotation_nonce))):
            credential = db.get(Credential, device.access_credential_id)
            if credential is not None and not credential.revoked and hmac.compare_digest(credential.token_hash, digest(access)):
                return _tokens(device, credential, access, refresh)
        _revoke(db, device, 'refresh_reuse')
        db.commit()
        _invalid()
    device.previous_refresh_hash = hashed
    db.add(CompanionRefreshHistory(token_hash=hashed, device_id=device.id))
    device.rotation_nonce_hash = digest(body.rotation_nonce)
    device.refresh_hash = digest(refresh)
    device.rotated_at = now()
    device.refresh_expires_at = min(aware(device.expires_at), now() + timedelta(days=30))
    device.generation += 1
    # Superseded access credentials are revoked along with this rotation; legacy
    # tokens are unrelated and never changed.
    db.execute(update(Credential).where(Credential.companion_device_id == device.id).values(revoked=True))
    credential = _access(db, device, access)
    audit(db, device.user_id, 'companion.device.renewed', f'device={device.id} generation={device.generation}')
    db.commit()
    return _tokens(device, credential, access, refresh)


@router.post('/token')
async def token(request: Request, response: Response, db: Session = Depends(session)):
    _throttle(db, 'token', request, 60, 60)
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/x-www-form-urlencoded':
        raise HTTPException(415, 'Use a form-encoded native token request')
    try:
        pairs = parse_qsl((await request.body()).decode('utf-8'), keep_blank_values=True, strict_parsing=True, max_num_fields=8)
        if len(dict(pairs)) != len(pairs):
            raise ValueError()
        fields = dict(pairs)
        model = CodeExchange if fields.get('grant_type') == 'authorization_code' else RefreshExchange
        body = model.model_validate(fields)
    except (ValueError, UnicodeError, ValidationError):
        return _token_error('invalid_request', 'The companion could not finish this request; please try again')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'
    try:
        return _exchange(db, body) if isinstance(body, CodeExchange) else _refresh(db, body)
    except InvalidGrant:
        return _token_error('invalid_grant', 'This connection expired or could not be completed; sign in again')
