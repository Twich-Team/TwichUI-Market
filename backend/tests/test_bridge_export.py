"""Authenticated immutable transport, pinned independent prices and explicit synthetic history."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import pytest
from sqlalchemy import delete
from market.bridge_contract import contract
from market.db import now
from market.ingest import ingest
from market.models import BridgeGeneration, BridgeRecord, Listing, Market, Snapshot, User
from market.security import issue


def key(item):return hashlib.sha256(json.dumps(item,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@pytest.fixture
def bridge(client,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','bridge-test-secret-'+'a'*32)
    with database.begin() as db:
        token,_,_=issue(db,db.get(User,1),'device')
        m=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic bridge fixture',verified=True)
        db.add(m);db.flush();mid=m.id
        today=datetime.combine(now().date(),datetime.min.time(),tzinfo=timezone.utc)
        def book(price,historical):
            rows=[{'id':i+1,'item':{'id':2589},'quantity':q,'buyout':price*q} for i,q in enumerate([3,3,4])]
            if historical:rows +=[{'id':10+i,'item':{'id':2},'quantity':q,'buyout':50*q} for i,q in enumerate([3,3,4])]
            rows +=[{'id':20,'item':{'id':2589,'bonus_lists':[9]},'quantity':1,'buyout':999},
                    {'id':21,'item':{'id':123},'quantity':2,'bid':50}]
            return json.dumps({'auctions':rows}).encode()
        a=ingest(db,mid,book(100,True),request_key='bridge-day-a',retrieved_at=today-timedelta(days=2),synthetic=True)
        b=ingest(db,mid,book(120,False),request_key='bridge-day-c',retrieved_at=today,synthetic=True)
        db.flush();oids=[a.id,b.id];sids=[a.snapshot_id,b.snapshot_id]
    client.headers['Authorization']='Bearer '+token
    return client,mid,oids,sids


def download(client,mid,**options):
    response=client.get(f'/api/v1/bridge/markets/{mid}/manifest',params=options)
    assert response.status_code==200,response.text
    e=response.json();g=copy.deepcopy(e['manifest']);g['records']=[];cursor=e['cursor'];pages=0
    while True:
        response=client.get(f'/api/v1/bridge/markets/{mid}/records',params={'cursor':cursor,'generation':g['generation_id'],'limit':1})
        assert response.status_code==200,response.text
        p=response.json();assert p['offset']==len(g['records']);g['records']+=p['records'];pages+=1
        if not p['has_more']:assert p['next_cursor'] is None;break
        cursor=p['next_cursor']
    contract().validate(g)
    return g,pages,e


def test_dates_gap_variants_history_only_and_bid_only(bridge):
    client,mid,oids,_=bridge;g,pages,_=download(client,mid)
    assert pages==4 and g['schema_version']==2 and g['desktop_sync_completed_at'] is None and g['synthetic']
    rows={(r['item_id'],r['variant_key']):r for r in g['records']};r=rows[2589,key({'id':2589})]
    assert r['current']['metrics']=={'minimum_copper':'120','quantity_weighted_ask_copper':'120','recent_copper':'120','market_value_copper':'100','historical_value_copper':None}
    assert [p['recent_copper'] for p in r['daily']]==['100','120']
    assert [g['observations'][p['observation_ref']]['observation_id'] for p in r['daily']]==list(map(str,oids))
    dates=[g['observations'][p['observation_ref']]['utc_day'] for p in r['daily']]
    assert (datetime.fromisoformat(dates[1])-datetime.fromisoformat(dates[0])).days==2
    assert rows[2,key({'id':2})]['current']['state']=='absent'
    bid=rows[123,key({'id':123})];assert bid['current']['metrics']['recent_copper'] is None and bid['current']['supply']==2
    assert rows[2589,key({'id':2589,'bonus_lists':[9]})]['current']['metrics']['recent_copper']=='999'


def test_legacy_algorithm_and_distribution_remain_distinct(bridge):
    client,mid,_,_=bridge;g,_,_=download(client,mid,algorithm='asking-v1-provisional')
    r=next(r for r in g['records'] if r['variant_json']=='{"id":2589}')
    assert r['current']['metrics']['market_value_copper']=='110' and r['current']['metrics']['historical_value_copper']=='110'
    assert r['current']['metric_basis']=='quantity_weighted_mean' and r['distribution']['algorithm']=='linear-unit-price-bands-v1'


def test_auth_algorithm_and_cursor_scope(bridge,database):
    client,mid,_,_=bridge;g,_,e=download(client,mid);route=f'/api/v1/bridge/markets/{mid}/records'
    assert client.get(f'/api/v1/bridge/markets/{mid}/manifest',params={'algorithm':'future-v9'}).status_code==422
    assert client.get(route,params={'cursor':e['cursor']+'x','generation':g['generation_id']}).status_code==409
    assert client.get(route,params={'cursor':e['cursor'],'generation':'f'*64}).status_code==409
    with database.begin() as db:
        u=User(username='other',password_hash='unused',role='member');db.add(u);db.flush();token,_,_=issue(db,u,'device')
    client.headers['Authorization']='Bearer '+token
    assert client.get(route,params={'cursor':e['cursor'],'generation':g['generation_id']}).status_code==409
    client.headers.pop('Authorization');assert client.get(f'/api/v1/bridge/markets/{mid}/manifest').status_code==401


def test_collection_and_retention_cannot_mix_pages(bridge,database):
    client,mid,_,sids=bridge;g,_,e=download(client,mid)
    with database.begin() as db:
        ingest(db,mid,b'{"auctions":[{"id":999,"item":{"id":99},"quantity":1,"buyout":100}]}',request_key='concurrent',synthetic=True)
        db.execute(delete(Listing).where(Listing.snapshot_id.in_(sids)))
        for sid in sids:db.get(Snapshot,sid).raw_retained=False
    p=client.get(f'/api/v1/bridge/markets/{mid}/records',params={'cursor':e['cursor'],'generation':g['generation_id'],'limit':100})
    assert p.status_code==200 and p.json()['records']==g['records']
    newer,_,_=download(client,mid);assert newer['generation_id']!=g['generation_id']


def test_missing_originals_preserve_only_original_algorithm(bridge,database):
    client,mid,_,sids=bridge
    with database.begin() as db:
        db.execute(delete(Listing).where(Listing.snapshot_id==sids[0]));db.get(Snapshot,sids[0]).raw_retained=False
    response=client.get(f'/api/v1/bridge/markets/{mid}/manifest')
    assert response.status_code==409 and 'asking-v1-provisional' in response.text
    g,_,_=download(client,mid,algorithm='asking-v1-provisional')
    assert len(next(r for r in g['records'] if r['item_id']==2)['daily'])==2


def test_materialization_failure_and_recovery(bridge,database):
    client,mid,_,_=bridge;g,_,e=download(client,mid);again,_,_=download(client,mid);assert again==g
    with database.begin() as db:db.execute(delete(BridgeRecord).where(BridgeRecord.generation_id==g['generation_id']))
    assert client.get(f'/api/v1/bridge/markets/{mid}/records',params={'cursor':e['cursor'],'generation':g['generation_id']}).status_code==409
    with database.begin() as db:db.execute(delete(BridgeGeneration).where(BridgeGeneration.generation_id==g['generation_id']))
    recovered,_,_=download(client,mid);assert recovered['records']==g['records']


def test_large_copper_exact_but_canonical_unsupported(bridge,database):
    client,mid,_,_=bridge
    with database.begin() as db:ingest(db,mid,b'{"auctions":[{"id":9,"item":{"id":99},"quantity":1,"buyout":9223372036854775807}]}',request_key='large',synthetic=True)
    g,_,_=download(client,mid);r=next(r for r in g['records'] if r['item_id']==99)
    assert r['current']['metrics']['quantity_weighted_ask_copper']=='9223372036854775807'
    assert r['current']['metrics']['recent_copper'] is None and r['current']['arithmetic_status']=='unsupported'


def test_schema2_precision_and_immutable_schema1_fixtures():
    root=Path(__file__).resolve().parents[2]/'contracts/bridge/v1'
    for name in ['canonical-generation.json','provisional-generation.json','source-canonical-generation.json','source-provisional-generation.json']:contract().read(root/name)
    g=contract().read(root/'source-canonical-generation.json');assert g['observations'][0]['observed_at'].endswith('.123456Z')
    g['schema_version']=3
    with pytest.raises(ValueError):contract().validate(contract().seal(g))


def test_bounded_cold_derivations_resume_without_claiming_complete(bridge,monkeypatch):
    from market import bridge_api
    client,mid,_,_=bridge
    monkeypatch.setattr(bridge_api,'MAX_COLD_SNAPSHOTS',1)
    r=client.get(f'/api/v1/bridge/markets/{mid}/manifest')
    assert r.status_code==202 and r.json()=={'state':'preparing','retry_after_seconds':1}
    g,_,_=download(client,mid);assert g['coverage']['generation_complete'] is True


def test_oversize_generation_refused_and_no_materialization_published(bridge,database,monkeypatch):
    client,mid,_,_=bridge
    monkeypatch.setattr(contract(),'MAX_BYTES',1000)
    assert client.get(f'/api/v1/bridge/markets/{mid}/manifest').status_code==413
    from sqlalchemy import func,select
    with database() as db:assert db.scalar(select(func.count()).select_from(BridgeGeneration))==0
