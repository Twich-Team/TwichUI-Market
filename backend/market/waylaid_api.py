"""Private Waylaid Crates calculations and administrator controls."""
import json
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .db import now, session
from .market_api import metadata_name, require_market
from .merchants_favor import RESOURCE, read_catalogue, refresh_seconds
from .metadata_recovery import enqueue_merchant_favor_refresh
from .models import ItemMedia, ItemMetadata, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, User
from .preferences import browser_member
from .security import admin, aware
from .waylaid_pricing import Basis, load_quotes, price_crate
from .waylaid_rewards import DEFAULT_REWARDS, RewardConflict, reward_settings, rewards_by_tier, save_reward

router = APIRouter(prefix='/api/v1')
SOURCE_URL = 'https://foreverdb.net'


class RewardEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    favor: Annotated[int, Field(ge=1, le=2**31 - 1)] | None
    revision: Annotated[int, Field(ge=0, le=2**53 - 2)]


def catalogue_view(resource, crates):
    source = json.loads(resource.source_json) if resource and resource.source_json else {}
    refreshed_at = source.get('confirmed_at') or source.get('retrieved_at')
    parsed = aware(datetime.fromisoformat(refreshed_at)) if refreshed_at else None
    return {
        'source_url': SOURCE_URL,
        'build': source.get('build'),
        'refreshed_at': refreshed_at,
        'stale': parsed is not None and now() - parsed > timedelta(seconds=2 * (refresh_seconds() or 86400)),
        'crate_count': len(crates),
        'supported_count': sum(not crate['unavailable_reason'] for crate in crates),
    }


def refresh_view(db, resource):
    job_status = db.execute(
        select(MetadataTask.state, MetadataTask.available_at, MetadataTask.attempts)
        .select_from(MetadataJob).join(MetadataTask, MetadataTask.job_id == MetadataJob.id)
        .where(MetadataJob.dedupe_key == RESOURCE).order_by(MetadataJob.id.desc()).limit(1)
    ).first()
    provider = db.get(MetadataProvider, 'foreverdb')
    state = job_status.state if job_status else 'idle'
    if state == 'queued' and job_status.attempts:
        state = 'retry'
    error = None
    if not provider or not provider.enabled or provider.credential_status != 'connected':
        error = 'Enable and verify the ForeverDB connection in Data Sources.'
    elif resource and resource.status not in ('pending', 'available'):
        error = {
            'rate_limited': 'ForeverDB limited requests. The worker will retry within the shared quota.',
            'transport_or_schema': 'ForeverDB could not return a valid catalogue. Check Data Sources before retrying.',
            'wrong_identity': 'ForeverDB returned unrecognized game data. Check the source build and try again.',
            'authorization': 'ForeverDB rejected the key. Verify the connection in Data Sources.',
            'forbidden': 'ForeverDB denied this request. Verify the key scope in Data Sources.',
            'subscription_required': 'ForeverDB rejected the current plan or quota. Check the provider account before retrying.',
        }.get(resource.status, 'The catalogue refresh failed. Check ForeverDB in Data Sources, then queue another refresh.')
    active = state in ('queued', 'running', 'retry')
    next_attempt = job_status.available_at if job_status and state in ('queued', 'retry') else None
    if resource and next_attempt is None:
        next_attempt = resource.retry_at if error else resource.refresh_at
    return {
        'state': state if active else 'failed' if error and job_status else 'idle',
        'error': error,
        'next_attempt_at': next_attempt,
    }


def item_views(db, region, names):
    if not names:
        return {}
    metadata = {row.item_id: row for row in db.scalars(select(ItemMetadata).where(
        ItemMetadata.region == region, ItemMetadata.item_id.in_(names),
    ))}
    assets = {row.item_id: row for row in db.execute(select(ItemMedia.item_id, ItemMedia.asset_hash, ItemMedia.source).where(
        ItemMedia.region == region, ItemMedia.item_id.in_(names), ItemMedia.asset_hash.is_not(None),
    ))}
    community_icons = [item_id for item_id, asset in assets.items() if asset.source == 'thewowdb']
    icon_credits = {}
    if community_icons:
        for source in db.scalars(select(MetadataSource).where(
            MetadataSource.region == region, MetadataSource.item_id.in_(community_icons),
            MetadataSource.locale == 'en_US', MetadataSource.provider == 'thewowdb',
            MetadataSource.source_json.is_not(None),
        )):
            icon_credits[source.item_id] = json.loads(source.source_json).get('attribution')
    result = {}
    for item_id, source_name in names.items():
        item = metadata_name(metadata.get(item_id), item_id)
        result[item_id] = {
            'item_id': item_id,
            'name': item['name'] if (item['metadata_provider'] and not item['metadata_synthetic']) or not source_name else source_name,
            'quality': item['quality'],
            'metadata_attribution': item['metadata_attribution'],
            'metadata_attributions': item['metadata_attributions'],
            'icon_attribution': icon_credits.get(item_id),
            'icon_url': f'/api/v1/items/{region}/{item_id}/icon?v={assets[item_id].asset_hash}' if item_id in assets else None,
        }
    return result


def crate_rows(db, market, crates, basis, owned):
    names = {}
    provider_quality = {}
    for crate in crates:
        names[crate['item_id']] = crate.get('name')
        provider_quality[crate['item_id']] = crate.get('quality')
        for bundle in crate['bundles']:
            for material in bundle['materials']:
                names.setdefault(material['item_id'], material.get('name'))
                provider_quality.setdefault(material['item_id'], material.get('quality'))
    items = item_views(db, market.region, names)
    for item_id, item in items.items():
        item['quality'] = item['quality'] or provider_quality.get(item_id)
    quotes = load_quotes(db, market, names, basis)
    rewards = rewards_by_tier(db)
    rows = []
    for crate in crates:
        reward = rewards.get(crate['tier'])
        reward_unavailable = crate.get('reward_unavailable_reason')
        favor = reward.favor if reward and not crate['unavailable_reason'] and not reward_unavailable else None
        bundles = {
            bundle['bundle_id']: {material['item_id']: material['quantity'] for material in bundle['materials']}
            for bundle in crate['bundles']
        }
        priced = price_crate(crate['item_id'], favor, bundles, quotes, owned=owned)
        priced['purchase_quote']['item'] = items[crate['item_id']]
        for bundle in priced['bundles']:
            for material in bundle['materials']:
                material['item'] = items[material['item_id']]
        rows.append({
            **priced,
            'item': items[crate['item_id']],
            'tier': crate['tier'],
            'required_level': crate['required_level'],
            'sealed_item_id': crate['sealed_item_id'],
            'favor': favor,
            'unavailable_reason': crate['unavailable_reason'],
            'reward_unavailable_reason': reward_unavailable,
        })
    return rows, {'snapshot_id': quotes.snapshot_id, 'observed_at': quotes.observed_at,
                  'freshness': quotes.freshness,
                  'synthetic': quotes.synthetic or any(quote.synthetic for quote in quotes.items.values())}


def pricing_session(db: Session = Depends(session)):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text("SET LOCAL statement_timeout = '5s'"))
    try:
        yield db
    except DBAPIError as error:
        if getattr(error.orig, 'sqlstate', None) != '57014':
            raise
        db.rollback()
        raise HTTPException(503, 'Crate prices took too long to load. Try again.') from None


@router.get('/waylaid-crates')
def compare_crates(
    market_id: Annotated[int, Query(ge=1, le=2**31 - 1)],
    basis: Basis = 'current',
    owned: bool = False,
    user: User = Depends(browser_member),
    db: Session = Depends(pricing_session),
):
    market = require_market(db, market_id)
    resource, data = read_catalogue(db)
    crates = data['crates'] if data else []
    rows, pricing = crate_rows(db, market, crates, basis, owned)
    return {'catalogue': catalogue_view(resource, crates), 'pricing': pricing, 'rows': rows}


@router.get('/admin/waylaid-crates')
def admin_crates(user: User = Depends(admin), db: Session = Depends(session)):
    resource, data = read_catalogue(db)
    crates = data['crates'] if data else []
    tiers = {crate['tier'] for crate in crates if crate['tier']}
    return {'catalogue': catalogue_view(resource, crates), 'rewards': reward_settings(db, tiers),
            'refresh': refresh_view(db, resource)}


@router.put('/admin/waylaid-crates/rewards/{tier}')
def edit_reward(
    tier: Annotated[str, Path(pattern=r'^[a-z][a-z0-9-]{0,47}$')],
    edit: RewardEdit,
    user: User = Depends(admin),
    db: Session = Depends(session),
):
    if tier not in DEFAULT_REWARDS and tier not in rewards_by_tier(db):
        _, data = read_catalogue(db)
        if not data or not any(crate['tier'] == tier for crate in data['crates']):
            raise HTTPException(404, 'Tier is unavailable in the local crate catalogue')
    try:
        return save_reward(db, user, tier, edit.favor, edit.revision)
    except RewardConflict:
        raise HTTPException(409, 'Reward changed elsewhere. Reload the saved value and try again.') from None


@router.post('/admin/waylaid-crates/refresh', status_code=202)
def refresh_crates(user: User = Depends(admin), db: Session = Depends(session)):
    enqueue_merchant_favor_refresh(db, actor_id=user.id)
    db.commit()
    resource, _ = read_catalogue(db)
    return refresh_view(db, resource)
