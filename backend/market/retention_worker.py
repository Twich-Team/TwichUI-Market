"""Bounded, restartable automation of the existing retention engine.

Service installation, configured policy, authorization and enablement are separate.
Only authorize_automatic (operator-only) records an owner's exact reviewed scope.
"""
import hashlib
import json
import inspect
import re
import logging
import os
from pathlib import Path
import signal
import time
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, text, update
from .db import Session, now, session
from .ingest import canonical
from .models import (Market, RetentionAutomation, RetentionBatch, RetentionExecution, User)
from .security import admin, audit, aware
from . import retention

SCHEDULER_LOCK = 7140238
# A changed scope/version invalidates prior automatic authorization.
SCOPE = {'version': 1, 'stages': ['daily_references','observations','raw_listings',
    'raw_feed_payloads','intraday_statistics','collection_logs','feed_checks','security_logs'],
    'daily_support_days':60, 'current_heads':'all markets including disabled',
    'shared_snapshots':'protect all retained observation dependencies',
    'sync':'existing 409/full refresh', 'concurrent_executions':1,
    'operations':'DELETE candidate rows except raw_feed_payloads, which clears compressed_payload',
    'engine_sha256':hashlib.sha256((inspect.getsource(retention.candidates)+inspect.getsource(retention.execute_selected)).encode()).hexdigest()}


class Limits(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    rows_per_batch: int = Field(default=5000, ge=100, le=10000)
    payloads_per_batch: int = Field(default=25, ge=1, le=100)
    max_batches: int = Field(default=12, ge=1, le=100)
    max_seconds: int = Field(default=20, ge=1, le=30)
    statement_ms: int = Field(default=2000, ge=100, le=3000)
    lock_ms: int = Field(default=250, ge=1, le=500)
    interval_seconds: int = Field(default=300, ge=60, le=86400)
    collector_margin_seconds: int = Field(default=30, ge=30, le=120)
    contention_retry_seconds: int = Field(default=60, ge=30, le=300)
    max_wal_bytes: int = Field(default=2*1024**3, ge=256*1024**2, le=8*1024**3)


def authorization_document(db, limits):
    policy = retention.policy_view(db)
    document = {'policy_hash':policy['policy_hash'], 'policy_revision':policy['revision'],
                'scope':SCOPE, 'limits':limits.model_dump()}
    return {**document, 'execution_hash':hashlib.sha256(canonical(document).encode()).hexdigest()}


def approved_document(db, row):
    try:
        if not row or not row.authorization: return None
        document = json.loads(row.authorization)
        expected = authorization_document(db, Limits(**document['limits']))
        actor = db.get(User, row.actor_id)
        if (document != expected or not actor or not actor.active or actor.role != 'admin'
                or not retention.policy_view(db)['application_authorized']): return None
        return document
    except (KeyError, TypeError, ValueError):
        return None


def recovery_ready(actor_id):
    """Rehash a present protected manager archive; require matching off-VM evidence.

    The operator-owned receipt is mounted read-only; it cannot be written by API
    policy saves. No configured path or absent external evidence is ready.
    """
    try:
        path = Path(os.environ.get('RETENTION_RECOVERY_EVIDENCE', '/retention-recovery/evidence.json'))
        if not path.is_file() or path.stat().st_size > 16384: return False
        evidence = json.loads(path.read_text())
        stamp = aware(datetime.fromisoformat(evidence['off_vm_verified_at']))
        if not now()-timedelta(hours=24) <= stamp <= now(): return False
        if evidence.get('off_vm_verified') is not True or not evidence.get('failure_domain'): return False
        if not re.fullmatch('[a-f0-9]{32}', evidence['backup_id']): return False
        from .backup_management import connect
        manifest = connect(actor_id, '/backups/'+evidence['backup_id']+'/manifest')
        dump = aware(datetime.fromisoformat(manifest['created_at']))
        restored = aware(datetime.fromisoformat(manifest['restoration_verified_at']))
        return (manifest['sha256'] == evidence['sha256'] and manifest['filename'] == evidence['filename']
            and manifest['protected'] is True and bool(manifest['required_by'])
            and manifest['verification'] == 'archive_integrity_verified' and bool(manifest['restored'])
            and now()-timedelta(hours=24) <= dump <= restored <= now()
            and dump <= stamp <= now()
            and evidence.get('restored_archive_sha256') == manifest['sha256'])
    except (OSError, KeyError, ValueError, TypeError, HTTPException):
        return False


def authorize_automatic(db, actor, notes, *, limits=None, expected_execution_hash):
    """Operator only, after owner approval of preview and exact execution hash.

    Does not enable maintenance. It must never be called as part of deployment.
    """
    limits = limits or Limits()
    retention.lock(db)
    document = authorization_document(db, limits)
    if expected_execution_hash != document['execution_hash']:
        raise ValueError('Reviewed execution hash no longer matches policy, scope and limits')
    if not recovery_ready(actor.id): raise ValueError('Protected local restore and off-VM recovery evidence required')
    retention.authorize_policy(db, actor, notes)
    row = db.get(RetentionAutomation, 1)
    if row is None:
        row = RetentionAutomation(id=1, enabled=False); db.add(row)
    row.enabled=False; row.next_run_at=None
    row.actor_id=actor.id; row.authorized_at=now(); row.authorization=canonical(document)
    audit(db,actor.id,'retention.automatic.authorized', 'execution='+document['execution_hash'])
    return document


def state_view(db):
    row = db.get(RetentionAutomation, 1)
    document = approved_document(db, row)
    last = db.scalar(select(RetentionExecution).order_by(RetentionExecution.id.desc()).limit(1))
    success = db.scalar(select(func.max(RetentionExecution.finished_at)).where(RetentionExecution.status.in_(['complete','budget_exhausted'])))
    stages = dict(db.execute(select(RetentionBatch.stage,func.sum(RetentionBatch.rows_removed)).group_by(RetentionBatch.stage)).all())
    reason = ('Policy is not authorized for automatic maintenance' if not document else
              'Automatic maintenance is disabled' if not row.enabled else last.reason if last else 'Awaiting first execution')
    return {'installed':os.environ.get('RETENTION_SCHEDULER_INSTALLED')=='true',
        'enabled':bool(row and row.enabled), 'authorized':bool(document),
        'authorization':document, 'proposal':authorization_document(db, Limits()),
        'recovery':recovery_evidence_view(),
        'next_run_at':row.next_run_at if row and row.enabled else None,
        'last_success_at':success, 'rows_by_stage':stages,
        'last_run': {'id':last.id,'started_at':last.started_at,'finished_at':last.finished_at,
                     'status':last.status,'reason':last.reason,'batches':last.batches,
                     'rows_processed':last.rows_processed} if last else None,
        'paused_reason':reason,
        'recovery_notice':'Automatic execution requires a present, rehashed, protected restored archive and matching off-VM verification within 24 hours.'}


class EnableInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


@retention.router.patch('/automation')
def enable(body:EnableInput, user:User=Depends(admin), db=Depends(session)):
    retention.lock(db)
    row = db.get(RetentionAutomation, 1)
    if body.enabled and (not approved_document(db,row) or not recovery_ready(user.id)):
        raise HTTPException(409,'Exact automatic policy authorization and protected local/off-VM recovery evidence required')
    if row:
        row.enabled=body.enabled; row.next_run_at=now() if body.enabled else None
    audit(db,user.id,'retention.automatic.enabled' if body.enabled else 'retention.automatic.paused')
    db.commit()
    return state_view(db)


def next_batch(db, policy, at, limits):
    # Counts/full preview are deliberately outside the repeated execution path.
    for name, model, predicate in retention.candidates(db,policy,at):
        keys=retention.primary_keys(model)
        maximum=limits.payloads_per_batch if name=='raw_feed_payloads' else limits.rows_per_batch
        ids=[list(row) for row in db.execute(select(*keys).where(predicate).order_by(*keys).limit(maximum))]
        if ids: return name, model, ids
    return None


def work_once(factory=Session, *, at=None, clock=time.monotonic):
    at=at or now()
    # Session-level leader lock spans separately committed bounded transactions.
    with factory().bind.connect() as leader:
        postgres=leader.dialect.name=='postgresql'
        if not postgres: return {'status':'unsupported'}
        if not leader.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':SCHEDULER_LOCK}):
            leader.rollback(); return {'status':'busy'}
        leader.commit()
        try:
            return _work(factory, at, clock)
        finally:
            leader.rollback()
            leader.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':SCHEDULER_LOCK})
            leader.commit()


def _work(factory, at, clock):
    with factory.begin() as db:
        # A held leader lock proves old in-flight receipts lost their process,
        # including when the owner paused/revoked authorization during a crash.
        db.execute(update(RetentionExecution).where(RetentionExecution.status=='running').values(
            status='interrupted', reason='Previous process interrupted; committed batches preserved', finished_at=at))
        row=db.get(RetentionAutomation,1)
        document=approved_document(db,row)
        if not row or not row.enabled or not document: return {'status':'inactive'}
        if row.next_run_at and aware(row.next_run_at)>at: return {'status':'not_due'}
        limits=Limits(**document['limits'])
        row.next_run_at=at+timedelta(seconds=limits.interval_seconds)
        receipt=RetentionExecution(policy_hash=document['policy_hash'],status='running')
        db.add(receipt);db.flush(); receipt_id=receipt.id; actor_id=row.actor_id
    started=clock(); outcome='budget_exhausted'; reason=None
    try:
        if not recovery_ready(actor_id):
            outcome='paused'; reason='Protected backup/restore or off-VM recovery verification unavailable'
        else:
            for _ in range(limits.max_batches):
                remaining=limits.max_seconds-(clock()-started)
                if remaining <= 0: break
                with factory.begin() as db:
                    # Recheck authorization and pause between every committed batch.
                    row=db.get(RetentionAutomation,1)
                    if not row or not row.enabled or approved_document(db,row)!=document:
                        outcome='paused'; reason='Authorization or enablement changed'; break
                    db.execute(text("SELECT set_config('statement_timeout', :value, true)"),{'value':str(min(limits.statement_ms,max(1,int(remaining*1000))))})
                    db.execute(text("SELECT set_config('lock_timeout', :value, true)"),{'value':str(limits.lock_ms)})
                    db.execute(text("SELECT set_config('transaction_timeout', :value, true)"),{'value':str(min(3000,max(1,int(remaining*1000))))})
                    if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
                        outcome='paused'; reason='Collection or synchronization is busy'; break
                    due=db.scalar(select(Market.id).where(Market.enabled.is_(True),Market.verified.is_(True),
                        Market.next_check<=now()+timedelta(seconds=limits.collector_margin_seconds)).limit(1))
                    if due:
                        outcome='paused'; reason='Collector due; yielding maintenance budget'; break
                    from .capacity import filesystem
                    disk=filesystem()
                    if disk['available_bytes'] is None or disk['available_bytes']<=disk['reserve_bytes']:
                        outcome='paused'; reason='PostgreSQL filesystem safety reserve unavailable or reached'; break
                    wal=db.scalar(text('SELECT coalesce(sum(size),0) FROM pg_ls_waldir()'))
                    if wal>limits.max_wal_bytes:
                        outcome='paused';reason='PostgreSQL WAL exceeds authorized maintenance budget';break
                    first=next_batch(db,retention.policy_view(db),now(),limits)
                    if first is None: outcome='complete';break
                    result=retention.execute_selected(db,retention.policy_view(db),first,now(),actor_id)
                    receipt=db.get(RetentionExecution,receipt_id)
                    receipt.batches+=1;receipt.rows_processed+=result['rows_removed']
                    progress=json.loads(receipt.progress)
                    progress[result['stage']]=progress.get(result['stage'],0)+result['rows_removed']
                    receipt.progress=canonical(progress)
                # Give a waiting collector/sync an opportunity between transactions.
                time.sleep(0.05)
    except Exception:
        outcome='failed'; reason='Maintenance transaction failed or timed out; batch rolled back'
        logging.error('Automatic retention batch failed; transaction rolled back')
    with factory.begin() as db:
        receipt=db.get(RetentionExecution,receipt_id)
        receipt.status=outcome;receipt.reason=reason;receipt.finished_at=now()
        # Retrying an empty contention attempt earlier prevents permanent phase
        # alignment with the five-minute collector. A cycle that committed any
        # rows retains its full authorized interval and cannot spend two budgets.
        if receipt.batches==0 and reason in ('Collection or synchronization is busy','Collector due; yielding maintenance budget'):
            row=db.get(RetentionAutomation,1)
            if row and row.enabled:
                row.next_run_at=at+timedelta(seconds=min(limits.contention_retry_seconds,limits.interval_seconds))
        return {'status':outcome,'reason':reason,'batches':receipt.batches,'rows_processed':receipt.rows_processed}


def main():
    logging.basicConfig(level=logging.INFO)
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    while not stopping:
        try: work_once()
        except Exception: logging.error('Retention scheduler unavailable; will retry')
        for _ in range(15):
            if stopping:break
            time.sleep(1)




def recovery_evidence_view():
    """Cheap, honest status; live execution separately rehashes the local archive."""
    try:
        path=Path(os.environ.get('RETENTION_RECOVERY_EVIDENCE','/retention-recovery/evidence.json'))
        if not path.is_file() or path.stat().st_size>16384:raise ValueError()
        evidence=json.loads(path.read_text())
        stamp=aware(datetime.fromisoformat(evidence['off_vm_verified_at']))
        recent=evidence.get('off_vm_verified') is True and bool(evidence.get('failure_domain')) and now()-timedelta(hours=24)<=stamp<=now()
        return {'off_vm_verification_recent':recent,'verified_at':stamp,'local_archive_status':'Revalidated under the backup lock before execution',
                'reason':None if recent else 'Off-VM recovery verification is missing or stale'}
    except (OSError,KeyError,TypeError,ValueError):
        return {'off_vm_verification_recent':False,'verified_at':None,'local_archive_status':'Live validation required',
                'reason':'Off-VM recovery verification is missing or stale'}


if __name__=='__main__': main()
