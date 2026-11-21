"""Rollback-only synthetic workload; refuses every database except market_test.
Run in bounded isolated test worker with /app backend and PYTHONPATH=/app.
Independent compact catalogue (10,000 groups / 30,000 variants), 10-year
single-variant daily history and 100,000-listing distribution workloads.
These fixtures benchmark queries, not upstream ingestion or live prices.
"""
import hashlib,json,statistics,time
from datetime import timedelta
from sqlalchemy import event,insert,text
from market.db import Session,engine,now
from market.models import Base,Market,Snapshot,Observation,DailyObservation,SnapshotStatistic,Listing
from market.catalogue import catalogue
from market.pricing import daily_history,ALGORITHM
from market.distribution import distribution
assert engine.url.database=='market_test','Refusing non-test database'
Base.metadata.create_all(engine)
at=now();key=hashlib.sha256(b'benchmark-base-variant').hexdigest()
report={'synthetic':True,'rollback_only':True,'workload':{'item_groups':10000,'latest_variants':30000,'daily_history_days':3651,'distribution_listings':100000},'measurements':{}}
with Session() as db:
    try:
        market=Market(region='us',ruleset_id=999,house_id=999,source_kind='auctions',label='SYNTHETIC rollback benchmark')
        db.add(market);db.flush();mid=market.id
        snapshots=[{'market_id':mid,'content_hash':hashlib.sha256(f'benchmark-{i}'.encode()).hexdigest(),'created_at':at-timedelta(days=i),'listing_count':100000 if i==0 else 1} for i in range(3651)]
        ids=list(db.scalars(insert(Snapshot).returning(Snapshot.id),snapshots))
        observations=[{'market_id':mid,'snapshot_id':sid,'request_key':hashlib.sha256(f'bench-{mid}-{i}'.encode()).hexdigest(),'retrieved_at':at-timedelta(days=i),'namespace':'synthetic-benchmark','payload_hash':'0'*64,'payload_bytes':0,'synthetic':True} for i,sid in enumerate(ids)]
        oids=list(db.scalars(insert(Observation).returning(Observation.id),observations))
        db.execute(insert(DailyObservation),[{'market_id':mid,'day':(at-timedelta(days=i)).date(),'observation_id':oid} for i,oid in enumerate(oids)])
        stats=[{'snapshot_id':sid,'item_id':25,'variant_key':key,'algorithm':ALGORITHM,'recent_price':10000+i,'lowest_buyout':10000+i,'supply':100000 if i==0 else 1,'priced_supply':100000 if i==0 else 1,'listing_count':100000 if i==0 else 1} for i,sid in enumerate(ids)]
        stats.extend({'snapshot_id':ids[0],'item_id':25+item,'variant_key':hashlib.sha256(f'variant-{variant}'.encode()).hexdigest(),'algorithm':ALGORITHM,'recent_price':item*100+variant,'lowest_buyout':item*100+variant,'supply':1,'priced_supply':1,'listing_count':1} for item in range(10000) for variant in range(3) if item or variant)
        db.execute(insert(SnapshotStatistic),stats)
        for start in range(0,100000,5000):
            db.execute(insert(Listing),[{'snapshot_id':ids[0],'auction_id':i+1,'item_id':25,'variant_key':key,'variant':'{}','quantity':1,'buyout':10000+i%10000} for i in range(start,start+5000)])
        db.flush()
        # Planner statistics are transaction-local here; the entire fixture rolls back.
        for table in ['snapshots','observations','daily_observations','snapshot_statistics','listings']:
            db.execute(text('ANALYZE '+table))
        def measure(name,job):
            durations=[];counts=[]
            for _ in range(5):
                queries=[]
                def record(*args):queries.append(1)
                event.listen(engine,'before_cursor_execute',record);started=time.perf_counter()
                try:result=job()
                finally:event.remove(engine,'before_cursor_execute',record)
                durations.append(round((time.perf_counter()-started)*1000,3));counts.append(len(queries))
            report['measurements'][name]={'median_ms':statistics.median(durations),'latency_ms':durations,'sql_counts':counts,'response_bytes':len(json.dumps(result,default=str).encode())}
            return result
        rows=measure('catalogue_50_groups',lambda:catalogue(mid,q='',sort='item_id',direction='asc',page=0,page_size=50,user=None,db=db));assert rows['total_items']==10000
        history=measure('daily_history_10_years',lambda:daily_history(db,mid,25,key,days=3650,at=at));assert len(history['points'])==3651
        compact=measure('daily_history_10_years_chart',lambda:daily_history(db,mid,25,key,days=3650,at=at,compact=True));assert len(compact['points'])==3651
        bands=measure('distribution_100000_listings',lambda:distribution(mid,25,key,bins=12,user=None,db=db));assert bands['listing_count']==100000
        report['query_plans']={}
        for name,sql,params in [('variant_history','SELECT * FROM snapshot_statistics WHERE item_id=25 AND variant_key=:key',{'key':key}),('daily_lookup','SELECT * FROM daily_observations WHERE market_id=:mid ORDER BY day',{'mid':mid}),('listing_variant','SELECT quantity,buyout FROM listings WHERE snapshot_id=:sid AND item_id=25 AND variant_key=:key',{'sid':ids[0],'key':key})]:
            report['query_plans'][name]=db.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql),params).scalar()
    finally:db.rollback()
print(json.dumps(report,default=str))
