"""Representative synthetic unified feed fixture. No provider/network collection.

Use only a disposable SQLite filename ending market_test.sqlite. The fake feed
transport exercises real normalization/publication and explicitly marks every
observation synthetic. It is independent of the genuine summary-slice benchmark.
"""
import hashlib,json,secrets
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select,delete
from market.db import Base,engine,Session,now
from market.models import User,Market,MarketFeed,PlayerMarketMapping,CompanionDevice,Observation,DailyObservation
from market.companion_auth import _access
from market.ingest import canonical,record_daily
from market.feed_collection import capture_feed,publish

class Fixture:
    def __init__(self,variants=26342):
        assert engine.dialect.name=='sqlite' and engine.url.database.endswith('market_test.sqlite') and 25000<=variants<=45125
        self.variants=variants;self.at=now()-timedelta(minutes=2)
        Base.metadata.create_all(engine)
        with Session.begin() as db:
            db.add(User(id=1,username='synthetic_performance',password_hash='not-a-login',role='member'))
            db.add(Market(id=2,region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic unified performance fixture',unified_coverage=True,verified=True,enabled=True,next_check=self.at-timedelta(days=3)))
            db.flush()
            for kind in ('auctions','commodities'):
                proof={'identity':{'region':'us','ruleset_id':2,'house_id':114,'source_kind':kind,'namespace':'dynamic-forever-us','scope':'ruleset_house'},'evidence_sha256':'a'*64}
                db.add(MarketFeed(market_id=2,source_kind=kind,enabled=True,verification=canonical(proof)))
            evidence=canonical({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde','upstream_receipt':'synthetic only','independent_observation':'synthetic only','independent_source_url':'https://fixture.invalid/performance'})
            db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,source_kind='auctions',transport_ruleset_id=2,confidence='verified',evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),verified_at=self.at))
            from market import environment
            d=CompanionDevice(user_id=1,name='Synthetic performance fixture',platform='Windows',app_version='2.0.0-beta.8',issuer_origin=environment.SESSION_ORIGIN,expires_at=self.at+timedelta(days=1),refresh_expires_at=self.at+timedelta(days=1),refresh_hash=hashlib.sha256(b'fixture-unused-refresh').hexdigest())
            db.add(d);db.flush();self.token=secrets.token_urlsafe(32);_access(db,d,self.token)
        for day in [3,2,0]:self.publish(0,self.at-timedelta(days=day))
        with Session() as db:self.initial=db.scalar(select(Observation.id).order_by(Observation.id.desc()).limit(1))
    def publish(self,step,at=None):
        at=at or self.at+timedelta(seconds=step)
        with Session.begin() as db:
            market=db.get(Market,2)
            feeds=list(db.scalars(select(MarketFeed).where(MarketFeed.market_id==2).order_by(MarketFeed.source_kind)))
            checks=[capture_feed(db,market,feed,Transport(self.variants,step),at) for feed in feeds]
            assert all(check.status=='collected' for check in checks)
            observation=publish(db,market,checks,at)
            # Fake source transport must never be mistaken for genuine data.
            observation.synthetic=True
    def reset(self):
        with Session.begin() as db:
            db.execute(delete(DailyObservation).where(DailyObservation.observation_id>self.initial))
            db.execute(delete(Observation).where(Observation.id>self.initial))
            record_daily(db,db.get(Observation,self.initial))

class Transport:
    def __init__(self,variants,step):self.variants=variants;self.step=step
    def fetch(self,market):
        kind=market.source_kind;rows=[]
        for i in range(self.variants):
            if ('commodities' if i%20==0 else 'auctions')!=kind:continue
            price=100+(i%100)+(7 if self.step and i%23==0 else 0)
            item=10000+i
            if self.step and i>=self.variants-10:item+=100000
            rows.append({'id':i+1,'item':{'id':item},'quantity':10,'unit_price' if kind=='commodities' else 'buyout':price if kind=='commodities' else price*10})
        path='/data/wow/ruleset/2/auctions/114'+('/commodities' if kind=='commodities' else '')
        body={'_links':{'self':{'href':'https://us.api.blizzard.com'+path+'?namespace=dynamic-forever-us'}},'auctions':rows}
        if kind=='auctions':body['id']=114
        return {'status':200,'headers':{'Battlenet-Namespace':'dynamic-forever-us','ETag':f'"synthetic-{kind}-{self.step}"'}},json.dumps(body).encode()
