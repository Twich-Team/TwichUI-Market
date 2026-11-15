"""One bounded primary-name pass, independent of auction collection.

Run inside an existing project worker context; no market/schedule mutations.
Stores a fixed-snapshot coverage comparison, never credentials.
"""
import argparse,json,time
from sqlalchemy import func,select
from market.db import Session,now
from market.models import ItemMetadata,Market,Observation,SnapshotStatistic
from market.metadata import resolve_once
from market.worker import BlizzardClient

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--limit',type=int,default=50,choices=range(1,101))
args=parser.parse_args()
with Session() as db:
    market=db.scalar(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id).limit(1))
    if market is None:raise SystemExit('No collecting verified feed; no enrichment performed')
    snapshot=db.scalar(select(Observation.snapshot_id).where(Observation.market_id==market.id).order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
    region=market.region
    market_id=market.id

def coverage():
    with Session() as db:
        ids=select(SnapshotStatistic.item_id).where(SnapshotStatistic.snapshot_id==snapshot).distinct().subquery()
        total=db.scalar(select(func.count()).select_from(ids))
        primary=db.scalar(select(func.count()).select_from(ids).join(ItemMetadata,(ItemMetadata.item_id==ids.c.item_id)&(ItemMetadata.region==region)).where(ItemMetadata.name.is_not(None)))
        community=db.scalar(select(func.count()).select_from(ids).join(ItemMetadata,(ItemMetadata.item_id==ids.c.item_id)&(ItemMetadata.region==region)).where(ItemMetadata.name.is_(None),ItemMetadata.fallback_name.is_not(None)))
        return {'item_ids':total,'primary_names':primary,'community_names':community,'unresolved':total-primary-community,'name_percent':round((primary+community)*100/total,2) if total else None}
result={'at':now().isoformat(),'market_id':market_id,'snapshot_id':snapshot,'before':coverage(),'maximum_requests':args.limit}
client=BlizzardClient()
count=0
for _ in range(args.limit):
    if not resolve_once(client=client):break
    count+=1
    time.sleep(1)
result.update({'completed_requests':count,'after':coverage(),'finished_at':now().isoformat(),'community_enabled':False,'note':'Primary Blizzard resolution only; fixed snapshot comparison. Concurrent background enrichment can contribute to the measured delta.'})
print(json.dumps(result,indent=2))
