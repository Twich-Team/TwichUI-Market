"""Destructive schema rehearsal restricted twice to PostgreSQL market_test.

Checks an actual 0012 legacy account/token/preference upgrade, populated native
downgrade refusal, safe empty-native downgrade and full empty-schema round trip.
Never accepts the production or restoration database.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

directory = Path.cwd()
backend = directory if (directory / 'alembic.ini').is_file() else directory / 'backend'
if not (backend / 'alembic.ini').is_file():
    raise SystemExit('Run from the repository or backend directory')
url = make_url(os.environ['DATABASE_URL'])
if url.database != 'market_test' or not url.drivername.startswith('postgresql'):
    raise SystemExit('Refusing destructive rehearsal outside PostgreSQL market_test')
engine = create_engine(url)
with engine.begin() as connection:
    assert connection.scalar(text('SELECT current_database()')) == 'market_test'
    connection.execute(text('DROP SCHEMA public CASCADE'))
    connection.execute(text('CREATE SCHEMA public'))


def alembic(*arguments, succeed=True):
    result = subprocess.run(['alembic', *arguments], cwd=backend, text=True, capture_output=True)
    if succeed and result.returncode:
        raise RuntimeError('Isolated Alembic operation failed: ' + result.stderr)
    return result


alembic('upgrade', '0012')
stamp = datetime.now(timezone.utc)
with engine.begin() as connection:
    connection.execute(text("INSERT INTO users (id,username,password_hash,role,active,created_at) VALUES (1,'migration_fixture','synthetic-nonlogin','member',true,:at)"), {'at': stamp})
    connection.execute(text("""INSERT INTO credentials (id,user_id,token_hash,kind,name,created_at,expires_at,revoked)
        VALUES (1,1,:digest,'device','Legacy migration fixture',:at,:expires,false)"""),
        {'digest': hashlib.sha256(b'synthetic-legacy-credential').hexdigest(), 'at': stamp, 'expires': stamp + timedelta(days=1)})
    connection.execute(text("INSERT INTO user_preferences (user_id,schema_version,revision,values_json,updated_at) VALUES (1,1,7,:values,:at)"),
        {'values': '{"explorer_days":60}', 'at': stamp})


def originals():
    with engine.connect() as connection:
        return {table: connection.scalar(text(f'SELECT row_to_json(t) FROM {table} t'))
                for table in ('users', 'credentials', 'user_preferences')}


before = originals()
alembic('upgrade', 'head')
alembic('check')
after = originals()
assert after['credentials'].pop('companion_device_id') is None
assert before == after

sys.path.insert(0, str(backend))
from sqlalchemy.orm import Session
from market.models import CompanionAuthorization

with Session(engine) as db, db.begin():
    state = secrets.token_urlsafe(32)
    db.add(CompanionAuthorization(id=secrets.token_urlsafe(32), device_name='Synthetic migration PC',
        platform='Windows', app_version='2.0.0', issuer_origin='https://localhost',
        redirect_uri='http://127.0.0.1:43123/companion/callback', state_value=state,
        state_hash=hashlib.sha256(state.encode()).hexdigest(), code_challenge=secrets.token_urlsafe(32),
        expires_at=stamp + timedelta(minutes=5)))
rejected = alembic('downgrade', '0012', succeed=False)
assert rejected.returncode and 'Export native authorization/device records' in rejected.stderr
with engine.begin() as connection:
    assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0013'
    assert connection.scalar(text('SELECT count(*) FROM companion_authorizations')) == 1
    connection.execute(text('DELETE FROM companion_authorizations'))
alembic('downgrade', '0012')
assert originals() == before
# The existing preferences downgrade also requires explicit removal; only this
# synthetic fixture is cleared to rehearse the complete empty-table round trip.
with engine.begin() as connection:
    connection.execute(text('DELETE FROM user_preferences'))
alembic('downgrade', 'base')
alembic('upgrade', 'head')
alembic('check')
print(json.dumps({'database': 'market_test', 'legacy_0012_rows_preserved': True,
    'native_populated_downgrade_refused': True, 'rejected_downgrade_retained_revision_and_rows': True,
    'empty_native_downgrade_preserved_legacy_rows': True, 'full_upgrade_parity_round_trip': True,
    'revision': '0013', 'synthetic_only': True}))
