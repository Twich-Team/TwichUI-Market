"""Rollback-only synthetic scheduler measurement on disposable market_test."""
from datetime import timedelta
import json
import os
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import event, insert, select, text
from market.db import Session,engine,now
from market.metadata_models import MetadataProvider,MetadataQuotaBucket
from market.metadata_recovery import ensure_providers
from market.provider_rates import bucket_start,configuration,observe,rate_view,reserve_budget

if engine.dialect.name!='postgresql' or engine.url.database!='market_test':
    raise SystemExit('Refusing non-test PostgreSQL database; use disposable market_test')
at=bucket_start(now(),60)
statements=[]
def count(*args):statements.append(1)
with Session() as db:
    ensure_providers(db)
    row=db.get(MetadataProvider,'thewowdb',with_for_update=True)
    row.rate_config=json.dumps({**configuration(row),'hourly_budget':72000,'daily_budget':1000000,'minimum_interval':.05})
    row.hour_used=row.day_used=0
    row.next_request_at=row.cooldown_until=row.rate_inflight_until=None
    db.execute(text("DELETE FROM metadata_quota_buckets WHERE provider='thewowdb'"))
    db.execute(insert(MetadataQuotaBucket),[{'provider':'thewowdb','resolution':60,'started_at':at-timedelta(minutes=i),'used':1} for i in range(1441)])
    db.flush()
    event.listen(engine,'before_cursor_execute',count)
    timings=[];queries=[]
    for i in range(10):
        instant=at+timedelta(seconds=i)
        statements.clear();started=time.perf_counter()
        assert reserve_budget(row,instant) is None
        observe(row,200,{},instant)
        db.flush()
        timings.append((time.perf_counter()-started)*1000);queries.append(len(statements))
    statements.clear();started=time.perf_counter();view=rate_view(row,at+timedelta(seconds=10))
    view_ms=(time.perf_counter()-started)*1000;view_queries=len(statements)
    event.remove(engine,'before_cursor_execute',count)
    bytes_used=db.scalar(text("SELECT pg_total_relation_size('metadata_quota_buckets')"))
    db.rollback()
print(json.dumps({'origin':'synthetic','scope':'Warm local PostgreSQL handler measurements; not upstream throughput or production p95',
    'minute_buckets_seeded':1441,'runs':10,'reservation_median_ms':round(statistics.median(timings),3),
    'reservation_max_ms':round(max(timings),3),'reservation_sql_statements':queries,
    'status_view_ms':round(view_ms,3),'status_view_sql_statements':view_queries,
    'quota_relation_bytes':bytes_used,'max_tick_rate_per_second':4,'transaction_rolled_back':True},indent=2))
