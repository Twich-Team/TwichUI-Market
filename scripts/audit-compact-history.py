"""Bounded read-only production aggregate audit; no deletion or proof insertion."""
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'backend/market/compaction_safety.py').read_text()
audit='''
import json,time
from datetime import datetime
from sqlalchemy import select,text,func
from market.db import Session
from market.models import Snapshot,Observation
at=datetime.fromisoformat('2026-11-24T12:54:00+00:00')
with Session.begin() as db:
    db.execute(text('SET TRANSACTION READ ONLY'))
    db.execute(text("SET LOCAL statement_timeout='2s'"))
    heads=select(Observation.snapshot_id).distinct(Observation.market_id).order_by(Observation.market_id,Observation.retrieved_at.desc(),Observation.id.desc())
    from datetime import timedelta
    recent=select(Observation.snapshot_id).where(Observation.retrieved_at>=at-timedelta(days=7))
    snapshots=list(db.execute(select(Snapshot.id,Snapshot.listing_count).where(Snapshot.id.not_in(heads),Snapshot.id.not_in(recent)).order_by(Snapshot.id)))
print(json.dumps(dict(type='scope',at=at.isoformat(),snapshots=len(snapshots),listing_rows=sum(n for _,n in snapshots))),flush=True)
for key,expected in snapshots:
    started=time.monotonic()
    try:
        with Session.begin() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            db.execute(text("SET LOCAL statement_timeout='2s'"))
            db.execute(text("SET LOCAL lock_timeout='100ms'"))
            db.execute(text("SET LOCAL max_parallel_workers_per_gather=0"))
            raw=raw_fingerprint(db,key);compact=compact_fingerprint(db,key)
        result=dict(type='snapshot',id=key,expected_listings=expected,raw_sha256=raw[0],compact_sha256=compact[0],variants=raw[1],listing_rows=raw[2],match=raw==compact and raw[2]==expected,seconds=round(time.monotonic()-started,3))
    except Exception as exc:result=dict(type='snapshot',id=key,match=False,error=type(exc).__name__)
    print(json.dumps(result),flush=True)
    time.sleep(.3)
'''
program="__package__='market'\n"+source+'\n'+audit
process=subprocess.run(['docker','--context','rootless','exec','-i','twichui-market-api-1','python','-'],input=program.encode(),timeout=600)
raise SystemExit(process.returncode)
