"""Populated source/identity preservation; destructive only on market_test."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
url = make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database != 'market_test':
    raise SystemExit('Refusing non-test PostgreSQL database')
engine = create_engine(url)

def migrate(*args, success=True):
    result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=root/'backend', capture_output=True, text=True)
    if success and result.returncode: raise RuntimeError(result.stderr)
    return result

with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'))
    db.execute(text('CREATE SCHEMA public'))
migrate('upgrade', 'recovery_20261117')
with engine.begin() as db:
    db.execute(text("INSERT INTO users(id,username,password_hash,role,active,created_at) VALUES(1,'synthetic-owner','nonlogin','admin',true,now())"))
    db.execute(text("INSERT INTO markets(id,region,ruleset_id,house_id,source_kind,label,enabled,verified,interval_seconds,next_check,failures) VALUES(2,'us',2,114,'auctions','Synthetic preserved market',true,true,300,now(),0)"))
    db.execute(text("INSERT INTO snapshots(id,market_id,content_hash,created_at,listing_count,raw_retained,statistics_retained) VALUES(17,2,:hash,now(),1,true,true)"), {'hash':'a'*64})
    db.execute(text("INSERT INTO observations(id,market_id,snapshot_id,request_key,retrieved_at,namespace,payload_hash,payload_bytes,synthetic) VALUES(23,2,17,'synthetic-original',now(),'dynamic-forever-us',:hash,123,true)"), {'hash':'b'*64})
    descriptor = '{"id":25}'
    variant = hashlib.sha256(descriptor.encode()).hexdigest()
    db.execute(text("INSERT INTO listings(id,snapshot_id,auction_id,item_id,variant,variant_key,quantity,buyout) VALUES(31,17,9007199254740993,25,:descriptor,:variant,2,999)"), {'descriptor':descriptor,'variant':variant})
    db.execute(text("INSERT INTO snapshot_statistics(snapshot_id,item_id,variant_key,algorithm,recent_price,lowest_buyout,supply,priced_supply,listing_count) VALUES(17,25,:variant,'asking-v1-provisional',500,500,2,2,1)"), {'variant':variant})
    db.execute(text("INSERT INTO daily_observations(market_id,day,observation_id) VALUES(2,current_date,23)"))
columns = {table:[c['name'] for c in inspect(engine).get_columns(table)]
           for table in inspect(engine).get_table_names() if table!='alembic_version'}
def fingerprints():
    with engine.connect() as db:
        return {table:hashlib.sha256(repr(db.execute(text('SELECT '+','.join('"'+c+'"' for c in cols)+
            ' FROM "'+table+'" ORDER BY '+','.join(str(i+1) for i in range(len(cols))))).all()).encode()).hexdigest()
            for table,cols in columns.items()}
before = fingerprints()
migrate('upgrade', 'head');migrate('check')
assert before == fingerprints()
with engine.connect() as db:
    assert db.scalar(text('SELECT unified_coverage FROM markets WHERE id=2')) is False
    assert db.scalar(text("SELECT source_kind FROM listings WHERE id=31")) == 'auctions'
migrate('downgrade', 'recovery_20261117')
assert before == fingerprints()
migrate('upgrade', 'head');migrate('check')
assert before == fingerprints()
with engine.begin() as db:
    expected_head = db.scalar(text('SELECT version_num FROM alembic_version'))
    db.execute(text("INSERT INTO market_feeds(market_id,source_kind,verification,enabled,failures) VALUES(2,'commodities','synthetic-evidence',false,0)"))
result = migrate('downgrade', 'recovery_20261117', success=False)
assert result.returncode and 'Retain feed evidence' in result.stderr
assert before == fingerprints()
with engine.connect() as db:
    assert db.scalar(text('SELECT count(*) FROM market_feeds')) == 1
    head = db.scalar(text('SELECT version_num FROM alembic_version'))
    # PostgreSQL rolls back the entire rejected downgrade, including any newer
    # additive migrations preceding the protected feed-evidence migration.
    assert head == expected_head
migrate('check')
print(json.dumps({'origin':'synthetic','database':'market_test','head':head,'preserved_original_tables':len(columns),
    'preserved_original_column_hashes':before,'history_and_large_auction_id_preserved':True,
    'collection_not_activated_by_migration':True,'empty_feed_round_trip':True,'populated_evidence_downgrade_refused':True}))
