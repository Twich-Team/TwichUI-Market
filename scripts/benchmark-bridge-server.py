"""Actual authenticated bridge API over a disposable SYNTHETIC SQLite database.

Measures cold derivation/materialization, warm manifest, pages and SQL counts.
SQLite/in-process HTTP is diagnostic evidence, never production PostgreSQL or
network latency acceptance. No collector/provider worker or live DB is contacted.
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--records",type=int,default=1000)
p.add_argument("--days",type=int,choices=(2,14,60),default=2)
p.add_argument("--runs",type=int,default=5)
p.add_argument("--report",type=Path,required=True)
a=p.parse_args()
assert 1<=a.records<=1000 and 1<=a.runs<=5
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="twichui-m15-server-") as directory:
    os.environ.update(DATABASE_URL="sqlite:///"+str(Path(directory)/"market_test.sqlite"),
        APP_ORIGIN="https://synthetic-capacity.example.invalid",
        SYNC_CURSOR_SECRET="synthetic-m15-cursor-secret-"+"x"*32,
        BRIDGE_CONTRACT_ROOT=str(root/"contracts/bridge/v1"))
    sys.path.insert(0,str(root/"backend"))
    started=time.perf_counter()
    from market.app import app
    from market.db import Base,engine,Session
    from market.models import User,Market
    from market.security import issue
    from market.ingest import ingest
    from market import bridge_api
    from fastapi.testclient import TestClient
    from sqlalchemy import event
    import_us=round((time.perf_counter()-started)*1e6)
    asof=datetime(2026,11,15,13,tzinfo=timezone.utc)
    bridge_api.now=lambda:asof
    Base.metadata.create_all(engine)
    started=time.perf_counter()
    with Session.begin() as db:
        user=User(username="synthetic_capacity",password_hash="not-a-login",role="member")
        db.add(user);db.flush();token,_,_=issue(db,user,"device")
        market=Market(region="us",ruleset_id=1,house_id=114,source_kind="auctions",
                      label="Synthetic benchmark only",verified=True,enabled=True)
        db.add(market);db.flush();mid=market.id
        for day in range(a.days):
            at=asof-timedelta(days=a.days-1-day,hours=1)
            payload={"auctions":[{"id":day*100000+i+1,"item":{"id":10000+i},"quantity":10,"buyout":1000}for i in range(a.records)]}
            ingest(db,mid,json.dumps(payload).encode(),request_key=f"synthetic-m15-{day}",
                   retrieved_at=at,modified=format_datetime(at-timedelta(hours=1),usegmt=True),synthetic=True)
    seed_us=round((time.perf_counter()-started)*1e6)
    queries=0
    @event.listens_for(engine,"before_cursor_execute")
    def count_query(*args):
        global queries
        queries+=1
    headers={"Authorization":"Bearer "+token}
    attempts=[]
    with TestClient(app) as client:
        for attempt in range(32):
            queries=0;started=time.perf_counter()
            response=client.get(f"/api/v1/bridge/markets/{mid}/manifest",headers=headers)
            attempts.append(dict(status=response.status_code,us=round((time.perf_counter()-started)*1e6),sql=queries))
            if response.status_code==200:
                envelope=response.json();break
            assert response.status_code==202,response.text
        else:
            raise RuntimeError("bounded source derivation did not finish")
        manifest=envelope["manifest"]
        assert manifest["synthetic"] and manifest["record_count"]==a.records
        assert manifest["coverage"]["delivered_observed_days"]==a.days
        samples=[]
        for repetition in range(a.runs):
            queries=0;started=time.perf_counter()
            response=client.get(f"/api/v1/bridge/markets/{mid}/manifest",headers=headers)
            assert response.status_code==200,response.text
            envelope=response.json();warm_us=round((time.perf_counter()-started)*1e6);warm_sql=queries
            assert envelope["manifest"]["generation_id"]==manifest["generation_id"]
            cursor=envelope["cursor"];count=0;pages=0;wire=0;queries=0;started=time.perf_counter()
            while cursor:
                response=client.get(f"/api/v1/bridge/markets/{mid}/records",
                    params={"cursor":cursor,"generation":manifest["generation_id"]},headers=headers)
                assert response.status_code==200,response.text
                page=response.json();assert page["generation_id"]==manifest["generation_id"]
                for r in page["records"]:
                    assert r["current"]["metrics"]["recent_copper"]=="100"
                    assert len(r["daily"])==a.days
                count+=len(page["records"]);wire+=len(response.content);pages+=1;cursor=page["next_cursor"]
            assert count==a.records
            samples.append(dict(warm_manifest_us=warm_us,warm_manifest_sql=warm_sql,
                page_total_us=round((time.perf_counter()-started)*1e6),page_sql=queries,pages=pages,wire_bytes=wire))
    report=dict(origin="synthetic",backend="disposable SQLite; actual authenticated ASGI requests",
        records=a.records,observed_days=a.days,production_acceptance=False,generation_id=manifest["generation_id"],
        import_us=import_us,seed_us=seed_us,cold_manifest_attempts=attempts,samples=samples,
        process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
