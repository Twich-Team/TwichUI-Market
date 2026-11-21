"""Transactional normalization; callers own transaction and rollback on failure."""
import hashlib
import json
from collections import defaultdict
from types import SimpleNamespace
from datetime import timedelta, timezone
from sqlalchemy import delete, insert, select, text
from .db import now
from .models import DailyObservation, Listing, Market, Observation, Snapshot, SnapshotStatistic
from .security import aware


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def positive(value, name, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or value <= 0 or value > 2**63 - 1:
        raise ValueError(f"Invalid {name}")
    return value


def normalize(payload, kind):
    if not isinstance(payload, dict) or not isinstance(payload.get('auctions'), list):
        # Missing auctions must be confirmed as empty by a live mapping; fail closed for now.
        raise ValueError('Expected explicit auctions array')
    if len(payload['auctions']) > 150000:
        raise ValueError('Too many listings')
    rows, seen = [], set()
    for auction in payload['auctions']:
        if not isinstance(auction, dict) or not isinstance(auction.get('item'), dict):
            raise ValueError('Malformed auction')
        aid = positive(auction.get('id'), 'auction id')
        if aid in seen:
            raise ValueError('Duplicate auction id')
        seen.add(aid)
        item_id = positive(auction['item'].get('id'), 'item id')
        if item_id > 2**31 - 1:
            raise ValueError('Item id out of range')
        quantity = positive(auction.get('quantity'), 'quantity')
        if quantity > 2**31 - 1:
            raise ValueError('Quantity out of range')
        variant = canonical(auction['item'])
        if len(variant) > 4096:
            raise ValueError('Item variant too large')
        buyout = positive(auction.get('buyout'), 'buyout', True)
        unit_price = positive(auction.get('unit_price'), 'unit price', True)
        bid = positive(auction.get('bid'), 'bid', True)
        if kind == 'commodities':
            if unit_price is None or buyout is not None:
                raise ValueError('Commodity requires unit price only')
            if unit_price * quantity > 2**63 - 1:
                raise ValueError('Commodity total out of range')
        elif kind == 'auctions':
            if unit_price is not None or (buyout is None and bid is None):
                raise ValueError('Auction requires buyout or bid')
        else:
            raise ValueError('Unknown source kind')
        time_left = auction.get('time_left')
        if time_left is not None and (not isinstance(time_left, str) or len(time_left) > 32):
            raise ValueError('Invalid time left')
        rows.append(dict(auction_id=aid, item_id=item_id, variant=variant,
                         variant_key=hashlib.sha256(variant.encode()).hexdigest(),
                         quantity=quantity, buyout=buyout, unit_price=unit_price,
                         bid=bid, time_left=time_left))
    return sorted(rows, key=lambda row: row['auction_id'])


def record_daily(db,observation):
    day=aware(observation.retrieved_at).astimezone(timezone.utc).date()
    current=db.get(DailyObservation,(observation.market_id,day))
    if current is None:
        db.add(DailyObservation(market_id=observation.market_id,day=day,observation_id=observation.id))
    else:
        previous=db.get(Observation,current.observation_id)
        if (aware(previous.retrieved_at),previous.id)<(aware(observation.retrieved_at),observation.id):
            current.observation_id=observation.id


def ingest(db, market_id, payload_bytes, *, request_key, retrieved_at=None, modified=None, synthetic=False):
    existing = db.scalar(select(Observation).where(Observation.request_key == request_key))
    if existing:
        if existing.market_id != market_id or existing.payload_hash != hashlib.sha256(payload_bytes).hexdigest():
            raise ValueError('Idempotency key conflict')
        return existing
    if not 1 <= len(request_key) <= 64 or len(payload_bytes) > 32 * 1024 * 1024:
        raise ValueError('Invalid request key or payload size')
    retrieved_at = retrieved_at or now()
    if retrieved_at.tzinfo is None or retrieved_at > now() + timedelta(minutes=5):
        raise ValueError('Invalid retrieval timestamp')
    if modified is not None and len(modified) > 100:
        raise ValueError('Invalid upstream timestamp')
    # Commit order is serialized for stable incremental synchronization watermarks.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(7140232)'))
    # One writer per market. Worker takes the same lock before fetching.
    market = db.scalar(select(Market).where(Market.id == market_id).with_for_update())
    if not market:
        raise ValueError('Unknown market')
    # Recheck after acquiring the market lock: another writer may have committed while we waited.
    existing = db.scalar(select(Observation).where(Observation.request_key == request_key))
    if existing:
        if existing.market_id != market_id or existing.payload_hash != hashlib.sha256(payload_bytes).hexdigest():
            raise ValueError('Idempotency key conflict')
        return existing
    rows = normalize(json.loads(payload_bytes), market.source_kind)
    content_hash = hashlib.sha256(canonical(rows).encode()).hexdigest()
    snapshot = db.scalar(select(Snapshot).where(Snapshot.market_id == market_id, Snapshot.content_hash == content_hash))
    if snapshot is None:
        snapshot = Snapshot(market_id=market_id, content_hash=content_hash, listing_count=len(rows))
        db.add(snapshot)
        db.flush()
    if snapshot.raw_retained:
        # Newly inserted snapshots have no raw rows; existing retained snapshots already do.
        needs_raw = db.scalar(select(Listing.id).where(Listing.snapshot_id==snapshot.id).limit(1)) is None
    else:
        db.execute(delete(Listing).where(Listing.snapshot_id==snapshot.id))
        needs_raw = True
    if needs_raw and rows:
        for offset in range(0,len(rows),1000):
            db.execute(insert(Listing),[{'snapshot_id':snapshot.id,'source_kind':market.source_kind,**row} for row in rows[offset:offset+1000]])
    snapshot.raw_retained=True
    if not snapshot.statistics_retained or db.scalar(select(SnapshotStatistic.item_id).where(
            SnapshotStatistic.snapshot_id==snapshot.id).limit(1)) is None:
        if not snapshot.statistics_retained:
            db.execute(delete(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==snapshot.id))
        from .pricing import ALGORITHM, summarize
        grouped=defaultdict(list)
        for row in rows:
            grouped[(row['item_id'],row['variant_key'])].append(row)
        statistics=[]
        for (item_id,variant_key),entries in grouped.items():
            statistics.append({'snapshot_id':snapshot.id,'item_id':item_id,'variant_key':variant_key,'algorithm':ALGORITHM,'source_kind':market.source_kind,
                               **summarize([SimpleNamespace(**row) for row in entries])})
        for offset in range(0,len(statistics),1000):
            db.execute(insert(SnapshotStatistic),statistics[offset:offset+1000])
    snapshot.statistics_retained=True
    observation = Observation(market_id=market_id, snapshot_id=snapshot.id, request_key=request_key,
                              retrieved_at=retrieved_at, upstream_modified=modified,
                              namespace=f'dynamic-forever-{market.region}',
                              payload_hash=hashlib.sha256(payload_bytes).hexdigest(),
                              payload_bytes=len(payload_bytes), synthetic=synthetic)
    db.add(observation)
    if market.last_success is None or aware(market.last_success) <= retrieved_at:
        market.last_success, market.last_modified = retrieved_at, modified
    db.flush()
    record_daily(db,observation)
    db.flush()
    return observation
