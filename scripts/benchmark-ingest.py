"""Synthetic bounded ingestion benchmark; refuses non-test databases."""
import argparse
import json
import resource
import time
from sqlalchemy import func,select
from market.db import Session,engine
from market.ingest import ingest
from market.models import Listing,Market,SnapshotStatistic

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--listings',type=int,default=10000)
args=parser.parse_args()
if engine.url.database!='market_test' or not 1<=args.listings<=100000:
    raise SystemExit('Use a disposable market_test database and 1–100000 listings')
body=json.dumps({'auctions':[{'id':index+1,'item':{'id':12300+index%100},'quantity':20,
                              'buyout':200000,'time_left':'VERY_LONG'} for index in range(args.listings)]}).encode()
started=time.monotonic()
with Session.begin() as db:
    market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic benchmark')
    db.add(market);db.flush()
    observation=ingest(db,market.id,body,request_key='synthetic-benchmark',synthetic=True)
    assert db.scalar(select(func.count()).select_from(Listing))==args.listings
    assert db.scalar(select(func.count()).select_from(SnapshotStatistic))==min(100,args.listings)
print(json.dumps({'synthetic':True,'listings':args.listings,'payload_bytes':len(body),
    'duration_seconds':round(time.monotonic()-started,3),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'container_memory_limit_mib':384,'container_cpu_limit':1}))
