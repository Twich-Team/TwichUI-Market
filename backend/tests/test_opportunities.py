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


def test_reported_scale_is_reproducible_and_neutral_even_with_strong_source_evidence(owner, database):
    from email.utils import format_datetime
    stamp = now()
    with database.begin() as db:
        market = Market(region='eu', ruleset_id=2, house_id=113, source_kind='auctions',
                        verified=True, label='Local arithmetic reconstruction')
        db.add(market)
        db.flush()
        # First two values are from the reported history. Remaining daily asks
        # are invented for this test; they are not a reconstruction of raw listings.
        prices = [1836361542, 775738042, 501, 501, 501, 402, 3]
        for index, unit in enumerate(prices):
            when = stamp - timedelta(days=6-index)
            rows = [{'id': aid, 'quantity': size, 'item': {'id': 117}, 'buyout': unit*size}
                    for aid, size in [(1, 2), (2, 3)]]
            ingest(db, market.id, json.dumps({'auctions': rows}).encode(), request_key=f'jerky-{index}',
                   retrieved_at=when, modified=format_datetime(when, usegmt=True))
        market_id = market.id
        market.last_modified = format_datetime(stamp, usegmt=True)
    path = f'/api/v1/markets/{market_id}'
    data = owner.get(path+'/deals?grouped=true&minimum_confidence=strong').json()
    assert data['market']['freshness'] == 'current'
    assert len(data['deals']) == 1
    deal = data['deals'][0]
    assert deal['market_value'] == '373157356' and deal['confidence'] == 'strong'
    assert deal['coverage_days'] == 7 and deal['matching_listings'] == 2 and deal['current_supply'] == 5
    assert deal['reference_quality']['state'] == 'needs_review' and '%' not in deal['reason']
    assert deal['discount_percent'] < 100
    rows = owner.get(path + '/deals', params={'item_id':117, 'variant_key':deal['variant_key'], 'limit':1, 'offset':1}).json()
    assert rows['deals'][0]['quantity'] == 3 and rows['deals'][0]['total_buyout'] == '9'
    item = owner.get(f"{path}/items/117/{deal['variant_key']}").json()['valuation']
    assert item['reference_quality'] == deal['reference_quality']
    assert [int(day['recent_price']) for day in item['history']] == prices
    signal = owner.get(path+'/signals?kind=price').json()['signals'][0]
    assert signal['reference_quality']['state'] == 'needs_review' and signal['change_percent'] > -100
    assert owner.get(path+'/signals?kind=supply').json()['signals'] == []


def test_group_paging_keeps_variants_and_matching_stacks_separate(owner, database):
    with database.begin() as db:
        market = Market(region='eu', ruleset_id=2, house_id=113, source_kind='auctions', label='Grouped stacks')
        db.add(market)
        db.flush()
        for day in [3, 2, 1, 0]:
            rows = [
                {'id': i+1, 'item': {'id': 117, 'bonus_lists': [i//2]}, 'quantity': 3,
                 'buyout': (10+i if not day else 600)} for i in range(6)
            ]
            rows.append({'id':7, 'item': {'id':117, 'bonus_lists':[0]}, 'quantity':24, 'buyout':24000})
            ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key=f'group-{day}',
                   retrieved_at=now()-timedelta(days=day),synthetic=True)
        path = f'/api/v1/markets/{market.id}'
    params = {'grouped':'true', 'limit':2, 'maximum_spend':20}
    first = owner.get(path+'/deals', params=params).json()
    second = owner.get(path+'/deals', params={**params,'offset':2}).json()
    assert first['candidates_truncated'] and not second['candidates_truncated']
    groups = first['deals'] + second['deals']
    assert len({row['variant_key'] for row in groups}) == 3
    group = next(row for row in groups if row['variant']['bonus_lists'] == [0])
    assert group['matching_listings'] == 2 and group['current_supply'] == 30
    assert group['total_buyout'] == '10' and group['quantity'] == 3
    drill = {'item_id':117, 'variant_key':group['variant_key'], 'maximum_spend':20, 'limit':1}
    assert owner.get(path+'/deals', params={**drill,'offset':1}).json()['deals'][0]['total_buyout'] == '11'
    assert owner.get(path+'/deals', params={**drill,'expected_snapshot':999999}).status_code == 409
    assert owner.get(path+'/deals?item_id=117').status_code == 422
    first = owner.get(path+'/signals?kind=price&limit=1').json()
    second = owner.get(path+'/signals?kind=price&limit=1&offset=1').json()
    assert first['candidates_truncated'] and first['signals'][0]['variant_key'] != second['signals'][0]['variant_key']


def test_reference_checks_use_only_days_in_the_same_window():
    from market.reference_quality import qualify_valuation, reference_quality
    prices = [100000, 30, 30, 30]
    valuation = {'history':[{'recent_price':v} for v in prices], 'market_coverage_days':3, 'coverage_days':4,
                 'recent_price':30,'market_value':30,'historical_value':25023}
    qualify_valuation(valuation)
    assert valuation['reference_quality']['state'] == 'available'
    assert valuation['historical_reference_quality']['state'] == 'needs_review'
    assert reference_quality(100,10,90,110,8)['state'] == 'needs_review'
    assert reference_quality(100,90,90,110,2)['state'] == 'limited'
    assert reference_quality(None,None,None,None,0)['state'] == 'unavailable'


def test_single_cheap_stack_does_not_disqualify_a_consistent_unit_reference(owner, database):
    with database.begin() as db:
        market = Market(region='us', ruleset_id=2, house_id=114, source_kind='auctions', label='Stable reference')
        db.add(market)
        db.flush()
        for day in [3, 2, 1, 0]:
            rows = [{'id':1, 'item':{'id':117}, 'quantity':100, 'buyout':100_000_000}]
            if day == 0:
                rows.append({'id':2, 'item':{'id':117}, 'quantity':1, 'buyout':1})
            ingest(db, market.id, json.dumps({'auctions': rows}).encode(), request_key=f'stable-{day}',
                   retrieved_at=now()-timedelta(days=day), synthetic=True)
        path = f'/api/v1/markets/{market.id}/deals?grouped=true'
    deal = owner.get(path).json()['deals'][0]
    assert deal['total_buyout'] == '1' and deal['reference_quality']['state'] == 'available'
    assert deal['discount_percent'] == 99.99 and '100%' not in deal['reason']
