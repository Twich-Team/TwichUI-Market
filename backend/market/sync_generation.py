"""Conservative compact-value generation; source snapshot identity alone is insufficient.

A 304 can cross a UTC day or a precise 14/60-day boundary. A newer observation ID
can also be a late historical import. Match asking-v1's daily winners, exact
window membership and ANY synthetic provenance before skipping variant work.
"""
from datetime import timedelta
import hashlib
import json
from typing import NamedTuple
from sqlalchemy import Integer, cast, func, select
from .models import Observation, Snapshot
from .pricing import ALGORITHM
from .security import aware


class Signature(NamedTuple):
    digest: str
    synthetic: bool


def signature(db, head, watermark):
    if head is None:
        return Signature(hashlib.sha256(json.dumps([ALGORITHM, None]).encode()).hexdigest(), False)
    stamp = aware(head.retrieved_at)
    day = (func.date(func.timezone('UTC', Observation.retrieved_at))
        if db.bind.dialect.name == 'postgresql' else func.date(Observation.retrieved_at))
    candidates = select(day.label('day'), Observation.snapshot_id, Observation.retrieved_at,
        func.row_number().over(partition_by=day, order_by=(Observation.retrieved_at.desc(), Observation.id.desc())).label('position'),
        func.max(cast(Observation.synthetic, Integer)).over().label('any_synthetic')).where(
            Observation.market_id == head.market_id, Observation.id <= watermark,
            Observation.retrieved_at >= stamp-timedelta(days=60), Observation.retrieved_at <= stamp).subquery()
    rows = list(db.execute(select(candidates.c.day, candidates.c.snapshot_id, candidates.c.retrieved_at,
        candidates.c.any_synthetic, Snapshot.statistics_retained).join(Snapshot, Snapshot.id == candidates.c.snapshot_id)
        .where(candidates.c.position == 1).order_by(candidates.c.day)))
    if not rows or any(not row.statistics_retained for row in rows):
        return None  # Never bypass unavailable history/retention checks.
    synthetic = bool(rows[0].any_synthetic)
    daily = [(str(row.day), row.snapshot_id, aware(row.retrieved_at) >= stamp-timedelta(days=14)) for row in rows]
    payload = json.dumps([ALGORITHM, head.snapshot_id, synthetic, daily], separators=(',', ':')).encode()
    return Signature(hashlib.sha256(payload).hexdigest(), synthetic)
