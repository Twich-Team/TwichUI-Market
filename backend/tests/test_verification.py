import json
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from market.models import Market,MarketVerification,SecurityEvent,User
from market.verification import verify_market,inspect_mapping


class FixtureClient:
    def __init__(self,*,namespace='dynamic-forever-us',house=110,status=200,missing=False):
        self.namespace,self.house,self.status,self.missing=namespace,house,status,missing
        self.calls=[]
    def authenticate(self):return 'synthetic-test-token'
    def throttle(self,meta):pass
    def transport(self,url,**kwargs):
        self.calls.append(url)
        if '/ruleset/index?' in url:data={'rulesets':[{'id':2}]}
        elif '/auctions/?' in url:data={'auctions':[{'id':110,'name':'Fixture house'}]}
        else:data={'id':self.house,'name':'Fixture house','auctions':[{'id':1,'item':{'id':12363},'quantity':2,'buyout':100}]}
        if self.missing:data={'_links':{}}
        body=json.dumps(data).encode()
        return {'url':url,'status':self.status,'headers':{'Battlenet-Namespace':self.namespace},'bytes':len(body)},body


def mapping(database):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Fixture')
        db.add(market);db.flush();return market.id


def test_live_verification_records_actor_hash_and_leaves_schedule_disabled(database):
    ident=mapping(database)
    result=verify_market(ident,'owner','Synthetic transport in isolated regression database',factory=database,client=FixtureClient(),pause=lambda _:None)
    with database.begin() as db:
        market=db.get(Market,ident)
        assert market.verified and not market.enabled
        record=db.get(MarketVerification,result['verification_id'])
        assert record.actor_id==db.scalar(select(User.id).where(User.username=='owner'))
        assert json.loads(record.evidence)['listing_count']==1
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.action=='market.verified'))
        assert len(record.evidence_hash)==64


@pytest.mark.parametrize('client',[FixtureClient(namespace='dynamic-classic-us'),FixtureClient(house=111),FixtureClient(status=429),FixtureClient(missing=True)])
def test_failed_live_evidence_cannot_verify_or_enable(database,client):
    ident=mapping(database)
    with pytest.raises(ValueError):verify_market(ident,'owner','Failure regression',factory=database,client=client,pause=lambda _:None)
    with database.begin() as db:
        assert not db.get(Market,ident).verified
        assert db.scalar(select(MarketVerification)) is None


def test_verification_requires_admin_and_disabled_mapping(database):
    ident=mapping(database)
    with pytest.raises(ValueError):verify_market(ident,'unknown','test',factory=database,client=FixtureClient())
    with database.begin() as db:db.get(Market,ident).enabled=True
    with pytest.raises(ValueError):verify_market(ident,'owner','test',factory=database,client=FixtureClient())


def test_untrusted_region_cannot_receive_credentials():
    market=SimpleNamespace(region='attacker.invalid',ruleset_id=2,house_id=110,source_kind='auctions')
    client=FixtureClient()
    with pytest.raises(ValueError):inspect_mapping(market,client,pause=lambda _:None)
    assert not client.calls


def test_verification_evidence_is_admin_read_only(owner,database):
    ident=mapping(database)
    verify_market(ident,'owner','Fixture evidence',factory=database,client=FixtureClient(),pause=lambda _:None)
    response=owner.get(f'/api/v1/admin/markets/{ident}/verifications')
    assert response.status_code==200 and response.json()[0]['evidence']['listing_count']==1
    assert owner.post(f'/api/v1/admin/markets/{ident}/verifications',json={'verified':True}).status_code==405


def test_guarded_initial_activation_requires_receipt_and_rejects_expansion(database):
    from market.verification import enable_initial
    ident=mapping(database)
    with pytest.raises(ValueError):enable_initial(ident,'owner','test',factory=database)
    verify_market(ident,'owner','Fixture verification',factory=database,client=FixtureClient(),pause=lambda _:None)
    result=enable_initial(ident,'owner','x'*2000,factory=database)
    assert result['enabled'] and result['interval_seconds']==300
    with database.begin() as db:
        db.add(Market(region='us',ruleset_id=2,house_id=111,source_kind='auctions',label='Other',enabled=True))
    with pytest.raises(ValueError):enable_initial(ident,'owner','No expansion',factory=database)


def test_altered_evidence_cannot_activate(database):
    from market.verification import enable_initial
    ident=mapping(database)
    verify_market(ident,'owner','Fixture verification',factory=database,client=FixtureClient(),pause=lambda _:None)
    with database.begin() as db:db.scalar(select(MarketVerification)).evidence='{}'
    with pytest.raises(ValueError):enable_initial(ident,'owner','test',factory=database)
