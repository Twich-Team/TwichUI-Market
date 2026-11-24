"""Idempotent collection and quota evidence for the isolated visual review."""
import os
from datetime import timedelta
from email.utils import format_datetime

from sqlalchemy import func, select

from market.db import Session, engine, now
from market.metadata_models import MetadataQuotaBucket
from market.models import CollectionRun, Market, Snapshot
from market.provider_rates import bucket_start


def seed():
    if not (os.environ.get('MARKET_UX_REVIEW') == 'true'
            and os.environ.get('SESSION_COOKIE_NAME') == 'market_ux_review_session'
            and engine.url.host == 'db' and engine.url.database == 'market_test'):
        raise RuntimeError('This fixture requires the isolated Market UX preview.')
    failure = 'Synthetic review: auction feed returned HTTP 503.'
    at = now() - timedelta(minutes=3)
    with Session.begin() as db:
        market = db.get(Market, 500, with_for_update=True)
        if not market or market.label != 'Recovery Tracker — synthetic':
            raise RuntimeError('The synthetic recovery market must exist first.')
        if db.scalar(select(CollectionRun.id).where(CollectionRun.market_id == market.id,
                                                     CollectionRun.error == failure).limit(1)):
            return
        for age in range(14):
            if age in (4, 9):
                continue
            for index in range(3 + age % 5):
                stamp = at - timedelta(days=age, minutes=index * 25)
                status, code, error = 'unchanged', 304, None
                if index == 1 and age in (2, 3, 7):
                    status, code, error = 'failed', 503, failure
                elif index == 2 and age == 6:
                    status, code, error = 'partial', 200, 'Synthetic review: one feed was unavailable.'
                elif index % 3 == 1:
                    status, code = 'collected', 200
                db.add(CollectionRun(market_id=market.id, checked_at=stamp, status=status,
                                     http_status=code, error=error, duration_seconds=1 + index,
                                     payload_bytes=0 if code != 200 else 120000 + index * 12000))
        if market.last_success is None:
            market.last_success = at
        if not market.last_modified:
            last = db.scalar(select(func.max(Snapshot.created_at)).where(Snapshot.market_id == market.id))
            if last:
                market.last_modified = format_datetime(last, usegmt=True)
        # Rolling usage is read from genuine quota buckets. Nothing contacts a provider.
        for provider, per_bucket in [('foreverdb', 6), ('thewowdb', 3), ('blizzard', 11)]:
            for hour in range(8):
                for minute in (2, 17, 32, 47):
                    moment = bucket_start(at - timedelta(hours=hour, minutes=minute), 60)
                    key = (provider, 60, moment)
                    if db.get(MetadataQuotaBucket, key) is None:
                        db.add(MetadataQuotaBucket(provider=provider, resolution=60,
                                                   started_at=moment, used=per_bucket))


seed()
