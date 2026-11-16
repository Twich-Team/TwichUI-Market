"""Synthetic rate-limit review only, after the ordinary browser suite. No I/O."""
from datetime import timedelta
import json
from sqlalchemy import select
from market.db import Session,engine,now
from market.metadata_recovery import ensure_providers
from market.provider_rates import configuration
from market.provider_secrets import encrypt
from market.models import Market,MetadataJob,MetadataProvider,MetadataTask,User

assert engine.url.database=='market_test','Refusing provider rate fixtures outside market_test'
with Session.begin() as db:
    ensure_providers(db)
    at=now()
    for ident,secret in [('everloot','evl_synthetic_rate_review_only'),('foreverdb','fdb_synthetic_rate_review_only')]:
        row=db.get(MetadataProvider,ident)
        row.credential_key_id,row.credential=encrypt(ident,secret)
        row.validated_at=at-timedelta(days=1)
        row.expires_at=at+timedelta(days=90)
        row.credential_status='connected'
        row.validation_requested=False
        row.pending_credential=row.pending_key_id=row.pending_expires_at=None
        row.enabled=ident=='foreverdb';row.automatic=False
        row.hour_start=row.day_start=at
        row.hour_used=350;row.day_used=900
        row.last_http_success=at-timedelta(minutes=20)
        row.last_recovery=at-timedelta(hours=1)
        config=configuration(row)
        if ident=='everloot':
            config.update(hourly_budget=2000,daily_budget=48000,minimum_interval=1.8,page_size=5000)
            row.rate_observation=json.dumps({'remaining':1650,'limit':2000,'reset_at':(at+timedelta(minutes=40)).isoformat(),'observed_at':at.isoformat()})
        else:
            config.update(minute_budget=60,hourly_budget=3600,daily_budget=10000,minimum_interval=1)
            row.cooldown_until=row.next_request_at=at+timedelta(minutes=10)
            row.last_rate_limit=at-timedelta(seconds=30)
            row.last_error='rate_limited';row.rate_streak=1
            row.adaptive_until=at+timedelta(minutes=25)
        row.rate_config=json.dumps(config)
        row.hourly_budget=config['hourly_budget'];row.daily_budget=config['daily_budget']
    owner=db.scalar(select(User).where(User.username=='owner'))
    market=db.scalar(select(Market).where(Market.house_id==113))
    job=db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key=='synthetic-provider-rate-wait'))
    if job is None:
        job=MetadataJob(actor_id=owner.id,market_id=market.id,mode='single',dedupe_key='synthetic-provider-rate-wait',providers_json='["foreverdb"]',total=1,request_budget=5,requests_used=1)
        db.add(job);db.flush()
    job.state='running'
    task=db.scalar(select(MetadataTask).where(MetadataTask.job_id==job.id))
    if task is None:
        task=MetadataTask(job_id=job.id,provider='foreverdb',region=market.region,item_id=20002)
        db.add(task)
    task.state='queued';task.attempts=1;task.available_at=at+timedelta(minutes=10)
    task.result_json=json.dumps({'provider':'foreverdb','status':'rate_limited','http_status':429,'outcome':'rate_limited','recovered_fields':[]})
print('Synthetic rate review fixtures seeded. No provider calls; no real credentials or entitlement observations.')
