"""Verify exact compact statistics before the first raw batch; retain durable proofs."""
import hashlib
import json
from decimal import Decimal
from sqlalchemy import BigInteger, Numeric, cast, func, literal, select
from fastapi import HTTPException
from .models import Listing, SecurityEvent, Snapshot, SnapshotStatistic
from .pricing import ALGORITHM, summarize

FIELDS=('snapshot_id','item_id','variant_key','source_kind','algorithm','recent_price','lowest_buyout','supply','priced_supply','listing_count')


def fingerprint(rows):
    digest=hashlib.sha256();count=0;listings=0
    for row in rows:
        values=[int(v) if isinstance(v,Decimal) else v for v in row]
        digest.update(json.dumps(values,separators=(',',':'),ensure_ascii=True).encode()+b'\n')
        count+=1;listings+=int(values[-1])
    return digest.hexdigest(),count,listings


def compact_fingerprint(db,snapshot_id):
    return fingerprint(db.execute(select(*(getattr(SnapshotStatistic,k) for k in FIELDS))
        .where(SnapshotStatistic.snapshot_id==snapshot_id).order_by(SnapshotStatistic.item_id,SnapshotStatistic.variant_key)
        .execution_options(yield_per=500)))


def raw_fingerprint(db,snapshot_id):
    if db.bind.dialect.name!='postgresql':
        from collections import defaultdict
        grouped=defaultdict(list)
        for row in db.scalars(select(Listing).where(Listing.snapshot_id==snapshot_id)):
            grouped[(row.item_id,row.variant_key,row.source_kind)].append(row)
        rows=[]
        for (item,key,kind),entries in sorted(grouped.items()):
            summary=summarize(entries)
            rows.append((snapshot_id,item,key,kind,ALGORITHM,*(summary[k] for k in FIELDS[5:])))
        return fingerprint(rows)
    priced=Listing.buyout.is_not(None) | Listing.unit_price.is_not(None)
    quantity=func.sum(Listing.quantity).filter(priced)
    total=func.sum(func.coalesce(cast(Listing.buyout,Numeric),cast(Listing.unit_price,Numeric)*Listing.quantity))
    unit=func.coalesce(cast(Listing.buyout,Numeric)/func.nullif(Listing.quantity,0),cast(Listing.unit_price,Numeric))
    query=select(Listing.snapshot_id,Listing.item_id,Listing.variant_key,Listing.source_kind,literal(ALGORITHM),
        cast(func.round(total/func.nullif(quantity,0)),BigInteger),cast(func.round(func.min(unit)),BigInteger),
        func.sum(Listing.quantity),func.coalesce(quantity,0),func.count()).where(Listing.snapshot_id==snapshot_id).group_by(
            Listing.snapshot_id,Listing.item_id,Listing.variant_key,Listing.source_kind).order_by(Listing.item_id,Listing.variant_key)
    return fingerprint(db.execute(query.execution_options(yield_per=500)))


def verify_statistics(db,snapshot_ids):
    for snapshot in db.scalars(select(Snapshot).where(Snapshot.id.in_(snapshot_ids))):
        compact=compact_fingerprint(db,snapshot.id)
        expected={'s':snapshot.id,'c':snapshot.content_hash,'h':compact[0],'n':snapshot.listing_count}
        previous=db.scalar(select(SecurityEvent.detail).where(SecurityEvent.action=='retention.aggregate.verified',
            SecurityEvent.detail.like('{"s":'+str(snapshot.id)+',%')).order_by(SecurityEvent.id.desc()).limit(1))
        if not snapshot.statistics_retained or compact[2]!=snapshot.listing_count:
            raise HTTPException(409,'Compact history is incomplete; raw data is preserved until aggregation is repaired')
        if previous and json.loads(previous)==expected:continue
        raw=raw_fingerprint(db,snapshot.id)
        if raw!=compact:
            raise HTTPException(409,'Compact history does not match raw variant prices, supply and listing totals; source data is preserved')
        db.add(SecurityEvent(action='retention.aggregate.verified',detail=json.dumps(expected,separators=(',',':'))))
