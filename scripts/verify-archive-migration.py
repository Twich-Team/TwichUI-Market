"""Additive archive migration preservation on disposable PostgreSQL only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]
url=make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database!='market_test':
    raise SystemExit('Refusing non-test PostgreSQL database; use disposable market_test')
engine=create_engine(url)
def migrate(*args):
    r=subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT/'backend',text=True,capture_output=True)
    if r.returncode:raise RuntimeError(r.stderr)
with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'));db.execute(text('CREATE SCHEMA public'))
migrate('upgrade','fdb_20261116')
from market.models import Market,User
from market.ingest import ingest
from sqlalchemy.orm import Session
with Session(engine) as db,db.begin():
    db.execute(text("INSERT INTO users(id,username,password_hash,role,active,created_at) VALUES(1,'archive_migration','nonlogin','member',true,now())"))
    market=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic only');db.add(market);db.flush()
    ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":720},"quantity":2,"buyout":400}]}',request_key='archive-migration-fixture',synthetic=True)
    db.execute(text("INSERT INTO user_preferences(user_id,schema_version,revision,values_json,updated_at) VALUES(1,1,3,'{}',now())"))
    mid=market.id
tables=sorted(set(inspect(engine).get_table_names())-{'alembic_version'})
columns={t:[c['name'] for c in inspect(engine).get_columns(t)] for t in tables}
def fingerprint():
    with engine.connect() as db:
        return {t:hashlib.sha256(repr(db.execute(text('SELECT row_to_json(t)::text FROM (SELECT '+','.join('\"'+c+'\"' for c in columns[t])+' FROM \"'+t+'\") t ORDER BY row_to_json(t)::text')).all()).encode()).hexdigest() for t in tables}
before=fingerprint();migrate('upgrade','head');migrate('check');assert fingerprint()==before
with engine.connect() as db: upgraded_revision=db.scalar(text('SELECT version_num FROM alembic_version'))
with engine.begin() as db:
    checkpoint='a'*64
    db.execute(text("INSERT INTO archive_checkpoints VALUES(:cp,:mid,1,1,'{}',now(),now()+interval '1 day')"),{'cp':checkpoint,'mid':mid})
    db.execute(text("INSERT INTO archive_members VALUES(:cp,0,1,'{}',true)"),{'cp':checkpoint})
    db.execute(text("INSERT INTO archive_digests VALUES(1,'synthetic',1,1,:sha,1)"),{'sha':'b'*64})
migrate('downgrade','fdb_20261116');assert fingerprint()==before
migrate('upgrade','head');migrate('check');assert fingerprint()==before
print(json.dumps({'origin':'synthetic','database':'market_test','baseline':'fdb_20261116','head':upgraded_revision,'original_tables_preserved':len(tables),'source_history_and_preferences_preserved':True,'only_disposable_archive_metadata_removed_on_downgrade':True,'upgrade_downgrade_reupgrade':True}))
