"""Bounded synthetic cold/warm projection cost in an isolated market_test database.
Never accepts production data or invokes collection/providers. Seed and measure in
separate processes so fixture allocation is not attributed to API generation.
"""
import argparse,hashlib,json,os,resource,time
from pathlib import Path
from datetime import timedelta
from sqlalchemy import select
from market.db import Base,engine,Session,now
from market.models import Market,PlayerMarketMapping
from market.ingest import ingest
from market import workshop_summary as summary
p=argparse.ArgumentParser();p.add_argument('action',choices=['seed','measure']);p.add_argument('--variants',type=int,default=45125);a=p.parse_args()
if engine.url.database!='market_test' or not 129<=a.variants<=45125:raise RuntimeError('isolated market_test and bounded count required')
if a.action=='seed':
 Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
 with Session.begin() as db:
  m=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic summary capacity only',verified=True,enabled=True);db.add(m);db.flush()
  evidence=json.dumps({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde','upstream_receipt':'synthetic','independent_observation':'synthetic','independent_source_url':'https://example.invalid/fixture'})
  db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,source_kind='auctions',transport_ruleset_id=1,confidence='verified',evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),verified_at=now()))
  for day,price in [(2,100),(0,120)]:
   auctions=[{'id':i*3+j+1,'item':{'id':10000+i},'quantity':q,'buyout':q*price}for i in range(a.variants)for j,q in enumerate([3,3,4])]
   ingest(db,m.id,json.dumps({'auctions':auctions}).encode(),request_key=f'summary-capacity-{day}',retrieved_at=now()-timedelta(days=day,minutes=1),synthetic=True)
 print(json.dumps({'synthetic':True,'variants':a.variants,'raw_listings_per_snapshot':3*a.variants,'seed_complete':True}))
else:
 out=[]
 for iteration in range(100):
  started=time.perf_counter();cpu=time.process_time()
  with Session.begin() as db:
   m=db.scalar(select(Market));g=summary.build(db,m)
   h=json.loads(g.manifest_json)if g else None
  out.append({'iteration':iteration,'wall_seconds':time.perf_counter()-started,'cpu_seconds':time.process_time()-cpu,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'ready':g is not None,'records':h['record_count']if h else None,'part_bytes':sum(x['bytes']for x in h['partitions'])if h else None,'largest_part_bytes':max((x['bytes']for x in h['partitions']),default=0)if h else None})
  if len(out)>2 and all(v['ready']for v in out[-3:]):break
 print(json.dumps({'synthetic':True,'variants':a.variants,'measurements':out},indent=2))
