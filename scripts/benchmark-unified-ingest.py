"""Replay the bounded real capture only into an isolated market_test database."""
import argparse
import hashlib
import json
import os
import resource
import tarfile
import time
from datetime import datetime
from pathlib import Path
from sqlalchemy import func, select
from market.db import Base, Session, engine
from market.ingest import canonical
from market.models import FeedCapture, Listing, Market, MarketFeed, Observation, Snapshot, SnapshotStatistic
from market.worker import collect_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    if not os.environ.get('DATABASE_URL', '').endswith('/market_test'):
        raise SystemExit('Refusing writes outside isolated market_test')
    if args.capture.stat().st_size > 16 * 1024**2:
        raise SystemExit('Capture archive byte bound')
    with tarfile.open(args.capture) as archive:
        members = archive.getmembers()
        if {m.name for m in members} != {'auctions.json', 'commodities.json', 'receipt.json'} or len(members) != 3:
            raise SystemExit('Unexpected archive membership')
        if any(not m.isfile() or m.size > 32 * 1024**2 for m in members):
            raise SystemExit('Archive member bound')
        receipts = {r['source_kind']: r for r in json.load(archive.extractfile('receipt.json'))}
        at = min(datetime.fromisoformat(r['retrieved_at']) for r in receipts.values())
        Base.metadata.create_all(engine)
        with Session.begin() as db:
            if db.scalar(select(func.count()).select_from(Market)):
                raise SystemExit('Refusing a nonempty test database')
            market = Market(id=2, region='us', ruleset_id=2, house_id=114, source_kind='auctions',
                unified_coverage=True, label='Isolated genuine response replay', enabled=True, verified=True,
                interval_seconds=300, next_check=at)
            db.add(market)
            db.flush()
            for kind in ('auctions', 'commodities'):
                identity = dict(region='us', ruleset_id=2, house_id=114, source_kind=kind,
                    namespace='dynamic-forever-us', scope='ruleset_house')
                db.add(MarketFeed(market_id=2, source_kind=kind, enabled=True,
                    verification=canonical({'identity': identity, 'evidence_sha256': receipts[kind]['sha256']})))
        class CapturedClient:
            def fetch(self, market):
                receipt = receipts[market.source_kind]
                body = archive.extractfile(market.source_kind+'.json').read(32*1024**2+1)
                if len(body) > 32*1024**2 or hashlib.sha256(body).hexdigest() != receipt['sha256']:
                    raise ValueError('Captured response integrity')
                return receipt, body
        started = time.monotonic()
        assert collect_once(Session, CapturedClient(), at=at)
        elapsed = time.monotonic()-started
    with Session() as db:
        head = db.scalar(select(Observation))
        if head is None: raise SystemExit('Composite publication failed')
        items = {str(item): {k: getattr(stat, k) for k in ('recent_price', 'lowest_buyout', 'supply', 'listing_count')}
                 for item in (4306, 14342, 6657)
                 if (stat := db.scalar(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==head.snapshot_id,
                     SnapshotStatistic.item_id==item))) is not None}
        print(json.dumps({'scope':'Genuine response replay into isolated market_test; no production ingestion',
            'source_receipts': list(receipts.values()), 'elapsed_seconds': round(elapsed, 3),
            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'memory_limit_mib':384, 'cpu_limit':0.5,
            'listing_count': db.scalar(select(func.count()).select_from(Listing)),
            'capture_count': db.scalar(select(func.count()).select_from(FeedCapture)),
            'snapshot_count': db.scalar(select(func.count()).select_from(Snapshot)),
            'items': items}, indent=2))


if __name__ == '__main__': main()
