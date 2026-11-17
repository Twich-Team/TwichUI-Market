"""Destructive rehearsal, hard-restricted to disposable PostgreSQL market_test."""
from datetime import timedelta
import json
from pathlib import Path
import subprocess
import os
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from market.db import now

url=make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database!='market_test':raise SystemExit('Refusing non-test database')
backend=Path(__file__).resolve().parents[1]/'backend'
engine=create_engine(url)

def migrate(*args, success=True):
    result=subprocess.run(['alembic',*args],cwd=backend,capture_output=True,text=True)
    if success and result.returncode:raise RuntimeError(result.stderr)
    return result

with engine.begin() as db:
    assert db.scalar(text('select current_database()'))=='market_test'
    db.execute(text('DROP SCHEMA public CASCADE'));db.execute(text('CREATE SCHEMA public'))
migrate('upgrade','0013')
at=now()
with engine.begin() as db:
    db.execute(text("INSERT INTO users (id,username,password_hash,role,active,created_at) VALUES (1,'metadata_migration_fixture','nonlogin','admin',true,:at)"),{'at':at})
    db.execute(text("INSERT INTO credentials (id,user_id,token_hash,kind,name,created_at,expires_at,revoked) VALUES (1,1,:hash,'device','fixture',:at,:expiry,false)"),{'hash':'a'*64,'at':at,'expiry':at+timedelta(days=1)})
    db.execute(text("INSERT INTO user_preferences(user_id,schema_version,revision,values_json,updated_at) VALUES (1,1,3,'{}',:at)"),{'at':at})
    db.execute(text("INSERT INTO item_metadata(region,item_id,name,status,namespace,checked_at,resolved_at,retry_after,synthetic) VALUES ('us',720,'Preserved fixture name','available','static-forever-us',:at,:at,:retry,false)"),{'at':at,'retry':at+timedelta(days=30)})

# Seed nonempty asking-price/history observations using only baseline-compatible models.
from market.models import Market
from market.ingest import ingest
from sqlalchemy.orm import Session
with Session(engine) as db,db.begin():
    market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic migration fixture')
    db.add(market);db.flush()
    ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":720},"quantity":2,"buyout":400}]}',request_key='migration-fixture',synthetic=True)

queries={'users':'select id,username,password_hash,role,active,created_at from users order by id','credentials':'select * from credentials order by id',
    'preferences':'select * from user_preferences order by user_id',
    'names':'select region,item_id,name,status,namespace,checked_at,resolved_at,retry_after,synthetic from item_metadata order by region,item_id',
    'observations':'select * from observations order by id','listings':'select * from listings order by snapshot_id,auction_id',
    'statistics':'select * from snapshot_statistics order by snapshot_id,item_id,variant_key'}
def originals():
    with engine.connect() as db:
        return {table:[dict(row) for row in db.execute(text(query)).mappings()] for table,query in queries.items()}

before=originals();migrate('upgrade','head');migrate('check');assert originals()==before
from market.models import MetadataProvider
with Session(engine) as db,db.begin():
    upgraded_revision=db.scalar(text('SELECT version_num FROM alembic_version'))
    db.add(MetadataProvider(provider='everloot',credential=b'synthetic-envelope',credential_key_id='fixture'))
rejected=migrate('downgrade','0013',success=False)
assert rejected.returncode and 'Export metadata and provider credentials' in rejected.stderr
with engine.begin() as db:
    assert db.scalar(text('select version_num from alembic_version'))==upgraded_revision
    db.execute(text('delete from metadata_providers'))
migrate('downgrade','0013');assert originals()==before
migrate('upgrade','head');migrate('check');assert originals()==before
print(json.dumps({'database':'market_test','revision':upgraded_revision,'existing_rows_preserved':True,
    'populated_downgrade_refused':True,'empty_downgrade_reupgrade':True,'synthetic_only':True}))
