"""Bounded rollback-only synthetic benchmark, PostgreSQL market_test only."""
import json
import os
from pathlib import Path
import resource
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import insert, text
from market.db import Session,engine,now
from market.models import ItemMetadata,Market,User
from market.ingest import ingest
from market.metadata_admin import overview
from market.metadata_catalog import import_everloot_page
from market.market_api import items
from market.catalogue import catalogue
assert engine.url.database=='market_test' and engine.dialect.name=='postgresql','Refusing benchmark outside isolated PostgreSQL market_test'
output={'synthetic_only':True,'at':now().isoformat(),'observed_item_ids':5000,'note':'Rollback-only fixtures; no provider calls or production coverage inference.'}
with Session() as db:
    tx=db.begin()
    market=Market(region='tw',ruleset_id=2,house_id=99999,source_kind='auctions',label='Rollback-only metadata benchmark')
    db.add(market);db.flush()
    ingest(db,market.id,json.dumps({'auctions':[{'id':i,'item':{'id':100000+i},'quantity':1,'buyout':100+i} for i in range(1,5001)]}).encode(),request_key='metadata-benchmark',synthetic=True)
    stamp=now()
    db.execute(insert(ItemMetadata),[{'region':'tw','item_id':100000+i,'namespace':'static-forever-tw','name':f'Synthetic Item {i:05d}','status':'available','synthetic':True,'checked_at':stamp,'retry_after':stamp} for i in range(1,3501)])
    body=json.dumps({'items':[{'itemId':100000+i,'class':{'name':'Armor'},'quality':{'name':'Rare'}} for i in range(1,501)],'gameData':{'build':'1.60.1.70532','credit':'Game data © Blizzard Entertainment'},'offset':0,'limit':500,'total':500,'next':None}).encode()
    cpu=time.process_time();start=time.perf_counter()
    imported,_=import_everloot_page(db,'tw',body)
    elapsed=time.perf_counter()-start
    output.update(imported_records=imported,import_seconds=round(elapsed,4),import_records_per_second=round(imported/elapsed,2),import_cpu_seconds=round(time.process_time()-cpu,4))
    db.execute(text('ANALYZE item_metadata'));db.execute(text('ANALYZE snapshot_statistics'))
    user=db.query(User).first()
    def bench(name,fn):
        fn();times=[]
        for _ in range(5):
            start=time.perf_counter();fn();times.append((time.perf_counter()-start)*1000)
        output[name]={'median_ms':round(statistics.median(times),3),'max_ms':round(max(times),3),'runs':5}
    bench('coverage',lambda:overview(market_id=market.id,user=user,db=db))
    bench('name_search',lambda:items(market.id,q='Item 034',after_id=0,limit=50,user=user,db=db))
    bench('market_explorer_catalogue',lambda:catalogue(market.id,q='',sort='item_id',direction='asc',page=0,page_size=50,user=user,db=db))
    output['search_explain']=[r[0] for r in db.execute(text("EXPLAIN (ANALYZE,BUFFERS) SELECT item_id FROM item_metadata WHERE lower(coalesce(name,fallback_name)) LIKE '%item 034%'"))]
    output['peak_process_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    output['catalogue_row_count']=db.scalar(text('select count(*) from item_metadata'))
    tx.rollback()
path=Path(__file__).resolve().parents[1]/'docs/evidence/metadata-recovery-performance.json'
path.write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:v for k,v in output.items() if k not in ('search_explain','catalogue_parameters')},indent=2))
