"""Enqueue a bounded primary-name job; the independent worker performs all I/O.

Retains the legacy --limit option without bypassing persistent provider budgets,
negative caches or cooldowns. No market/collector configuration is changed.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select
from market.db import Session
from market.models import Market
from market.metadata_recovery import enqueue,ensure_providers

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--limit',type=int,default=50,choices=range(1,101))
parser.add_argument('--market',type=int)
args=parser.parse_args()
with Session.begin() as db:
    query=select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)
    if args.market:query=query.where(Market.id==args.market)
    market=db.scalar(query.limit(1))
    if market is None:raise SystemExit('No matching verified collecting market; no recovery enqueued')
    ensure_providers(db)
    job,created=enqueue(db,market.id,'missing',['blizzard'],limit=args.limit,budget=args.limit)
    result={'job_id':job.id,'created':created,'state':job.state,'maximum_requests':job.request_budget,
        'note':'Queued only. Inspect Administration → Item Metadata; the independent worker honors all provider limits.'}
print(json.dumps(result,indent=2))
