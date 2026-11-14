"""Isolated preference API tests; never touch production users or market history."""
import json
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from market.app import app
from market.models import Credential, Market, User, UserPreference
from market.security import hasher, issue
from market import environment


def patch(client, changes, revision=0):
    return client.patch('/api/v1/me/preferences', json={
        'schema_version':1, 'expected_revision':revision, 'changes':changes})


def test_defaults_persistence_and_personal_only(owner, database):
    default=owner.get('/api/v1/me/preferences').json()
    assert default['user_id']==1
    assert default['revision']==0 and default['values']['explorer_days']==14
    assert default['values']['market_id'] is None and default['effective_market_id'] is None
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Fixture',enabled=True)
        db.add(market);db.flush();mid=market.id
    changed=patch(owner,{'market_id':mid,'explorer_days':60,'item_page_size':50,
        'item_columns':{'listing_count':False},'item_sort':{'id':'supply','desc':True},
        'deal_mode':'price','deal_change':40,'deal_spend_gold':250.5,'deal_coverage':7,
        'deal_confidence':'strong','deal_direction':'decrease'})
    assert changed.status_code==200,changed.text
    data=changed.json();assert data['revision']==1 and data['effective_market_id']==mid
    assert data['values']['item_columns']['supply'] is True
    assert owner.get('/api/v1/me/preferences').json()==data
    # A separate website login for the same user restores PostgreSQL state.
    with TestClient(app) as other:
        assert other.post('/api/v1/auth/login',json={'username':'owner','password':'correct horse battery'}).status_code==200
        assert other.get('/api/v1/me/preferences').json()==data
    with database() as db:
        assert db.get(Market,mid).enabled
        assert db.scalar(select(func.count()).select_from(UserPreference))==1


def test_account_isolation_csrf_and_no_device_mutations(owner,database):
    assert patch(owner,{'explorer_days':365}).status_code==200
    with database.begin() as db:
        member=User(username='member',password_hash=hasher.hash('member secure password'),role='member')
        db.add(member);db.flush()
        token,_,_=issue(db,member,'device')
    with TestClient(app) as member:
        assert member.get('/api/v1/me/preferences').status_code==401
        session=member.post('/api/v1/auth/login',json={'username':'member','password':'member secure password'}).json()
        own=member.get('/api/v1/me/preferences').json()
        assert own['user_id']!=1 and own['values']['explorer_days']==14
        assert patch(member,{'explorer_days':7}).status_code==403
        member.headers['x-csrf-token']=session['csrf_token']
        assert patch(member,{'explorer_days':7}).status_code==200
        assert patch(member,{'user_id':1},1).status_code==422
        assert member.get('/api/v1/me/preferences/1').status_code==404
        assert member.patch('/api/v1/me/preferences/1',json={}).status_code==404
        assert member.get('/api/v1/me/preferences',headers={'Authorization':'Bearer '+token}).status_code==403
        assert patch(member,{'enabled':True},1).status_code==422
    assert owner.get('/api/v1/me/preferences').json()['values']['explorer_days']==365


@pytest.mark.parametrize('changes',[
    {'market_id':True},{'market_id':0},{'market_id':999999},{'market_id':'1'},
    {'explorer_days':30},{'explorer_days':None},{'item_page_size':1000},
    {'item_columns':{'name':False}},{'item_columns':{'supply':'false'}},
    {'item_sort':{'id':'sql','desc':False}},{'item_sort':{'id':'name','desc':1}},
    {'deal_mode':'arbitrary'},{'deal_change':0},{'deal_change':1001},
    {'deal_spend_gold':-1},{'deal_spend_gold':100000001},{'deal_spend_gold':'50'},
    {'deal_coverage':16},{'deal_confidence':'certain'},{'deal_direction':'both'},
    {'unknown':'x'},{'schema_version':99},
])
def test_strict_values_and_unknown_fields(owner,database,changes):
    assert patch(owner,changes).status_code==422
    assert owner.get('/api/v1/me/preferences').json()['revision']==0
    with database() as db:assert db.get(UserPreference,1) is None


def test_version_size_and_bounded_chunked_body(owner):
    assert owner.patch('/api/v1/me/preferences',json={'schema_version':2,'expected_revision':0,'changes':{}}).status_code==422
    assert owner.patch('/api/v1/me/preferences',json={'schema_version':True,'expected_revision':0,'changes':{}}).status_code==422
    assert owner.patch('/api/v1/me/preferences',json={'schema_version':1,'expected_revision':0,'changes':{},'user_id':2}).status_code==422
    assert owner.patch('/api/v1/me/preferences',content=b'x'*4097).status_code==413
    assert owner.patch('/api/v1/me/preferences',content=iter([b'x'*2048,b'x'*2049])).status_code==413


@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity','1e999'])
def test_nonfinite_json_is_rejected_without_a_server_error(owner,value):
    content='{"schema_version":1,"expected_revision":0,"changes":{"deal_spend_gold":'+value+'}}'
    assert owner.patch('/api/v1/me/preferences',content=content).status_code==422


def test_revision_conflicts_merge_and_reset_do_not_resurrect(owner):
    first=patch(owner,{'explorer_days':60});assert first.status_code==200
    assert patch(owner,{'item_page_size':100}).status_code==409
    updated=patch(owner,{'item_page_size':100},1).json()
    assert updated['values']['explorer_days']==60
    reset=owner.post('/api/v1/me/preferences/reset',json={'schema_version':1,'expected_revision':2})
    assert reset.status_code==200 and reset.json()['revision']==3
    assert reset.json()['values']['explorer_days']==14 and reset.json()['values']['item_page_size']==25
    assert patch(owner,{'explorer_days':7},2).status_code==409
    assert owner.post('/api/v1/me/preferences/reset',json={'schema_version':1,'expected_revision':2}).status_code==409


def test_unavailable_saved_market_falls_back_without_overwriting(owner,database):
    with database.begin() as db:
        db.add(Market(id=7,region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Historical',enabled=False))
        db.add(Market(id=8,region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Collecting',enabled=True))
    assert owner.get('/api/v1/me/preferences').json()['effective_market_id']==8
    assert patch(owner,{'market_id':7}).json()['effective_market_id']==7
    with database.begin() as db:db.delete(db.get(Market,7))
    data=owner.get('/api/v1/me/preferences').json()
    assert data['market_fallback'] and data['effective_market_id']==8 and data['values']['market_id']==7
    assert patch(owner,{'explorer_days':60},1).json()['values']['market_id']==7
    with database.begin() as db:
        db.add(Market(id=7,region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Returned',enabled=False))
    assert owner.get('/api/v1/me/preferences').json()['effective_market_id']==7


def test_preview_allows_only_personal_preferences(owner,monkeypatch):
    monkeypatch.setattr(environment,'READ_ONLY',True)
    assert patch(owner,{'explorer_days':60}).status_code==200
    assert owner.post('/api/v1/me/preferences/reset',json={'schema_version':1,'expected_revision':1}).status_code==200
    assert owner.post('/api/v1/admin/markets',json={}).status_code==403
    assert owner.post('/api/v1/devices',json={'name':'forbidden'}).status_code==403


@pytest.mark.parametrize('existing',[False,True])
def test_postgresql_concurrent_writers_get_one_commit_and_one_conflict(owner,database,existing):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row-lock concurrency test')
    revision=0
    if existing:
        assert patch(owner,{'explorer_days':7}).status_code==200
        revision=1
    # Independent requests, connections and browser sessions, same starting revision.
    def writer(days):
        with TestClient(app) as client:
            login=client.post('/api/v1/auth/login',json={'username':'owner','password':'correct horse battery'}).json()
            client.headers['x-csrf-token']=login['csrf_token']
            return patch(client,{'explorer_days':days},revision).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses=list(pool.map(writer,[60,365]))
    assert sorted(statuses)==[200,409]
    assert owner.get('/api/v1/me/preferences').json()['revision']==revision+1
