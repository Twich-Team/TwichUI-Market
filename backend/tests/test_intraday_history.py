"""True hourly history from observations/statistics; all records are isolated fixtures."""
import json
from datetime import datetime,timedelta,timezone
import pytest
from sqlalchemy import select,delete
from market.db import now
from market.ingest import ingest
from market.models import Market,Observation,Snapshot,SnapshotStatistic
from market.intraday_history import intraday


def seed(database,stamps=None):
    at=now().replace(minute=0,second=0,microsecond=0)-timedelta(minutes=10)
    stamps=stamps or [at-timedelta(hours=49),at-timedelta(hours=30),at-timedelta(hours=3,minutes=20),at-timedelta(hours=3),at-timedelta(hours=1),at]
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic intraday')
        other=Market(region='eu',ruleset_id=2,house_id=114,source_kind='auctions',label='Other synthetic market')
        db.add_all([market,other]);db.flush();market_id=market.id
        observations=[]
        for index,stamp in enumerate(stamps):
            obs=ingest(db,market_id,json.dumps({'auctions':[
                {'id':1,'item':{'id':25},'quantity':2,'buyout':200+index*20},
                {'id':2,'item':{'id':25,'bonus_lists':[1]},'quantity':1,'buyout':9999},
                {'id':3,'item':{'id':35},'quantity':1,'buyout':7777},
            ]}).encode(),request_key=f'hour-{index}',retrieved_at=stamp,synthetic=True)
            observations.append(obs.id)
        ingest(db,other.id,b'{"auctions":[{"id":1,"item":{"id":25},"quantity":1,"buyout":999999}]}',request_key='other',retrieved_at=stamps[-1],synthetic=True)
        variants=list(db.scalars(select(SnapshotStatistic.variant_key).where(SnapshotStatistic.item_id==25).distinct()))
        variant=next(v for v in variants if db.scalar(select(SnapshotStatistic.recent_price).where(SnapshotStatistic.variant_key==v).limit(1))!=9999)
    return at,market_id,variant,observations


def test_hourly_latest_selection_windows_money_identity_and_real_provenance(owner,database,monkeypatch):
    at,market,variant,observations=seed(database)
    monkeypatch.setattr('market.intraday_history.now',lambda:at)
    path=f'/api/v1/markets/{market}/items/25/{variant}/intraday-history'
    result=owner.get(path+'?hours=24');assert result.status_code==200,result.text
    data=result.json();assert data['hours']==24 and data['source_observation_count']==4
    assert len(data['points'])==3 and [r['recent_price'] for r in data['points']]==['130','140','150']
    assert data['points'][0]['observation_id']==str(observations[3])
    assert data['points'][0]['observations_in_hour']==2
    assert all(r['snapshot_id'] and r['namespace'] and len(r['payload_hash'])==64 for r in data['points'])
    assert len(owner.get(path+'?hours=48').json()['points'])==4
    assert owner.get(path+'?hours=25').status_code==422
    assert owner.get(path+'?hours=9999').status_code==422
    assert owner.get(path.replace(variant,'bad')).status_code==422
    owner.cookies.clear();assert owner.get(path).status_code==401


def test_compacted_absent_unsupported_and_sparse_are_not_fabricated(database):
    at,market,variant,observations=seed(database)
    with database.begin() as db:
        first=db.get(Observation,observations[3]);db.get(Snapshot,first.snapshot_id).statistics_retained=False
        second=db.get(Observation,observations[4]);db.execute(delete(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==second.snapshot_id,SnapshotStatistic.variant_key==variant,SnapshotStatistic.item_id==25))
        third=db.get(Observation,observations[5]);db.get(SnapshotStatistic,(third.snapshot_id,25,variant)).algorithm='unsupported-fixture'
    with database() as db:
        data=intraday(db,market,25,variant,24,at=at)
    assert [r['status'] for r in data['points']]==['compacted','not_listed','unsupported_algorithm']
    assert [r['supply'] for r in data['points']]==[None,0,None]
    assert all(r['recent_price'] is None for r in data['points'])
    with database() as db:assert intraday(db,market,25,variant,24,at=at+timedelta(days=10))['points']==[]


@pytest.mark.parametrize('stamps',[
 ['2026-11-01T05:10:00+00:00','2026-11-01T06:10:00+00:00'], # repeated 1 AM in New York
 ['2026-03-08T06:10:00+00:00','2026-03-08T07:10:00+00:00'], # skipped local hour
 ['2026-11-16T23:59:00+00:00','2026-11-17T00:01:00+00:00'],
])
def test_utc_hour_boundaries_remain_distinct_across_dst_and_midnight(database,stamps):
    times=[datetime.fromisoformat(s) for s in stamps]
    _,market,variant,_=seed(database,times)
    with database() as db:data=intraday(db,market,25,variant,24,at=times[-1])
    assert len(data['points'])==2
    assert data['points'][0]['bucket_start']!=data['points'][1]['bucket_start']
    assert [r['observed_at'] for r in data['points']]==stamps


def test_scan_guard_never_returns_a_silent_truncated_history(owner,database,monkeypatch):
    at,market,variant,_=seed(database)
    monkeypatch.setattr('market.intraday_history.now',lambda:at)
    monkeypatch.setattr('market.intraday_history.MAX_OBSERVATIONS',2)
    response=owner.get(f'/api/v1/markets/{market}/items/25/{variant}/intraday-history?hours=48')
    assert response.status_code==503 and 'No partial history' in response.json()['detail']
