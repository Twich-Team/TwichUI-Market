"""Refuse source deletion until exact compact listing totals exist for each snapshot."""
from sqlalchemy import func, select
from fastapi import HTTPException
from .models import Snapshot, SnapshotStatistic


def verify_statistics(db,snapshot_ids):
    totals=dict(db.execute(select(SnapshotStatistic.snapshot_id,func.sum(SnapshotStatistic.listing_count))
        .where(SnapshotStatistic.snapshot_id.in_(snapshot_ids)).group_by(SnapshotStatistic.snapshot_id)).all())
    for snapshot in db.scalars(select(Snapshot).where(Snapshot.id.in_(snapshot_ids))):
        if not snapshot.statistics_retained or totals.get(snapshot.id,0)!=snapshot.listing_count:
            raise HTTPException(409,'Compact history is incomplete; raw data is preserved until aggregation is repaired')
