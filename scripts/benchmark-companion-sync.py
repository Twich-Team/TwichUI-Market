"""Bounded synthetic sync pricing benchmark, PostgreSQL market_test only.

All fixture rows roll back. Output contains timings/query counts, never credentials.
This measures backend compact pricing, not native startup or real Blizzard cadence.
"""
from datetime import timedelta
import json
import os
from time import perf_counter
from sqlalchemy import event, text
from market.db import engine, Session, now
from market.ingest import ingest
from market.models import Market
from market.sync_api import compact
from market.sync_generation import signature

if engine.url.database != 'market_test' or not engine.url.drivername.startswith('postgresql'):
    raise SystemExit('Benchmark accepts PostgreSQL market_test only')
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_database()')) == 'market_test'


def measured(operation):
    count=0
    def query(connection,cursor,statement,parameters,context,many):
        nonlocal count
        if statement.lstrip().upper().startswith('SELECT'):count+=1
    event.listen(engine,'before_cursor_execute',query)
    started=perf_counter()
    try:result=operation()
    finally:event.remove(engine,'before_cursor_execute',query)
    return result,{'seconds':round(perf_counter()-started,6),'selects':count}


with Session() as db:
    try:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic benchmark only')
        db.add(market);db.flush()
        stamp=now().replace(hour=12,minute=0,second=0,microsecond=0)
        for day in range(60,-1,-1):
            payload=json.dumps({'auctions':[{'id':item,'item':{'id':item},'quantity':10,'buyout':1000+day*10+item} for item in range(1,101)]}).encode()
            head=ingest(db,market.id,payload,request_key=f'benchmark-{day}',retrieved_at=stamp-timedelta(days=day),synthetic=True)
        from market.models import Observation
        observation=head
        keys=[(item,'base') for item in range(1,101)]
        # Use the actual canonical variant value emitted by ingestion.
        from market.models import SnapshotStatistic
        keys=[(row.item_id,row.variant_key) for row in db.query(SnapshotStatistic).filter_by(snapshot_id=observation.snapshot_id).all()]
        original,legacy=measured(lambda:{key:compact(db,observation,*key,observation.id) for key in keys})
        result={'synthetic_only':True,'variants':len(keys),'daily_observations':61,'legacy_per_variant':legacy}
        try:from market.sync_api import compact_many
        except ImportError:pass
        else:
            generation=signature(db,observation,observation.id)
            batched,metrics=measured(lambda:compact_many(db,observation,keys,generation))
            assert batched==original
            result.update(batched=metrics,exact_wire_values_equal=True)
        print(json.dumps(result))
    finally:db.rollback()
