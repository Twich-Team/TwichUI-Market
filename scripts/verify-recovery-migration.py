"""Additive recovery evidence preservation. Destructive only on isolated market_test."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
root=Path(__file__).resolve().parents[1]
url=make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database!='market_test':raise SystemExit('Refusing non-test PostgreSQL database')
engine=create_engine(url)
def migrate(*args,success=True):
    p=subprocess.run([sys.executable,'-m','alembic',*args],cwd=root/'backend',capture_output=True,text=True)
    if success and p.returncode:raise RuntimeError(p.stderr)
    return p
with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'));db.execute(text('CREATE SCHEMA public'))
migrate('upgrade','usability_20261117')
with engine.begin() as db:
    db.execute(text("INSERT INTO users(id,username,password_hash,role,active,created_at) VALUES(1,'synthetic-preserved','nonlogin','admin',true,now())"))
    db.execute(text("INSERT INTO metadata_sources(region,item_id,locale,provider,status,revision,http_status,checked_at,retry_at,fields_json,source_json) VALUES('us',25,'en_US','blizzard','metadata_unavailable',0,404,now(),now()+interval '7 days',NULL,NULL)"))
columns={table:[c['name'] for c in inspect(engine).get_columns(table)] for table in inspect(engine).get_table_names() if table!='alembic_version'}
def fingerprints():
    with engine.connect() as db:
        return {t:hashlib.sha256(repr(db.execute(text('SELECT '+','.join('"'+c+'"' for c in cols)+' FROM "'+t+'" ORDER BY '+','.join(str(i+1) for i in range(len(cols))))).all()).encode()).hexdigest() for t,cols in columns.items()}
before=fingerprints();migrate('upgrade','head');migrate('check');assert before==fingerprints()
with engine.connect() as db: protected_head=db.scalar(text('SELECT version_num FROM alembic_version'))
migrate('downgrade','usability_20261117');assert before==fingerprints()
migrate('upgrade','head');migrate('check');assert before==fingerprints()
with engine.begin() as db:
    db.execute(text("INSERT INTO metadata_attempts(provider,region,item_id,kind,started_at,state) VALUES('blizzard','us',25,'metadata',now(),'reserved')"))
p=migrate('downgrade','usability_20261117',success=False)
assert p.returncode and 'Retain recovery evidence' in p.stderr
with engine.connect() as db:
    assert db.scalar(text('select count(*) from metadata_attempts'))==1
    assert db.scalar(text('select version_num from alembic_version'))==protected_head
assert before==fingerprints()
print(json.dumps({'origin':'synthetic','database':'market_test','head':protected_head,'original_tables_preserved':len(columns),'original_negative_cache_preserved':True,'empty_round_trip':True,'populated_evidence_downgrade_refused':True}))
