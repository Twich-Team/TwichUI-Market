import json
from datetime import timedelta
from sqlalchemy import select
from market.db import now
from market.ingest import ingest
from market.models import Listing, Market


def seed(database):
    with database.begin() as db:
        market = Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic market')
        db.add(market)
        db.flush()
        for days,price in [(3,1000),(2,1000),(1,1000),(0,200)]:
            data = json.dumps({'auctions':[{'id':2**53+1,'item':{'id':12363},'quantity':10,'buyout':price}]}).encode()
            observation = ingest(db,market.id,data,request_key=str(days),retrieved_at=now()-timedelta(days=days),synthetic=True)
        variant = db.scalar(select(Listing.variant_key).where(Listing.snapshot_id==observation.snapshot_id))
        return market.id,variant


def test_authenticated_research_contract(owner,database):
    market,variant = seed(database)
    rows = owner.get('/api/v1/markets').json()['markets']
    assert rows[0]['freshness'] == 'unknown'
    assert rows[0]['source_age_seconds'] is None
    result = owner.get(f'/api/v1/markets/{market}/items?q=12363').json()
    assert result['items'][0]['name_verified'] is False
    assert result['synthetic']
    result = owner.get(f'/api/v1/markets/{market}/items/12363/{variant}').json()
    assert result['valuation']['recent_price'] == '20'
    assert result['valuation']['market_value'] == '80'
    assert result['listings'][0]['auction_id'] == str(2**53+1)
    assert result['listings'][0]['buyout'] == '200'
    assert result['provenance'] == 'asking_listings_only'
    assert owner.get(f'/api/v1/markets/{market}/items?q=Arcane').json()['search_notice']
    assert owner.get(f'/api/v1/markets/{market}/items?q=999999999999999999999999').json()['items'] == []


def test_explainable_deals_and_filters(owner,database):
    market,variant = seed(database)
    path = f'/api/v1/markets/{market}/deals'
    result = owner.get(path).json()
    assert result['synthetic']
    assert len(result['deals']) == 1
    deal = result['deals'][0]
    assert deal['discount_percent'] == 75
    assert deal['coverage_days'] == 4
    assert deal['total_buyout'] == '200'
    assert deal['confidence'] == 'limited'
    assert 'provisional' in deal['reason']
    assert owner.get(path+'?maximum_spend=199').json()['deals'] == []
    assert owner.get(path+'?minimum_discount=80').json()['deals'] == []
    assert owner.get(path+'?minimum_coverage=5').json()['deals'] == []


def test_market_creation_guards_and_monitoring(owner):
    body = {'region':'eu','ruleset_id':2,'house_id':113,'source_kind':'auctions','label':'EU Alliance'}
    response = owner.post('/api/v1/admin/markets',json=body)
    assert response.status_code == 201
    market = response.json()
    assert not market['verified'] and not market['enabled']
    assert owner.post('/api/v1/admin/markets',json=body).status_code == 409
    path = f"/api/v1/admin/markets/{market['id']}/schedule"
    assert owner.patch(path,json={'enabled':True,'interval_seconds':1800}).status_code == 409
    assert owner.patch(path,json={'enabled':False,'interval_seconds':60}).status_code == 422
    assert owner.patch(path,json={'enabled':False,'interval_seconds':3600}).json()['interval_seconds'] == 3600
    assert owner.get('/api/v1/admin/storage').json()['observations'] == 0
    assert owner.get('/api/v1/admin/collection-runs').json()['runs'] == []


def test_research_private_and_unknown_market(client,owner):
    owner.post('/api/v1/auth/logout')
    assert client.get('/api/v1/markets').status_code == 401
    login = client.post('/api/v1/auth/login',json={'username':'owner','password':'correct horse battery'})
    assert login.status_code == 200
    assert client.get('/api/v1/markets/999/items').status_code == 404
    assert client.get('/api/v1/markets/999999999999999999999/items').status_code == 422


def test_backup_status_reports_missing_corrupt_and_verified_metadata(owner,monkeypatch,tmp_path):
    monkeypatch.setattr('market.market_api.BACKUP_DIRECTORY',tmp_path)
    assert owner.get('/api/v1/admin/storage').json()['backup']['status']=='not_configured'
    (tmp_path/'status.json').write_text('{bad')
    assert owner.get('/api/v1/admin/storage').json()['backup']['status']=='unavailable'
    (tmp_path/'status.json').write_text(json.dumps({'status':'ok','last_success':'2026-11-13T12:00:00+00:00',
        'last_restoration_verified_at':'2026-11-13T13:00:00+00:00','secret':'never return arbitrary keys'}))
    result=owner.get('/api/v1/admin/storage').json()['backup']
    assert result['last_restoration_verified_at']=='2026-11-13T13:00:00+00:00'
    assert 'secret' not in result


def test_extended_history_is_authenticated_and_retains_provenance(owner,database):
    market,variant=seed(database)
    result=owner.get(f'/api/v1/markets/{market}/items/12363/{variant}/history?days=365').json()
    assert len(result['points'])==4
    assert result['points'][-1]['recent_price']=='20'
    assert result['points'][0]['namespace']=='dynamic-forever-eu'
    assert result['synthetic']
    assert owner.get(f'/api/v1/markets/{market}/items/12363/{variant}/history?days=99999').status_code==422


def test_new_market_reports_insufficient_history_without_invented_opportunities(owner,database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='New fixture market')
        db.add(market);db.flush();ident=market.id
        ingest(db,ident,b'{"auctions":[{"id":1,"item":{"id":12363},"quantity":1,"buyout":100}]}',request_key='one-day',synthetic=True)
    deals=owner.get(f'/api/v1/markets/{ident}/deals').json()
    assert deals['deals']==[] and deals['history_coverage']=={'observed_days':1,'required_days':3,'status':'insufficient','basis':'utc_days_within_14_days'}
    for kind in ['supply','price']:
        result=owner.get(f'/api/v1/markets/{ident}/signals?kind={kind}').json()
        assert result['signals']==[] and result['history_coverage']['observed_days']==0
        assert result['history_coverage']['status']=='insufficient'
