"""Disposable usability acceptance: synthetic accounts, devices, icons and observations."""
import base64, hashlib, json
from datetime import timedelta
from sqlalchemy import select
from market.db import Session, engine, now
from market.ingest import ingest
from market.models import User, CompanionDevice, ItemMedia, Market
from market.metadata import store_metadata
assert engine.url.database == 'market_test', 'Refusing usability fixtures outside market_test'
with Session.begin() as db:
    if db.scalar(select(User.id).where(User.username=='obsolete_fixture')):
        raise SystemExit('Usability fixtures already exist')
    db.add(User(username='obsolete_fixture',password_hash='disabled-fixture',role='member',active=False))
    owner=db.scalar(select(User).where(User.username=='owner'))
    db.add(CompanionDevice(user_id=owner.id,name='Obsolete synthetic PC',platform='Windows',app_version='2.0.0-beta.2',
        issuer_origin='http://proxy:8080',expires_at=now()+timedelta(days=90),refresh_expires_at=now()+timedelta(days=90),
        refresh_hash=hashlib.sha256(b'usability-synthetic-revoked').hexdigest(),revoked=True))
    market=Market(region='eu',ruleset_id=2,house_id=115,source_kind='auctions',label='Synthetic usability review')
    db.add(market); db.flush()
    png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
    for ident in range(31000,31032):
        store_metadata(db,'eu',ident,json.dumps({'id':ident,'name':f'Synthetic review item {ident}','quality':{'type':'UNCOMMON'}}).encode(),synthetic=True)
        db.add(ItemMedia(region='eu',item_id=ident,status='available',data=png,byte_count=len(png),content_type='image/png',asset_hash=hashlib.sha256(png).hexdigest()))
    for day in [3,2,1,0]:
        rows=[{'id':i,'item':{'id':i},'quantity':2,'buyout':1000 if day==0 else 2000} for i in range(31000,31032)]
        ingest(db,market.id,json.dumps({'auctions':rows}).encode(),request_key=f'usability-{day}',retrieved_at=now()-timedelta(days=day),synthetic=True)
print('Usability fixtures seeded in disposable market_test; no providers or collector')
# Real stored fixture measurements: an explicit 3-hour gap, never filled by UI.
from market.models import StorageMeasurement
from sqlalchemy import delete
with Session.begin() as db:
    db.execute(delete(StorageMeasurement))
    hour=now().replace(minute=0,second=0,microsecond=0)
    for ago in range(48,-1,-1):
        if ago in (15,16,17): continue
        db.add(StorageMeasurement(sampled_at=hour-timedelta(hours=ago),database_bytes=2684354560+(48-ago)*1048576))
