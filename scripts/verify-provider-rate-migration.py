"""Disposable PostgreSQL preservation/downgrade rehearsal. Never production."""
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
url = make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database != 'market_test':
    raise SystemExit('Refusing non-test PostgreSQL database; use disposable market_test')
engine = create_engine(url)


def migrate(*args, success=True):
    result = subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=ROOT/'backend', capture_output=True, text=True)
    if success and result.returncode: raise RuntimeError(result.stderr)
    return result


with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'))
    db.execute(text('CREATE SCHEMA public'))
migrate('upgrade', 'bridge_20261115')
from datetime import datetime, timezone
at = datetime.now(timezone.utc)
with engine.begin() as db:
    db.execute(text("INSERT INTO metadata_providers (provider,enabled,automatic,hourly_budget,daily_budget,hour_used,day_used,hour_start,day_start,next_request_at,cooldown_until,credential,credential_key_id,credential_status,validation_requested,validation_revision) VALUES ('foreverdb',false,false,60,500,44,333,:at,:at,:next,:cool,:secret,'fixture','connected',false,4)"),
        {'at':at,'next':at+timedelta(seconds=3),'cool':at+timedelta(hours=2),'secret':b'synthetic-encrypted-envelope-only'})
    original = dict(db.execute(text('SELECT * FROM metadata_providers')).mappings().one())
migrate('upgrade','head')
migrate('check')
with engine.begin() as db:
    after = dict(db.execute(text('SELECT * FROM metadata_providers')).mappings().one())
    assert {key:after[key] for key in original} == original
    assert after['rate_config'] is None and after['rate_streak'] == 0
    db.execute(text("INSERT INTO metadata_quota_buckets VALUES ('foreverdb',60,:at,1)"), {'at':at})
    db.execute(text("UPDATE metadata_providers SET rate_config='{}'"))
rejected=migrate('downgrade','bridge_20261115',success=False)
assert rejected.returncode and 'Export provider rate settings and accounting' in rejected.stderr
with engine.begin() as db:
    assert db.scalar(text('SELECT version_num FROM alembic_version')) == 'rates_20261115'
    assert db.scalar(text('SELECT used FROM metadata_quota_buckets')) == 1
    db.execute(text('DELETE FROM metadata_quota_buckets'))
    db.execute(text('UPDATE metadata_providers SET rate_config=NULL'))
migrate('downgrade','bridge_20261115')
with engine.connect() as db:
    assert dict(db.execute(text('SELECT * FROM metadata_providers')).mappings().one()) == original
migrate('upgrade','head')
migrate('check')
print(json.dumps({'origin':'synthetic','database':'market_test','baseline_revision':'bridge_20261115',
    'head_revision':'rates_20261115','settings_credentials_usage_cooldown_preserved':True,
    'populated_downgrade_refused':True,'empty_rate_state_downgrade_reupgrade':True}))
