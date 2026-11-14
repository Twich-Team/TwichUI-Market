"""Unchanged source payloads can still change compact rolling valuations."""
from datetime import timedelta, timezone
import json
from sqlalchemy import select
from market import sync_api
from market.db import now
from market.ingest import ingest
from market.models import Market, Observation, Snapshot
from market.sync_generation import signature


def seed(database, stamp, *, price=100, synthetic=False):
    with database.begin() as db:
        market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic generation fixture',verified=True)
        db.add(market);db.flush();market_id=market.id
        add(db,market_id,'initial',stamp,price=price,synthetic=synthetic)
        return market_id


def add(db, market, key, stamp, *, price=100, synthetic=False):
    # Synthetic fixture regardless of provenance flag; the flag is varied to test warnings.
    return ingest(db,market,json.dumps({'auctions':[{'id':1,'item':{'id':1},'quantity':1,'buyout':price}]}).encode(),
        request_key=key,retrieved_at=stamp,synthetic=synthetic)


def fail_compact(*args, **kwargs):
    raise AssertionError('unchanged generation must not scan or price each variant')


def test_same_day_unchanged_payload_skips_variant_work_and_advances_cursor(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().replace(hour=10,minute=0,second=0,microsecond=0)
    market=seed(database,stamp);path=f'/api/v1/sync/markets/{market}'
    initial=owner.get(path).json()
    with database.begin() as db:add(db,market,'conditional-check',stamp+timedelta(minutes=5))
    monkeypatch.setattr(sync_api,'compact',fail_compact)
    result=owner.get(path,params={'cursor':initial['cursor']});assert result.status_code==200,result.text
    page=result.json();assert page['changes']==[] and not page['has_more']
    assert page['target_observation_id']!=initial['target_observation_id'] and page['cursor']!=initial['cursor']
    assert page['observed_at']!=initial['observed_at']


def test_unchanged_payload_across_utc_day_updates_coverage(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().astimezone(timezone.utc).replace(hour=23,minute=59,second=0,microsecond=0)-timedelta(days=1)
    market=seed(database,stamp);path=f'/api/v1/sync/markets/{market}';initial=owner.get(path).json()
    with database.begin() as db:add(db,market,'new-utc-day',stamp+timedelta(minutes=2))
    page=owner.get(path,params={'cursor':initial['cursor']}).json()
    assert page['changes'][0]['value']['coverage_days']==2
    assert page['changes'][0]['value']['market_coverage_days']==2


def test_precise_fourteen_day_boundary_changes_reference_with_same_snapshot(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().replace(hour=10,minute=0,second=0,microsecond=0)
    market=seed(database,stamp-timedelta(days=14)+timedelta(seconds=1),price=300)
    with database.begin() as db:add(db,market,'head',stamp)
    path=f'/api/v1/sync/markets/{market}';initial=owner.get(path).json();assert initial['changes'][0]['value']['market_value']=='200'
    with database.begin() as db:add(db,market,'cross-cutoff',stamp+timedelta(seconds=2))
    page=owner.get(path,params={'cursor':initial['cursor']}).json()
    value=page['changes'][0]['value'];assert value['market_value']=='100' and value['historical_value']=='200'
    assert value['market_coverage_days']==1


def test_sixty_day_boundary_expires_history_without_upstream_change(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().replace(hour=10,minute=0,second=0,microsecond=0)
    market=seed(database,stamp-timedelta(days=60)+timedelta(seconds=1),price=300)
    with database.begin() as db:add(db,market,'head',stamp)
    path=f'/api/v1/sync/markets/{market}';initial=owner.get(path).json();assert initial['changes'][0]['value']['historical_value']=='200'
    with database.begin() as db:add(db,market,'cross-cutoff',stamp+timedelta(seconds=2))
    page=owner.get(path,params={'cursor':initial['cursor']}).json()
    assert page['changes'][0]['value']['historical_value']=='100' and page['changes'][0]['value']['coverage_days']==1


def test_non_winning_synthetic_observation_changes_warning_and_noop_preserves_it(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().replace(hour=10,minute=0,second=0,microsecond=0)
    market=seed(database,stamp);path=f'/api/v1/sync/markets/{market}';initial=owner.get(path).json();assert not initial['synthetic']
    with database.begin() as db:add(db,market,'late-synthetic-earlier-same-day',stamp-timedelta(minutes=5),synthetic=True)
    page=owner.get(path,params={'cursor':initial['cursor']}).json()
    assert page['synthetic'] and page['changes'][0]['value']['synthetic']
    monkeypatch.setattr(sync_api,'compact',fail_compact)
    noop=owner.get(path,params={'cursor':page['cursor']}).json();assert noop['changes']==[] and noop['synthetic']
    metadata=owner.get(f'/api/v1/companion/markets/{market}/observations/'+page['target_observation_id']).json()
    assert metadata['observation_id']==initial['target_observation_id']
    assert metadata['watermark_observation_id']==page['target_observation_id']
    assert not metadata['synthetic'] and metadata['valuation_synthetic']


def test_irrelevant_late_history_keeps_generation_and_historical_metadata_is_watermark_bound(owner,database,monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-generation-key-over-32-characters')
    stamp=now().replace(hour=10,minute=0,second=0,microsecond=0)
    market=seed(database,stamp);path=f'/api/v1/sync/markets/{market}';initial=owner.get(path).json()
    old=owner.get(f'/api/v1/companion/markets/{market}/observations/'+initial['target_observation_id']).json()
    with database.begin() as db:add(db,market,'outside-window',stamp-timedelta(days=61),price=999,synthetic=True)
    monkeypatch.setattr(sync_api,'compact',fail_compact)
    page=owner.get(path,params={'cursor':initial['cursor']}).json();assert page['changes']==[] and not page['synthetic']
    after=owner.get(f'/api/v1/companion/markets/{market}/observations/'+initial['target_observation_id']).json()
    assert old==after
    with database.begin() as db:add(db,market,'relevant-late-history',stamp-timedelta(days=2),price=999)
    still=owner.get(f'/api/v1/companion/markets/{market}/observations/'+initial['target_observation_id']).json()
    assert still==old


def test_generation_refuses_missing_retained_daily_statistics(database):
    stamp=now();market=seed(database,stamp-timedelta(days=5),price=300)
    with database.begin() as db:
        old=db.scalar(select(Observation).where(Observation.market_id==market))
        add(db,market,'head',stamp)
        db.get(Snapshot,old.snapshot_id).statistics_retained=False
        db.flush();head=db.scalar(select(Observation).where(Observation.market_id==market).order_by(Observation.id.desc()))
        assert signature(db,head,head.id) is None
