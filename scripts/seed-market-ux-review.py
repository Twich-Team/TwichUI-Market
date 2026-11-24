"""Seed the isolated UX review through stdin. Run before exposing its proxy."""

import json
import os
import sys
from datetime import timedelta
from sqlalchemy import select
from market.db import Session, engine, now
from market.ingest import ingest
from market.metadata import store_metadata
from market.models import Market, User, CollectionRun
from market.security import hasher

assert engine.url.host == 'db' and engine.url.database == 'market_test'
assert os.environ['SESSION_COOKIE_NAME'] == 'market_ux_review_session'
passwords = json.load(sys.stdin)
assert set(passwords) == {'review_member', 'review_admin'}
with Session.begin() as db:
    initialized = set(db.scalars(select(User.username).where(User.username.in_(passwords))))
    if initialized == passwords.keys():
        print('Review accounts already initialized.')
        raise SystemExit(0)
    if initialized:
        raise RuntimeError('Partial review account bootstrap. Inspect the isolated database.')
    for account in db.scalars(select(User)):
        if account.username in ('owner', 'member_fixture'):
            account.username = 'review_admin' if account.role == 'admin' else 'review_member'
            account.password_hash = hasher.hash(passwords[account.username])
        else:
            account.active = False
    market = db.scalar(select(Market).where(Market.house_id == 113))
    market.label = 'Guild review · synthetic auctions'
    at = now()
    for ident, name, quality in [(117, 'Tough Jerky', 'COMMON'), (8177, 'Training Sword', 'COMMON'),
                                 (2840, 'Copper Bar', 'COMMON'), (1705, 'Lesser Moonstone', 'UNCOMMON')]:
        store_metadata(db, 'eu', ident, json.dumps(dict(id=ident, name=name, quality=dict(type=quality), level=5)).encode(), synthetic=True)
    for ago in range(8, -1, -1):
        stamp = at - timedelta(days=ago)
        jerky = {5: 1836361542, 4: 775738042, 0: 3}.get(ago, 55)
        rows = []
        def stack(ident, count, unit, bonus=None):
            item = {'id': ident}
            if bonus is not None:
                item['bonus_lists'] = [bonus]
            rows.append(dict(id=80000+len(rows), item=item, quantity=count, buyout=count*unit))
        for qty in (1, 4, 8):
            stack(117, qty, jerky)
        for idx in range(40):
            stack(8177, 1, 70+idx*3+ago, 12730+idx)
        for index in range(65):
            stack(2840, 2+(index%4), (48 if not ago else 130)+index%3)
        stack(1705, 7 if ago else 120, 1250+120*ago)
        ingest(db, market.id, json.dumps({'auctions':rows}).encode(), request_key=f'ux-review-{ago}',
               retrieved_at=stamp, synthetic=True)
    market.last_success = at
    market.last_modified = at.strftime('%a, %d %b %Y %H:%M:%S GMT')
    db.add(CollectionRun(market_id=market.id,checked_at=at,status='unchanged',http_status=304,duration_seconds=1))
print('Review accounts and synthetic observations ready.')
