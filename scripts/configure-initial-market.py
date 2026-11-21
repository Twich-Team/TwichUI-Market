"""Privileged marketdev operator: create only a disabled, unverified initial feed."""
import subprocess
PROGRAM='''
import json
from sqlalchemy import select
from market.db import Session
from market.models import Market,SecurityEvent,User
with Session.begin() as db:
    actor=db.scalar(select(User).where(User.username=='owner',User.role=='admin',User.active.is_(True)))
    if actor is None:raise RuntimeError('Active owner required')
    market=db.scalar(select(Market).where(Market.region=='us',Market.ruleset_id==2,Market.house_id==110,Market.source_kind=='auctions'))
    if market is None:
        market=Market(region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='US Forever — Alliance house 110 (ruleset aliases)',interval_seconds=300,enabled=False,verified=False)
        db.add(market);db.flush()
        db.add(SecurityEvent(actor_id=actor.id,action='market.created',detail=f'market={market.id} operator=marketdev disabled_initial_feed'))
    print(json.dumps({'market_id':market.id,'verified':market.verified,'enabled':market.enabled}))
'''
subprocess.run(['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml','run','--rm','-T','--no-deps','worker','python','-'],input=PROGRAM.encode(),check=True)
