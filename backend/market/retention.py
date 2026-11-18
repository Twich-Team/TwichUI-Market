"""Proposed retention, signed previews and explicitly authorized bounded stages.

No scheduler calls this destructive engine. Operator authorization is separate
from administrator proposal/confirmation and invalidated on every policy edit.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, text, tuple_, update
from sqlalchemy.orm import Session
from .db import now, session
from .ingest import canonical
from .models import (CollectionRun, DailyObservation, Listing, Market, Observation, FeedCapture, FeedCheck, MarketFeed,
                     RetentionBatch, RetentionPolicy, RetentionPolicyChange, SecurityEvent, Snapshot, SnapshotStatistic, User)
from .security import admin, audit, aware

router = APIRouter(prefix='/api/v1/admin/retention')
BATCH_ROWS = 5000


class PolicyInput(BaseModel):
    raw_days: int = Field(default=7, ge=1, le=3650)
    intraday_days: int = Field(default=90, ge=64, le=3650)
    daily_days: int = Field(default=365, ge=90, le=3650)
    operational_days: int = Field(default=90, ge=7, le=3650)
    security_days: int = Field(default=365, ge=30, le=3650)


def policy_view(db):
    row = db.get(RetentionPolicy, 1)
    policy = PolicyInput(**{key:getattr(row,key) for key in PolicyInput.model_fields}) if row else PolicyInput()
    result = policy.model_dump()
    result['revision'] = row.revision if row else 0
    result['policy_hash'] = hashlib.sha256(canonical(result).encode()).hexdigest()
    result['application_authorized'] = bool(row and row.approved_hash == result['policy_hash'])
    result['daily_support_days'] = 60
    result['batch_row_limit'] = BATCH_ROWS
    return result


def lock(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SET LOCAL statement_timeout='8s'"))
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
            raise HTTPException(409, 'Collection or synchronization is busy; retry the preview')


def candidates(db, policy, at):
    # Protect the latest market head even when disabled or far older than the policy.
    ranked = select(Observation.id,Observation.snapshot_id,
        func.row_number().over(partition_by=Observation.market_id,
            order_by=(Observation.retrieved_at.desc(),Observation.id.desc())).label('position')).subquery()
    heads = select(ranked.c.id).where(ranked.c.position==1)
    current = select(ranked.c.snapshot_id).where(ranked.c.position==1)
    daily_cutoff = (at-timedelta(days=policy['daily_days']+60)).date()
    surviving_daily = select(DailyObservation.observation_id).where(DailyObservation.day>=daily_cutoff)
    recent_raw = select(Observation.snapshot_id).where(Observation.retrieved_at>=at-timedelta(days=policy['raw_days']))
    recent_statistics = select(Observation.snapshot_id).where(Observation.retrieved_at>=at-timedelta(days=policy['intraday_days']))
    daily_snapshots = select(Observation.snapshot_id).where(Observation.id.in_(surviving_daily))
    raw_snapshots = select(Snapshot.id).where(Snapshot.id.not_in(current),Snapshot.id.not_in(recent_raw))
    stat_snapshots = select(Snapshot.id).where(Snapshot.id.not_in(current),Snapshot.id.not_in(recent_statistics),Snapshot.id.not_in(daily_snapshots))
    return [
        ('daily_references',DailyObservation,DailyObservation.day<daily_cutoff),
        ('observations',Observation,(Observation.retrieved_at<at-timedelta(days=policy['intraday_days'])) & Observation.id.not_in(heads) & Observation.id.not_in(surviving_daily)),
        ('raw_listings',Listing,Listing.snapshot_id.in_(raw_snapshots)),
        ('raw_feed_payloads', FeedCapture, (FeedCapture.payload_retained_at < at-timedelta(days=policy['raw_days'])) & FeedCapture.compressed_payload.is_not(None) & FeedCapture.id.not_in(select(MarketFeed.capture_id).where(MarketFeed.capture_id.is_not(None)))),
        ('intraday_statistics',SnapshotStatistic,SnapshotStatistic.snapshot_id.in_(stat_snapshots)),
        ('collection_logs',CollectionRun,CollectionRun.checked_at<at-timedelta(days=policy['operational_days'])),
        ('feed_checks', FeedCheck, FeedCheck.checked_at < at-timedelta(days=policy['operational_days'])),
        ('security_logs',SecurityEvent,(SecurityEvent.created_at<at-timedelta(days=policy['security_days'])) & ~SecurityEvent.action.like('retention.%')),
    ]


def primary_keys(model):
    return list(model.__table__.primary_key.columns)


def plan(db, at):
    policy = policy_view(db)
    stages=[]; first=None
    for name, model, predicate in candidates(db,policy,at):
        count=db.scalar(select(func.count()).select_from(model).where(predicate))
        estimate=None
        if db.bind.dialect.name=='postgresql':
            # PostgreSQL allocation/estimated live tuples is an approximation including index overhead.
            size, estimated_rows=db.execute(text('SELECT pg_total_relation_size(CAST(:table AS regclass)), reltuples FROM pg_class WHERE oid=CAST(:table AS regclass)'),{'table':model.__tablename__}).one()
            estimate=round(size*count/max(estimated_rows,count,1)) if count else 0
        stages.append({'stage':name,'eligible_rows':count,'estimated_logical_bytes':estimate})
        if first is None and count:
            keys=primary_keys(model)
            ids=[list(row) for row in db.execute(select(*keys).where(predicate).order_by(*keys).limit(BATCH_ROWS))]
            first=(name,model,ids)
    fingerprint=hashlib.sha256(canonical({'policy':policy['policy_hash'],'at':at.isoformat(),'first':
        [first[0],[[str(v) for v in row] for row in first[2]]] if first else None}).encode()).hexdigest()
    return policy,stages,first,fingerprint


def sign(payload):
    from .sync_api import secret
    encoded=canonical(payload)
    return encoded+'.'+hmac.new(secret(),encoded.encode(),hashlib.sha256).hexdigest()


def validate_confirmation(value):
    from .sync_api import secret
    try:
        encoded,signature=value.rsplit('.',1)
        if not hmac.compare_digest(signature,hmac.new(secret(),encoded.encode(),hashlib.sha256).hexdigest()):raise ValueError()
        data=json.loads(encoded)
        if data['purpose']!='retention-batch' or aware(datetime.fromisoformat(data['expires']))<now():raise ValueError()
        return data
    except (ValueError,KeyError,TypeError):
        raise HTTPException(409,'Preview expired or invalid; preview again')


def backup_ready():
    from .market_api import backup_state
    backup=backup_state()
    try:
        stamp=aware(datetime.fromisoformat(backup['last_restoration_verified_at']))
        dump=aware(datetime.fromisoformat(backup['last_success']))
        if not backup.get('filename') or backup.get('restored_archive_filename')!=backup['filename'] or backup.get('restored_archive_created_at')!=backup['last_success']:return False
        digest=backup.get('restored_archive_sha256','')
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):return False
        return stamp>=dump and backup.get('status') in ('ok','available','success','healthy','manual_backup_verified') and now()-timedelta(days=1)<=stamp<=now() and now()-timedelta(days=1)<=dump<=now()
    except (KeyError,TypeError,ValueError):return False


@router.get('')
def get_policy(user:User=Depends(admin),db:Session=Depends(session)):
    return {**policy_view(db),'backup_restore_ready':backup_ready(),
            'policy_configured':db.get(RetentionPolicy,1) is not None, 'scheduled':False,
            'completed_batches':db.scalar(select(func.count()).select_from(RetentionBatch)),
            'last_completed_at':db.scalar(select(func.max(RetentionBatch.created_at))),
            'notice':'Proposal only. Current snapshot and 60-day valuation support are protected; live application requires separate owner/operator authorization.'}


@router.patch('')
def update_policy(body:PolicyInput,user:User=Depends(admin),db:Session=Depends(session)):
    if body.raw_days>body.intraday_days or body.intraday_days>body.daily_days:
        raise HTTPException(422,'Raw retention must not exceed intraday retention, which must not exceed daily retention')
    lock(db)
    row=db.get(RetentionPolicy,1)
    if row is None:row=RetentionPolicy(id=1,revision=0);db.add(row)
    old=policy_view(db)
    for key,value in body.model_dump().items():setattr(row,key,value)
    row.revision+=1;row.approved_hash=None;row.approved_at=None;row.updated_at=now()
    db.add(RetentionPolicyChange(actor_id=user.id,before=canonical({k:old[k] for k in PolicyInput.model_fields}),after=canonical(body.model_dump())))
    audit(db,user.id,'retention.policy.updated',f'revision={row.revision}; full before/after in retention_policy_changes')
    db.commit()
    return policy_view(db)


@router.get('/preview')
def preview(user:User=Depends(admin),db:Session=Depends(session)):
    lock(db)
    at=now()
    policy,stages,first,fingerprint=plan(db,at)
    confirmation=sign({'purpose':'retention-batch','actor':user.id,'at':at.isoformat(),'hash':fingerprint,'expires':(at+timedelta(minutes=15)).isoformat()})
    allocation=db.scalar(text('SELECT pg_database_size(current_database())')) if db.bind.dialect.name=='postgresql' else None
    return {'status':'dry_run','policy':policy,'stages':stages,'next_stage':first[0] if first else None,
        'next_batch_rows':len(first[2]) if first else 0,'confirmation':confirmation,
        'database_allocated_bytes':allocation,'estimated_logical_bytes':sum(row['estimated_logical_bytes'] or 0 for row in stages),
        'filesystem_recoverable_bytes':None,'estimate_notice':'Approximate proportional table/index allocation. DELETE permits database reuse; filesystem shrink is unknown. Daily history includes 60 days of supporting references.',
        'backup_restore_ready':backup_ready()}


class ApplyInput(BaseModel):
    confirmation:str=Field(min_length=1,max_length=2048)
    confirm:bool


@router.post('/apply')
def apply_batch(body:ApplyInput,user:User=Depends(admin),db:Session=Depends(session)):
    data=validate_confirmation(body.confirmation)
    if not body.confirm or data['actor']!=user.id:raise HTTPException(409,'Administrator confirmation for this preview is required')
    lock(db)
    at=aware(datetime.fromisoformat(data['at']))
    policy,stages,first,fingerprint=plan(db,at)
    if not policy['application_authorized'] or not backup_ready():
        raise HTTPException(409,'Owner/operator policy approval and fresh verified backup restoration are required')
    if not hmac.compare_digest(fingerprint,data['hash']):raise HTTPException(409,'Policy or candidates changed; preview again')
    if first is None:return {'status':'complete','rows_removed':0}
    name,model,ids=first
    keys=primary_keys(model)
    predicate=tuple_(*keys).in_([tuple(row) for row in ids])
    if model in (Listing,SnapshotStatistic):
        snapshot_ids=list(db.scalars(select(model.snapshot_id).where(predicate).distinct()))
        flag=Snapshot.raw_retained if model is Listing else Snapshot.statistics_retained
        db.execute(update(Snapshot).where(Snapshot.id.in_(snapshot_ids)).values({flag:False}))
    removed = (db.execute(update(FeedCapture).where(predicate).values(compressed_payload=None)).rowcount
        if model is FeedCapture else db.execute(delete(model).where(predicate)).rowcount)
    db.add(RetentionBatch(actor_id=user.id,policy_hash=policy['policy_hash'],stage=name,rows_removed=removed,cutoff=at,history_floor=at-timedelta(days=policy["daily_days"]) if name=="daily_references" else None))
    audit(db,user.id,'retention.batch.applied',f'stage={name} rows={removed} policy={policy["policy_hash"]}')
    db.commit()
    return {'status':'batch_applied','stage':name,'rows_removed':removed,'preview_required':True}


def history_floor(db):
    return db.scalar(select(func.max(RetentionBatch.history_floor)))


def authorize_policy(db, actor, notes):
    """Operator-only, invoke only after explicit owner policy approval."""
    if not notes.strip() or len(notes)>2000 or not actor.active or actor.role!='admin':raise ValueError('Active administrator and owner approval notes required')
    lock(db)
    row=db.get(RetentionPolicy,1)
    if row is None or not backup_ready():raise ValueError('Saved policy and fresh backup/restore verification required')
    policy=policy_view(db)
    row.approved_hash=policy['policy_hash'];row.approved_at=now()
    audit(db,actor.id,'retention.policy.authorized',f'policy={row.approved_hash}; {notes}'[:200])
    return row.approved_hash
