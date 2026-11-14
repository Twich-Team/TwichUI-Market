import base64,hashlib,json
from datetime import timedelta
from sqlalchemy import select
import pytest
from market.db import now
from market.ingest import ingest
from market.item_attributes import attributes
from market.item_media import image_type,icon_url,resolve_media_once
from market.metadata import store_metadata
from market.models import ItemMedia,ItemMetadata,Market
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQpUAAAAASUVORK5CYII=')


def setup(database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Profile fixture',enabled=True,verified=True)
        db.add(market);db.flush()
        ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":25},"quantity":1,"buyout":100}]}',request_key='profiles',synthetic=True)
        return market.id


class Client:
    def __init__(self,status=200,url='https://render.worldofwarcraft.com/forever-us/icons/56/135274.jpg'):
        self.status,self.url=status,url;self.calls=0
    def fetch_item_media(self,region,item):
        self.calls+=1
        return {'status':self.status,'headers':{'Battlenet-Namespace':'static-1.60.1_70399-forever-us'}},json.dumps({'id':item,'assets':[{'key':'icon','value':self.url}]}).encode()


def test_rich_blizzard_attributes_remain_base_item_and_region_scoped(owner,database):
    ident=setup(database)
    payload={'id':25,'name':'Fixture Sword','quality':{'type':'RARE'},'level':20,'sell_price':123,
             'preview_item':{'item':{'id':25},'weapon':{'damage':{'display_string':'10 - 20 Damage'}},'stats':[{'display':{'display_string':'+4 Strength'}}]}}
    with database.begin() as db:store_metadata(db,'us',25,json.dumps(payload).encode(),synthetic=True,resolved_namespace='static-1.60.1_70399-forever-us')
    profile=owner.get(f'/api/v1/markets/{ident}/item-profiles/25').json()
    assert profile['quality']=='RARE' and profile['attributes']['scope']=='base_item'
    assert profile['attributes']['vendor_sell']=='123' and len(profile['attributes']['lines'])==2
    assert profile['source']['confidence']=='synthetic'
    assert profile['source']['namespace']=='static-1.60.1_70399-forever-us'
    assert 'not inferred' in profile['variant_notice']
    assert owner.get('/api/v1/items/eu/25/icon').status_code==404


def test_media_cache_independent_of_name_and_has_private_etag(owner,database):
    ident=setup(database);at=now();client=Client()
    assert resolve_media_once(database,client,at=at,image_fetch=lambda _: (PNG,'image/png'))
    assert not resolve_media_once(database,client,at=at+timedelta(minutes=1),image_fetch=lambda _:None)
    response=owner.get('/api/v1/items/us/25/icon')
    assert response.status_code==200 and response.content==PNG
    assert response.headers['content-type']=='image/png'
    assert response.headers['cache-control'].startswith('private')
    assert owner.get('/api/v1/items/us/25/icon',headers={'If-None-Match':response.headers['etag']}).status_code==304
    assert owner.get(f'/api/v1/markets/{ident}/item-profiles/25').json()['metadata_status']=='unresolved'
    with database() as db:assert db.get(ItemMedia,('us',25)).namespace=='static-1.60.1_70399-forever-us'


@pytest.mark.parametrize('url',['http://render.worldofwarcraft.com/us/icons/56/a.jpg','https://render.worldofwarcraft.com.evil.test/us/icons/56/a.jpg','https://user:secret@render.worldofwarcraft.com/us/icons/56/a.jpg','https://127.0.0.1/icon.jpg','https://render.worldofwarcraft.com/us/icons/56/a.svg','https://render.worldofwarcraft.com:8443/us/icons/56/a.jpg','https://render.worldofwarcraft.com/us/icons/56/a.jpg?token=secret'])
def test_untrusted_images_never_fetch(database,url):
    setup(database);called=[]
    assert resolve_media_once(database,Client(url=url),image_fetch=lambda value:called.append(value))
    assert called==[]
    with database() as db:assert db.get(ItemMedia,('us',25)).status=='error'


def test_missing_media_is_negative_cached_and_wrong_edition_rejected(database):
    setup(database);at=now();client=Client(404)
    assert resolve_media_once(database,client,at=at)
    assert not resolve_media_once(database,client,at=at+timedelta(days=1))
    assert client.calls==1
    with database.begin() as db:
        with pytest.raises(ValueError):store_metadata(db,'us',25,b'{"id":25,"name":"Wrong edition"}',resolved_namespace='static-retail-us')
    with pytest.raises(ValueError):image_type(b'<svg onload="bad"></svg>')
    with pytest.raises(ValueError):attributes({'id':25,'preview_item':{'item':{'id':26}}})


def test_metadata_priority_only_queues_observed_items_with_csrf(owner,database):
    ident=setup(database)
    assert owner.post(f'/api/v1/markets/{ident}/item-metadata-requests',json={'item_ids':[25,9999]}).json()=={'queued':1}
    with database() as db:
        assert db.get(ItemMetadata,('us',25)).requested_at is not None
        assert db.get(ItemMetadata,('us',9999)) is None
    owner.headers.pop('x-csrf-token')
    assert owner.post(f'/api/v1/markets/{ident}/item-metadata-requests',json={'item_ids':[25]}).status_code==403
