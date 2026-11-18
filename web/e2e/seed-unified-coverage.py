"""Verified item identities with synthetic prices; no provider calls. Test DB only."""
import json
from datetime import timedelta
from email.utils import format_datetime
from types import SimpleNamespace
from sqlalchemy import select
from market.db import Session, engine, now
from market.ingest import canonical, ingest
from market.metadata import store_metadata
from market.models import Market, MarketFeed, Observation, User
from market.security import hasher
from market.worker import collect_once

assert engine.url.database == 'market_test', 'Refusing unified fixtures outside market_test'
at = now()-timedelta(minutes=1)
with Session.begin() as db:
    if db.scalar(select(User.id).where(User.username=='commodity_fixture')) is None:
        db.add(User(username='commodity_fixture', password_hash=hasher.hash('synthetic commodity browser password'), role='member'))
    market = db.scalar(select(Market).where(Market.region=='us',Market.ruleset_id==2,
        Market.house_id==114,Market.source_kind=='auctions'))
    if market is None:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic unified coverage')
        db.add(market)
    market.label='Synthetic unified coverage'
    market.unified_coverage=market.enabled=market.verified=True
    market.interval_seconds=300
    market.next_check=at
    db.flush()
    mid = market.id
    ingest(db, mid, b'{"auctions":[{"id":1,"item":{"id":25},"quantity":1,"buyout":999}]}',
        request_key='unified-browser-precoverage', retrieved_at=at-timedelta(days=3), synthetic=True)
    for kind in ('auctions', 'commodities'):
        proof = {'identity': dict(region='us', ruleset_id=2, house_id=114, source_kind=kind,
            namespace='dynamic-forever-us', scope='ruleset_house'), 'evidence_sha256': 'f'*64}
        db.add(MarketFeed(market_id=mid, source_kind=kind, enabled=True, verification=canonical(proof)))
    for item, name, cls in ((4306, 'Silk Cloth', 7), (14342, 'Mooncloth', 7), (6657, 'Savory Deviate Delight', 0)):
        store_metadata(db, 'us', item, json.dumps({'id': item, 'name': name, 'quality': {'type':'COMMON'},
            'item_class': {'id':cls,'name':'Trade Goods' if cls==7 else 'Consumable'},'level':1}).encode(), synthetic=True)

class Fixtures:
    def fetch(self, market):
        kind = market.source_kind
        path = '/data/wow/ruleset/2/auctions/114'+('/commodities' if kind=='commodities' else '')
        rows = [{'id':1,'item':{'id':25},'quantity':1,'buyout':999}] if kind=='auctions' else [
            {'id':10,'item':{'id':4306},'quantity':20,'unit_price':123},
            {'id':11,'item':{'id':4306},'quantity':10,'unit_price':200},
            {'id':12,'item':{'id':14342},'quantity':3,'unit_price':4567},
            {'id':13,'item':{'id':6657},'quantity':4,'unit_price':890}]
        body = {'_links': {'self': {'href':'https://us.api.blizzard.com'+path+'?namespace=dynamic-forever-us'}},'auctions':rows}
        if kind=='auctions': body['id']=114
        return {'status':200,'headers':{'Battlenet-Namespace':'dynamic-forever-us','Last-Modified':format_datetime(at)}},json.dumps(body).encode()
assert collect_once(Session, Fixtures(), at=at)
with Session.begin() as db:
    db.get(Market, mid).enabled=False
    for observation in db.scalars(select(Observation).where(Observation.market_id==mid)):
        observation.synthetic=True
print('Synthetic unified coverage fixture seeded; no production or provider writes')
