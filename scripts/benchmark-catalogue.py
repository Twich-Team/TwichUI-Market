"""Read-only legacy/new catalogue latency, SQL count and response size measurements."""
import argparse,json,statistics,time
from sqlalchemy import event
from market.db import Session,engine
from market.models import User
from market.market_api import items
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--market',type=int,default=1)
parser.add_argument('--runs',type=int,default=5,choices=range(1,21))
parser.add_argument('--endpoint',choices=['legacy','catalogue'],default='legacy')
args=parser.parse_args()
counts=[];durations=[];sizes=[]
for _ in range(args.runs):
    queries=[]
    def record(*_):queries.append(1)
    with Session() as db:
        user=db.get(User,1)
        event.listen(engine,'before_cursor_execute',record)
        started=time.perf_counter()
        try:
            if args.endpoint=='legacy':result=items(args.market,q='',after_id=0,limit=50,user=user,db=db)
            else:
                from market.catalogue import catalogue
                result=catalogue(args.market,q='',sort='item_id',direction='asc',page=0,page_size=50,user=user,db=db)
        finally:event.remove(engine,'before_cursor_execute',record)
        durations.append(round((time.perf_counter()-started)*1000,3));counts.append(len(queries))
        sizes.append(len(json.dumps(result,default=str).encode()))
print(json.dumps({'endpoint':args.endpoint,'market':args.market,'runs':args.runs,'latency_ms':durations,'median_ms':statistics.median(durations),'sql_counts':counts,'response_bytes':sizes,'returned_rows':len(result['items']),'row_kind':'variants' if args.endpoint=='legacy' else 'item_groups','read_only':True}))
