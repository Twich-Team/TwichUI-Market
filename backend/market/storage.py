"""Hourly bounded PostgreSQL storage measurements, independent of collection."""
import logging
import signal
import time
from datetime import timedelta
from sqlalchemy import delete, select, text
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
        db.add(StorageMeasurement(sampled_at=hour,database_bytes=size))
        db.execute(delete(StorageMeasurement).where(StorageMeasurement.sampled_at<hour-timedelta(days=90)))
    return 'sampled'


def history(db):
    rows=list(db.scalars(select(StorageMeasurement).order_by(StorageMeasurement.sampled_at)))
    elapsed=(rows[-1].sampled_at-rows[0].sampled_at).total_seconds() if len(rows)>1 else 0
    delta=rows[-1].database_bytes-rows[0].database_bytes if elapsed else None
    return {'samples':[{'sampled_at':r.sampled_at,'database_bytes':r.database_bytes} for r in rows],
            'delta_bytes':delta,'elapsed_seconds':elapsed,
            'bytes_per_day':round(delta*86400/elapsed) if elapsed else None,
            'retention_days':90,'interval_seconds':3600}


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
