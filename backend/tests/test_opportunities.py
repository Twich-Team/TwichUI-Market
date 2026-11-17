import json
from datetime import timedelta
from sqlalchemy import select
from market.db import now
from market.ingest import ingest
from market.models import Market
from market.opportunities import evidence


def seed(database,*,disappear=False):
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic opportunities')
        db.add(market);db.flush()
        for day in [3,2,1,0]:
            rows=[] if disappear and day==0 else [{'id':1,'item':{'id':12363},'quantity':3 if day==0 else 10,'buyout':150 if day==0 else 1000}]
            ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key=f'signal-{day}',retrieved_at=now()-timedelta(days=day),synthetic=True)
        return market.id


def test_supply_and_price_changes_have_explainable_baselines_and_filters(owner,database):
    market=seed(database)
    price=owner.get(f'/api/v1/markets/{market}/signals?kind=price').json()
    assert price['synthetic'] and len(price['signals'])==1
    row=price['signals'][0]
    assert row['change_percent']==-50
    assert row['current_price']=='50' and row['reference_price']=='100'
    assert row['confidence']=='limited' and row['coverage_days']==3
    supply=owner.get(f'/api/v1/markets/{market}/signals?kind=supply').json()['signals'][0]
    assert supply['change_percent']==-70 and supply['current_supply']==3 and supply['reference_supply']==10
    assert owner.get(f'/api/v1/markets/{market}/signals?kind=supply&direction=increase').json()['signals']==[]
    assert owner.get(f'/api/v1/markets/{market}/signals?kind=supply&minimum_change=80').json()['signals']==[]
    assert owner.get(f'/api/v1/markets/{market}/signals?kind=price&minimum_confidence=moderate').json()['signals']==[]


def test_complete_supply_disappearance_is_not_inferred_as_sales(owner,database):
    market=seed(database,disappear=True)
    result=owner.get(f'/api/v1/markets/{market}/signals?kind=supply').json()
    assert result['signals'][0]['change_percent']==-100
    assert result['signals'][0]['current_supply']==0
    assert 'not completed sales' in result['signals'][0]['cautions'][0]
    archived=owner.get(f'/api/v1/markets/{market}/items?q=12363').json()
    assert archived['historical_results'] and archived['items'][0]['item_id']==12363
    variant=archived['items'][0]['variant_key']
    assert owner.get(f'/api/v1/markets/{market}/items/12363/{variant}').json()['valuation']['supply']==0


def test_deals_evaluate_listings_beyond_the_previous_candidate_cutoff(owner,database):
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Full scan fixture')
        db.add(market);db.flush();market_id=market.id
        for day in [3,2,1,0]:
            rows=[{'id':index+1,'item':{'id':1},'quantity':1,'buyout':1000} for index in range(1000)]
            rows.append({'id':1001,'item':{'id':12363},'quantity':1,'buyout':500 if day==0 else 1000})
            ingest(db,market_id,json.dumps({'auctions':rows}).encode(),request_key=f'full-scan-{day}',retrieved_at=now()-timedelta(days=day),synthetic=True)
    result=owner.get(f'/api/v1/markets/{market_id}/deals').json()
    assert len(result['deals'])==1 and result['deals'][0]['item_id']==12363
    assert not result['candidates_truncated']
    with database.begin() as db:
        for row in rows: row['buyout']=500
        ingest(db,market_id,json.dumps({'auctions':rows}).encode(),request_key='many-matches',synthetic=True)
    limited=owner.get(f'/api/v1/markets/{market_id}/deals').json()
    assert len(limited['deals'])==100 and limited['candidates_truncated']


def test_confidence_measures_source_evidence_not_resale_probability():
    assert evidence(10,'current',True,False)=='strong'
    assert evidence(3,'current',True,False)=='moderate'
    assert evidence(10,'unknown',True,False)=='limited'
    assert evidence(10,'current',False,False)=='limited'
    assert evidence(10,'current',True,True)=='limited'


def test_zero_copper_reference_and_future_source_timestamp_fail_conservatively(owner,database):
    from email.utils import format_datetime
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Zero reference fixture',
            last_modified=format_datetime(now()+timedelta(days=1),usegmt=True))
        db.add(market);db.flush();market_id=market.id
        for day in [3,2,1,0]:
            ingest(db,market_id,b'{"auctions":[{"id":1,"item":{"id":12363},"quantity":20,"buyout":1}]}',
                request_key=f'zero-{day}',retrieved_at=now()-timedelta(days=day),modified=market.last_modified,synthetic=True)
    assert owner.get(f'/api/v1/markets/{market_id}/deals').json()['deals']==[]
    assert owner.get(f'/api/v1/markets/{market_id}/signals?kind=price').json()['signals']==[]
    assert owner.get('/api/v1/markets').json()['markets'][0]['freshness']=='unknown'


def test_opportunity_icons_are_delivered_without_tooltip_requests(owner, database):
    from market.models import ItemMedia
    market = seed(database)
    with database.begin() as db:
        db.add(ItemMedia(region='eu', item_id=12363, status='available', asset_hash='a'*64,
                         data=b'synthetic-only', byte_count=14, content_type='image/png'))
        # The same ID from a different edition/region must never replace its local URL.
        db.add(ItemMedia(region='us', item_id=12363, status='available', asset_hash='b'*64))
    for path, key in [('deals','deals'),('signals?kind=price','signals'),('signals?kind=supply','signals')]:
        data = owner.get(f'/api/v1/markets/{market}/{path}').json()
        assert data[key][0]['icon_url'] == '/api/v1/items/eu/12363/icon?v='+'a'*64
    with database.begin() as db:
        db.get(ItemMedia, ('eu',12363)).asset_hash = None
    assert owner.get(f'/api/v1/markets/{market}/deals').json()['deals'][0]['icon_url'] is None
