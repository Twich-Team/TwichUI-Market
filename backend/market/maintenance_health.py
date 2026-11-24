"""Read-only retention health, separate from immutable destructive authorization scope."""
import json
import os
from datetime import timedelta
from fastapi import Depends
from sqlalchemy import func, select, text
from .db import now, session
from .models import RetentionExecution, RetentionBatch, Snapshot, SnapshotStatistic, Observation, DailyObservation, SecurityEvent
from .retention import router, policy_view
from .retention_worker import state_view
from .security import admin


def composition(db, allocation):
    """Relation metadata only: no listing scans, and table indexes counted once.

    pg_table_size includes TOAST (and its internal indexes), while
    pg_indexes_size counts the table's own indexes. They are disjoint.
    """
    notice = 'Allocated relation bytes; table categories include TOAST. Indexes are separate. Other includes database files outside these relations. This is not live logical data or disk reclaimed.'
    if db.bind.dialect.name != 'postgresql' or allocation is None:
        return dict(status='unavailable', total_bytes=allocation, categories=[], notice=notice)
    tables = db.execute(text('''SELECT relname,
        pg_table_size(relid) AS table_bytes, pg_indexes_size(relid) AS index_bytes
        FROM pg_stat_user_tables''')).mappings()
    groups = {'raw': 0, 'intraday': 0, 'daily': 0, 'metadata': 0, 'indexes': 0, 'other': 0}
    labels = {'raw': 'Raw auction data', 'intraday': 'Intraday history', 'daily': 'Daily references',
              'metadata': 'Item metadata', 'indexes': 'Indexes', 'other': 'Other database storage'}
    for row in tables:
        name = row['relname']
        group = ('raw' if name in ('listings', 'feed_captures') else
                 'intraday' if name in ('snapshot_statistics', 'observations', 'snapshots') else
                 'daily' if name == 'daily_observations' else
                 'metadata' if name in ('item_metadata', 'item_media') or name.startswith('item_metadata_') else 'other')
        groups[group] += int(row['table_bytes'])
        groups['indexes'] += int(row['index_bytes'])
    accounted = sum(groups.values())
    if accounted > allocation:
        # Concurrent allocation changes must not create negative or overlapping slices.
        return dict(status='changed_during_measurement', total_bytes=allocation, categories=[], notice=notice)
    groups['other'] += allocation-accounted
    return dict(status='measured', total_bytes=allocation,
        categories=[dict(key=key, label=labels[key], bytes=value,
                         percent=round(value*100/allocation, 2) if allocation else 0)
                    for key, value in groups.items()], notice=notice)


def activity(db, at=None):
    """Existing bounded metadata, never a count of the large listings relation.

    Snapshot.listing_count records rows in each newly ingested content generation;
    retention receipts record actual committed deletions. These are record counts,
    not bytes, and no aggregation or filesystem-reclaim measurement is inferred.
    """
    at = at or now()
    since = (at-timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    utc_day = lambda column: func.date(func.timezone('UTC',column)) if db.bind.dialect.name=='postgresql' else func.date(column)
    day = utc_day(Snapshot.created_at)
    ingested = db.execute(select(day, func.sum(Snapshot.listing_count))
        .where(Snapshot.created_at >= since, Snapshot.created_at <= at).group_by(day)).all()
    batch_day = utc_day(RetentionBatch.created_at)
    removed = db.execute(select(batch_day, RetentionBatch.stage, func.sum(RetentionBatch.rows_removed))
        .where(RetentionBatch.created_at >= since, RetentionBatch.created_at <= at)
        .group_by(batch_day, RetentionBatch.stage)).all()
    days = {}
    for date, count in ingested:
        days.setdefault(str(date), {})['raw_added'] = int(count)
    for date, stage, count in removed:
        entry = days.setdefault(str(date), {})
        entry.setdefault('removed_by_category', {})[stage] = int(count)
        if stage == 'raw_listings':
            entry['raw_removed'] = int(count)
    return dict(since=since, measured_at=at, unit='records',
        days=[dict(day=date, **values) for date, values in sorted(days.items())],
        notice='Recorded new snapshot listing counts and committed cleanup rows. Missing days are unknown. Ingestion counts describe retained snapshot metadata. Compacted records and reclaimed disk bytes are not measured.')


@router.get('/health')
def health(user=Depends(admin),db=Depends(session)):
    if db.bind.dialect.name=='postgresql':db.execute(text("SET LOCAL statement_timeout='3s'"))
    automation=state_view(db)
    runs=list(db.scalars(select(RetentionExecution).order_by(RetentionExecution.id.desc()).limit(20)))
    last=runs[0] if runs else None
    integrity_paused=bool(last and last.status=='paused' and (last.reason or '').startswith('Integrity verification failed'))
    status=('paused' if integrity_paused else 'disabled' if not automation['enabled'] else 'unauthorized' if not automation['authorized'] else
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
            canonical_cache_retention_enabled=os.environ.get('RETENTION_CANONICAL_CACHE_PRUNING')=='true',notice='Compact snapshot statistics and UTC daily references are produced during ingestion. Presence alone does not prove complete aggregation; destructive batches require their own validation.'),
        database_bytes=allocation,tables=tables,composition=composition(db,allocation),activity=activity(db),
        housekeeping=dict(last_success_at=housekeeping.created_at,removed=json.loads(housekeeping.detail)) if housekeeping else None,
        recent_runs=[dict(id=r.id,started_at=r.started_at,finished_at=r.finished_at,status=r.status,reason=r.reason,
            rows_processed=r.rows_processed,batches=r.batches,removed_by_category=json.loads(r.progress)) for r in runs],
        storage_notice='DELETE makes PostgreSQL space reusable after vacuum. It does not promise smaller files or reclaimed host space.')
