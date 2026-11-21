"""Load an explicit production-derived summary slice into isolated market_test."""
import hashlib, json, os
from datetime import datetime,timedelta
from pathlib import Path
from sqlalchemy import insert, text, DateTime, Date
from market.db import Base, engine, Session, now
from market.models import Market, Snapshot, SnapshotStatistic, Observation, ItemSourceCoverage, PlayerMarketMapping, User, CompanionDevice, Credential
from market.security import hasher,digest
assert engine.url.database == 'market_test'
data=json.loads(Path(os.environ['SYNC_PERF_FIXTURE']).read_bytes())
assert data['format']=='production-derived-sync-summary-slice-v1' and data['production_read_only']
Base.metadata.create_all(engine)
def typed(model,row):
    result=dict(row)
    for col in model.__table__.columns:
        if result.get(col.name) is not None:
            if isinstance(col.type,DateTime):result[col.name]=datetime.fromisoformat(result[col.name])
            elif isinstance(col.type,Date):result[col.name]=datetime.fromisoformat(result[col.name]).date()
    return result
with Session.begin() as db:
    if db.get(Market,2):raise RuntimeError('Benchmark seed must start empty')
    db.add(User(id=1,username='sync-performance-fixture',password_hash=hasher.hash('isolated performance fixture only'),role='member'))
    db.flush()
    m=dict(data['market']);m.update(label='Production-derived performance fixture',enabled=True,last_success=now())
    db.add(Market(**m));db.flush()
    evidence=json.dumps({'region':m['region'],'house_id':m['house_id'],'ruleset':'Normal','faction':'Horde','upstream_receipt':'Synthetic isolated fixture identity only','independent_observation':'Synthetic isolated fixture identity only','independent_source_url':'https://fixture.invalid/performance'},sort_keys=True)
    if db.scalar(__import__('sqlalchemy').select(PlayerMarketMapping).where(PlayerMarketMapping.region==m['region'],PlayerMarketMapping.ruleset=='Normal',PlayerMarketMapping.faction=='Horde',PlayerMarketMapping.source_kind==m['source_kind'])) is None: db.add(PlayerMarketMapping(region=m['region'],ruleset='Normal',faction='Horde',house_id=m['house_id'],transport_ruleset_id=m['ruleset_id'],source_kind=m['source_kind'],confidence='verified',evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),verified_at=now()))
    db.execute(insert(Snapshot),[typed(Snapshot,r) for r in data['snapshots']])
    for start in range(0,len(data['statistics']),1000):db.execute(insert(SnapshotStatistic),data['statistics'][start:start+1000])
    if data['coverage']:db.execute(insert(ItemSourceCoverage),[typed(ItemSourceCoverage,r) for r in data['coverage']])
    initial=[typed(Observation,r) for r in data['observations'] if r['id']<=data['full_target']]
    db.execute(insert(Observation),initial)
    device=CompanionDevice(user_id=1,name='Isolated native performance fixture',platform='Windows',app_version='2.0.0-beta.8',issuer_origin=os.environ['APP_ORIGIN'],expires_at=now()+timedelta(days=1),refresh_expires_at=now()+timedelta(days=1),refresh_hash='f'*64)
    db.add(device);db.flush()
    credential=Credential(user_id=1,kind='companion',token_hash=digest(os.environ['SYNC_PERF_TOKEN']),name='Isolated performance fixture',companion_device_id=device.id,expires_at=now()+timedelta(days=1))
    db.add(credential);db.flush();device.access_credential_id=credential.id
with engine.begin() as db:
    for table in ['observations','snapshots','snapshot_statistics','item_source_coverage']:db.execute(text('ANALYZE '+table))
print(json.dumps({'fixture_only':True,'production_derived':True,'history_scope':data['history_scope'],'variants':sum(r['snapshot_id']==next(o['snapshot_id'] for o in data['observations'] if o['id']==data['full_target']) for r in data['statistics']),'statistics':len(data['statistics']),'initial_watermark':data['full_target']}))
