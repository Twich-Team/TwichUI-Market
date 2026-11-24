"""Bound raw details while preserving daily market history and fetch provenance."""
import argparse
import json
import os
from datetime import timedelta
from sqlalchemy import delete, func, select, text
from .db import Session, now
from .models import RetentionPolicy, CollectionRun, Credential, DailyObservation, Invitation, Listing, LoginAttempt, Observation, SecurityEvent, Snapshot, SnapshotStatistic, CompanionAuthorization


def maintain(factory=Session, *, apply=False, at=None, compact=None):
    at=at or now()
    compact=compact if compact is not None else os.environ.get('HISTORY_COMPACTION_ENABLED','false').lower()=='true'
    collection_days=int(os.environ.get('COLLECTION_LOG_DAYS','90'))
    security_days=int(os.environ.get('SECURITY_EVENT_DAYS','365'))
    raw_days=int(os.environ.get('RAW_LISTING_DAYS','7'))
    statistics_days=int(os.environ.get('DETAILED_STATISTICS_DAYS','90'))
    if (not 7<=collection_days<=3650 or not 30<=security_days<=3650
            or not 1<=raw_days<=60 or not 64<=statistics_days<=3650):
        raise ValueError('Retention outside safe operational bounds')
    predicates=[(CollectionRun,CollectionRun.checked_at<at-timedelta(days=collection_days)),
                (SecurityEvent,SecurityEvent.created_at<at-timedelta(days=security_days)),
                (LoginAttempt,LoginAttempt.window_start<at-timedelta(days=1)),
                (Credential,(Credential.expires_at<at-timedelta(days=30)) & Credential.companion_device_id.is_(None) &
                 ~select(CompanionAuthorization.id).where(CompanionAuthorization.approved_credential_id==Credential.id).exists()),
                (Invitation,Invitation.expires_at<at-timedelta(days=30))]
    with factory.begin() as db:
        if apply and compact and not (db.bind.url.database == 'market_test' or
                (db.bind.dialect.name == 'sqlite' and db.bind.url.database in (None, ':memory:'))):
            raise ValueError('Legacy history compaction is test-only. Use the approved policy, verified backup and signed bounded retention batches for production.')
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140233)')):
            return {'status':'busy'}
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
            return {'status':'busy'}
        if db.bind.dialect.name=='postgresql':
            db.execute(text("SET LOCAL statement_timeout='3s'"))
            db.execute(text("SET LOCAL lock_timeout='250ms'"))
        policy=db.get(RetentionPolicy,1)
        if policy:
            # Proposals may extend preservation immediately; only explicit batches shorten it.
            predicates[0]=(CollectionRun,CollectionRun.checked_at<at-timedelta(days=max(collection_days,policy.operational_days)))
            predicates[1]=(SecurityEvent,(SecurityEvent.created_at<at-timedelta(days=max(security_days,policy.security_days))) & ~SecurityEvent.action.like('retention.%'))
        result={'status':'applied' if apply else 'dry_run','historical_observations':'preserved_indefinitely',
                'compaction_enabled':compact,'deleted':{},'eligible':{}}
        for model,predicate in predicates:
            count=db.scalar(select(func.count()).select_from(model).where(predicate))
            result['eligible'][model.__tablename__]=count
            result['deleted'][model.__tablename__]=count if not apply else 0
            if apply:
                keys=list(model.__table__.primary_key.columns)
                from sqlalchemy import tuple_
                ids=list(db.execute(select(*keys).where(predicate).order_by(*keys).limit(5000)))
                if ids:result['deleted'][model.__tablename__]=db.execute(delete(model).where(tuple_(*keys).in_([tuple(row) for row in ids]))).rowcount
        if not compact:
            if apply:
                db.add(SecurityEvent(action='maintenance.housekeeping.complete',detail=json.dumps(result['deleted'],separators=(',',':'))))
            return result
        # Keep every provenance observation and the last UTC-day reference forever.
        ranked=select(Observation.snapshot_id,func.row_number().over(partition_by=Observation.market_id,
            order_by=(Observation.retrieved_at.desc(),Observation.id.desc())).label('position')).subquery()
        current=select(ranked.c.snapshot_id).where(ranked.c.position==1)
        recent_raw=select(Observation.snapshot_id).where(Observation.retrieved_at>=at-timedelta(days=raw_days))
        raw_ids=list(db.scalars(select(Snapshot.id).where(Snapshot.raw_retained.is_(True),
            Snapshot.id.not_in(current),Snapshot.id.not_in(recent_raw))))
        recent_statistics=select(Observation.snapshot_id).where(Observation.retrieved_at>=at-timedelta(days=statistics_days))
        daily_snapshots=select(Observation.snapshot_id).join(DailyObservation,DailyObservation.observation_id==Observation.id)
        statistic_ids=list(db.scalars(select(Snapshot.id).where(Snapshot.statistics_retained.is_(True),
            Snapshot.id.not_in(current),Snapshot.id.not_in(recent_statistics),Snapshot.id.not_in(daily_snapshots))))
        result['deleted']['raw_listings']=db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id.in_(raw_ids)))
        result['deleted']['detailed_statistics']=db.scalar(select(func.count()).select_from(SnapshotStatistic).where(SnapshotStatistic.snapshot_id.in_(statistic_ids)))
        if apply:
            for offset in range(0,len(raw_ids),500):
                batch=raw_ids[offset:offset+500]
                db.execute(delete(Listing).where(Listing.snapshot_id.in_(batch)))
                for row in db.scalars(select(Snapshot).where(Snapshot.id.in_(batch))): row.raw_retained=False
            for offset in range(0,len(statistic_ids),500):
                batch=statistic_ids[offset:offset+500]
                db.execute(delete(SnapshotStatistic).where(SnapshotStatistic.snapshot_id.in_(batch)))
                for row in db.scalars(select(Snapshot).where(Snapshot.id.in_(batch))): row.statistics_retained=False
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--compact-history',action='store_true',default=None)
    args=parser.parse_args()
    print(json.dumps(maintain(apply=args.apply,compact=args.compact_history)))


if __name__=='__main__':
    main()
