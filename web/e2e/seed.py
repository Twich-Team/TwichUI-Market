"""Explicitly synthetic browser fixtures; refuses a non-test database."""
import json
from datetime import timedelta
from market.db import Session,engine,now
from market.ingest import ingest
from market.metadata import store_metadata
from market.models import Market,User
from market.security import hasher

assert engine.url.database=='market_test','Refusing to seed a non-test database'
with Session.begin() as db:
    store_metadata(db,'eu',12363,b'{"id":12363,"name":"Synthetic Arcane Crystal"}',synthetic=True)
    db.add(User(username='owner',password_hash=hasher.hash('synthetic browser owner password'),role='admin'))
    db.add(User(username='member_fixture',password_hash=hasher.hash('synthetic browser member password'),role='member'))
    for house,label in [(113,'Synthetic Alliance'),(114,'Synthetic Horde')]:
        market=Market(region='eu',ruleset_id=2,house_id=house,source_kind='auctions',label=label)
        db.add(market)
        db.flush()
        for days in [3,2,1,0]:
            quantity=10 if days==0 and house==113 else 20
            price=500 if days==0 and house==113 else 2000
            body=json.dumps({'auctions':[{'id':9007199254740993,'item':{'id':12363},'quantity':quantity,'buyout':price,'time_left':'LONG'}]}).encode()
            ingest(db,market.id,body,request_key=f'browser-{house}-{days}',retrieved_at=now()-timedelta(days=days),synthetic=True)
print('Synthetic browser fixtures seeded in isolated market_test')
