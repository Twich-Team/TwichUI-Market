"""Administration only enqueues work; no browser request contacts providers."""
from datetime import datetime, timedelta
import json
import re
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import JSON, Integer, cast, func, or_, select, update
from sqlalchemy.orm import Session
from .db import now, session
from .models import ItemMedia, ItemMetadata, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, User
from .metadata_providers import PROVIDERS
from .metadata_recovery import ACTIVE, candidates, enqueue, ensure_providers, job_counts, observed_query, provider_limits
from .provider_secrets import SecretUnavailable, encrypt, keyring, rotate
from .security import admin, audit, aware

router = APIRouter(prefix='/api/v1/admin')


class ProviderUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    automatic: bool
    hourly_budget: int = Field(ge=1, le=240)
    daily_budget: int = Field(ge=1, le=2000)


class KeyReplacement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: SecretStr
    expires_at: datetime | None = None


class RecoveryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    market_id: int = Field(ge=1, le=2**31-1)
    mode: Literal['single', 'missing', 'stale', 'bulk']
    item_id: int | None = Field(default=None, ge=1, le=2**31-1)
    providers: list[Literal['blizzard', 'everloot', 'foreverdb', 'thewowdb']] = Field(min_length=1, max_length=4)
    limit: int = Field(default=100, ge=1, le=1000)
    request_budget: int = Field(default=100, ge=1, le=1000)


def provider_row(db, ident):
    if ident not in PROVIDERS: raise HTTPException(404, 'Unknown metadata provider')
    ensure_providers(db)
    return db.get(MetadataProvider, ident, with_for_update=True)


def provider_view(row):
    spec = PROVIDERS[row.provider]
    days = (aware(row.expires_at) - now()).total_seconds() / 86400 if row.expires_at else None
    warning = 'expired' if days is not None and days <= 0 else next((f'expires_within_{n}_days' for n in (7, 14, 30) if days is not None and days <= n), None)
    return {'provider':row.provider, 'name':spec.label, 'enabled':row.enabled, 'automatic':row.automatic,
        'configured':bool(row.credential) if row.provider!='blizzard' else bool(__import__('os').environ.get('BLIZZARD_CLIENT_ID') and __import__('os').environ.get('BLIZZARD_CLIENT_SECRET')), 'key_required':spec.key_required,
        'credential_status':row.credential_status, 'validation_pending':row.validation_requested,
        'validation_error':row.validation_error, 'last_validated_at':row.validated_at, 'expires_at':row.expires_at,
        'expiration_warning':warning, 'last_success':row.last_success, 'recent_error':row.last_error,
        'cooldown_until':row.cooldown_until, 'next_request_at':row.next_request_at,
        'hourly_budget':row.hourly_budget, 'daily_budget':row.daily_budget, 'hour_used':row.hour_used,
        'day_used':row.day_used, 'note':spec.note, 'url':spec.url}


@router.get('/metadata-providers')
def providers(user: User = Depends(admin), db: Session = Depends(session)):
    ensure_providers(db)
    try: keyring(); ready = True
    except SecretUnavailable: ready = False
    result = {'credential_storage_ready':ready, 'providers':[provider_view(db.get(MetadataProvider, ident)) for ident in PROVIDERS]}
    db.commit()
    return result


@router.patch('/metadata-providers/{ident}')
def configure(ident: str, body: ProviderUpdate, user: User = Depends(admin), db: Session = Depends(session)):
    row = provider_row(db, ident)
    hourly_ceiling,daily_ceiling,_=provider_limits(row)
    if body.hourly_budget > hourly_ceiling or body.daily_budget > daily_ceiling:
        raise HTTPException(422, f'Current provider ceiling is {hourly_ceiling} requests/hour and {daily_ceiling}/day')
    for field in ('enabled', 'automatic', 'hourly_budget', 'daily_budget'): setattr(row, field, getattr(body, field))
    audit(db, user.id, 'metadata.provider.configured', f'provider={ident}; enabled={body.enabled}; automatic={body.automatic}')
    db.commit()
    return provider_view(row)


@router.post('/metadata-providers/{ident}/credentials', status_code=202)
def replace_key(ident: str, body: KeyReplacement, user: User = Depends(admin), db: Session = Depends(session)):
    row = provider_row(db, ident)
    if ident not in ('everloot', 'foreverdb'): raise HTTPException(422, 'This provider uses existing OAuth or keyless access')
    key = body.key.get_secret_value()
    if not re.fullmatch(r'(?:evl_|fdb_)[!-~]{8,2044}', key) or not key.startswith('evl_' if ident == 'everloot' else 'fdb_'):
        raise HTTPException(422, 'Use a valid provider API key')
    expiry = aware(body.expires_at) if body.expires_at else None
    if expiry and (expiry <= now() or expiry > now() + timedelta(days=366)):
        raise HTTPException(422, 'Expiration must be within the next year')
    try: key_id, ciphertext = encrypt(ident, key)
    except SecretUnavailable as error: raise HTTPException(503, str(error)) from None
    row.pending_credential, row.pending_key_id, row.pending_expires_at = ciphertext, key_id, expiry
    row.validation_requested = True; row.validation_revision += 1; row.validation_error = None
    audit(db, user.id, 'metadata.credential.staged', f'provider={ident}')
    db.commit()
    return {'status':'validation_queued', 'previous_key_preserved':bool(row.credential)}


@router.post('/metadata-providers/{ident}/test', status_code=202)
def test_connection(ident: str, user: User = Depends(admin), db: Session = Depends(session)):
    row = provider_row(db, ident)
    if ident == 'foreverdb' and not (row.credential or row.pending_credential): raise HTTPException(409, 'Provider key is not configured')
    row.validation_requested = True; row.validation_revision += 1; row.validation_error = None
    audit(db, user.id, 'metadata.connection.test_queued', f'provider={ident}')
    db.commit()
    return {'status':'validation_queued'}


@router.post('/metadata-providers/rotate-encryption')
def rotate_encryption(user: User = Depends(admin), db: Session = Depends(session)):
    try: count = rotate(db)
    except SecretUnavailable as error: raise HTTPException(503, str(error)) from None
    audit(db, user.id, 'metadata.encryption.rotated', f'envelopes={count}')
    db.commit()
    return {'rotated_envelopes':count}


@router.post('/item-metadata/preview')
def preview(body: RecoveryInput, user: User = Depends(admin), db: Session = Depends(session)):
    try:
        items = candidates(db, body.market_id, body.mode, min(body.limit, 1000 // len(set(body.providers))), body.providers, item_id=body.item_id)
        if body.mode == 'single' and body.item_id is None: raise ValueError('Enter a numeric item ID')
        if body.mode == 'bulk' and body.providers != ['everloot']: raise ValueError('Bulk import supports Everloot only')
    except ValueError as error: raise HTTPException(422, str(error)) from None
    return {'item_count':len(items), 'estimated_requests':len(items) * len(set(body.providers)), 'request_budget':body.request_budget,
        'bounded':True, 'note':'Upper bound before negative caches, disabled providers and quotas. Bulk is at most the selected page budget; client attributes only.'}


@router.post('/item-metadata/jobs', status_code=202)
def start(body: RecoveryInput, user: User = Depends(admin), db: Session = Depends(session)):
    try:
        ensure_providers(db)
        job, created = enqueue(db, body.market_id, body.mode, body.providers, actor_id=user.id, item_id=body.item_id,
            limit=body.limit, budget=body.request_budget)
    except ValueError as error: raise HTTPException(422, str(error)) from None
    db.commit()
    return {'job_id':job.id, 'created':created, 'state':job.state}


def job_view(db, job):
    return {'id':job.id, 'market_id':job.market_id, 'mode':job.mode, 'state':job.state, 'providers':json.loads(job.providers_json),
        'total':job.total, 'counts':job_counts(db, job.id), 'requests_used':job.requests_used, 'request_budget':job.request_budget,
        'created_at':job.created_at, 'updated_at':job.updated_at}


@router.get('/item-metadata/jobs')
def jobs(user: User = Depends(admin), db: Session = Depends(session)):
    return {'jobs':[job_view(db, job) for job in db.scalars(select(MetadataJob).order_by(MetadataJob.id.desc()).limit(30))]}


@router.get('/item-metadata/jobs/{job_id}')
def job_detail(job_id: int, after: int = Query(0, ge=0), user: User = Depends(admin), db: Session = Depends(session)):
    job = db.get(MetadataJob, job_id)
    if job is None: raise HTTPException(404, 'Recovery job not found')
    rows = list(db.scalars(select(MetadataTask).where(MetadataTask.job_id == job_id, MetadataTask.id > after).order_by(MetadataTask.id).limit(101)))
    return {**job_view(db, job), 'results':[{'id':task.id, 'item_id':task.item_id, 'provider':task.provider, 'state':task.state,
        'attempts':task.attempts, 'available_at':task.available_at, 'result':json.loads(task.result_json) if task.result_json else None} for task in rows[:100]],
        'next_after':rows[99].id if len(rows) > 100 else None}


@router.post('/item-metadata/jobs/{job_id}/{action}')
def control(job_id: int, action: Literal['pause', 'resume', 'cancel'], user: User = Depends(admin), db: Session = Depends(session)):
    job = db.get(MetadataJob, job_id, with_for_update=True)
    if job is None: raise HTTPException(404, 'Recovery job not found')
    target = {'pause':'paused', 'resume':'queued', 'cancel':'cancelled'}[action]
    allowed = {'pause':('queued','running'), 'resume':('paused',), 'cancel':ACTIVE}
    if job.state not in allowed[action]: raise HTTPException(409, 'Job cannot change from its current state')
    job.state, job.updated_at = target, now()
    if action == 'cancel':
        db.execute(update(MetadataTask).where(MetadataTask.job_id == job_id, MetadataTask.state == 'queued').values(state='cancelled'))
    audit(db, user.id, 'metadata.job.' + action, f'job={job_id}')
    db.commit()
    return job_view(db, job)


@router.get('/item-metadata')
def overview(market_id: int | None = Query(None, ge=1), user: User = Depends(admin), db: Session = Depends(session)):
    ids = observed_query(market_id).subquery()
    join = select(func.count(), func.count(ItemMetadata.name),
        func.count(ItemMetadata.fallback_name).filter(ItemMetadata.name.is_(None)), func.count(ItemMedia.asset_hash),
        func.count(ItemMetadata.item_id).filter(ItemMetadata.http_status == 404),
        func.count(ItemMetadata.details), func.count(ItemMetadata.catalog_json),
        func.count().filter(ItemMetadata.name.is_(None),or_(ItemMetadata.http_status.is_(None),ItemMetadata.http_status!=404))).select_from(ids).outerjoin(ItemMetadata,
        (ItemMetadata.region == ids.c.region) & (ItemMetadata.item_id == ids.c.item_id)).outerjoin(ItemMedia,
        (ItemMedia.region == ids.c.region) & (ItemMedia.item_id == ids.c.item_id))
    total, primary, supplemental, icons, primary_missing, attributes, catalog, primary_pending = db.execute(join).one()
    source_name=cast(MetadataSource.fields_json,JSON)['name'].as_string()
    sources = list(db.execute(select(MetadataSource.provider, func.count(), func.count(source_name)).join(ids,
        (ids.c.region == MetadataSource.region) & (ids.c.item_id == MetadataSource.item_id)).group_by(MetadataSource.provider)))
    overlaps=select(MetadataSource.region,MetadataSource.item_id,func.count(source_name).label('names'),func.count(func.distinct(source_name)).label('distinct_names')).join(ids,(ids.c.region==MetadataSource.region)&(ids.c.item_id==MetadataSource.item_id)).group_by(MetadataSource.region,MetadataSource.item_id).subquery()
    overlap_count=db.scalar(select(func.count()).select_from(overlaps).where(overlaps.c.names>1))
    conflicting_count=db.scalar(select(func.count()).select_from(overlaps).where(overlaps.c.distinct_names>1))
    recent = list(db.scalars(select(MetadataTask).where(MetadataTask.state == 'completed', MetadataTask.result_json.is_not(None)).order_by(MetadataTask.updated_at.desc(), MetadataTask.id.desc()).limit(20)))
    return {'snapshot_scope':'Latest recorded observation per selected market', 'measured_at':now(), 'observed':total,
        'resolved_names':primary+supplemental, 'missing_names':total-primary-supplemental,
        'name_percent':round(100*(primary+supplemental)/total, 2) if total else None, 'primary_names':primary,
        'supplemental_names':supplemental, 'primary_missing_responses':primary_missing,
        'primary_pending':primary_pending, 'icons_available':icons, 'icons_missing':total-icons,
        'primary_attributes':attributes, 'catalog_records':catalog, 'provider_name_overlap':overlap_count,'conflicting_names':conflicting_count,
        'last_enrichment':db.scalar(select(func.max(MetadataProvider.last_success))),
        'pending_queue':db.scalar(select(func.count()).select_from(MetadataTask).where(MetadataTask.state == 'queued')),
        'active_jobs':db.scalar(select(func.count()).select_from(MetadataJob).where(MetadataJob.state.in_(ACTIVE))),
        'provider_records':[{'provider':r[0], 'checked':r[1], 'names_available':r[2]} for r in sources],
        'recent_results':[{'item_id':r.item_id, 'provider':r.provider, 'at':r.updated_at, 'result':json.loads(r.result_json)} for r in recent]}
