"""Owned native device metadata/bootstrap; no token exposure or collection mutations."""
from email.utils import parsedate_to_datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .companion_auth import AppVersion, Strict, _revoke, display_name
from .db import now, session
from .market_api import MarketId, market_view
from .models import CompanionDevice, Credential, Market, Observation, Snapshot, User, UserPreference
from .preferences import browser_member, read_values
from .security import admin, audit, aware, identity

router = APIRouter(prefix='/api/v1/companion')
DeviceId = Annotated[int, Path(ge=1, le=2**31-1)]


def metadata(db, market, observation, *, watermark=None):
    snapshot = db.get(Snapshot, observation.snapshot_id) if observation else None
    upstream = None
    if observation and observation.upstream_modified:
        try:
            upstream = aware(parsedate_to_datetime(observation.upstream_modified)).isoformat()
        except (ValueError, TypeError, OverflowError):
            pass
    from .sync_generation import signature
    if watermark is None:
        watermark = db.scalar(select(Observation.id).where(Observation.market_id == market.id)
            .order_by(Observation.id.desc()).limit(1))
    valuation = signature(db, observation, watermark or 0)
    return {'market_id': market.id, 'server_checked_at': aware(market.last_success) if market.last_success else None,
            'upstream_updated_at': upstream,
            'observation_id': str(observation.id) if observation else None,
            'watermark_observation_id': str(watermark) if watermark else None,
            'snapshot_id': str(snapshot.id) if snapshot else None,
            'generation': f'{snapshot.id}:{snapshot.content_hash}' if snapshot else None,
            'valuation_generation': valuation.digest if valuation else None,
            'valuation_synthetic': valuation.synthetic if valuation else None,
            'synthetic': observation.synthetic if observation else False}


def device_view(db, device):
    market = db.get(Market, device.selected_market_id) if device.selected_market_id else None
    def stamp(value):
        return aware(value) if value is not None else None
    return {'id': device.id, 'user_id': device.user_id, 'name': device.name,
            'platform': device.platform, 'app_version': device.app_version,
            'authorized_at': stamp(device.created_at), 'expires_at': stamp(device.expires_at),
            'renewal_expires_at': stamp(device.refresh_expires_at),
            'last_connection_at': stamp(device.last_connection_at), 'last_sync_at': stamp(device.last_sync_at),
            'selected_market_id': device.selected_market_id,
            'selected_market_name': market.label if market else None, 'revoked': device.revoked}


def paired(request):
    device = getattr(request.state, 'companion_device', None)
    if device is None:
        raise HTTPException(403, 'Use an authorized desktop connection')
    return device


@router.get('/bootstrap')
def bootstrap(request: Request, user: User = Depends(identity), db: Session = Depends(session)):
    saved = read_values(db.get(UserPreference, user.id))['market_id']
    choices = []
    for market in db.scalars(select(Market).where(Market.verified.is_(True)).order_by(Market.id)):
        value = market_view(market, player_identity=True)
        for key in ('last_success', 'next_check'):
            if value[key] is not None:
                value[key] = aware(value[key])
        value['available_for_sync'] = market.enabled and value['player_identity_verified']
        latest = db.scalar(select(Observation).where(Observation.market_id == market.id)
            .order_by(Observation.retrieved_at.desc(), Observation.id.desc()).limit(1))
        value['source'] = metadata(db, market, latest)
        choices.append(value)
    available = [item['id'] for item in choices if item['available_for_sync']]
    suggestion = saved if saved in available else next(iter(available), None)
    device = getattr(request.state, 'companion_device', None)
    if device is not None:
        # A bootstrap is a real authenticated connection, not a client claim of installation.
        db.execute(update(CompanionDevice).where(CompanionDevice.id == device.id).values(last_connection_at=now()))
        db.commit()
    return {'contract_version': 1, 'account': {'id': user.id, 'username': user.username},
            'markets': choices, 'preferred_market_id': saved, 'suggested_market_id': suggestion,
            'preference_fallback': saved is not None and saved != suggestion,
            'device': device_view(db, device) if device is not None else None}


@router.get('/markets/{market_id}/observations/{observation_id}')
def observation_metadata(market_id: MarketId, observation_id: Annotated[int, Path(ge=1, le=2**31-1)],
                         user: User = Depends(identity), db: Session = Depends(session)):
    market = db.get(Market, market_id)
    observation = db.get(Observation, observation_id)
    if market is None or not market.verified or observation is None or observation.market_id != market_id:
        raise HTTPException(404, 'Observed market data unavailable')
    head = db.scalar(select(Observation).where(Observation.market_id == market_id, Observation.id <= observation_id)
        .order_by(Observation.retrieved_at.desc(), Observation.id.desc()).limit(1))
    return metadata(db, market, head, watermark=observation_id)


class Activity(Strict):
    market_id: Annotated[int, Field(strict=True, ge=1, le=2**31-1)] | None = None
    app_version: AppVersion


@router.post('/activity', status_code=204)
def activity(body: Activity, request: Request, user: User = Depends(identity), db: Session = Depends(session)):
    device = paired(request)
    market = db.get(Market, body.market_id) if body.market_id else None
    if body.market_id is not None and (market is None or not market.verified):
        raise HTTPException(422, 'Choose an available verified market')
    device.app_version = body.app_version
    device.selected_market_id = body.market_id
    device.last_connection_at = now()
    db.commit()


def record_sync(db, request, market_id, observation_id, completed):
    device = getattr(request.state, 'companion_device', None)
    if device is not None:
        device.last_connection_at = now()
        if device.selected_market_id is None:
            device.selected_market_id = market_id
        if completed and observation_id:
            # Only the authenticated sync handler can mark server-side completion;
            # no client-supplied installation/success timestamp is accepted.
            device.last_sync_at = now()
            device.last_observation_id = observation_id or None
        db.commit()


@router.get('/devices')
def devices(user: User = Depends(browser_member), db: Session = Depends(session)):
    rows = list(db.scalars(select(CompanionDevice).where(CompanionDevice.user_id == user.id)
        .order_by(CompanionDevice.revoked, CompanionDevice.expires_at.desc(), CompanionDevice.id.desc()).limit(200)))
    legacy = list(db.scalars(select(Credential).where(Credential.user_id == user.id,
        Credential.kind == 'device', Credential.companion_device_id.is_(None))
        .order_by(Credential.revoked, Credential.expires_at.desc(), Credential.id.desc()).limit(200)))
    return {'devices': [device_view(db, row) for row in rows],
            'legacy_devices': [{'id': row.id, 'name': row.name, 'revoked': row.revoked, 'expires_at': row.expires_at} for row in legacy]}


def owned(db, user, device_id):
    device = db.get(CompanionDevice, device_id)
    if device is None or device.user_id != user.id:
        raise HTTPException(404, 'Desktop connection not found')
    return device


class Rename(Strict):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    _name = field_validator('name')(display_name)


@router.patch('/devices/{device_id}')
def rename(device_id: DeviceId, body: Rename, user: User = Depends(browser_member), db: Session = Depends(session)):
    device = owned(db, user, device_id)
    device.name = body.name
    db.execute(update(Credential).where(Credential.companion_device_id == device.id).values(name=body.name))
    audit(db, user.id, 'companion.device.renamed', f'device={device.id}')
    db.commit()
    return device_view(db, device)


@router.delete('/devices/{device_id}', status_code=204)
def revoke(device_id: DeviceId, user: User = Depends(browser_member), db: Session = Depends(session)):
    device = owned(db, user, device_id)
    _revoke(db, device, 'owner_revocation', actor_id=user.id)
    db.commit()


@router.post('/devices/self/revoke', status_code=204)
def revoke_self(request: Request, user: User = Depends(identity), db: Session = Depends(session)):
    _revoke(db, paired(request), 'desktop_disconnect', actor_id=user.id)
    db.commit()


@router.get('/admin/devices')
def admin_devices(user: User = Depends(admin), db: Session = Depends(session)):
    return {'devices': [device_view(db, row) for row in db.scalars(select(CompanionDevice).order_by(CompanionDevice.id.desc()).limit(200))]}


@router.delete('/admin/devices/{device_id}', status_code=204)
def admin_revoke(device_id: DeviceId, user: User = Depends(admin), db: Session = Depends(session)):
    device = db.get(CompanionDevice, device_id)
    if device is None:
        raise HTTPException(404, 'Desktop connection not found')
    _revoke(db, device, 'administrator_revocation', actor_id=user.id)
    db.commit()
