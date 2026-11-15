"""Review-only synthetic provider outcomes; never run outside market_test.

After canonical browser verification, align the isolated review fixture's job
market with production's demonstrated first-market/collecting-market mismatch.
No worker/provider is called. These are deliberately synthetic attempts, not
reconstructed live history. The same records are used for before and after.
"""
import json
from sqlalchemy import select
from market.db import Session, engine, now
from market.models import Market, MetadataJob, MetadataTask, ItemMetadata
assert engine.url.database == 'market_test', 'Refusing review fixtures outside market_test'
with Session.begin() as db:
    markets=list(db.scalars(select(Market).order_by(Market.id)))
    assert len(markets)==2 and all(m.label.startswith('Synthetic') for m in markets)
    original=db.scalar(select(MetadataJob).where(MetadataJob.dedupe_key=='synthetic-admin-histories'))
    assert original is not None
    original.market_id=markets[1].id
    if db.scalar(select(MetadataJob.id).where(MetadataJob.dedupe_key=='synthetic-polish-review')):
        raise SystemExit('Review fixtures already present')
    job=MetadataJob(market_id=markets[1].id,mode='single',state='completed',dedupe_key='synthetic-polish-review',providers_json='["blizzard","everloot","thewowdb"]',total=6,request_budget=6,requests_used=6)
    db.add(job);db.flush()
    fixtures=[
        ('blizzard','name_recovered','available',200,'Synthetic restored item name',['name']),
        ('everloot','missing','metadata_unavailable',404,None,[]),
        ('thewowdb','name_recovered','available',200,'Synthetic community item name',['name','quality']),
        ('everloot','attributes_recovered','available',200,'Synthetic attribute-only result',['level']),
        ('thewowdb','access_blocked','forbidden',403,None,[]),
        ('blizzard','already_known','not_modified',304,'Synthetic previously known item',[]),
    ]
    for index,(provider,outcome,status,http_status,name,fields) in enumerate(fixtures):
        item_id=291000+index
        if name:db.add(ItemMetadata(region='eu',item_id=item_id,name=name,quality='RARE' if 'quality' in fields else None,namespace='static-forever-eu',synthetic=True))
        db.add(MetadataTask(job_id=job.id,provider=provider,region='eu',item_id=item_id,state='completed' if http_status!=403 else 'failed',attempts=1,updated_at=now(),result_json=json.dumps({'status':status,'http_status':http_status,'outcome':outcome,'recovered_fields':fields,'new_fields':fields,'source':{'edition':'forever','confidence':'synthetic','build':'1.60.1.70532'}})))
print('Six synthetic review outcomes stored in isolated market_test; no provider calls')
