"""Synthetic administration histories only; never contacts a metadata provider."""
import json,hashlib
from datetime import timedelta
from sqlalchemy import select
from market.db import Session,engine,now
from market.models import CompanionDevice,ItemMetadata,MetadataJob,MetadataTask,SecurityEvent,User,Market
assert engine.url.database=='market_test','Refusing administration fixtures outside market_test'
with Session.begin() as db:
    owner=db.scalar(select(User).where(User.username=='owner'))
    market=db.scalar(select(Market).where(Market.house_id==113))
    if db.scalar(select(MetadataJob.id).where(MetadataJob.dedupe_key=='synthetic-admin-histories')):raise SystemExit('Administration fixtures already seeded')
    job=MetadataJob(actor_id=owner.id,market_id=market.id,mode='single',state='completed',dedupe_key='synthetic-admin-histories',providers_json=json.dumps(['blizzard','everloot','foreverdb','thewowdb']),total=70,request_budget=70,requests_used=70)
    db.add(job);db.flush()
    outcomes=['name_recovered','attributes_recovered','already_known','no_usable_data','missing','invalid_response','access_blocked','rate_limited']
    providers=['blizzard','everloot','foreverdb','thewowdb']
    for index in range(70):
        outcome=outcomes[index%len(outcomes)];provider=providers[index%4];ident=290000+index
        fields=['name','quality'] if outcome=='name_recovered' else ['quality'] if outcome=='attributes_recovered' else []
        status={'missing':'metadata_unavailable','invalid_response':'transport_or_schema','access_blocked':'forbidden','rate_limited':'rate_limited'}.get(outcome,'available')
        db.add(ItemMetadata(region='eu',item_id=ident,namespace='static-forever-eu',name=f'Synthetic item {index+1}',status='available',synthetic=True))
        db.add(MetadataTask(job_id=job.id,provider=provider,region='eu',item_id=ident,state='completed',attempts=1,updated_at=now()-timedelta(minutes=index),result_json=json.dumps({'status':status,'http_status':403 if outcome=='access_blocked' else 404 if outcome=='missing' else 429 if outcome=='rate_limited' else 200,'outcome':outcome,'new_fields':fields,'recovered_fields':fields,'source':{'provider':provider,'edition':'forever','build':'1.60.1.70532','confidence':'synthetic'}})))
        db.add(SecurityEvent(actor_id=owner.id,action='metadata.synthetic.recorded',detail=f'fixture={index}'))
    db.add(CompanionDevice(user_id=owner.id,name='Synthetic review PC',platform='Windows',app_version='2.0.0-beta.2',issuer_origin='http://proxy',expires_at=now()+timedelta(days=1),refresh_expires_at=now()+timedelta(days=90),refresh_hash=hashlib.sha256(b'synthetic-review-only-no-token').hexdigest(),last_connection_at=now(),last_sync_at=now(),selected_market_id=market.id))
print('Synthetic administration fixtures seeded; zero provider calls')
