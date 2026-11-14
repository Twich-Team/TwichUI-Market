"""Bounded Forever item-name resolution with provenance and negative caching."""
import hashlib
import json
import time
from datetime import timedelta
from urllib.error import URLError
from sqlalchemy import and_,or_,select,text
from .db import Session,now
from .models import ItemMetadata,Listing,Market,Observation


def store_metadata(db,region,item_id,body,*,at=None,synthetic=False):
    at=at or now()
    if region not in ('eu','us','kr','tw') or type(item_id) is not int or not 1<=item_id<=2**31-1 or len(body)>262144:
        raise ValueError('Invalid item metadata request')
    payload=json.loads(body)
    if not isinstance(payload,dict) or type(payload.get('id')) is not int or payload['id']!=item_id:
        raise ValueError('Item metadata identity mismatch')
    name=payload.get('name')
    if isinstance(name,dict): name=name.get('en_US')
    if not isinstance(name,str) or not 1<=len(name.strip())<=255 or any(ord(char)<32 for char in name):
        raise ValueError('Invalid item name')
    row=db.get(ItemMetadata,(region,item_id))
    if row is None:
        row=ItemMetadata(region=region,item_id=item_id,namespace=f'static-forever-{region}')
        db.add(row)
    row.name,row.status=name.strip(),'available'
    row.checked_at,row.retry_after=at,at+timedelta(days=30)
    row.resolved_at=at
    row.http_status,row.payload_hash,row.synthetic=200,hashlib.sha256(body).hexdigest(),synthetic
    db.flush()
    return row


def resolve_once(factory=Session,client=None,*,at=None):
    from .worker import BlizzardClient,UpstreamFailure,retry_seconds
    at=at or now()
    client=client or BlizzardClient()
    if getattr(client,'blocked_until',0)>time.monotonic(): return False
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
            return False
        candidate=None
        for market in db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)):
            latest=db.scalar(select(Observation).where(Observation.market_id==market.id)
                .order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
            if not latest: continue
            item=db.scalar(select(Listing.item_id).outerjoin(ItemMetadata,and_(ItemMetadata.region==market.region,
                ItemMetadata.item_id==Listing.item_id)).where(Listing.snapshot_id==latest.snapshot_id,
                or_(ItemMetadata.item_id.is_(None),ItemMetadata.retry_after<=at)).distinct().order_by(Listing.item_id).limit(1))
            if item is not None:
                candidate=(market.region,item)
                break
        if candidate is None: return False
        region,item=candidate
        row=db.get(ItemMetadata,(region,item))
        if row is None:
            row=ItemMetadata(region=region,item_id=item,namespace=f'static-forever-{region}')
            db.add(row)
        try:
            metadata,body=client.fetch_item(region,item)
            row.http_status=metadata['status']
            if metadata['status']==200:
                store_metadata(db,region,item,body,at=at,synthetic=metadata.get('synthetic',False))
            else:
                row.status='missing' if metadata['status']==404 else 'error'
                delay=7*86400 if metadata['status']==404 else max(900,retry_seconds(metadata['headers'].get('Retry-After'),at))
                row.checked_at,row.retry_after=at,at+timedelta(seconds=delay)
        except (UpstreamFailure,URLError,TimeoutError,ValueError,UnicodeError,KeyError):
            row.status='error'
            row.checked_at,row.retry_after=at,at+timedelta(minutes=15)
        return True
