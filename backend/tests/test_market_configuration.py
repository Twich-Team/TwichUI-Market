import hashlib,json
from datetime import timedelta
from sqlalchemy import func,select
from market.db import now
from market.models import Market,MarketVerification,Observation,PlayerMarketMapping
from market.ingest import ingest

def verified_player_mapping(db,house,faction):
    evidence={'region':'us','house_id':house,'ruleset':'Normal','faction':faction,
        'upstream_receipt':{'synthetic':True},'independent_observation':{'synthetic_player_scan':True},'independent_source_url':'https://example.test/fixture'}
    encoded=json.dumps(evidence)
    db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction=faction,house_id=house,transport_ruleset_id=2,source_kind='auctions',confidence='verified',evidence=encoded,evidence_hash=hashlib.sha256(encoded.encode()).hexdigest(),verified_at=now()))

def test_unresolved_player_choices_cannot_create_or_enable(owner,database):
    options=owner.get('/api/v1/admin/market-options').json()
    assert all(not choice['available'] for choice in options['choices'])
    result=owner.post('/api/v1/admin/configured-markets',json={'region':'us','ruleset':'Normal','faction':'Horde','enabled':False})
    assert result.status_code==409
    with database() as db:assert db.scalar(select(func.count()).select_from(Market))==0

def test_alias_creation_rejected_independent_of_ruleset_url(owner):
    body={'region':'us','house_id':110,'ruleset_id':2,'source_kind':'auctions','label':'Synthetic feed'}
    assert owner.post('/api/v1/admin/markets',json=body).status_code==201
    assert owner.post('/api/v1/admin/markets',json={**body,'ruleset_id':1}).status_code==409

def test_verified_guided_resolution_and_confirmed_transition_preserve_history(owner,database):
    with database.begin() as db:
        verified_player_mapping(db,113,'Horde')
        old=Market(region='us',house_id=110,ruleset_id=2,source_kind='auctions',label='Old fixture',enabled=True,verified=True)
        db.add(old);db.flush()
        ingest(db,old.id,b'{"auctions":[{"id":1,"item":{"id":25},"quantity":1,"buyout":100}]}',request_key='old-fixture',synthetic=True)
        old_id=old.id
    response=owner.post('/api/v1/admin/configured-markets',json={'region':'us','ruleset':'Normal','faction':'Horde'})
    assert response.status_code==201,response.text
    new=response.json()
    assert new['house_id']==113 and new['label']=='US — Normal — Horde' and not new['enabled']
    path=f"/api/v1/admin/markets/{new['id']}/schedule"
    assert owner.patch(path,json={'enabled':True,'interval_seconds':300}).status_code==409
    with database.begin() as db:
        market=db.get(Market,new['id']);market.verified=True
        evidence=json.dumps({'mapping':{'region':'us','house_id':113,'ruleset_id':2,'source_kind':'auctions'}})
        db.add(MarketVerification(market_id=market.id,actor_id=1,evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),notes='Synthetic receipt'))
    assert owner.patch(path,json={'enabled':True,'interval_seconds':300}).status_code==409
    transition={'from_market_id':old_id,'to_market_id':new['id'],'confirm':False}
    assert owner.post('/api/v1/admin/market-transition',json=transition).status_code==409
    assert owner.post('/api/v1/admin/market-transition',json={**transition,'confirm':True}).status_code==200
    with database() as db:
        assert not db.get(Market,old_id).enabled and db.get(Market,new['id']).enabled
        assert db.scalar(select(func.count()).select_from(Observation).where(Observation.market_id==old_id))==1

def test_upstream_verified_does_not_mean_player_verified(owner,database):
    with database.begin() as db:
        market=Market(region='us',house_id=113,ruleset_id=2,source_kind='auctions',label='Synthetic unknown',verified=True)
        db.add(market);db.flush();ident=market.id
    assert owner.patch(f'/api/v1/admin/markets/{ident}/schedule',json={'enabled':True,'interval_seconds':300}).status_code==409
    assert owner.get(f'/api/v1/admin/markets/{ident}/diagnostics').json()['player_identity'] is None
