"""Archive columns preserve original owned/security rows; disposable market_test only."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
ROOT=Path(__file__).resolve().parents[1]
url=make_url(os.environ['DATABASE_URL'])
if not url.drivername.startswith('postgresql') or url.database!='market_test':
    raise SystemExit('Refusing non-test PostgreSQL database')
engine=create_engine(url)
def migrate(*args,success=True):
    result=subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT/'backend',capture_output=True,text=True)
    if success and result.returncode:raise RuntimeError(result.stderr)
    return result
with engine.begin() as db:
    db.execute(text('DROP SCHEMA public CASCADE'));db.execute(text('CREATE SCHEMA public'))
migrate('upgrade','archive_20261116')
from market.models import User,CompanionDevice,Credential,SecurityEvent,UserPreference
from market.db import now
from datetime import timedelta
with engine.begin() as db:
    # Core inserts list original fields and do not assume future ORM schema columns.
    db.execute(User.__table__.insert().values(id=1,username='synthetic-migration',password_hash='nonlogin',role='admin',active=True))
    db.execute(CompanionDevice.__table__.insert().values(id=1,user_id=1,name='Synthetic retained PC',platform='Windows',app_version='2.0.0-beta.3',issuer_origin='https://synthetic.invalid',expires_at=now()+timedelta(days=1),refresh_expires_at=now()+timedelta(days=30),refresh_hash='a'*64))
    db.execute(Credential.__table__.insert().values(id=1,user_id=1,kind='companion',name='Synthetic retained PC',token_hash='b'*64,expires_at=now()+timedelta(hours=1),companion_device_id=1))
    db.execute(SecurityEvent.__table__.insert().values(actor_id=1,action='synthetic.migration.evidence'))
    db.execute(UserPreference.__table__.insert().values(user_id=1,values_json='{}'))
columns={t:[c['name'] for c in inspect(engine).get_columns(t)] for t in ('users','companion_devices','credentials','security_events','user_preferences')}
def fingerprint():
    with engine.connect() as db:
        return {t:hashlib.sha256(repr(db.execute(text('SELECT '+','.join('"'+c+'"' for c in cols)+' FROM '+t+' ORDER BY 1')).all()).encode()).hexdigest() for t,cols in columns.items()}
before=fingerprint();migrate('upgrade','head');migrate('check');assert fingerprint()==before
for table in ('users','companion_devices'):
    with engine.begin() as db:db.execute(text('UPDATE '+table+' SET archived_at=now() WHERE id=1'))
    rejected=migrate('downgrade','archive_20261116',success=False)
    assert rejected.returncode and 'Restore archived entries' in rejected.stderr
    with engine.begin() as db:
        assert db.scalar(text('SELECT version_num FROM alembic_version'))=='usability_20261117'
        db.execute(text('UPDATE '+table+' SET archived_at=NULL WHERE id=1'))
    assert fingerprint()==before
migrate('downgrade','archive_20261116');assert fingerprint()==before
migrate('upgrade','head');migrate('check');assert fingerprint()==before
print(json.dumps({'origin':'synthetic','database':'market_test','original_account_device_credential_preference_audit_rows_preserved':True,'both_populated_archive_downgrades_refused':True,'round_trip':True}))
