"""Read-only bounded market-summary capture. No listings, accounts or credentials.

Run inside the deployed API container and redirect stdout to an ignored file.
Captures complete variant sets for <=8 selected snapshots and exact daily winners,
not a sampled current market. History is an explicitly bounded benchmark slice.
"""
import hashlib
import json
from datetime import timedelta
from sqlalchemy import select, text
from market.db import engine
from market.models import Market, Observation, Snapshot, SnapshotStatistic, ItemSourceCoverage
from market.security import aware

with engine.connect() as db:
    db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
    db.execute(text("SET LOCAL statement_timeout='3s'"))
    db.execute(text("SET LOCAL lock_timeout='250ms'"))
    head = db.execute(select(Observation.__table__).where(Observation.market_id == 2).order_by(Observation.id.desc()).limit(1)).mappings().one()
    recent = list(db.execute(select(Observation.__table__).where(Observation.market_id == 2,
        Observation.id <= head['id']).order_by(Observation.id.desc()).limit(32)).mappings())
    daily = list(db.execute(text("""SELECT DISTINCT ON ((retrieved_at AT TIME ZONE 'UTC')::date) *
        FROM observations WHERE market_id=2 AND id<=:head AND retrieved_at>=:start AND retrieved_at<=:at
        ORDER BY (retrieved_at AT TIME ZONE 'UTC')::date,retrieved_at DESC,id DESC"""),
        {'head': head['id'], 'start': aware(head['retrieved_at']) - timedelta(days=60), 'at': head['retrieved_at']}).mappings())
    selected = {row['id']: dict(row) for row in daily}
    selected.update({row['id']: dict(row) for row in recent[:2]})
    previous = next((row for row in recent if row['snapshot_id'] != head['snapshot_id']), None)
    if previous is None: raise RuntimeError('Bounded recent window has no changed observation for incremental baseline')
    selected[previous['id']] = dict(previous)
    ids = sorted({row['snapshot_id'] for row in selected.values()})
    if len(ids) > 8: raise RuntimeError('Snapshot bound exceeded; review explicit benchmark capture scope')
    snapshots = [dict(r) for r in db.execute(select(Snapshot.__table__).where(Snapshot.id.in_(ids))).mappings()]
    if any(not s['statistics_retained'] for s in snapshots): raise RuntimeError('Selected statistics are not fully retained')
    market = dict(db.execute(select(Market.__table__).where(Market.id == 2)).mappings().one())
    market = {k: market[k] for k in ['id','region','ruleset_id','house_id','source_kind','unified_coverage','verified']}
    statistics = []
    for sid in ids:
        after = (0, '')
        while True:
            from sqlalchemy import tuple_
            rows = list(db.execute(select(SnapshotStatistic.__table__).where(SnapshotStatistic.snapshot_id == sid,
                tuple_(SnapshotStatistic.item_id, SnapshotStatistic.variant_key) > after)
                .order_by(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).limit(2000)).mappings())
            if not rows: break
            statistics.extend(dict(r) for r in rows)
            after = (rows[-1]['item_id'], rows[-1]['variant_key'])
            if len(statistics) > 250_000: raise RuntimeError('Record bound exceeded')
    coverage = [dict(r) for r in db.execute(select(ItemSourceCoverage.__table__).where(ItemSourceCoverage.market_id == 2)).mappings()]
    floor = db.scalar(text('SELECT max(history_floor) FROM retention_batches'))
    for o in selected.values():
        # These are market ingestion keys, not credentials; replace incidental identifiers.
        o['request_key'] = 'sync-performance-' + str(o['id'])
    result = {'format':'production-derived-sync-summary-slice-v1','production_read_only':True,
        'history_scope':'exact daily winners plus recent changed/repeat observations; not a complete production archive',
        'market':market,'observations':sorted(selected.values(),key=lambda r:r['id']),
        'snapshots':snapshots,'statistics':statistics,'coverage':coverage,
        'history_floor':floor,'full_target':previous['id'],'incremental_target':head['id'],
        'unchanged_target':recent[1]['id'] if recent[1]['snapshot_id']==head['snapshot_id'] else head['id']}
    raw = json.dumps(result,default=str,separators=(',',':')).encode()
    if len(raw) > 128*1024*1024: raise RuntimeError('Capture byte bound exceeded')
    print(raw.decode())
    db.rollback()
