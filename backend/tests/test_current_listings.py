import json
from sqlalchemy import select
from market.ingest import ingest
from market.models import Market,SnapshotStatistic

def test_exact_unit_sort_all_listings_pagination_and_bid_only(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Synthetic listing fixture')
        db.add(market);db.flush()
        rows=[{'id':i,'item':{'id':25},'quantity':3,'buyout':100} for i in range(1,251)]
        rows.extend([{'id':251,'item':{'id':25},'quantity':1,'buyout':34},{'id':252,'item':{'id':25},'quantity':1,'bid':20}])
        obs=ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key='listings',synthetic=True)
        variant=db.scalar(select(SnapshotStatistic.variant_key));ident=market.id;snapshot=str(obs.snapshot_id)
    path=f'/api/v1/markets/{ident}/items/25/{variant}/listings'
    result=owner.get(path+'?page_size=100').json()
    assert result['total']==252 and len(result['listings'])==100
    assert result['listings'][0]['buyout']=='100' and result['listings'][0]['unit_price'] is None
    result=owner.get(path+'?page=2&page_size=100').json()
    assert len(result['listings'])==52 and result['listings'][-1]['buyout'] is None
    assert result['listings'][-2]['buyout']=='34'
    desc=owner.get(path+'?sort=unit&direction=desc').json()
    assert desc['listings'][0]['auction_id']=='251'
    assert owner.get(path+'?expected_snapshot='+snapshot).status_code==200
    assert owner.get(path+'?expected_snapshot=9999').status_code==409
    assert owner.get(path+'?page_size=101').status_code==422

def test_commodity_unit_values_remain_precision_safe(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=113,source_kind='commodities',label='Synthetic commodity fixture')
        db.add(market);db.flush()
        ingest(db,market.id,b'{"auctions":[{"id":9007199254740993,"item":{"id":25},"quantity":2,"unit_price":9007199254740993}]}',request_key='commodity',synthetic=True)
        variant=db.scalar(select(SnapshotStatistic.variant_key));ident=market.id
    result=owner.get(f'/api/v1/markets/{ident}/items/25/{variant}/listings').json()
    row=result['listings'][0]
    assert row['unit_price']=='9007199254740993' and row['auction_id']=='9007199254740993'
    assert row['buyout'] is None and row['quantity']==2


def test_unit_sort_distinguishes_extremely_close_rational_prices(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Synthetic rational fixture')
        db.add(market);db.flush()
        rows=[{'id':i,'item':{'id':25},'quantity':q,'buyout':4_000_000_000*q+1} for i,q in [(1,2147483646),(2,2147483647)]]
        ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key='close-rationals',synthetic=True)
        variant=db.scalar(select(SnapshotStatistic.variant_key));ident=market.id
    rows=owner.get(f'/api/v1/markets/{ident}/items/25/{variant}/listings?sort=unit').json()['listings']
    assert [row['auction_id'] for row in rows]==['2','1']
