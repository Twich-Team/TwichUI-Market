from datetime import timedelta
from sqlalchemy import func,select
from market.db import now
from market.maintenance import maintain
from market.ingest import ingest
from market.models import CollectionRun,Listing,Market,Observation,SecurityEvent


def test_operational_retention_dry_run_and_apply(database):
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic retention fixture')
        db.add(market)
        db.flush()
        ingest(db,market.id,b'{"auctions":[{"id":1,"item":{"id":2},"quantity":1,"buyout":100}]}',
               request_key='old-history',retrieved_at=now()-timedelta(days=500),synthetic=True)
        db.add(CollectionRun(market_id=market.id,status='failed',checked_at=now()-timedelta(days=100)))
        db.add(CollectionRun(market_id=market.id,status='collected',checked_at=now()))
        db.add(SecurityEvent(action='old.fixture',created_at=now()-timedelta(days=400)))
    result=maintain(database)
    assert result['deleted']['collection_runs']==1
    assert result['deleted']['security_events']==1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(CollectionRun))==2
    assert maintain(database,apply=True)['historical_observations']=='preserved_indefinitely'
    with database() as db:
        assert db.scalar(select(func.count()).select_from(CollectionRun))==1
        assert db.scalar(select(func.count()).select_from(SecurityEvent))==0
        assert db.scalar(select(func.count()).select_from(Market))==1
        assert db.scalar(select(func.count()).select_from(Observation))==1
        assert db.scalar(select(func.count()).select_from(Listing))==1


def test_referenced_sessions_and_companion_audit_credentials_are_retained(owner, database, monkeypatch):
    from test_companion_auth import authorize
    from market.models import Credential, CompanionAuthorization
    from market.security import issue
    monkeypatch.setenv("SYNC_CURSOR_SECRET", "synthetic-maintenance-only-signing-key-32-characters")
    tokens=authorize(owner)
    with database.begin() as db:
        approvals=list(db.scalars(select(CompanionAuthorization)))
        approved_id=approvals[0].approved_credential_id
        db.get(Credential,approved_id).expires_at=now()-timedelta(days=31)
        native=db.scalar(select(Credential).where(Credential.companion_device_id==tokens['device']['id']))
        native.expires_at=now()-timedelta(days=31)
        native_id=native.id
    maintain(database,apply=True)
    with database() as db:
        assert db.get(Credential,approved_id) is not None
        assert db.get(Credential,native_id) is not None
        assert db.scalar(select(CompanionAuthorization)) is not None


def test_legacy_history_application_rejects_non_test_database_identity(database, monkeypatch):
    from sqlalchemy.engine import make_url
    import pytest
    # Only the engine label changes; the connection is still the disposable fixture.
    with database() as db: engine=db.bind
    monkeypatch.setattr(engine,'url',make_url('postgresql+psycopg://synthetic/production'))
    with pytest.raises(ValueError,match='signed bounded retention'):
        maintain(database,apply=True,compact=True)
