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
