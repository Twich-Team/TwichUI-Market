"""Rollback-only 5,000-item selector probe. Refuses every non-test database."""
import base64,json,os,resource,statistics,sys,time
from datetime import timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import event,insert,select
from market.db import Base,Session,engine,now
from market.ingest import ingest
from market.metadata_recovery import ensure_providers,schedule_automatic
from market.models import Market,ItemMetadata,ItemMedia,MetadataProvider,MetadataSource,MetadataTask
if engine.dialect.name!='postgresql' or engine.url.database!='market_test':raise SystemExit('Refusing non-test PostgreSQL database')
Base.metadata.create_all(engine)
at=now();count=[0]
def query_count(*args):count[0]+=1
png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQpUAAAAASUVORK5CYII=')
with Session() as db:
    ensure_providers(db)
    for p in db.scalars(select(MetadataProvider)):
        p.enabled=p.automatic=p.provider in ('blizzard','foreverdb')
        if p.provider=='foreverdb':p.credential=b'synthetic-not-a-key'
    market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic selector benchmark',enabled=True,verified=True)
    db.add(market);db.flush()
    ingest(db,market.id,json.dumps({'auctions':[{'id':i,'item':{'id':i},'quantity':1,'buyout':100} for i in range(1,5001)]}).encode(),request_key='synthetic-selector-benchmark',synthetic=True)
    metadata=[];sources=[];media=[]
    for i in range(1,5001):
        fields={'quality':'COMMON','class':'Trade Goods'}
        if i<4990:fields['name']=f'Synthetic {i}'
        metadata.append({'region':'us','item_id':i,'name':fields.get('name'),'namespace':'static-forever-us','quality':'COMMON','catalog_json':json.dumps({'fields':fields,'provenance':{},'conflicts':[]})})
        sources.append({'region':'us','item_id':i,'provider':'blizzard','locale':'en_US','status':'available','fields_json':json.dumps(fields),'source_json':'{}','http_status':200,'checked_at':at-timedelta(days=1),'retry_at':at+timedelta(days=29)})
        media.append({'region':'us','item_id':i,'status':'available','data':png,'byte_count':len(png),'retry_after':at+timedelta(days=30)})
    db.execute(insert(ItemMetadata),metadata);db.execute(insert(MetadataSource),sources);db.execute(insert(ItemMedia),media);db.flush()
    timings=[];cpus=[];queries=[]
    event.listen(engine,'before_cursor_execute',query_count)
    try:
        for sample in range(6):
            nested=db.begin_nested();count[0]=0;wall=time.perf_counter();cpu=time.process_time()
            schedule_automatic(db,at,allow_mock=True);db.flush()
            timings.append((time.perf_counter()-wall)*1000);cpus.append((time.process_time()-cpu)*1000);queries.append(count[0])
            task=db.scalar(select(MetadataTask));assert task and task.provider=='foreverdb' and task.item_id==4990
            nested.rollback()
    finally:event.remove(engine,'before_cursor_execute',query_count)
    db.rollback()
print(json.dumps({'synthetic_only':True,'items':5000,'missing_names':11,'provider_requests':0,'warm_runs':5,
    'warm_wall_median_ms':round(statistics.median(timings[1:]),3),'warm_worker_cpu_median_ms':round(statistics.median(cpus[1:]),3),
    'warm_sql_statement_counts':queries[1:],'process_peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
    'limits':'192 MiB, one CPU; PostgreSQL isolated separately. Includes bounded local decision audit and writes rolled back each sample; excludes external I/O and production data. Not production p95.'},sort_keys=True))
