"""Frozen legacy auction seed using only columns reflected from the old schema.

Current ORM defaults may refer to newer additive columns. Rehearsals must create
old-format rows before migration and preserve all their original fields.
"""
from datetime import datetime, timezone
import hashlib
import json
from sqlalchemy import MetaData, Table, text


def seed_legacy_auction(connection, *, ruleset_id=2, request_key, label):
    if connection.dialect.name!='postgresql' or connection.scalar(text('SELECT current_database()'))!='market_test':
        raise ValueError('Legacy fixtures require isolated PostgreSQL market_test')
    metadata=MetaData()
    tables={name:Table(name,metadata,autoload_with=connection) for name in
            ('markets','snapshots','observations','listings','snapshot_statistics','daily_observations')}
    at=datetime.now(timezone.utc)
    mid=connection.scalar(tables['markets'].insert().values(region='us',ruleset_id=ruleset_id,house_id=114,
        source_kind='auctions',label=label,enabled=False,verified=False,interval_seconds=1800,
        next_check=at,failures=0,last_success=at).returning(tables['markets'].c.id))
    descriptor='{"id":720}'
    key=hashlib.sha256(descriptor.encode()).hexdigest()
    row={'auction_id':1,'item_id':720,'variant':descriptor,'variant_key':key,'quantity':2,
         'buyout':400,'unit_price':None,'bid':None,'time_left':None}
    raw=json.dumps([row],sort_keys=True,separators=(',',':')).encode()
    sid=connection.scalar(tables['snapshots'].insert().values(market_id=mid,content_hash=hashlib.sha256(raw).hexdigest(),
        created_at=at,listing_count=1,raw_retained=True,statistics_retained=True).returning(tables['snapshots'].c.id))
    connection.execute(tables['listings'].insert().values(snapshot_id=sid,**row))
    connection.execute(tables['snapshot_statistics'].insert().values(snapshot_id=sid,item_id=720,variant_key=key,
        algorithm='asking-v1-provisional',recent_price=200,lowest_buyout=200,supply=2,priced_supply=2,listing_count=1))
    payload=b'{"auctions":[{"id":1,"item":{"id":720},"quantity":2,"buyout":400}]}'
    oid=connection.scalar(tables['observations'].insert().values(market_id=mid,snapshot_id=sid,request_key=request_key,
        retrieved_at=at,namespace='dynamic-forever-us',payload_hash=hashlib.sha256(payload).hexdigest(),
        payload_bytes=len(payload),synthetic=True).returning(tables['observations'].c.id))
    connection.execute(tables['daily_observations'].insert().values(market_id=mid,day=at.date(),observation_id=oid))
    return mid
