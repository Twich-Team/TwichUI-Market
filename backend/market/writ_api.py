"""Browser-only Crafting Writ comparisons from the local catalogue."""
import json
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .crafting_writs import RESOURCE, read_catalogue, refresh_seconds
from .db import now, session
from .market_api import require_market
from .market_configuration import mapping_for
from .metadata_recovery import enqueue_crafting_writ_refresh
from .models import MetadataJob, MetadataProvider, MetadataTask, User
from .preferences import browser_member
from .security import admin, aware
from .waylaid_api import item_views, refresh_view
from .waylaid_pricing import Basis, load_quotes
from .writ_pricing import Method, price_writ
from .writ_rewards import RewardConflict, effective_reward, reward_settings, reward_view, save_reward

router = APIRouter(prefix='/api/v1')
RewardScope = Literal['tier', 'writ']
RecipeId = Annotated[int, Field(ge=1, le=2**31 - 1)]


class RewardEdit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reputation: Annotated[int, Field(ge=1, le=2**31 - 1)] | None
    revision: Annotated[int, Field(ge=0, le=2**53 - 2)]


def catalogue_view(resource, data):
    data = data or {}
    source = json.loads(resource.source_json) if resource and resource.source_json else {}
    refreshed_at = source.get('confirmed_at') or source.get('retrieved_at')
    parsed = aware(datetime.fromisoformat(refreshed_at)) if refreshed_at else None
    writs = data.get('writs', [])
    supported = sum(
        writ.get('hand_in_allowed') is True and bool(writ['objectives']) and (
            all(objective.get('buy_allowed') is True for objective in writ['objectives'])
            or all(any(
                recipe.get('craft_allowed') is True and recipe['item_id'] == objective['item_id']
                and recipe.get('output_quantity') and recipe.get('skill') and recipe.get('ingredients')
                and not recipe.get('output_random') and recipe.get('output_min') == recipe.get('output_max')
                and recipe.get('output_min') in (None, recipe.get('output_quantity'))
                for recipe in writ['recipes']
            ) for objective in writ['objectives'])
        ) for writ in writs
    )
    return {
        'source_url': source.get('catalogue_url') or data.get('source_url') or 'https://foreverdb.net',
        'source_label': data.get('source_label'),
        'source_observed_at': data.get('source_observed_at'),
        'build': source.get('build') or data.get('build'),
        'refreshed_at': refreshed_at,
        'stale': parsed is not None and now() - parsed > timedelta(seconds=2 * (refresh_seconds() or 86400)),
        'writ_count': len(writs),
        'supported_count': supported,
        'incomplete_count': len(writs) - supported,
        'partial_count': sum(bool(writ.get('incomplete_reason')) for writ in writs),
    }


def item_names(writs):
    names = {}
    for writ in writs:
        for item in (writ, *writ['objectives'], *(
            ingredient for recipe in writ['recipes'] for ingredient in recipe['ingredients']
        )):
            item_id, name = item['item_id'], item.get('name')
            if name or item_id not in names:
                names[item_id] = name
    return names


def reward_data(writ, settings):
    value, source = effective_reward(writ, settings)
    return {'reputation': value, 'reward_source': source, 'provider_reputation': writ.get('provider_reward')}


def priced_rows(writs, items, quotes, settings, *, side, owned, method, max_skill, confirmed_recipes):
    rows = []
    for writ in writs:
        reward = reward_data(writ, settings)
        faction = writ.get('faction')
        factions = writ.get('factions', {})
        if factions:
            faction = factions.get(side)
        if isinstance(faction, str):
            faction = {'id': None, 'name': faction}
        supported_sides = writ.get('allowed_sides')
        if supported_sides and side not in supported_sides:
            writ = {**writ, 'hand_in_allowed': False}
        priced = price_writ(writ, reward['reputation'], quotes, owned=owned, method=method,
                            max_skill=max_skill, confirmed_recipes=confirmed_recipes)
        priced['purchase_quote']['item'] = items[writ['item_id']]
        for route in (priced['craft'], priced['buy']):
            route['purchase_quote']['item'] = items[writ['item_id']]
            for line in (*route['materials'], *route['basket']):
                line['item'] = items[line['item_id']]
        rows.append({
            **priced, **reward, 'item': items[writ['item_id']], 'tier': writ.get('tier'),
            'profession': writ.get('profession'), 'quest_id': writ.get('quest_id'), 'faction': faction,
            'objectives': [{**obj, 'item': items[obj['item_id']]} for obj in writ['objectives']],
            'recipe_candidates': writ['recipes'], 'restrictions': writ.get('restrictions', []),
            'incomplete_reason': writ.get('incomplete_reason'),
        })
    return rows


def pricing_session(db: Session = Depends(session)):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text("SET LOCAL statement_timeout = '5s'"))
    try:
        yield db
    except DBAPIError as error:
        if getattr(error.orig, 'sqlstate', None) != '57014':
            raise
        db.rollback()
        raise HTTPException(503, 'Writ prices took too long to load. Try again.') from None


@router.get('/crafting-writs')
def compare_writs(
    market_id: Annotated[int, Query(ge=1, le=2**31 - 1)],
    basis: Basis = 'current',
    owned: bool = False,
    method: Method = 'cheapest',
    profession: Annotated[str | None, Query(pattern=r'^[a-z][a-z0-9-]{0,47}$')] = None,
    max_skill: Annotated[int | None, Query(ge=1, le=1000)] = None,
    confirmed_recipes: Annotated[list[RecipeId] | None, Query(max_length=40)] = None,
    user: User = Depends(browser_member),
    db: Session = Depends(pricing_session),
):
    market = require_market(db, market_id)
    mapping = mapping_for(db, market)
    resource, data = read_catalogue(db)
    writs = data['writs'] if data else []
    professions = sorted({writ['profession'] for writ in writs if writ.get('profession')})
    if profession:
        writs = [writ for writ in writs if writ.get('profession') == profession]
    names = item_names(writs)
    items = item_views(db, market.region, names)
    quotes = load_quotes(db, market, names, basis)
    rows = priced_rows(writs, items, quotes, reward_settings(db),
                       side=mapping.faction.lower() if mapping else None, owned=owned,
                       method=method, max_skill=max_skill, confirmed_recipes=set(confirmed_recipes or ()))
    return {
        'catalogue': catalogue_view(resource, data),
        'professions': [{'slug': slug, 'label': slug.replace('-', ' ').title()} for slug in professions],
        'pricing': {'snapshot_id': quotes.snapshot_id, 'observed_at': quotes.observed_at,
                    'freshness': quotes.freshness,
                    'synthetic': quotes.synthetic or any(quote.synthetic for quote in quotes.items.values())},
        'rows': rows,
    }


def writ_refresh_view(db, resource):
    if refresh_seconds():
        return {**refresh_view(db, resource, resource_name=RESOURCE), 'operation': 'catalogue'}

    job = db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key == 'crafting-writ-items')
                    .order_by(MetadataJob.id.desc()).limit(1))
    tasks = list(db.scalars(select(MetadataTask).where(MetadataTask.job_id == job.id))) if job else []
    queued = [task for task in tasks if task.state == 'queued']
    results = {json.loads(task.result_json or '{}').get('status') for task in tasks}
    provider = db.get(MetadataProvider, 'foreverdb')
    error = None
    if not provider or not provider.enabled or provider.credential_status != 'connected':
        error = 'Enable and verify the ForeverDB connection in Data Sources.'
    elif results.intersection(('authorization', 'forbidden', 'subscription_required', 'credential_unavailable')):
        error = 'Verify the ForeverDB key, scope and quota in Data Sources.'
    elif any(task.state == 'failed' for task in tasks):
        error = 'Some item metadata requests failed. Check Data Sources and queue another refresh.'
    elif results.intersection(('rate_limited', 'provider_cooldown', 'temporarily_unavailable')):
        error = 'ForeverDB is cooling down. The worker will retry within the shared quota.'

    state = 'idle'
    if any(task.state == 'running' for task in tasks):
        state = 'running'
    elif queued:
        state = 'retry' if error or any(task.attempts for task in queued) else 'queued'
    elif error and job:
        state = 'failed'
    return {
        'operation': 'metadata_backfill', 'state': state, 'error': error,
        'next_attempt_at': min((task.available_at for task in queued), default=None),
        'last_finished_at': job.updated_at if job and job.state == 'completed' else None,
    }


def reward_keys(writs, scope):
    return {writ['tier'] if scope == 'tier' else str(writ['item_id'])
            for writ in writs if writ.get('quest_id') and (scope == 'writ' or writ.get('tier'))}


def admin_writ_view(writ, settings, items):
    key = str(writ['item_id'])
    reward = reward_data(writ, settings)
    return {
        **settings.get(('writ', key), reward_view(key)),
        'effective_reputation': reward['reputation'],
        'provider_reputation': reward['provider_reputation'],
        'reward_source': reward['reward_source'],
        'item': items[writ['item_id']], 'tier': writ.get('tier'), 'quest_id': writ['quest_id'],
    }


@router.get('/admin/crafting-writs')
def admin_writs(user: User = Depends(admin), db: Session = Depends(session)):
    resource, data = read_catalogue(db)
    writs = data['writs'] if data else []
    settings = reward_settings(db)
    tiers = reward_keys(writs, 'tier')
    tiers.update(key for scope, key in settings if scope == 'tier')
    items = item_views(db, 'us', {writ['item_id']: writ.get('name') for writ in writs})
    return {
        'catalogue': catalogue_view(resource, data),
        'refresh': writ_refresh_view(db, resource),
        'tiers': [settings.get(('tier', tier), reward_view(tier)) for tier in sorted(tiers)],
        'writs': [admin_writ_view(writ, settings, items) for writ in writs if writ.get('quest_id')],
    }


@router.put('/admin/crafting-writs/rewards/{scope}/{key}')
def edit_reward(
    scope: RewardScope,
    key: Annotated[str, Path(pattern=r'^(?:[a-z][a-z0-9-]{0,47}|[1-9][0-9]{0,9})$')],
    edit: RewardEdit,
    user: User = Depends(admin),
    db: Session = Depends(session),
):
    _, data = read_catalogue(db)
    writs = data['writs'] if data else []
    if key not in reward_keys(writs, scope) and (scope, key) not in reward_settings(db):
        raise HTTPException(404, 'That reward setting is unavailable in the local writ catalogue')
    try:
        return save_reward(db, user, scope, key, edit.reputation, edit.revision)
    except RewardConflict:
        raise HTTPException(409, 'Reward changed elsewhere. Reload the saved value and try again.') from None


@router.post('/admin/crafting-writs/refresh', status_code=202)
def refresh_writs(user: User = Depends(admin), db: Session = Depends(session)):
    try:
        enqueue_crafting_writ_refresh(db, actor_id=user.id)
    except ValueError as error:
        raise HTTPException(409, str(error)) from None
    db.commit()
    resource, _ = read_catalogue(db)
    return writ_refresh_view(db, resource)
