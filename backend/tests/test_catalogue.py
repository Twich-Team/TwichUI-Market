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
    assert item['sole_variant_key'] is None
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
        assert len(statements)<=9 # Includes auth and the PostgreSQL request-local deadline.
        statements.clear()
        assert owner.get(f'/api/v1/markets/{ident}/items').status_code==200
        assert len(statements)<=7
    finally:event.remove(engine,'before_cursor_execute',count)


def test_name_search_on_a_new_snapshot_with_stale_planner_statistics(database):
    """Production's unseen snapshot was estimated as one row, repeating the search.

    Exercise the real PostgreSQL planner under a short statement deadline rather
    than requiring an operator ANALYZE after every collected snapshot.
    """
    import pytest
    from sqlalchemy import text
    from market.catalogue import catalogue
    from market.models import ItemMetadata
    if database.kw['bind'].dialect.name!='postgresql':pytest.skip('PostgreSQL planner regression')
    count=6000
    payload=json.dumps({'auctions':[{'id':i+1,'item':{'id':50000+i},'quantity':2,'buyout':200} for i in range(count)]}).encode()
    with database.begin() as db:
        db.execute(text('ALTER TABLE snapshot_statistics SET (autovacuum_enabled=false)'))
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Synthetic stale planner regression')
        db.add(market);db.flush();ident=market.id
        db.add_all([ItemMetadata(region='us',item_id=50000+i,name=f'{"Needle" if i%60==0 else "Haystack"} fixture {i}',namespace='synthetic',synthetic=True) for i in range(count)])
        ingest(db,ident,payload,request_key='old-statistics',retrieved_at=now()-timedelta(days=1),synthetic=True)
        db.execute(text('ANALYZE snapshot_statistics, item_metadata'))
        # A changed book creates a snapshot absent from the sampled distribution.
        changed=json.loads(payload);changed['auctions'][0]['buyout']=400
        ingest(db,ident,json.dumps(changed).encode(),request_key='unseen-snapshot',synthetic=True)
    with database() as db:
        db.execute(text("SET LOCAL statement_timeout='2s'"))
        page=catalogue(ident,q='needle',sort='item_id',direction='asc',page=1,page_size=25,user=None,db=db)
        assert page['total_items']==100
        assert [r['item_id'] for r in page['items']]==list(range(51500,53000,60))
        assert page['items'][0]['price_ranges']['market_value']=={'minimum':'100','maximum':'100'}
        # A saved name-sort preference must also load the complete unfiltered
        # catalogue without joining every current variant to every matching ID.
        page=catalogue(ident,q='',sort='name',direction='asc',page=0,page_size=25,user=None,db=db)
        expected=sorted(range(count),key=lambda i:f'{"Needle" if i%60==0 else "Haystack"} fixture {i}'.lower())[:25]
        assert page['total_items']==count
        assert [r['item_id'] for r in page['items']]==[50000+i for i in expected]
        page=catalogue(ident,q='haystack',sort='name',direction='asc',page=0,page_size=25,user=None,db=db)
        assert page['total_items']==5900
        assert [r['item_id'] for r in page['items']]==[50000+i for i in expected]
        page=catalogue(ident,q='',sort='market_value',direction='desc',page=0,page_size=25,user=None,db=db)
        assert page['items'][0]['item_id']==50000
        assert page['items'][0]['price_ranges']['market_value']=={'minimum':'150','maximum':'150'}


def test_catalogue_ranges_exclude_vanished_variants_and_items(owner,database):
    ident=seed(database)
    with database.begin() as db:
        ingest(db,ident,json.dumps({'auctions':[
            {'id':2,'item':{'id':25,'bonus_lists':[2]},'quantity':3,'buyout':2100},
            {'id':3,'item':{'id':26},'quantity':1,'bid':50}
        ]}).encode(),request_key='only-one-current-variant',retrieved_at=now()+timedelta(seconds=1),synthetic=True)
    result=owner.get(f'/api/v1/markets/{ident}/catalogue?q=sword').json()
    assert result['total_items']==1
    item=result['items'][0]
    assert item['variant_count']==1 and item['supply']==3 and item['listing_count']==1
    assert item['price_ranges']['recent_price']=={'minimum':'700','maximum':'700'}
    # Reference pricing is independently computed by the existing pricing API.
    with database() as db:
        expected=values(db,ident,25,item['sole_variant_key'])
    for field in ('market_value','historical_value'):
        assert item['price_ranges'][field]=={'minimum':str(expected[field]),'maximum':str(expected[field])}
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?q=27').json()['items']==[]
    assert [row['item_id'] for row in owner.get(f'/api/v1/markets/{ident}/catalogue').json()['items']]==[25,26]


def test_database_search_timeout_returns_an_actionable_error(owner,database,monkeypatch):
    import pytest
    from sqlalchemy import text
    import market.catalogue as module
    if database.kw['bind'].dialect.name!='postgresql':pytest.skip('PostgreSQL timeout handling')
    ident=seed(database);original=module.context
    def slow(db,*args,**kwargs):
        result=original(db,*args,**kwargs)
        db.execute(text("SET LOCAL statement_timeout='1ms'"))
        db.execute(text('SELECT pg_sleep(0.05)'))
        return result
    monkeypatch.setattr(module,'context',slow)
    response=owner.get(f'/api/v1/markets/{ident}/catalogue?q=sword')
    assert response.status_code==503
    assert 'Try an item ID or a narrower search' in response.json()['detail']
    monkeypatch.setattr(module,'context',original)
    assert owner.get(f'/api/v1/markets/{ident}/catalogue?q=sword').status_code==200


def test_private_catalogue_requires_authentication(client,database):
    ident=seed(database)
    assert client.get(f'/api/v1/markets/{ident}/catalogue').status_code==401
    assert client.get(f'/api/v1/markets/{ident}/catalogue/25/variants').status_code==401


def test_rolling_history_overlays_match_original_point_in_time_reference(owner,database):
    from market.pricing import daily_history
    from datetime import datetime
    ident=seed(database)
    key=owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants').json()['variants'][0]['variant_key']
    with database() as db:
        history=daily_history(db,ident,25,key,days=365)
        for point in history['points']:
            expected=values(db,ident,25,key,at=datetime.fromisoformat(point['observed_at']))
            assert point['market_value']==expected['market_value']
            assert point['historical_value']==expected['historical_value']


def test_distribution_uses_every_listing_including_rows_beyond_display_limit(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Distribution fixture')
        db.add(market);db.flush();ident=market.id
        auctions=[{'id':i+1,'item':{'id':25},'quantity':2,'buyout':1000+i} for i in range(250)]
        auctions.append({'id':999,'item':{'id':25},'quantity':3,'bid':10})
        observation=ingest(db,ident,json.dumps({'auctions':auctions}).encode(),request_key='distribution',synthetic=True)
        key=db.scalar(select(Listing.variant_key).where(Listing.snapshot_id==observation.snapshot_id).limit(1))
    result=owner.get(f'/api/v1/markets/{ident}/distribution/25/{key}').json()
    assert result['priced_supply']==500 and result['unpriced_supply']==3 and result['priced_listing_count']==250 and result['listing_count']==251
    assert sum(b['supply'] for b in result['bands'])==500
    assert len(result['bands'])<=12 and result['synthetic']


def test_variant_expansion_rejects_a_changed_snapshot(owner,database):
    ident=seed(database)
    snapshot=owner.get(f'/api/v1/markets/{ident}/catalogue').json()['snapshot_id']
    assert owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants?expected_snapshot={snapshot}').status_code==200
    assert owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants?expected_snapshot=stale').status_code==409


def test_compact_chart_history_preserves_exact_prices_and_provenance_flags(owner,database):
    ident=seed(database)
    variant=owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants').json()['variants'][0]['variant_key']
    path=f'/api/v1/markets/{ident}/items/25/{variant}/history'
    full=owner.get(path).json();chart=owner.get(path+'?view=chart').json()
    assert chart['synthetic'] and len(chart['points'])==len(full['points'])
    for actual,expected in zip(chart['points'],full['points']):
        assert actual=={key:expected[key] for key in actual}
        assert isinstance(actual['recent_price'],str)
        assert actual['observed_at']==expected['observed_at']
        assert 'payload_hash' not in actual and actual['reference_synthetic']
    assert owner.get(path+'?view=unknown').status_code==422


def test_catalogue_supplies_only_verified_sole_current_variant(owner,database):
    ident=seed(database)
    rows=owner.get(f'/api/v1/markets/{ident}/catalogue').json()['items']
    for row in rows:
        variants=owner.get(f"/api/v1/markets/{ident}/catalogue/{row['item_id']}/variants").json()['variants']
        assert row['sole_variant_key']==(variants[0]['variant_key'] if len(variants)==1 else None)


def test_last_seen_is_variant_observation_not_latest_market_check(owner,database):
    from market.security import aware
    ident=seed(database)
    variant=owner.get(f'/api/v1/markets/{ident}/catalogue/25/variants').json()['variants'][0]['variant_key']
    before=owner.get(f'/api/v1/markets/{ident}/items/25/{variant}').json()
    with database.begin() as db:
        ingest(db,ident,b'{"auctions":[{"id":99,"item":{"id":26},"quantity":1,"buyout":50}]}',request_key='variant-gone',retrieved_at=now()+timedelta(minutes=1),synthetic=True)
    after=owner.get(f'/api/v1/markets/{ident}/items/25/{variant}').json()
    assert after['last_seen_at']==before['last_seen_at']
    unknown=owner.get(f'/api/v1/markets/{ident}/items/999999/{variant}').json()
    assert unknown['last_seen_at'] is None
