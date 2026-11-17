"""Same seeded population and clock, actual frozen versus new worker. Synthetic only."""
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import time
import types
import tracemalloc
from sqlalchemy import select,func
from market.db import Base,now
from market.ingest import ingest
from market.models import ItemMetadata,ItemMedia,Market,MetadataProvider,MetadataSource
from market.metadata_catalog import store_source
from market.metadata_recovery import ensure_providers
import market.metadata_recovery as current
from test_item_profiles import PNG


def test_same_population_replay(database,monkeypatch,tmp_path):
    fixture=Path(__file__).parent/'fixtures/recovery-policy-baseline.py'
    frozen=fixture.read_bytes()
    assert hashlib.sha256(frozen).hexdigest()=='4dbb2e94ae9daafe6810f5342cb4af1f308c2e3c67484e4a189bb89dbbfdb655'
    old=types.ModuleType('market.recovery_baseline');old.__package__='market'
    exec(compile(frozen,str(fixture),'exec'),old.__dict__)
    assert database.kw['bind'].url.database=='market_test'
    anchor=now();outputs={}
    for label,worker in [('provider_first',old),('item_centric',current)]:
        engine=database.kw['bind'];Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
        with database.begin() as db:
            ensure_providers(db)
            for p in db.scalars(select(MetadataProvider)):
                p.enabled=p.automatic=p.provider in ('foreverdb','thewowdb')
                p.hourly_budget,p.daily_budget=60,500
                if p.provider=='foreverdb':p.credential=b'synthetic-test-only'
            market=Market(region='us',ruleset_id=2,house_id=114,label='Synthetic replay',source_kind='auctions',enabled=True,verified=True)
            db.add(market);db.flush()
            auctions=[{'id':i,'item':{'id':1000+i},'quantity':1,'buyout':100} for i in range(1,41)]
            ingest(db,market.id,json.dumps({'auctions':auctions}).encode(),request_key='synthetic-replay',synthetic=True)
            for i in range(1,41):
                fields={'quality':'COMMON','class':'Trade Goods'}
                if i>10:fields['name']=f'Synthetic item {1000+i}'
                if 10<i<=20:fields.pop('quality')
                store_source(db,'us',1000+i,'blizzard',fields,{'provider':'blizzard','edition':'forever','locale':'en_US','confidence':'synthetic'},at=anchor-timedelta(days=2))
                if i>10:db.get(ItemMetadata,('us',1000+i)).name=f'Synthetic item {1000+i}'
                db.add(ItemMedia(region='us',item_id=1000+i,data=PNG,byte_count=len(PNG),status='available',retry_after=anchor+timedelta(days=30)))
        monkeypatch.setattr(worker,'credential_value',lambda *args,**kwargs:'synthetic-test-only')
        calls=[];new_names=[];new_attributes=[];already=[];last_priority=None;distribution={}
        def fetcher(provider,item_id,**kwargs):
            nonlocal last_priority
            with database() as db:
                row=db.get(ItemMetadata,('us',item_id));fields=json.loads(row.catalog_json)['fields']
            had_name=bool(fields.get('name'));had_quality=bool(fields.get('quality'))
            calls.append((provider,item_id));distribution[provider]=distribution.get(provider,0)+1
            if not had_name:new_names.append(len(calls));last_priority=len(calls)
            if not had_quality:new_attributes.append(len(calls));last_priority=len(calls)
            if had_name and had_quality:already.append(len(calls))
            if provider=='foreverdb':
                return {'status':200,'headers':{}},json.dumps({'data':{'id':item_id,'name':f'Synthetic item {item_id}','quality':'Common','class':'Trade Goods'},'meta':{'build':'1.60.1.70532'}}).encode()
            payload=json.loads((Path(__file__).parent/'fixtures/provider-diagnostics/thewowdb-worn-shortsword.json').read_text())
            payload.update(id=item_id,name=f'Synthetic item {item_id}',quality='common')
            return {'status':200,'headers':{}},json.dumps(payload).encode()
        # Fixed tick count and pace, not a real provider campaign. Existing
        # budgets/cooldowns still execute in both policies.
        tracemalloc.start();wall=time.perf_counter();cpu=time.process_time()
        for step in range(80):worker.tick(database,at=anchor+timedelta(seconds=61*step),fetcher=fetcher)
        retained,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
        outputs[label]={'traced_retained_bytes':retained,'traced_peak_bytes':peak,'external_requests':len(calls),'new_name_requests':len(new_names),'new_attribute_requests':len(new_attributes),'already_known':len(already),
            'provider_distribution':distribution,'last_priority_request':last_priority,'first_name_request':min(new_names,default=None),
            'clock_span_seconds':61*79,'worker_wall_seconds':round(time.perf_counter()-wall,4),'worker_cpu_seconds':round(time.process_time()-cpu,4)}
    assert outputs['item_centric']['new_name_requests']==10
    assert outputs['item_centric']['first_name_request']==1
    assert outputs['provider_first']['first_name_request']>1
    assert outputs['item_centric']['external_requests']<outputs['provider_first']['external_requests']
    report={'synthetic_only':True,'baseline_sha':'fa089a2660e745d6f77f5c2b0b7bbcb9109d6ae8','population':40,'ticks':80,'results':outputs,
        'limitations':'Synthetic trade goods, 10 missing names/10 missing quality/20 complete. Secondary unchanged responses are deterministic. CPU excludes PostgreSQL server; wall includes SQL and mocks. No production efficiency claim. No artwork recovery in this replay.'}
    print(json.dumps(report,sort_keys=True))
    target=Path(__import__('os').environ.get('RECOVERY_REPLAY_OUTPUT','/tmp/metadata-policy-replay.json'))
    if not __import__('os').access(target.parent,__import__('os').W_OK):target=tmp_path/'replay.json'
    target.write_text(json.dumps(report,indent=2)+'\n')
