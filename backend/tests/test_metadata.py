import json
from datetime import timedelta
import pytest
from sqlalchemy import select
from market.db import now
from market.ingest import ingest
from market.metadata import resolve_once,store_metadata
from market.models import ItemMetadata,Market
from market.security import aware


def setup(database):
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic metadata',verified=True,enabled=True)
        db.add(market);db.flush()
        ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":12363},"quantity":1,"buyout":100}]}',request_key='metadata',synthetic=True)
        return market.id


class Client:
    def __init__(self,status=200): self.calls=0;self.status=status
    def fetch_item(self,region,item):
        self.calls+=1
        assert region=='eu' and item==12363
        return {'status':self.status,'headers':{},'synthetic':True},json.dumps({'id':item,'name':{'en_US':'Synthetic Arcane Crystal'}}).encode()


def test_name_resolution_provenance_and_refresh_cache(database):
    setup(database)
    at=now();client=Client()
    assert resolve_once(database,client,at=at)
    assert not resolve_once(database,client,at=at+timedelta(minutes=1))
    assert client.calls==1
    with database() as db:
        row=db.get(ItemMetadata,('eu',12363))
        assert row.name=='Synthetic Arcane Crystal'
        assert row.namespace=='static-forever-eu'
        assert row.payload_hash and row.synthetic
        assert aware(row.resolved_at)==at


def test_missing_names_negative_cache_and_unverified_markets(database):
    market=setup(database)
    at=now();client=Client(404)
    assert resolve_once(database,client,at=at)
    assert not resolve_once(database,client,at=at+timedelta(days=1))
    with database.begin() as db:
        row=db.get(ItemMetadata,('eu',12363))
        assert row.name is None and row.status=='missing'
        assert aware(row.retry_after)==at+timedelta(days=7)
        db.get(Market,market).verified=False
    assert not resolve_once(database,client,at=at+timedelta(days=8))
    assert client.calls==1


def test_case_insensitive_search_and_region_isolation(owner,database):
    market=setup(database)
    with database.begin() as db:
        store_metadata(db,'eu',12363,b'{"id":12363,"name":"Synthetic Arcane Crystal"}',synthetic=True)
        store_metadata(db,'us',12363,b'{"id":12363,"name":"Other Region Name"}',synthetic=True)
    result=owner.get(f'/api/v1/markets/{market}/items?q=ARCANE').json()
    assert result['items'][0]['name']=='Synthetic Arcane Crystal'
    assert result['items'][0]['name_verified'] is False
    assert result['items'][0]['metadata_synthetic']
    assert owner.get(f'/api/v1/markets/{market}/items',params={'q':'%'}).json()['items']==[]
    assert owner.get(f'/api/v1/markets/{market}/items?q=Other').json()['items']==[]


@pytest.mark.parametrize('body',[b'{"id":1,"name":"Wrong item"}',b'{"id":12363,"name":""}',b'{"id":12363,"name":12}',b'[]'])
def test_malformed_metadata_cannot_be_saved(database,body):
    with database() as db:
        with pytest.raises(ValueError): store_metadata(db,'eu',12363,body,synthetic=True)
        db.rollback()
        assert db.scalar(select(ItemMetadata)) is None
