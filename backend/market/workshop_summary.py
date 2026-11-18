"""Bounded current-market research summaries. No new pricing calculation.

U1 routing/tuple semantics, extended explicitly for historical reference coverage.
This protocol is independent of the optional retained-history archive.
"""
from collections import defaultdict
from datetime import datetime, timedelta
import hashlib
import json
import re
import uuid
from functools import lru_cache
from pathlib import Path
import jsonschema

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import delete, func, insert, select, text, tuple_
from sqlalchemy.orm import Session

from . import bridge_api as bridge, canonical_pricing as cp, environment
from .bridge_contract import contract
from .db import now, session
from .market_api import MarketId, require_market
from .models import BridgeGeneration, BridgeRecord, Observation, Snapshot, User
from .security import aware
from .market_configuration import mapping_for

FORMAT = 'twichui-workshop-summary'
ALGORITHM = 'workshop-summary-v1:' + cp.ALGORITHM
STAGING = 'workshop-summary-stage-v1:' + cp.ALGORITHM
PROJECTION_BATCH = 1000
BUCKETS = 64
MAX_PART = 128 * 1024
MAX_TOTAL = 8 * 1024 * 1024
MAX_MANIFEST = 64 * 1024
MAX_RECORDS = 150_000
COLUMNS = ['item_id', 'variant_key', 'state', 'recent_copper', 'market_value_copper',
           'minimum_copper', 'supply', 'age_seconds', 'confidence',
           'historical_value_copper', 'priced_days_14', 'priced_days_60', 'observed_days_60']
STATES = ['priced', 'supply_only', 'absent', 'unknown', 'unsupported']
router = APIRouter(prefix='/api/v1/workshop')


def canonical(value):
    return contract().canonical(value)


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


@lru_cache(maxsize=1)
def manifest_validator():
    bundle = Path(contract().__file__).resolve().parents[2]
    schema = json.loads((bundle / 'workshop-summary/v1/manifest.schema.json').read_bytes())
    return jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())


def need(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, low, high):
    need(type(value) is int and low <= value <= high, 'summary integer bound')


def validate_row(row, bucket=None):
    need(type(row) is list and len(row) == len(COLUMNS), 'summary tuple shape')
    integer(row[0], 1, 2**31-1)
    need(type(row[1]) is str and re.fullmatch('[0-9a-f]{64}', row[1]), 'exact upstream variant')
    if bucket is not None:
        need(row[0] % BUCKETS == bucket, 'summary route')
    integer(row[2], 0, 4)
    for price in (row[3], row[4], row[5], row[9]):
        need(price is None or type(price) is str and re.fullmatch('[1-9][0-9]{0,10}', price)
             and int(price) <= cp.MAX_COPPER, 'supported exact copper')
    if row[6] is not None:
        integer(row[6], 0, 2**53-1)
    integer(row[7], 0, 0)
    integer(row[8], 0, 1)
    integer(row[10], 0, 14)
    for n in row[11:]:
        integer(n, 0, 60)
    need(row[10] <= row[11] <= row[12], 'reference coverage')
    need((row[9] is None or row[11] >= 3) and (row[4] is None or row[10] > 0), 'priced reference support')
    prices = (row[3], row[4], row[5], row[9])
    if row[2] == 0:
        need(any(p is not None for p in prices) and row[8] == 0 and row[6] is not None and row[6] > 0, 'priced evidence')
    else:
        need(all(p is None for p in prices) and row[8] == 1, 'unavailable prices')
        need(row[6] == 0 if row[2] == 2 else row[6] is not None and row[6] > 0 if row[2] == 1 else row[6] is None, 'unavailable supply')


def project(record):
    c = record['current']
    need(c['algorithm'] == cp.ALGORITHM, 'canonical algorithm required')
    state, supply, confidence = 3, None, 1
    prices = [None] * 4
    if c['complete']:
        if c['state'] == 'absent':
            state, supply = 2, 0
        elif c['arithmetic_status'] == 'unsupported':
            state = 4
        elif c['state'] == 'listed':
            supply = c['supply']
            metrics = c['metrics']
            prices = [metrics[k] for k in ('recent_copper', 'market_value_copper', 'minimum_copper', 'historical_value_copper')]
            state = 0 if any(p is not None for p in prices) else 1
            confidence = 0 if state == 0 else 1
    coverage = c['coverage']
    row = [record['item_id'], record['variant_key'], state, *prices[:3], supply, 0,
           confidence, prices[3], coverage['priced_days_14'], coverage['priced_days_60'],
           coverage['observed_days_60']]
    validate_row(row)
    return row


def seal(metadata, rows):
    """O(one bounded part per bucket), with whole-generation refusal, no pruning."""
    parts, counts, sizes = defaultdict(list), defaultdict(int), defaultdict(lambda: 2)
    previous, total, count = None, 0, 0
    for row in rows:
        validate_row(row)
        key = tuple(row[:2])
        need(previous is None or previous < key, 'unique sorted exact identities')
        previous = key
        bucket = row[0] % BUCKETS
        raw = canonical(row)
        sizes[bucket] += len(raw) + bool(parts[bucket])
        need(sizes[bucket] <= MAX_PART, 'summary partition exceeds 128 KiB; no generation published')
        total += len(raw) + bool(parts[bucket])
        count += 1
        need(count <= MAX_RECORDS and total + 2 * BUCKETS <= MAX_TOTAL, 'summary generation exceeds bounded coverage; no generation published')
        parts[bucket].append(raw)
        counts[bucket] += 1
    encoded, descriptors = {}, []
    for bucket in sorted(parts):
        raw = b'[' + b','.join(parts[bucket]) + b']'
        encoded[bucket] = raw
        descriptors.append(dict(bucket=bucket, bytes=len(raw), record_count=counts[bucket],
                                sha256=hashlib.sha256(raw).hexdigest()))
    manifest = dict(metadata, format=FORMAT, schema_version=1, contract_version=1,
                    columns=COLUMNS, states=STATES, confidence_states=['limited', 'unavailable'],
                    confidence_ceiling='limited', can_satisfy_local_competition=False,
                    identity_basis='exact_upstream_hashes; native_link_mapping_unavailable',
                    record_count=count, partitioning=dict(algorithm='item_id_modulo', buckets=64,
                    max_partition_bytes=MAX_PART, max_total_bytes=MAX_TOTAL), partitions=descriptors,
                    coverage=dict(scope='current_observed_exact_variants', complete=True,
                    source_records=count, delivered_records=count, missing='unavailable',
                    detailed_history='not_delivered'))
    manifest['generation_id'] = digest(manifest)
    need(len(canonical(manifest)) <= MAX_MANIFEST, 'summary manifest bound')
    try:
        manifest_validator().validate(manifest)
    except jsonschema.ValidationError as error:
        raise ValueError('Summary source contract is invalid; previous data is preserved') from error
    return manifest, encoded


def build(db, market):
    # Immutable observations and derived source records permit a pinned prefix.
    # This export lock never owns the collector/global ingest lock.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SET LOCAL statement_timeout='10s'"))
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140288, :market)'), {'market': market.id}):
            raise HTTPException(409, 'Market summary is preparing; retry on the existing schedule')
    stage = db.scalar(select(BridgeGeneration).where(BridgeGeneration.market_id == market.id, BridgeGeneration.algorithm == STAGING).limit(1))
    progress = json.loads(stage.manifest_json) if stage else None
    latest = db.scalar(select(Observation).where(Observation.market_id == market.id)
                       .order_by(Observation.retrieved_at.desc(), Observation.id.desc()).limit(1))
    if latest is None:
        raise HTTPException(409, 'No observed market summary is available yet')
    # A pinned preparation prefix survives collector arrivals and process restarts.
    at = datetime.fromisoformat(progress['source_at'].replace('Z', '+00:00')) if progress else bridge.utc(latest.retrieved_at)
    watermark, current, daily, observations = bridge.selected_observations(db, market, at, cp.ALGORITHM)
    identity = bridge.market_identity(db, market)
    if not identity['mapping_verified']:
        raise HTTPException(409, 'Verified Forever market mapping is required')
    identity['faction'] = mapping_for(db, market).faction
    signature = digest([FORMAT, 1, bridge.REVISION, cp.HISTORY_BASIS, identity,
                        [[o.id, o.snapshot_id] for o in observations]])
    cached = db.scalar(select(BridgeGeneration).where(BridgeGeneration.market_id == market.id,
                       BridgeGeneration.algorithm == ALGORITHM, BridgeGeneration.source_signature == signature))
    if cached:
        if stage:
            db.delete(stage)
        return cached
    if stage and stage.source_signature != signature:
        raise HTTPException(409, 'Summary source identity changed during preparation; previous data is preserved')
    if stage is None:
        progress = dict(source_at=bridge.stamp(at), cursor=None, count=0)
        stage = BridgeGeneration(generation_id=digest(['preparing', signature]), market_id=market.id,
            algorithm=STAGING, source_signature=signature, manifest_json=canonical(progress).decode(), created_at=now())
        db.add(stage)
        db.flush()
    snapshots = {s.id: s for s in db.scalars(select(Snapshot).where(Snapshot.id.in_({o.snapshot_id for o in observations})))}
    if len(snapshots) != len({o.snapshot_id for o in observations}) or any(not s.statistics_retained for s in snapshots.values()):
        raise HTTPException(409, 'Retained summary support is unavailable; previous data remains valid')
    missing = [s for s in snapshots.values() if bridge.derivation(db, s, cp.ALGORITHM) is None]
    if any(not s.raw_retained for s in missing):
        raise HTTPException(409, 'Canonical source support is unavailable; no substitute pricing is activated')
    for snapshot in missing[:1]:
        bridge.prepare_snapshot(db, snapshot, cp.ALGORITHM, market.source_kind)
    if missing:
        return None
    # Only current observed variants: historical-only identities are explicitly
    # outside this summary universe. History supports references, not daily charts.
    from .models import BridgeDerivedRecord
    query = select(BridgeDerivedRecord.item_id, BridgeDerivedRecord.variant_key).where(
        BridgeDerivedRecord.snapshot_id == current.snapshot_id, BridgeDerivedRecord.algorithm == cp.ALGORITHM,
        BridgeDerivedRecord.revision == bridge.REVISION)
    if progress['cursor']:
        query = query.where(tuple_(BridgeDerivedRecord.item_id, BridgeDerivedRecord.variant_key) > tuple(progress['cursor']))
    keys = db.execute(query.order_by(BridgeDerivedRecord.item_id, BridgeDerivedRecord.variant_key).limit(PROJECTION_BATCH + 1)).all()
    more = len(keys) > PROJECTION_BATCH
    keys = keys[:PROJECTION_BATCH]
    if progress['count'] + len(keys) > MAX_RECORDS:
        raise HTTPException(413, 'Current market exceeds summary record limit; no items were silently omitted')
    refs = {o.id: i for i, o in enumerate(observations)}
    appended = defaultdict(list)
    for start in range(0, len(keys), 100):
        batch = [tuple(k) for k in keys[start:start+100]]
        values = bridge.record_batch(db, batch, list(snapshots), cp.ALGORITHM)
        for key in batch:
            row = project(bridge.assemble_record(key, values, current, daily, refs, cp.ALGORITHM, at, set()))
            appended[row[0] % BUCKETS].append(canonical(row).decode())
    # At most 64 bounded partials, with no visible generation until sealing.
    partials = {r.position: r for r in db.scalars(select(BridgeRecord).where(BridgeRecord.generation_id == stage.generation_id))}
    total = sum(len(r.record_json) for r in partials.values())
    for bucket, chunks in appended.items():
        existing = partials.get(bucket)
        old = existing.record_json if existing else '[]'
        combined = old[:-1] + (',' if old != '[]' else '') + ','.join(chunks) + ']'
        if len(combined) > MAX_PART:
            raise HTTPException(413, 'Summary partition exceeds 128 KiB; no generation published')
        total += len(combined) - (len(old) if existing else 0)
        if total > MAX_TOTAL:
            raise HTTPException(413, 'Summary exceeds bounded coverage; no generation published')
        if existing:
            existing.record_json = combined
        else:
            existing = BridgeRecord(generation_id=stage.generation_id, position=bucket, record_json=combined)
            db.add(existing)
            partials[bucket] = existing
    progress['count'] += len(keys)
    if keys:
        progress['cursor'] = list(keys[-1])
    stage.manifest_json = canonical(progress).decode()
    if more:
        return None
    final_rows = sorted((row for p in partials.values() for row in json.loads(p.record_json)), key=lambda r: tuple(r[:2]))
    metadata = dict(issuer_id=str(uuid.uuid5(uuid.NAMESPACE_URL, environment.SESSION_ORIGIN)), market=identity,
                    pricing_algorithm=cp.ALGORITHM, history_basis=cp.HISTORY_BASIS,
                    source_kind='market_server_asking_summary', source_watermark=str(watermark),
                    source_observation=dict(observation_id=str(current.id), observed_at=bridge.stamp(at), scope_complete=True),
                    generated_at=bridge.stamp(at), synthetic=any(o.synthetic for o in observations))
    try:
        manifest, parts = seal(metadata, final_rows)
    except ValueError as error:
        raise HTTPException(413, str(error)) from error
    row = BridgeGeneration(generation_id=manifest['generation_id'], market_id=market.id, algorithm=ALGORITHM,
                           source_signature=signature, manifest_json=canonical(manifest).decode(), created_at=now())
    db.add(row)
    db.flush()
    db.delete(stage)
    if parts:
        db.execute(insert(BridgeRecord), [dict(generation_id=row.generation_id, position=b, record_json=raw.decode()) for b, raw in parts.items()])
    # Two disposable exports per market; never delete observations or user data.
    old = list(db.scalars(select(BridgeGeneration.generation_id).where(BridgeGeneration.market_id == market.id,
        BridgeGeneration.algorithm == ALGORITHM).order_by(BridgeGeneration.created_at.desc(), BridgeGeneration.generation_id.desc()).offset(2)))
    if old:
        db.execute(delete(BridgeGeneration).where(BridgeGeneration.generation_id.in_(old)))
    return row


@router.get('/markets/{market_id}/summary')
def summary(market_id: MarketId, request: Request, user: User = Depends(bridge.device_identity), db: Session = Depends(session)):
    market = require_market(db, market_id)
    if not market.verified:
        raise HTTPException(404, 'Verified observed market required')
    row = build(db, market)
    db.commit()
    if row is None:
        return JSONResponse({'state': 'preparing'}, status_code=202, headers={'Retry-After': '5', 'Cache-Control': 'no-store'})
    headers = {'ETag': '"' + row.generation_id + '"', 'Cache-Control': 'no-store'}
    if request.headers.get('if-none-match') == headers['ETag']:
        return Response(status_code=304, headers=headers)
    return JSONResponse(dict(account_id=user.id, manifest=json.loads(row.manifest_json)), headers=headers)


@router.get('/markets/{market_id}/summary/{generation}/parts/{bucket}')
def part(market_id: MarketId, generation: str, bucket: int, user: User = Depends(bridge.device_identity), db: Session = Depends(session)):
    require_market(db, market_id)
    if re.fullmatch('[0-9a-f]{64}', generation) is None or not 0 <= bucket < BUCKETS:
        raise HTTPException(422, 'Invalid summary identity')
    row = db.get(BridgeGeneration, generation)
    if row is None or row.market_id != market_id or row.algorithm != ALGORITHM:
        raise HTTPException(410, 'Summary expired; restart the same authenticated download')
    raw = db.scalar(select(BridgeRecord.record_json).where(BridgeRecord.generation_id == generation, BridgeRecord.position == bucket))
    if raw is None:
        raise HTTPException(404, 'Partition not included; absence is not established')
    return Response(content=raw, media_type='application/json', headers={'Cache-Control': 'no-store'})
