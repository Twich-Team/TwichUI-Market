"""Optional bounded synthetic mobile-scale fixture. Never a worker or provider campaign."""
import json
from market.db import Session,engine,now
from market.models import Market
from market.ingest import ingest
assert engine.url.database=='market_test','Refusing non-test database'
with Session.begin() as db:
    market=Market(region='eu',ruleset_id=2,house_id=115,source_kind='auctions',label='Synthetic mobile scale — 5,000 distinct items')
    db.add(market);db.flush()
    rows=[{'id':800000+i,'item':{'id':800000+i},'quantity':i%20+1,'buyout':(i%20+1)*(10000+i),'time_left':'LONG'} for i in range(5000)]
    ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key='mobile-scale-5000',retrieved_at=now(),synthetic=True)
    print('Synthetic mobile scale market:',market.id,'items:',len(rows))
