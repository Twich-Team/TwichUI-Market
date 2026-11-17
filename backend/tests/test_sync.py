import json
from datetime import timedelta
import pytest
from market.db import now
from market.ingest import ingest
from market.models import Market


@pytest.fixture(autouse=True)
def signing_key(monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-test-signing-key-32-characters-long')


def setup(database,count=3,when=None):
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic sync')
        db.add(market)
        db.flush()
        insert(db,market.id,range(1,count+1),'initial',when=when or now()-timedelta(days=1))
        return market.id


def insert(db,market,items,key,price=100,when=None):
    body=json.dumps({'auctions':[{'id':item,'item':{'id':item},'quantity':1,'buyout':price} for item in items]}).encode()
    return ingest(db,market,body,request_key=key,retrieved_at=when or now(),synthetic=True)


def test_initial_sync_resumes_stable_target_and_incremental_changes(owner,database):
    market=setup(database)
    path=f'/api/v1/sync/markets/{market}'
    first=owner.get(path+'?limit=1').json()
    assert first['has_more'] and len(first['changes'])==1
    assert first['changes'][0]['value']['recent_price']=='100'
    with database.begin() as db:
        insert(db,market,[2,3,4],'second',price=200)
    # A page retry is byte-for-byte deterministic even after a newer observation arrives.
    next_page=owner.get(path,params={'cursor':first['cursor'],'limit':1}).json()
    assert next_page==owner.get(path,params={'cursor':first['cursor'],'limit':1}).json()
    assert next_page['target_observation_id']==first['target_observation_id']
    final=owner.get(path,params={'cursor':next_page['cursor'],'limit':1}).json()
    assert not final['has_more']
    incremental=owner.get(path,params={'cursor':final['cursor']}).json()
    assert {row['item_id']:row['operation'] for row in incremental['changes']}=={1:'delete',2:'upsert',3:'upsert',4:'upsert'}
    assert incremental['synthetic']
    assert owner.get(path,params={'cursor':incremental['cursor']}).json()['changes']==[]


def test_cursor_tampering_market_binding_and_configuration(owner,database,monkeypatch):
    market=setup(database)
    cursor=owner.get(f'/api/v1/sync/markets/{market}').json()['cursor']
    assert owner.get(f'/api/v1/sync/markets/{market}',params={'cursor':cursor+'x'}).status_code==409
    with database.begin() as db:
        other=Market(region='eu',ruleset_id=1,house_id=113,source_kind='auctions',label='Other')
        db.add(other)
        db.flush()
        other_id=other.id
    assert owner.get(f'/api/v1/sync/markets/{other_id}',params={'cursor':cursor}).status_code==409
    monkeypatch.delenv('SYNC_CURSOR_SECRET')
    assert owner.get(f'/api/v1/sync/markets/{market}').status_code==503


def test_device_auth_revocation_and_private_sync(owner,database):
    market=setup(database)
    device=owner.post('/api/v1/devices',json={'name':'Synthetic desktop'}).json()
    bearer={'authorization':f"Bearer {device['token']}"}
    assert owner.get(f'/api/v1/sync/markets/{market}',headers=bearer).status_code==200
    owner.delete(f"/api/v1/devices/{device['id']}")
    assert owner.get(f'/api/v1/sync/markets/{market}',headers=bearer).status_code==401
    owner.post('/api/v1/auth/logout')
    assert owner.get(f'/api/v1/sync/markets/{market}').status_code==401


def test_empty_market_and_empty_current_snapshot(owner,database):
    market=setup(database,count=0)
    path=f'/api/v1/sync/markets/{market}'
    initial=owner.get(path).json()
    assert initial['changes']==[] and not initial['has_more']
    with database.begin() as db:
        insert(db,market,[1],'add')
    added=owner.get(path,params={'cursor':initial['cursor']}).json()
    assert added['changes'][0]['operation']=='upsert'
    with database.begin() as db:
        insert(db,market,[],'remove')
    removed=owner.get(path,params={'cursor':added['cursor']}).json()
    assert removed['changes']==[{'operation':'delete','item_id':1,'variant_key':added['changes'][0]['variant_key'],'value':None}]


def test_late_history_import_does_not_rewind_current_supply(owner,database):
    market=setup(database,count=1)
    path=f'/api/v1/sync/markets/{market}'
    initial=owner.get(path).json()
    with database.begin() as db:
        insert(db,market,[1],'late-history',price=300,when=now()-timedelta(days=5))
    updated=owner.get(path,params={'cursor':initial['cursor']}).json()
    value=updated['changes'][0]['value']
    assert value['recent_price']=='100'
    assert value['market_value']=='200'
    assert value['supply']==1


def test_incremental_sync_survives_raw_listing_pruning(owner,database):
    from market.maintenance import maintain
    market=setup(database,count=2,when=now()-timedelta(days=5))
    path=f'/api/v1/sync/markets/{market}'
    initial=owner.get(path).json()
    with database.begin() as db:
        insert(db,market,[2,3],'after-raw-prune',price=200)
    maintain(database,apply=True,compact=True)
    updated=owner.get(path,params={'cursor':initial['cursor']}).json()
    assert {row['item_id']:row['operation'] for row in updated['changes']}=={1:'delete',2:'upsert',3:'upsert'}


def test_compacted_non_daily_cursor_requires_full_reset(owner,database):
    from market.maintenance import maintain
    from market.models import Market
    at=now().replace(hour=12,minute=0,second=0,microsecond=0)-timedelta(days=500)
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Compacted cursor fixture')
        db.add(market);db.flush();market_id=market.id
        insert(db,market_id,[1],'compacted-first',when=at)
    path=f'/api/v1/sync/markets/{market_id}'
    initial=owner.get(path).json()
    with database.begin() as db:
        insert(db,market_id,[1],'compacted-daily',when=at+timedelta(hours=1),price=200)
        insert(db,market_id,[],'compacted-current')
    maintain(database,apply=True,compact=True)
    assert owner.get(path,params={'cursor':initial['cursor']}).status_code==409
    assert owner.get(path).json()['changes']==[]


def test_pinned_watermark_releases_ingest_lock_before_page_reads(owner,database,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from sqlalchemy import select,func,text
    from market.models import Observation
    import market.sync_generation as generation
    market=setup(database,count=3)
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL competing ingest lock regression')
        original=db.scalar(select(func.max(Observation.id)))
    entered,release=Event(),Event();real_signature=generation.signature
    def reading_page(*args,**kwargs):
        if not entered.is_set():
            entered.set()
            assert release.wait(10),'Competing ingest did not complete'
        return real_signature(*args,**kwargs)
    monkeypatch.setattr(generation,'signature',reading_page)
    path=f'/api/v1/sync/markets/{market}'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(owner.get,path+'?limit=1')
        try:
            assert entered.wait(10),'Sync did not reach pinned page reads'
            with database.begin() as writer:
                assert writer.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')), 'Page reads still own collector lock'
                insert(writer,market,[2,3,4],'during-download',price=200)
        finally:release.set()
        first=future.result(timeout=15)
    assert first.status_code==200,first.text
    first=first.json();assert first['target_observation_id']==str(original)
    page=first;download=list(first['changes'])
    while page['has_more']:
        page=owner.get(path,params={'cursor':page['cursor'],'limit':1}).json()
        assert page['target_observation_id']==str(original)
        download.extend(page['changes'])
    assert [row['item_id'] for row in download]==[1,2,3]
    assert all(row['value']['recent_price']=='100' for row in download)
    newer=owner.get(path,params={'cursor':page['cursor']}).json()
    assert int(newer['target_observation_id'])>original
    assert {r['item_id']:r['operation'] for r in newer['changes']}=={1:'delete',2:'upsert',3:'upsert',4:'upsert'}
    assert all(r['value']['recent_price']=='200' for r in newer['changes'] if r['operation']=='upsert')
