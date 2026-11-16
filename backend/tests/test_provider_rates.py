"""Synthetic quotas and mocked responses on the isolated market_test database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import pytest
from sqlalchemy import func, select
from market.db import now
from market.metadata_models import MetadataQuotaBucket
from market.models import MetadataJob, MetadataProvider, MetadataTask, SecurityEvent
from market.metadata_recovery import ensure_providers, enqueue, tick
from market.provider_rates import (RateLimits, accounting, configuration, cooldown, effective,
    observe, rate_view, reserve_budget, retry_delay, validate_configuration)
from market.provider_secrets import encrypt
from market.security import aware
from test_metadata_recovery import keyfile, setup, response, tooltip

AT = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def configured(db, ident='everloot', **changes):
    ensure_providers(db)
    row = db.get(MetadataProvider, ident)
    config = configuration(row, AT)
    config.update(changes)
    row.rate_config = json.dumps(config)
    row.hourly_budget, row.daily_budget = config['hourly_budget'], config['daily_budget']
    return row


def request_once(database, at, ident='everloot'):
    with database.begin() as db:
        row = db.get(MetadataProvider, ident)
        wait = reserve_budget(row, at)
        if wait is None: observe(row, 200, {}, at)
        return wait


def test_approved_foreverdb_allowance_preserves_every_guard_and_secret(owner, database, keyfile):
    setup(database, 'foreverdb')
    with database.begin() as db:
        row = db.get(MetadataProvider,'foreverdb')
        row.credential_key_id,row.credential = encrypt('foreverdb','fdb_synthetic_approved_key')
        row.validated_at = now()
        row.enabled = row.automatic = False
        row.hour_start,row.hour_used,row.day_start,row.day_used = now(),44,now(),333
        row.cooldown_until = now()+timedelta(hours=2)
        original = (row.credential,row.credential_key_id,row.cooldown_until)
        body = configuration(row)
    body.update(minute_budget=300,hourly_budget=10000,daily_budget=50000,minimum_interval=0.2)
    path='/api/v1/admin/metadata-providers/foreverdb/rate-limits'
    assert owner.patch(path,json=body).status_code == 422
    saved=owner.patch(path,json={**body,'entitlement_acknowledged':True})
    assert saved.status_code == 200
    assert saved.json()['rate_limits']['configured']['minute_budget'] == 300
    assert saved.json()['rate_limits']['limit_sources']['minute_budget'] == 'administrator_configured'
    with database() as db:
        row=db.get(MetadataProvider,'foreverdb')
        assert (row.credential,row.credential_key_id,row.cooldown_until) == original
        assert (row.hour_used,row.day_used) == (44,333)
        assert not row.enabled and not row.automatic
        assert db.scalar(select(func.count()).select_from(MetadataJob)) == 0
    assert 'fdb_synthetic' not in saved.text


@pytest.mark.parametrize('ident,changes',[
    ('blizzard',{'hourly_budget':241}),('blizzard',{'minimum_interval':1}),
    ('everloot',{'page_size':5000}),('everloot',{'hourly_budget':2000}),
    ('foreverdb',{'minute_budget':None}),('foreverdb',{'page_size':50}),
    ('thewowdb',{'requests_per_second':None,'burst_capacity':None}),
    ('everloot',{'requests_per_second':2,'burst_capacity':120}),
])
def test_provider_specific_safeguards(owner,database,ident,changes):
    with database.begin() as db:
        ensure_providers(db);body=configuration(db.get(MetadataProvider,ident))
    assert owner.patch(f'/api/v1/admin/metadata-providers/{ident}/rate-limits',json={**body,**changes,'entitlement_acknowledged':True}).status_code == 422


@pytest.mark.parametrize('changes',[
    {'hourly_budget':0},{'daily_budget':-1},{'hourly_budget':True},
    {'daily_budget':2**63},{'minimum_interval':0},{'minimum_interval':math.inf},
    {'minimum_interval':math.nan},{'max_concurrent':2},{'max_concurrent':0},
    {'requests_per_second':3},{'burst_capacity':121},{'page_size':5001},
])
def test_invalid_values_are_rejected(changes):
    body=dict(hourly_budget=20,daily_budget=100,minimum_interval=180)
    with pytest.raises(ValueError): RateLimits(**{**body,**changes})


def test_keyed_everloot_full_allowance_and_expiry_fallback(owner,database,keyfile):
    setup(database)
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot')
        row.credential_key_id,row.credential=encrypt('everloot','evl_synthetic_key')
        row.validated_at=now()
        body=configuration(row)
    body.update(hourly_budget=2000,daily_budget=48000,minimum_interval=1.8,page_size=5000)
    assert owner.patch('/api/v1/admin/metadata-providers/everloot/rate-limits',json=body).status_code == 200
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot');row.expires_at=AT-timedelta(seconds=1)
        limits=effective(row,AT)
        assert (limits['hourly_budget'],limits['page_size'],limits['minimum_interval']) == (20,500,180)
        assert configuration(row)['hourly_budget'] == 2000


def test_rolling_minute_boundary_and_usage_after_window_expiry(database):
    with database.begin() as db:
        configured(db,'foreverdb',minute_budget=2,minimum_interval=0.05)
    assert request_once(database,AT,'foreverdb') is None
    assert request_once(database,AT+timedelta(seconds=.1),'foreverdb') is None
    assert request_once(database,AT+timedelta(seconds=1),'foreverdb') == AT+timedelta(seconds=61)
    assert request_once(database,AT+timedelta(seconds=60.9),'foreverdb') == AT+timedelta(seconds=61)
    assert request_once(database,AT+timedelta(seconds=61),'foreverdb') is None
    with database() as db:
        state=rate_view(db.get(MetadataProvider,'foreverdb'),AT+timedelta(days=2))
        assert state['windows']['day']['used'] == state['windows']['hour']['used'] == 0


def test_shared_hour_day_windows_and_restart_persistence(database):
    with database.begin() as db: configured(db,hourly_budget=2,daily_budget=3)
    assert request_once(database,AT) is None
    assert request_once(database,AT+timedelta(minutes=3)) is None
    assert request_once(database,AT+timedelta(minutes=6)) == AT+timedelta(hours=1,minutes=1)
    assert request_once(database,AT+timedelta(hours=1,minutes=1)) is None
    # Every helper call opened a new session; no process-local counters exist.
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot')
        row.rate_config=json.dumps({**configuration(row),'hourly_budget':5})
        row.hourly_budget=5
    assert request_once(database,AT+timedelta(hours=2)) == AT+timedelta(days=1,minutes=1)
    assert request_once(database,AT+timedelta(days=1,minutes=1)) is None


def test_edits_mid_window_never_restore_usage_or_tokens(database):
    with database.begin() as db: configured(db,'thewowdb',minimum_interval=.05,burst_capacity=2)
    assert request_once(database,AT,'thewowdb') is None
    with database.begin() as db:
        row=db.get(MetadataProvider,'thewowdb')
        row.rate_config=json.dumps({**configuration(row),'burst_capacity':120,'daily_budget':1})
        row.daily_budget=1
        assert row.rate_tokens == 1
    with database() as db:
        row=db.get(MetadataProvider,'thewowdb')
        assert rate_view(row,AT)['windows']['day']['remaining'] == 0
    assert request_once(database,AT+timedelta(seconds=1),'thewowdb') > AT+timedelta(hours=23)


def test_token_bucket_refill_burst_and_concurrency_lease(database):
    with database.begin() as db: configured(db,'thewowdb',minimum_interval=.05,burst_capacity=2)
    assert request_once(database,AT,'thewowdb') is None
    assert request_once(database,AT+timedelta(seconds=.05),'thewowdb') is None
    assert request_once(database,AT+timedelta(seconds=.1),'thewowdb') == AT+timedelta(seconds=.5)
    assert request_once(database,AT+timedelta(seconds=.5),'thewowdb') is None
    with database.begin() as db:
        row=db.get(MetadataProvider,'thewowdb')
        assert reserve_budget(row,AT+timedelta(seconds=1)) is None
    with database.begin() as db:
        row=db.get(MetadataProvider,'thewowdb')
        assert reserve_budget(row,AT+timedelta(seconds=2)) == AT+timedelta(seconds=121)
        assert row.hour_used == 4  # interrupted I/O remains charged


def test_postgres_atomic_reservations_and_provider_independence(database):
    if database.kw['bind'].dialect.name != 'postgresql':pytest.skip('PostgreSQL row-lock evidence')
    with database.begin() as db: configured(db,'thewowdb',minimum_interval=.05)
    def attempt(_):
        with database.begin() as db:return reserve_budget(db.get(MetadataProvider,'thewowdb'),AT)
    with ThreadPoolExecutor(max_workers=4) as workers: results=list(workers.map(attempt,range(8)))
    assert results.count(None) == 1
    assert request_once(database,AT,'everloot') is None
    with database() as db:
        assert db.get(MetadataProvider,'thewowdb').hour_used == 1
        assert db.scalar(select(func.sum(MetadataQuotaBucket.used)).where(MetadataQuotaBucket.provider=='thewowdb',MetadataQuotaBucket.resolution==60)) == 1


@pytest.mark.parametrize('value,expected',[(None,0),('bad',0),('-1',0),('0',0),('120',120),('9'*50,366*86400),('Wed, 99 Nov 2026 12:00:00 GMT',0)])
def test_retry_after_invalid_seconds_and_bounding(value,expected):
    assert retry_delay(value,AT) == expected


def test_http_date_clock_skew_adaptive_cooldown_and_503():
    row=MetadataProvider(provider='thewowdb',hourly_budget=60,daily_budget=500)
    assert retry_delay(format_datetime(AT-timedelta(seconds=1)),AT) == 0
    assert retry_delay(format_datetime(AT+timedelta(seconds=30)),AT) == 30
    assert retry_delay(format_datetime(AT-timedelta(minutes=1)),AT,format_datetime(AT-timedelta(minutes=3))) == 120
    cooldown(row,429,{'retry-after':'10'},AT)
    assert row.cooldown_until == AT+timedelta(seconds=60) and row.rate_tokens == 0
    cooldown(row,429,{'Retry-After':'1'},AT+timedelta(seconds=60))
    assert row.cooldown_until == AT+timedelta(seconds=180) and row.rate_streak == 2
    assert effective(row,AT+timedelta(seconds=181))['minimum_interval'] >= 4
    after=AT+timedelta(seconds=1081)
    assert effective(row,after)['minimum_interval'] == 60
    cooldown(row,503,{'Retry-After':'500'},after)
    assert row.cooldown_until == after+timedelta(seconds=500)
    assert row.last_rate_limit == AT+timedelta(seconds=60)
    other=MetadataProvider(provider='everloot')
    assert cooldown(other,403,{},AT) == 'forbidden'
    assert other.last_rate_limit is None


def test_response_observations_are_safe_and_never_claim_recovery(database):
    with database.begin() as db:
        row=configured(db,'thewowdb')
        observe(row,200,{'X-RateLimit-Remaining':'12','Authorization':'fdb_should_never_escape','RateLimit-Limit':'oops'},AT)
        state=rate_view(row,AT)
        assert state['provider_reported']['remaining'] == 12
        assert state['provider_reported']['limit'] is None
        assert state['last_http_success'] == AT and state['last_useful_recovery'] is None
        assert 'fdb_' not in row.rate_observation
        observe(row,429,{'RateLimit-Remaining':'0','RateLimit-Limit':'2000','RateLimit-Reset':'300'},AT)
        assert row.cooldown_until == AT+timedelta(seconds=300)


def test_429_job_waits_resumes_and_records_actual_use(owner,database):
    market=setup(database);at=now()
    with database.begin() as db:
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=3,at=at);job_id=job.id
    tick(database,at=at,fetcher=lambda *a,**kw:response(429,headers={'Retry-After':'120'}),automatic=False)
    detail=owner.get(f'/api/v1/admin/item-metadata/jobs/{job_id}').json()
    assert detail['counts'] == {'queued':1} and detail['failed'] == 0 and detail['waiting'][0]['provider'] == 'everloot'
    tick(database,at=at+timedelta(seconds=121),fetcher=lambda *a,**kw:pytest.fail('Pace guard bypassed'),automatic=False)
    tick(database,at=at+timedelta(seconds=181),fetcher=lambda *a,**kw:response(),automatic=False)
    with database() as db:
        job=db.get(MetadataJob,job_id);row=db.get(MetadataProvider,'everloot')
        assert job.state == 'completed' and job.requests_used == row.hour_used == 2
        assert row.last_recovery == at+timedelta(seconds=181)


def test_exhausted_campaign_preserves_429_work_until_explicit_retry(owner,database):
    market=setup(database);at=now()
    with database.begin() as db:
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=1,at=at);job_id=job.id
    tick(database,at=at,fetcher=lambda *a,**kw:response(429),automatic=False)
    tick(database,at=at+timedelta(minutes=4),fetcher=lambda *a,**kw:pytest.fail('Campaign cap bypassed'),automatic=False)
    result=owner.get(f'/api/v1/admin/item-metadata/jobs/{job_id}').json()
    assert result['state'] == 'paused' and result['retry_allowance_needed']
    assert result['counts'] == {'queued':1} and result['requests_used'] == 1
    assert owner.post(f'/api/v1/admin/item-metadata/jobs/{job_id}/retry-allowance',json={'additional_requests':1}).status_code == 200
    tick(database,at=at+timedelta(minutes=5),fetcher=lambda *a,**kw:response(),automatic=False)
    assert owner.get(f'/api/v1/admin/item-metadata/jobs/{job_id}').json()['state'] == 'completed'


def test_key_rotation_validation_preserves_quota_and_honors_lowercase_retry(database,keyfile):
    setup(database);at=now()
    with database.begin() as db:
        row=configured(db)
        row.pending_key_id,row.pending_credential=encrypt('everloot','evl_synthetic_replacement')
        row.validation_requested=True
    tick(database,at=at,fetcher=lambda *a,**kw:response(429,headers={'retry-after':'300'}),automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,'everloot')
        assert row.validation_requested and row.pending_credential and row.hour_used == 1
        assert at+timedelta(seconds=300) <= aware(row.cooldown_until) < at+timedelta(seconds=301)
    from test_metadata_recovery import page
    tick(database,at=at+timedelta(seconds=301),fetcher=lambda *a,**kw:response(body=page()),automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,'everloot')
        assert row.credential and not row.pending_credential and row.hour_used == 2


def test_new_rate_controls_require_admin_session_and_csrf(client,owner,database):
    with database.begin() as db:ensure_providers(db);body=configuration(db.get(MetadataProvider,'blizzard'))
    path='/api/v1/admin/metadata-providers/blizzard/rate-limits'
    # Owner fixture shares the client; explicitly remove CSRF and cookies in turn.
    assert client.patch(path,json=body,headers={'X-CSRF-Token':''}).status_code == 403
    client.cookies.clear()
    assert client.patch(path,json=body).status_code in (401,403)


def test_cooling_validation_does_not_starve_another_provider(database):
    from test_community_metadata import payload
    setup(database)
    at=now()
    with database.begin() as db:
        row=db.get(MetadataProvider,'everloot');row.validation_requested=True;row.cooldown_until=at+timedelta(hours=1)
        db.get(MetadataProvider,'thewowdb').validation_requested=True
    calls=[]
    value=payload();value['id']=25
    tick(database,at=at,fetcher=lambda provider,*a,**kw:(calls.append(provider),response(body=json.dumps(value).encode()))[1],automatic=False)
    assert calls == ['thewowdb']
    with database() as db:
        assert db.get(MetadataProvider,'everloot').validation_requested
        assert db.get(MetadataProvider,'thewowdb').validated_at == at


def test_503_retry_after_recovers_without_permanent_block(database):
    market=setup(database);at=now()
    with database.begin() as db:
        job,_=enqueue(db,market,'single',['everloot'],item_id=720,budget=3,at=at);job_id=job.id
    tick(database,at=at,fetcher=lambda *a,**kw:response(503,headers={'Retry-After':'300'}),automatic=False)
    tick(database,at=at+timedelta(seconds=299),fetcher=lambda *a,**kw:pytest.fail('503 cooldown bypassed'),automatic=False)
    tick(database,at=at+timedelta(seconds=301),fetcher=lambda *a,**kw:response(),automatic=False)
    with database() as db:
        assert db.get(MetadataJob,job_id).state == 'completed'
        assert db.get(MetadataProvider,'everloot').last_rate_limit is None


def test_a_fresh_process_reads_committed_usage_and_cooldown(database):
    if database.kw['bind'].dialect.name != 'postgresql':pytest.skip('Independent PostgreSQL process')
    with database.begin() as db:
        row=configured(db)
        assert reserve_budget(row,AT) is None
        observe(row,429,{},AT);cooldown(row,429,{},AT)
    source="""import json
from datetime import datetime,timezone
from market.db import Session
from market.models import MetadataProvider
from market.provider_rates import rate_view
with Session() as db:
 s=rate_view(db.get(MetadataProvider,'everloot'),datetime(2026,11,16,12,0,tzinfo=timezone.utc))
 print(json.dumps({'used':s['windows']['hour']['used'],'cooling':s['cooling_down'],'last_rate_limit':s['last_rate_limit'].isoformat()}))
"""
    result=subprocess.run([sys.executable,'-c',source],capture_output=True,text=True,timeout=15,
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])})
    assert result.returncode == 0,result.stderr
    assert json.loads(result.stdout) == {'used':1,'cooling':True,'last_rate_limit':AT.isoformat()}


def test_scheduler_wakes_for_configured_pace_without_busy_idle_polling(database,monkeypatch):
    from market.enrichment import next_delay
    with database.begin() as db:
        row=configured(db,'foreverdb',minute_budget=60,minimum_interval=1)
        row.enabled=row.automatic=True;row.credential=b'synthetic';row.validated_at=AT
        row.next_request_at=AT+timedelta(seconds=1)
    assert next_delay(database,at=AT,worked=True) == 1
    assert next_delay(database,at=AT+timedelta(seconds=2),worked=False) == 15


def test_live_configuration_reconsiders_wait_without_bypassing_cooldown(owner,database,keyfile):
    market=setup(database,'foreverdb');at=now()
    with database.begin() as db:
        row=configured(db,'foreverdb')
        row.credential_key_id,row.credential=encrypt('foreverdb','fdb_synthetic_approved_key')
        row.validated_at=at;row.cooldown_until=at+timedelta(minutes=10)
        job,_=enqueue(db,market,'single',['foreverdb'],item_id=720,budget=3,at=at)
        db.flush()
        task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job.id));task.available_at=at+timedelta(hours=1)
        task_id=task.id
        body={**configuration(row),'hourly_budget':3600,'daily_budget':10000,'minute_budget':60,'entitlement_acknowledged':True}
    assert owner.patch('/api/v1/admin/metadata-providers/foreverdb/rate-limits',json=body).status_code == 200
    with database() as db:
        assert aware(db.get(MetadataTask,task_id).available_at) == at+timedelta(minutes=10)


def test_retry_after_starts_at_response_receipt_not_request_start(database,monkeypatch):
    import market.metadata_recovery as recovery
    market=setup(database);at=now()
    with database.begin() as db:enqueue(db,market,'single',['everloot'],item_id=720,budget=3,at=at)
    clock=[100.0]
    monkeypatch.setattr(recovery,'monotonic',lambda:clock[0])
    def slow_response(*a,**kw):
        clock[0]+=8
        return response(429,headers={'Retry-After':'300'})
    tick(database,at=at,fetcher=slow_response,automatic=False)
    with database() as db:
        row=db.get(MetadataProvider,'everloot')
        assert aware(row.cooldown_until) == at+timedelta(seconds=308)
        assert row.rate_inflight_until is None
