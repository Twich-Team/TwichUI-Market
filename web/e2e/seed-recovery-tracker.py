"""Isolated deterministic Recovery Tracker evidence. Never a provider campaign."""
import json
from datetime import timedelta
from market.db import Session,engine,now
from market.models import Market,User,MetadataProvider,MetadataSource,MetadataTask,MetadataJob,MetadataAttempt
from market.metadata_recovery import ensure_providers
from market.metadata_catalog import store_source
from market.ingest import ingest
from market.security import hasher
assert engine.url.database=='market_test'
at=now()
with Session.begin() as db:
    user=db.query(User).filter_by(username='owner').first()
    if not user:db.add(User(username='owner',role='admin',password_hash=hasher.hash('synthetic browser owner password')))
    ensure_providers(db)
    for p in db.query(MetadataProvider):
        p.enabled=p.automatic=p.provider in ('blizzard','foreverdb','thewowdb')
        p.credential_status='oauth_connected' if p.provider=='blizzard' else 'keyless'
        if p.provider=='foreverdb':
            p.credential=b'synthetic-placeholder-not-decryptable';p.validated_at=at;p.credential_status='connected'
            p.cooldown_until=at+timedelta(minutes=20)
    market=Market(id=500,region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Recovery Tracker — synthetic',enabled=True,verified=True)
    db.add(market);db.flush()
    ingest(db,market.id,json.dumps({'auctions':[{'id':i,'item':{'id':80000+i},'quantity':1,'buyout':1000} for i in range(1,61)]}).encode(),request_key='synthetic-tracker',synthetic=True)
    for i in range(1,61):
        if i%3 and i!=1:store_source(db,'us',80000+i,'everloot',{'name':f'Synthetic recovery {i:02d}'},{'provider':'everloot','edition':'forever','locale':'en_US'},at=at-timedelta(days=2))
        if i%5==0:db.add(MetadataSource(region='us',item_id=80000+i,provider='blizzard',http_status=404,status='metadata_unavailable',checked_at=at-timedelta(hours=1),retry_at=at+timedelta(days=6)))
    store_source(db,'us',80001,'foreverdb',{'name':'Synthetic recovery 01','quality':'COMMON'},
        {'provider':'foreverdb','edition':'forever','locale':'en_US','confidence':'synthetic','build':'1.60.1.70532','item_build':'1.60.1.70532','item_mapping_version':2},at=at-timedelta(minutes=10))
    src=db.get(MetadataSource,('us',80001,'en_US','foreverdb'))
    src.recovery_json=json.dumps({'new_fields':['name','quality'],'updated_fields':[],'last_useful_at':(at-timedelta(minutes=10)).isoformat(),'outcome':'name_recovered'})
    db.add_all([
        MetadataAttempt(provider='foreverdb',region='us',item_id=80001,kind='metadata',started_at=at-timedelta(minutes=10),completed_at=at-timedelta(minutes=10),state='finished',http_status=200,outcome='name_recovered',returned_json='["name","quality"]',new_json='["name","quality"]',decision_json=json.dumps({'explanation':'Synthetic fixture: ForeverDB was eligible for name and quality.'})),
        MetadataAttempt(provider='thewowdb',region='us',item_id=80001,kind='metadata',started_at=at-timedelta(minutes=5),completed_at=at-timedelta(minutes=5),state='finished',http_status=304,outcome='already_known',returned_json='[]',new_json='[]'),
        MetadataAttempt(provider='foreverdb',region='us',item_id=80002,kind='metadata',started_at=at-timedelta(minutes=2),state='reserved')])
    job=MetadataJob(market_id=market.id,mode='single',state='completed',dedupe_key='synthetic-tracker-history',providers_json='["thewowdb"]',total=1,requests_used=1)
    db.add(job);db.flush()
    db.add(MetadataTask(job_id=job.id,provider='thewowdb',region='us',item_id=80001,state='completed',attempts=1,result_json='{"status":"available","recovered_fields":["name"]}',updated_at=at-timedelta(days=1)))
print('Synthetic recovery tracker fixtures seeded; no worker/provider requests')
