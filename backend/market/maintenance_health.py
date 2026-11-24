"""Read-only retention health, separate from immutable destructive authorization scope."""
import json
from fastapi import Depends
from sqlalchemy import func, select, text
from .db import now, session
from .models import RetentionExecution, RetentionBatch, Snapshot, SnapshotStatistic, Observation, DailyObservation, SecurityEvent
from .retention import router, policy_view
from .retention_worker import state_view
from .security import admin


@router.get('/health')
def health(user=Depends(admin),db=Depends(session)):
    if db.bind.dialect.name=='postgresql':db.execute(text("SET LOCAL statement_timeout='3s'"))
    automation=state_view(db)
    runs=list(db.scalars(select(RetentionExecution).order_by(RetentionExecution.id.desc()).limit(20)))
    last=runs[0] if runs else None
    status=('disabled' if not automation['enabled'] else 'unauthorized' if not automation['authorized'] else
            last.status if last and last.status in ('running','failed','paused','interrupted') else 'enabled')
    absent=db.scalar(select(func.count()).select_from(Snapshot).where(Snapshot.statistics_retained.is_(True),
        ~select(SnapshotStatistic.snapshot_id).where(SnapshotStatistic.snapshot_id==Snapshot.id).exists()))
    from .compaction_safety import canonical_daily_pending
    canonical_pending=db.scalar(select(func.count()).select_from(canonical_daily_pending(db,policy_view(db),now()).subquery()))
    tiers={}
    for name,model,field in [('observations',Observation,Observation.retrieved_at),('snapshots',Snapshot,Snapshot.created_at),('daily',DailyObservation,DailyObservation.day)]:
        count,oldest,newest=db.execute(select(func.count(),func.min(field),func.max(field)).select_from(model)).one()
        tiers[name]=dict(records=count,oldest=oldest,newest=newest)
    housekeeping=db.scalar(select(SecurityEvent).where(SecurityEvent.action=='maintenance.housekeeping.complete').order_by(SecurityEvent.id.desc()).limit(1))
    tables=[]
    allocation=None
    if db.bind.dialect.name=='postgresql':
        allocation=db.scalar(text('SELECT pg_database_size(current_database())'))
        tables=[dict(r._mapping) for r in db.execute(text('SELECT relname AS name,n_live_tup AS estimated_live_rows,n_dead_tup AS estimated_dead_rows,last_autovacuum,last_autoanalyze,pg_total_relation_size(relid) AS allocated_bytes FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10'))]
    return dict(measured_at=now(),status=status,policy=policy_view(db),automation=automation,tiers=tiers,
        aggregation=dict(missing_statistic_snapshots=absent,pending_canonical_daily_snapshots=canonical_pending,status='attention' if absent or canonical_pending else 'present',
            notice='Compact snapshot statistics and UTC daily references are produced during ingestion. Presence alone does not prove complete aggregation; destructive batches require their own validation.'),
        database_bytes=allocation,tables=tables,housekeeping=dict(last_success_at=housekeeping.created_at,removed=json.loads(housekeeping.detail)) if housekeeping else None,
        recent_runs=[dict(id=r.id,started_at=r.started_at,finished_at=r.finished_at,status=r.status,reason=r.reason,
            rows_processed=r.rows_processed,batches=r.batches,removed_by_category=json.loads(r.progress)) for r in runs],
        storage_notice='DELETE makes PostgreSQL space reusable after vacuum. It does not promise smaller files or reclaimed host space.')
