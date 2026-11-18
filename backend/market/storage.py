"""Hourly bounded PostgreSQL storage measurements, independent of collection."""
import logging
import signal
import time
from datetime import timedelta
from sqlalchemy import delete, func, select, text
from .db import Session, now
from .models import StorageMeasurement


def sample(factory=Session, *, at=None):
    at=at or now()
    hour=at.replace(minute=0,second=0,microsecond=0)
    with factory.begin() as db:
        if db.bind.dialect.name!='postgresql':
            return 'unsupported'
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140234)')):
            return 'busy'
        if db.get(StorageMeasurement,hour) is not None:
            return 'already_sampled'
        size=db.scalar(text('SELECT pg_database_size(current_database())'))
        from .capacity import filesystem
        from .retention import candidates, policy_view
        from .models import RetentionBatch
        # Hourly backlog accounting, outside the collector and scheduler locks.
        # A failed/slow count leaves the measurement unknown, never falsely zero.
        eligible=None
        try:
            with db.begin_nested():
                db.execute(text("SET LOCAL statement_timeout='5s'"))
                eligible=sum(db.scalar(select(func.count()).select_from(model).where(predicate))
                    for _,model,predicate in candidates(db,policy_view(db),at))
        except Exception:
            eligible=None
        processed=db.scalar(select(func.coalesce(func.sum(RetentionBatch.rows_removed),0)))
        db.add(StorageMeasurement(sampled_at=hour,database_bytes=size,
            retention_eligible_rows=eligible,retention_processed_rows=processed,
            filesystem_available_bytes=filesystem()['available_bytes']))
        db.execute(delete(StorageMeasurement).where(StorageMeasurement.sampled_at<hour-timedelta(days=90)))
    return 'sampled'


def history(db):
    rows=list(db.scalars(select(StorageMeasurement).order_by(StorageMeasurement.sampled_at)))
    elapsed=(rows[-1].sampled_at-rows[0].sampled_at).total_seconds() if len(rows)>1 else 0
    delta=rows[-1].database_bytes-rows[0].database_bytes if elapsed else None
    return {'samples':[{'sampled_at':r.sampled_at,'database_bytes':r.database_bytes} for r in rows],
            'delta_bytes':delta,'elapsed_seconds':elapsed,
            'bytes_per_day':round(delta*86400/elapsed) if elapsed else None,
            'retention_days':90,'interval_seconds':3600,
            'retention_throughput':throughput(rows)}


def main():
    logging.basicConfig(level=logging.INFO)
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    while not stopping:
        try:
            sample()
        except Exception:
            logging.error('Storage measurement failed; will retry')
        for _ in range(60):
            if stopping:break
            time.sleep(1)


if __name__=='__main__':main()


def operational_status(db):
    """Catalogue estimates, physical capacity, vacuum and collection facts."""
    from sqlalchemy import func
    from .capacity import status
    from .models import Market, Observation, DailyObservation, RetentionExecution
    from .retention import policy_view, backup_ready
    from .retention_worker import state_view
    capacity=status(db)
    automation=state_view(db)
    warnings=[]
    allocated=capacity['database_allocated_bytes'];limit=capacity['database_limit_bytes']
    if allocated is not None and allocated>=limit*.85: warnings.append('Database allocation approaches its collector cap')
    disk=capacity['filesystem']
    if disk['available_bytes'] is None: warnings.append('PostgreSQL physical filesystem measurement unavailable')
    elif disk['available_bytes']<=disk['reserve_bytes']*1.25: warnings.append('Filesystem free space approaches its safety reserve')
    if capacity['paused_reason']: warnings.append(capacity['paused_reason'])
    markets=list(db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True))))
    failures=[{'market_id':m.id,'house_id':m.house_id,'last_error':m.last_error,'last_success':m.last_success} for m in markets if m.failures]
    if failures: warnings.append('Collection reports failures; check market feed diagnostics')
    if not automation['authorized']: warnings.append('Retention is configured but unauthorized for automatic execution')
    if automation['enabled']:
        due=automation['next_run_at']
        if due and now()>aware_date(due)+timedelta(minutes=10): warnings.append('Scheduled historical maintenance has stopped or is overdue')
        if automation['last_run'] and automation['last_run']['status'] in ('paused','failed','interrupted'): warnings.append(automation['last_run']['reason'])
    if not backup_ready(): warnings.append('Fresh backup and successful restoration evidence are missing')
    if automation['recovery']['reason']: warnings.append(automation['recovery']['reason']+'; historical pruning is blocked')
    backlog=throughput(list(db.scalars(select(StorageMeasurement).order_by(StorageMeasurement.sampled_at))))
    if backlog['status']=='falling_behind':warnings.append('Eligible history is accumulating faster than maintenance processes it')
    vacuum=[];wal=None;reusable=None;live=None;checkpoints=None
    if db.bind.dialect.name=='postgresql':
        vacuum=[dict(r) for r in db.execute(text('''SELECT relname, n_live_tup, n_dead_tup, last_autovacuum, last_autoanalyze,
            pg_total_relation_size(relid) AS allocated_bytes,
            pg_relation_size(relid) AS heap_bytes FROM pg_stat_user_tables
            ORDER BY pg_total_relation_size(relid) DESC LIMIT 12''')).mappings()]
        # Dead tuple proportions exclude indexes/toast and do not estimate fragmentation.
        reusable=sum(round(r['heap_bytes']*r['n_dead_tup']/max(1,r['n_live_tup']+r['n_dead_tup'])) for r in vacuum)
        live=sum(round(r['heap_bytes']*r['n_live_tup']/max(1,r['n_live_tup']+r['n_dead_tup'])) for r in vacuum)
        wal=int(db.scalar(text('SELECT coalesce(sum(size),0) FROM pg_ls_waldir()')))
        checkpoints=dict(db.execute(text('SELECT num_timed,num_requested,write_time,sync_time,stats_reset FROM pg_stat_checkpointer')).mappings().one())
        if wal>2*1024**3: warnings.append('PostgreSQL WAL exceeds the default maintenance allowance')
        if any(r['n_dead_tup']>100000 and r['n_dead_tup']>r['n_live_tup']*.2 for r in vacuum): warnings.append('Dead tuples are accumulating; inspect autovacuum')
    return {'retention_throughput':backlog,'capacity':capacity,'automation':automation,'warnings':warnings,'collection_failures':failures,
        'oldest_observation_at':db.scalar(select(func.min(Observation.retrieved_at))),
        'oldest_daily_day':db.scalar(select(func.min(DailyObservation.day))),
        'estimated_live_heap_bytes':live,'estimated_reusable_heap_bytes':reusable,
        'estimate_notice':'Dead-tuple heap estimate for largest tables; excludes indexes, TOAST and fragmentation. DELETE makes internal space reusable after vacuum; allocated files do not immediately shrink.',
        'vacuum':vacuum,'wal_allocated_bytes':wal,'checkpoints':checkpoints,
        'retention_policy':policy_view(db)}


def aware_date(value):
    from .security import aware
    return aware(value)


def throughput(rows):
    usable=[r for r in rows if r.retention_eligible_rows is not None and r.retention_processed_rows is not None]
    if len(usable)<2:return {'status':'insufficient_measurements','newly_eligible_rows_per_day':None,'processed_rows_per_day':None}
    first,last=usable[max(0,len(usable)-24)],usable[-1]
    seconds=(last.sampled_at-first.sampled_at).total_seconds()
    if seconds<=0:return {'status':'insufficient_measurements','newly_eligible_rows_per_day':None,'processed_rows_per_day':None}
    reclaimed=last.retention_processed_rows-first.retention_processed_rows
    added=max(0,last.retention_eligible_rows-first.retention_eligible_rows+reclaimed)
    return {'status':'falling_behind' if added>reclaimed and last.retention_eligible_rows>0 else 'measured',
        'newly_eligible_rows_per_day':round(added*86400/seconds),
        'processed_rows_per_day':round(reclaimed*86400/seconds),'backlog_rows':last.retention_eligible_rows,
        'elapsed_seconds':seconds}
