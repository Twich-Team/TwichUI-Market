"""Explicitly synthetic browser fixtures; refuses a non-test database."""
import json
from datetime import timedelta
from market.db import Session,engine,now
from market.ingest import ingest
from market.metadata import store_metadata
from market.models import Market,User,StorageMeasurement,CollectionRun
from market.security import hasher

assert engine.url.database=='market_test','Refusing to seed a non-test database'
with Session.begin() as db:
    db.add_all([StorageMeasurement(sampled_at=now()-timedelta(days=1),database_bytes=10485760),StorageMeasurement(sampled_at=now(),database_bytes=11534336)])
    store_metadata(db,'eu',12363,b'{"id":12363,"name":"Synthetic Arcane Crystal","quality":{"type":"UNCOMMON"},"level":60,"required_level":55,"preview_item":{"item":{"id":12363},"stats":[{"display":{"display_string":"+10 Fixture Strength"}}]}}',synthetic=True)
    store_metadata(db,'eu',20000,b'{"id":20000,"name":"Synthetic Enchanted Blade","quality":{"type":"RARE"},"level":40}',synthetic=True)
    db.add(User(username='owner',password_hash=hasher.hash('synthetic browser owner password'),role='admin'))
    db.add(User(username='member_fixture',password_hash=hasher.hash('synthetic browser member password'),role='member'))
    for name in ['prefs_persistence','prefs_isolation_a','prefs_isolation_b','prefs_resilience']:
        db.add(User(username=name,password_hash=hasher.hash('synthetic preferences password'),role='member'))
    for house,label in [(113,'Synthetic Alliance'),(114,'Synthetic Horde')]:
        market=Market(region='eu',ruleset_id=2,house_id=house,source_kind='auctions',label=label)
        db.add(market)
        db.flush()
        for days in [3650,800,3,2,1,0]:
            quantity=10 if days==0 and house==113 else 20
            price=500 if days==0 and house==113 else 2000
            rows=[{'id':9007199254740993,'item':{'id':12363},'quantity':quantity,'buyout':price,'time_left':'LONG'}]
            if house==113:
                rows.extend([{'id':1000+variant,'item':{'id':20000,'bonus_lists':[variant]},'quantity':variant+1,'buyout':(variant+1)*10000*(variant+1)} for variant in [1,2]])
                rows.extend([{'id':2000+index,'item':{'id':20001+index},'quantity':1,'buyout':10000} for index in range(40)])
            body=json.dumps({'auctions':rows}).encode()
            ingest(db,market.id,body,request_key=f'browser-{house}-{days}',retrieved_at=now()-timedelta(days=days),synthetic=True)
        db.add(CollectionRun(market_id=market.id,checked_at=now(),status='success',http_status=200,duration_seconds=2,payload_bytes=len(body),error=None))
print('Synthetic browser fixtures seeded in isolated market_test')
