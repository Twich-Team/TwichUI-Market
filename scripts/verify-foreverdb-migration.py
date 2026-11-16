"""Disposable PostgreSQL rehearsal of additive ForeverDB queue/cache migration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]
url=make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database!='market_test':
    raise SystemExit('Refusing non-test PostgreSQL database; use disposable market_test')
engine=create_engine(url)
def migrate(*args,success=True):
    r=subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT/'backend',capture_output=True,text=True)
    if success and r.returncode:raise RuntimeError(r.stderr)
    return r
with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'));db.execute(text('CREATE SCHEMA public'))
migrate('upgrade','rates_20261115')
with engine.begin() as db:
    db.execute(text("INSERT INTO metadata_providers(provider,enabled,automatic,hourly_budget,daily_budget,hour_used,day_used,credential,credential_key_id,credential_status,validation_requested,validation_revision,rate_streak) VALUES ('foreverdb',true,true,150,500,17,321,:secret,'fixture','connected',false,2,0)"),{'secret':b'synthetic-encrypted-envelope'})
    db.execute(text("INSERT INTO metadata_sources(region,item_id,locale,provider,status,revision,fields_json,source_json) VALUES ('us',8188,'en_US','foreverdb','available',1,:fields,:source)"),{'fields':'{"name":"Synthetic retained item"}','source':'{"provider":"foreverdb","build":"1.60.1.70938"}'})
    db.execute(text("INSERT INTO metadata_jobs(id,mode,state,dedupe_key,providers_json,total,request_budget,requests_used,created_at,updated_at) VALUES(1,'single','paused','synthetic-migration','[\"foreverdb\"]',1,2,1,now(),now())"))
    db.execute(text("INSERT INTO metadata_tasks(job_id,provider,region,item_id,locale,state,attempts,available_at,updated_at) VALUES(1,'foreverdb','us',8188,'en_US','queued',1,now(),now())"))
    tables=('metadata_providers','metadata_sources','metadata_versions','metadata_jobs','metadata_tasks','item_metadata')
    columns={t:list(db.scalars(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=:t ORDER BY ordinal_position"),{'t':t})) for t in tables}
def fingerprint():
    with engine.connect() as db:
        return {t:hashlib.sha256(repr(db.execute(text('SELECT '+','.join('"'+c+'"' for c in cols)+' FROM '+t+' ORDER BY 1,2')).all()).encode()).hexdigest() for t,cols in columns.items()}
before=fingerprint();migrate('upgrade','head');migrate('check');assert fingerprint()==before
with engine.begin() as db:
    db.execute(text("""INSERT INTO metadata_resources(region,resource,"offset",status) VALUES('us','professions/alchemy',0,'pending')"""))
    db.execute(text("UPDATE metadata_tasks SET resource='professions/alchemy'"))
r=migrate('downgrade','rates_20261115',success=False)
assert r.returncode and 'Retain ForeverDB resource data' in r.stderr
with engine.begin() as db:
    assert db.scalar(text('SELECT version_num FROM alembic_version'))=='fdb_20261116'
    db.execute(text('DELETE FROM metadata_resources'));db.execute(text('UPDATE metadata_tasks SET resource=NULL'))
migrate('downgrade','rates_20261115');assert fingerprint()==before
migrate('upgrade','head');migrate('check');assert fingerprint()==before
print(json.dumps({'database':'market_test','baseline':'rates_20261115','head':'fdb_20261116','original_metadata_credentials_counters_and_jobs_preserved':True,'populated_resource_downgrade_refused':True,'upgrade_check_downgrade_reupgrade':True}))
