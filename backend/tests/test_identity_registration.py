"""Synthetic operator/transaction tests; these are not live mapping evidence."""
import hashlib
import json
from datetime import timedelta
import pytest
from sqlalchemy import func, select
from market.db import now
from market.identity_registration import IDENTITY, register
from market.ingest import ingest
from market.models import Market, MarketVerification, Observation, PlayerMarketMapping, SecurityEvent


def research():
    samples = [{'item_id':i, 'house_id':h, 'ruleset':r, 'region':'us', 'faction':'Horde',
        'matched':True, 'quantity':i+10, 'api_quantity':i+10, 'minimum_unit_copper':1,
        'api_minimum_unit_copper':1, 'source_url':f'https://forevermastery.com/en/items/{i}-fixture'}
        for h,r in ((113,'PvP'),(114,'Normal')) for i in range(1,5)]
    return {**IDENTITY, 'observed_at':now().isoformat(), 'independent_observation':{'samples':samples},
        'independent_source_url':'https://forevermastery.com/en/prices/us-normal-horde',
        'upstream_probes':{'responses':[{'mapping':{'region':'us','transport_ruleset_id':2,
        'house_id':114,'source_kind':'auctions'},'sha256':'synthetic-payload',
        'headers':{'Last-Modified':'synthetic-generation'}}]}}


def invoke(review, database, monkeypatch, *, report_hash='synthetic-payload', actor='owner', expected=None):
    def inspect(market, client, pause):
        assert market.house_id==114 and not market.enabled
        return {'mapping':{'region':'us','ruleset_id':2,'house_id':114,'source_kind':'auctions'},
            'requests':[{'sha256':report_hash,'headers':{'Last-Modified':'synthetic-generation'}}]}
    monkeypatch.setattr('market.identity_registration.inspect_mapping', inspect)
    raw=json.dumps(review).encode()
    return register(raw, expected or hashlib.sha256(raw).hexdigest(), actor, factory=database)


def test_registration_is_disabled_audited_and_cannot_duplicate(database, monkeypatch, owner):
    with database.begin() as db:
        old=Market(region='us', house_id=110, ruleset_id=2, source_kind='auctions',
            label='Synthetic original', enabled=True, verified=True)
        db.add(old);db.flush();old_id=old.id
        ingest(db,old.id,b'{"auctions":[{"id":99,"item":{"id":25},"quantity":1,"buyout":100}]}',
            request_key='registration-history', synthetic=True)
    review=research()
    result=invoke(review,database,monkeypatch)
    assert result['enabled'] is False and result['transition_executed'] is False
    with database() as db:
        assert db.get(Market,old_id).enabled
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert db.scalar(select(func.count()).select_from(MarketVerification))==1
        assert db.scalar(select(func.count()).select_from(PlayerMarketMapping))==1
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.action=='market.identity.registered'))
    with pytest.raises(ValueError,match='already registered'):
        invoke(review,database,monkeypatch)
    transition={'from_market_id':old_id,'to_market_id':result['market_id'],'confirm':False}
    assert owner.post('/api/v1/admin/market-transition',json=transition).status_code==409
    assert owner.post('/api/v1/admin/market-transition',json={**transition,'confirm':True}).status_code==200
    with database() as db:
        assert not db.get(Market,old_id).enabled
        assert db.get(Market,result['market_id']).enabled
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert db.scalar(select(func.count()).select_from(Market).where(Market.enabled.is_(True)))==1


@pytest.mark.parametrize('failure', ['hash','identity','stale','samples','upstream','actor','enabled','alias'])
def test_failed_registration_preserves_configuration(database,monkeypatch,failure):
    review=research()
    if failure=='identity':review['house_id']=113
    if failure=='stale':review['observed_at']=(now()-timedelta(days=2)).isoformat()
    if failure=='samples':review['independent_observation']['samples'][0]['api_quantity']=99999
    if failure in ('enabled','alias'):
        with database.begin() as db:
            db.add(Market(region='us',house_id=114,ruleset_id=1 if failure=='alias' else 2,
                source_kind='auctions',label='Conflicting fixture',enabled=failure=='enabled',verified=False))
    with pytest.raises(ValueError):
        invoke(review,database,monkeypatch,report_hash='changed' if failure=='upstream' else 'synthetic-payload',
            actor='missing' if failure=='actor' else 'owner',expected='wrong' if failure=='hash' else None)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(MarketVerification))==0
        assert db.scalar(select(func.count()).select_from(PlayerMarketMapping))==0
        assert db.scalar(select(func.count()).select_from(Market))==(1 if failure in ('enabled','alias') else 0)


@pytest.mark.parametrize('failure',['stale','corrupt','third_feed'])
def test_transition_rechecks_evidence_and_single_feed(owner,database,monkeypatch,failure):
    result=invoke(research(),database,monkeypatch)
    with database.begin() as db:
        old=Market(region='us',house_id=110,ruleset_id=2,source_kind='auctions',
            label='Synthetic old',enabled=True,verified=True)
        db.add(old);db.flush();old_id=old.id
        if failure=='third_feed':
            db.add(Market(region='eu',house_id=110,ruleset_id=2,source_kind='auctions',
                label='Conflicting synthetic feed',enabled=True,verified=True))
        receipt=db.get(MarketVerification,result['verification_id'])
        if failure=='stale':receipt.created_at=now()-timedelta(days=2)
        if failure=='corrupt':receipt.evidence_hash='0'*64
    response=owner.post('/api/v1/admin/market-transition',json={
        'from_market_id':old_id,'to_market_id':result['market_id'],'confirm':True})
    assert response.status_code==409
    with database() as db:
        assert db.get(Market,old_id).enabled
        assert not db.get(Market,result['market_id']).enabled
        assert not db.scalar(select(SecurityEvent).where(SecurityEvent.action=='market.transition.confirmed'))
