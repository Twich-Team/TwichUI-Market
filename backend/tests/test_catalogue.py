import json
from datetime import timedelta
from sqlalchemy import event,select
from market.db import now
from market.ingest import ingest
from market.metadata import store_metadata
from market.models import Listing,Market
from market.pricing import values


def seed(database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Catalogue fixture')
        db.add(market);db.flush();ident=market.id
        store_metadata(db,'us',25,b'{"id":25,"name":"Fixture Sword"}',synthetic=True)
        for day in [2,1,0]:
            payload={'auctions':[{'id':1,'item':{'id':25,'bonus_lists':[1]},'quantity':2,'buyout':400},
                                 {'id':2,'item':{'id':25,'bonus_lists':[2]},'quantity':3,'buyout':1500},
                                 {'id':3,'item':{'id':26},'quantity':1,'bid':50},
                                 {'id':4,'item':{'id':27},'quantity':1,'buyout':9007199254740993}]}
            ingest(db,ident,json.dumps(payload).encode(),request_key=f'catalogue-{day}',retrieved_at=now()-timedelta(days=day),synthetic=True)
        return ident


def test_catalogue_groups_variants_without_blending_price_and_pages_stably(owner,database):
    ident=seed(database)
    response=owner.get(f'/api/v1/markets/{ident}/catalogue?page_size=1').json()
    assert response['total_items']==3 and len(response['items'])==1
    item=response['items'][0]
    assert item['variant_count']==2 and item['supply']==5 and item['listing_count']==2
    assert item['price_ranges']['recent_price']=={'minimum':'200','maximum':'500'}
    assert item['price_ranges']['market_value']=={'minimum':'200','maximum':'500'}
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?page=1&page_size=1').json()['items'][0]['item_id']==26
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?sort=recent_price&direction=desc').json()['items'][0]['price_ranges']['recent_price']['minimum']=='9007199254740993'
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?sort=recent_price').json()['items'][-1]['item_id']==26
    assert response['synthetic'] and item['synthetic']


def test_variant_references_match_existing_pricing_and_region_search(owner,database):
    ident=seed(database)
    result=owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants?page_size=1').json()
    assert result['total_variants']==2 and len(result['variants'])==1
    variant=result['variants'][0]
    with database() as db:
        reference=values(db,ident,25,variant['variant_key'])
    assert variant['recent_price']==str(reference['recent_price'])
    assert variant['market_value']==str(reference['market_value'])
    assert variant['historical_value']==str(reference['historical_value'])
    assert variant['coverage_days']==reference['market_coverage_days']
    assert variant['variant']['bonus_lists']
    assert len(owner.get(f'/api/v1/markets/{ident}/catalogue?q=SWORD').json()['items'])==1
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?q=%25').json()['items']==[]
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?q=99999999999999999999').json()['items']==[]
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?sort=arbitrary_sql').status_code==422
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?page_size=101').status_code==422


def test_catalogue_and_legacy_queries_do_not_scale_with_variant_count(owner,database):
    ident=seed(database)
    statements=[]
    engine=database.kw['bind']
    def count(*_):statements.append(1)
    event.listen(engine,'before_cursor_execute',count)
    try:
        assert owner.get(f'/api/v1/markets/{ident}/catalogue').status_code==200
        assert len(statements)<=8 # Includes authenticated credential/user lookups.
        statements.clear()
        assert owner.get(f'/api/v1/markets/{ident}/items').status_code==200
        assert len(statements)<=7
    finally:event.remove(engine,'before_cursor_execute',count)


def test_private_catalogue_requires_authentication(client,database):
    ident=seed(database)
    assert client.get(f'/api/v1/markets/{ident}/catalogue').status_code==401
    assert client.get(f'/api/v1/markets/{ident}/catalogue/25/variants').status_code==401
