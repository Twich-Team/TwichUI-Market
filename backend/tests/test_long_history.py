import json
from datetime import timedelta,timezone
from sqlalchemy import func,select
from market.db import now
from market.ingest import ingest
from market.maintenance import maintain
from market.models import DailyObservation,Listing,Market,Observation,Snapshot,SnapshotStatistic
from market.pricing import daily_history,values


def sample(db,market,key,at,price):
    body=json.dumps({'auctions':[{'id':1,'item':{'id':12363},'quantity':10,'buyout':price}]}).encode()
    return ingest(db,market,body,request_key=key,retrieved_at=at,synthetic=True)


def test_raw_cleanup_preserves_prices_daily_provenance_and_current_snapshot(database):
    at=now().replace(hour=12,minute=0,second=0,microsecond=0)-timedelta(days=1)
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Long history fixture')
        db.add(market);db.flush();market_id=market.id
        early=sample(db,market_id,'old-early',at-timedelta(days=500,hours=1),5000)
        daily=sample(db,market_id,'old-daily',at-timedelta(days=500),1000)
        week=sample(db,market_id,'week',at-timedelta(days=7),2000)
        current=sample(db,market_id,'current',at,3000)
        variant=db.scalar(select(SnapshotStatistic.variant_key).where(SnapshotStatistic.snapshot_id==current.snapshot_id))
        before=values(db,market_id,12363,variant,at=at)
        ids=early.snapshot_id,daily.snapshot_id,week.snapshot_id,current.snapshot_id
    maintain(database,apply=True,at=at,compact=True)
    with database() as db:
        after=values(db,market_id,12363,variant,at=at)
        assert before==after
        assert not db.get(Snapshot,ids[0]).statistics_retained
        assert db.get(Snapshot,ids[1]).statistics_retained
        assert not db.get(Snapshot,ids[1]).raw_retained
        assert db.get(Snapshot,ids[3]).raw_retained
        assert db.scalar(select(func.count()).select_from(Observation))==4
        history=daily_history(db,market_id,12363,variant,730,at=at)
        assert [row['recent_price'] for row in history['points']]==[100,200,300]
        assert history['points'][0]['namespace']=='dynamic-forever-eu'
        assert history['points'][0]['payload_hash']
    # Repeated contents can rehydrate a previously pruned snapshot safely.
    with database.begin() as db:
        restored=sample(db,market_id,'rehydrated',at,5000)
        assert restored.snapshot_id==ids[0]
        assert db.get(Snapshot,ids[0]).statistics_retained
        assert db.get(Snapshot,ids[0]).raw_retained
        assert db.scalar(select(func.count()).select_from(Listing).where(Listing.snapshot_id==ids[0]))==1


def test_daily_index_uses_utc_and_late_imports_do_not_replace_later_observation(database):
    at=now().replace(hour=22,minute=0,second=0,microsecond=0)-timedelta(days=2)
    with database.begin() as db:
        market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='UTC fixture')
        db.add(market);db.flush()
        latest=sample(db,market.id,'utc',at.astimezone(timezone(timedelta(hours=3))),2000)
        sample(db,market.id,'late',at-timedelta(hours=1),1000)
        day=db.get(DailyObservation,(market.id,at.date()))
        assert day.observation_id==latest.id
