"""Administration history performance on disposable PostgreSQL market_test only."""
import json,statistics,time
from datetime import timedelta
from sqlalchemy import insert,select
from market.db import Session,engine,now
from market.models import Market,MetadataJob,MetadataTask,SecurityEvent,User
if engine.dialect.name!='postgresql' or engine.url.database!='market_test':raise SystemExit('Refusing administration benchmark outside PostgreSQL market_test')
with Session.begin() as db:
    owner=db.scalar(select(User).where(User.username=='owner'))
    market=db.scalar(select(Market).order_by(Market.id))
    at=now()-timedelta(days=2)
    job=db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key=='synthetic-admin-performance'))
    if not job:
        job=MetadataJob(actor_id=owner.id,market_id=market.id,mode='single',state='completed',dedupe_key='synthetic-admin-performance',providers_json='["everloot"]',total=10000,request_budget=1,requests_used=0,created_at=at,updated_at=at)
        db.add(job);db.flush()
        for start in range(0,10000,500):
            db.execute(insert(MetadataTask),[{'job_id':job.id,'provider':'everloot','region':market.region,'item_id':400000+i,'state':'completed','attempts':1,'available_at':at,'updated_at':at,'result_json':'{"status":"metadata_unavailable","http_status":404,"outcome":"missing"}'} for i in range(start,start+500)])
            db.execute(insert(SecurityEvent),[{'actor_id':owner.id,'action':'metadata.synthetic.performance','detail':'Synthetic performance fixture','created_at':at} for _ in range(500)])
from fastapi.testclient import TestClient
from market.app import app
result={'synthetic':True,'provider_requests':0,'history_rows':10000,'measurements':[]}
with TestClient(app) as client:
    assert client.post('/api/v1/auth/login',json={'username':'owner','password':'synthetic browser owner password'}).status_code==200
    for path in ('metadata-attempts?limit=25','metadata-attempts?limit=25&offset=5000&provider=everloot&outcome=missing','security?limit=25','security?limit=25&q=metadata','jobs?limit=25',f'unresolved?market_id={market.id}&limit=25','collection?limit=25'):
        durations=[]
        for _ in range(5):
            start=time.perf_counter();response=client.get('/api/v1/admin/records/'+path);durations.append((time.perf_counter()-start)*1000)
            assert response.status_code==200,(path,response.status_code)
            value=response.json();assert len(value['rows'])<=25
        result['measurements'].append({'path':path,'mean_ms':round(statistics.mean(durations),2),'max_ms':round(max(durations),2),'response_bytes':len(response.content),'rows_returned':len(value['rows']),'total':value['total']})
print(json.dumps(result,indent=2))
