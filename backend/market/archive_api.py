"""Authenticated, pinned retained-summary archive. No collection or provider calls.

The archive retains every available observation and unique snapshot summary,
not a variant × date cross-product and not a giant bridge generation.
"""
import base64
import importlib.util
from functools import lru_cache
from pathlib import Path
from datetime import timedelta
import hashlib
import hmac
import json
import os
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, delete, func, or_, select, tuple_
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from . import bridge_api as bridge, canonical_pricing as cp, environment
from .bridge_contract import contract
from .db import now, session
from .market_api import MarketId, require_market
from .models import (ArchiveCheckpoint, ArchiveDigest, ArchiveMember, BridgeDerivedRecord,
                     Observation, Snapshot, SnapshotStatistic, User, ItemSourceCoverage)
from .security import aware
from .sync_api import secret

router = APIRouter(prefix='/api/v1/archive')
REVISION = 1
MAX_PAGE = 1024 * 1024
MAX_OBSERVATIONS = 100_000
MAX_SNAPSHOTS = 4096
MAX_RECORDS = 100_000_000  # Normalized archive evidence, never a WoW generation.
MAX_METADATA = 64 * 1024 * 1024
MAX_CHECKPOINTS = 512
MAX_CHECKPOINT_METADATA = 256 * 1024 * 1024
TTL = timedelta(hours=24)
SUMMARY_FIELDS = ('state', 'supply', 'priced_supply', 'listing_count', 'minimum_listing_copper',
                  'recent_copper', 'quantity_weighted_ask_copper')


def canonical(value):
    return contract().canonical(value)


def normalized(value, revision=1, coverage=None):
    result = {'variant_json': value['variant_json'],
            'summary': {k: value['summary'][k] for k in SUMMARY_FIELDS}}
    if revision == 2 and coverage is not None:
        result['source_kind'] = coverage.source_kind
        result['coverage_started_at'] = bridge.stamp(coverage.first_observed_at)
    return result


def record_entry(snapshot, item, variant, value, revision=1, coverage=None):
    return {'kind': 'variant', 'snapshot_id': str(snapshot), 'item_id': item,
            'variant_key': variant, 'value': normalized(value, revision, coverage)}


def record_query(snapshot_ids, algorithm, revision=1, source_kind=None):
    model = BridgeDerivedRecord if algorithm == cp.ALGORITHM else SnapshotStatistic
    q = select(model.snapshot_id, model.item_id, model.variant_key).where(model.snapshot_id.in_(snapshot_ids))
    if model is BridgeDerivedRecord:
        q = q.where(model.algorithm == algorithm, model.revision == bridge.REVISION)
    if revision == 1 and source_kind is not None:
        q = q.where(model.source_kind == source_kind)
    return q, model


def coverage_batch(db, market_id, keys):
    if not keys: return {}
    return {(r.item_id, r.variant_key): r for r in db.scalars(select(ItemSourceCoverage).where(
        ItemSourceCoverage.market_id == market_id,
        tuple_(ItemSourceCoverage.item_id, ItemSourceCoverage.variant_key).in_(keys)))}


def evidence_digest(db, snapshot, algorithm, source_kind, revision=1):
    saved = db.get(ArchiveDigest, (snapshot.id, algorithm, revision))
    if not snapshot.statistics_retained:
        raise HTTPException(409, 'Retained snapshot evidence unavailable')
    if saved:
        return saved
    if algorithm == cp.ALGORITHM or snapshot.raw_retained:
        bridge.prepare_snapshot(db, snapshot, algorithm, source_kind)
    q, model = record_query([snapshot.id], algorithm, revision, source_kind)
    after = (0, '')
    count = byte_count = 0
    sha = hashlib.sha256()
    while True:
        keys = list(db.execute(q.where(tuple_(model.item_id, model.variant_key) > after)
                               .order_by(model.item_id, model.variant_key).limit(100)))
        if not keys:
            break
        pairs = [(i, v) for _, i, v in keys]
        values = bridge.record_batch(db, pairs, [snapshot.id], algorithm)
        coverage = coverage_batch(db, snapshot.market_id, pairs) if revision == 2 else {}
        for sid, item, variant in keys:
            raw = canonical(record_entry(sid, item, variant, values[sid, item, variant], revision, coverage.get((item, variant))))
            if len(raw) > 65536:
                raise HTTPException(413, 'Archive record byte limit')
            sha.update(raw + b'\n')
            byte_count += len(raw) + 1
            count += 1
        after = pairs[-1]
    saved = ArchiveDigest(snapshot_id=snapshot.id, algorithm=algorithm, revision=revision,
                          record_count=count, records_sha256=sha.hexdigest(), records_bytes=byte_count)
    db.add(saved)
    db.flush()
    return saved


def authorization_key(credential):
    # Companion access credentials rotate; the authenticated device remains the
    # same principal. Legacy device tokens retain their existing credential key.
    return -credential.companion_device_id if credential.companion_device_id is not None else credential.id


def get_checkpoint(db, checkpoint, market, user, credential, unexpired=True):
    row = db.get(ArchiveCheckpoint, checkpoint)
    if (row is None or row.market_id != market or row.user_id != user.id or row.credential_id != authorization_key(credential)
            or (unexpired and aware(row.expires_at) <= now())):
        raise HTTPException(409, 'Archive checkpoint unavailable; restart pending download')
    return row


def cursor(row, phase=0, after=None, position=0, chain=None):
    p = {'v': 1, 'kind': 'archive', 'checkpoint': row.checkpoint_id, 'market': row.market_id,
         'account': row.user_id, 'credential': row.credential_id, 'phase': phase,
         'after': after or [0, 0, ''], 'position': position, 'chain': chain or '0' * 64,
         'expires': int(aware(row.expires_at).timestamp())}
    raw = base64.urlsafe_b64encode(canonical(p)).decode().rstrip('=')
    return raw + '.' + hmac.new(secret(), ('archive-v1:' + raw).encode(), hashlib.sha256).hexdigest()


def decode(value, row):
    try:
        raw, signature = value.split('.')
        if not hmac.compare_digest(signature, hmac.new(secret(), ('archive-v1:' + raw).encode(), hashlib.sha256).hexdigest()):
            raise ValueError()
        p = json.loads(base64.b64decode(raw + '=' * (-len(raw) % 4), altchars=b'-_', validate=True))
        if (set(p) != {'v', 'kind', 'checkpoint', 'market', 'account', 'credential', 'phase', 'after', 'position', 'chain', 'expires'}
                or p['v'] != 1 or p['kind'] != 'archive'
                or (p['checkpoint'], p['market'], p['account'], p['credential']) != (row.checkpoint_id, row.market_id, row.user_id, row.credential_id)
                or type(p['phase']) is not int or not 0 <= p['phase'] <= 3
                or type(p['position']) is not int or not 0 <= p['position'] <= MAX_RECORDS + MAX_OBSERVATIONS + MAX_SNAPSHOTS
                or type(p['expires']) is not int or p['expires'] != int(aware(row.expires_at).timestamp())
                or not isinstance(p['after'], list) or len(p['after']) != 3
                or any(type(x) is not int or x < 0 for x in p['after'][:2])
                or not isinstance(p['after'][2], str) or len(p['after'][2]) > 64
                or re.fullmatch('[0-9a-f]{64}', p['chain']) is None):
            raise ValueError()
        return p
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(409, 'Invalid archive cursor; restart pending download')


@router.get('/markets/{market_id}/checkpoint')
def checkpoint(market_id: MarketId, request: Request, algorithm: str = Query(cp.ALGORITHM, max_length=80),
               protocol: int = Query(1, ge=1, le=2),
               base: str | None = Query(None, min_length=64, max_length=64),
               user: User = Depends(bridge.device_identity), db: Session = Depends(session)):
    if algorithm not in (cp.ALGORITHM, bridge.LEGACY):
        raise HTTPException(422, 'Unsupported archive pricing algorithm')
    market = require_market(db, market_id)
    if not market.verified:
        raise HTTPException(404, 'Verified market required')
    bridge.lock(db)
    at = now()
    previous = get_checkpoint(db, base, market_id, user, request.state.credential, False) if base else None
    old = json.loads(previous.header_json) if previous else None
    if old and old['protocol_version'] != protocol:
        raise HTTPException(409, 'Archive source coverage protocol changed; bootstrap required')
    if old and old['pricing_algorithm'] != algorithm:
        raise HTTPException(409, 'Archive base algorithm mismatch')
    base_watermark = int(old['watermark_observation_id']) if old else 0
    watermark = db.scalar(select(func.max(Observation.id)).where(Observation.market_id == market_id, Observation.retrieved_at <= at))
    if watermark is None:
        raise HTTPException(409, 'No retained observations')
    obs_query = select(Observation).where(Observation.market_id == market_id, Observation.id <= watermark, Observation.retrieved_at <= at)
    count, earliest, latest = db.execute(obs_query.with_only_columns(func.count(), func.min(Observation.retrieved_at), func.max(Observation.retrieved_at))).one()
    if count > MAX_OBSERVATIONS:
        raise HTTPException(413, 'Archive observation bound')
    if old and db.scalar(select(func.count()).select_from(obs_query.where(Observation.id <= base_watermark).subquery())) != old['total_observations']:
        raise HTTPException(409, 'Source retention changed; bootstrap required')
    ids = list(db.scalars(select(Observation.snapshot_id).where(Observation.market_id == market_id,
             Observation.id <= watermark, Observation.retrieved_at <= at).distinct().order_by(Observation.snapshot_id).limit(MAX_SNAPSHOTS + 1)))
    if len(ids) > MAX_SNAPSHOTS:
        raise HTTPException(413, 'Archive snapshot bound')
    snapshots = {s.id: s for s in db.scalars(select(Snapshot).where(Snapshot.id.in_(ids)))}
    if len(snapshots) != len(ids):
        raise HTTPException(409, 'Retained snapshots unavailable')
    if any(not s.statistics_retained for s in snapshots.values()):
        raise HTTPException(409, 'Retained snapshot evidence unavailable')
    digests = {d.snapshot_id: d for d in db.scalars(select(ArchiveDigest).where(
        ArchiveDigest.snapshot_id.in_(ids), ArchiveDigest.algorithm == algorithm, ArchiveDigest.revision == protocol))}
    pending = [s for s in snapshots.values() if s.id not in digests]
    for s in pending[:1]:
        digests[s.id] = evidence_digest(db, s, algorithm, market.source_kind, protocol)
    if len(pending) > 1:
        db.commit()
        return JSONResponse({'state': 'preparing', 'retry_after_seconds': 1}, status_code=202, headers={'Cache-Control': 'no-store', 'Retry-After': '1'})
    identity = bridge.market_identity(db, market)
    # Repeated equivalent requests reuse a still-valid checkpoint. Never evict an
    # unexpired peer download merely because another device requests a refresh.
    previous_rows = list(db.scalars(select(ArchiveCheckpoint).order_by(ArchiveCheckpoint.created_at.desc())))
    for existing in previous_rows:
        if aware(existing.expires_at) <= at:
            continue
        saved = json.loads(existing.header_json)
        if (existing.market_id == market_id and existing.user_id == user.id
                and existing.credential_id == authorization_key(request.state.credential)
                and saved['protocol_version'] == protocol and saved['pricing_algorithm'] == algorithm and saved['base_checkpoint_id'] == base
                and saved['watermark_observation_id'] == str(watermark)
                and saved['total_observations'] == count and saved['total_snapshots'] == len(ids)
                and saved['market'] == identity and saved['generated_at'][:10] == at.date().isoformat()):
            db.commit()
            return JSONResponse({'header': saved, 'cursor': cursor(existing)}, headers={'Cache-Control': 'no-store'})
    for existing in reversed(previous_rows):
        if aware(existing.expires_at) <= at and (len(previous_rows) >= MAX_CHECKPOINTS or aware(existing.created_at) < at - timedelta(days=7)):
            db.execute(delete(ArchiveMember).where(ArchiveMember.checkpoint_id == existing.checkpoint_id))
            db.delete(existing)
    db.flush()
    if db.scalar(select(func.count()).select_from(ArchiveCheckpoint)) >= MAX_CHECKPOINTS:
        raise HTTPException(503, 'Archive checkpoint storage busy; retry after an existing checkpoint expires')
    stored_metadata = db.scalar(select(func.coalesce(func.sum(func.length(ArchiveMember.value_json)), 0)))
    # Persist only bounded checkpoint metadata. Variant evidence remains normalized
    # in existing immutable versioned derivations/statistics, never copied per checkpoint.
    checkpoint_id = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    row = ArchiveCheckpoint(checkpoint_id=checkpoint_id, market_id=market_id, user_id=user.id,
          credential_id=authorization_key(request.state.credential), header_json='{}', created_at=at, expires_at=at + TTL)
    db.add(row)
    db.flush()
    sha = hashlib.sha256()
    byte_count = 0
    sent_observations = sent_snapshots = sent_records = 0
    total_records = 0
    transfer_bytes = 0
    old_snapshots = set(db.scalars(select(Observation.snapshot_id).where(Observation.market_id == market_id,
                         Observation.id <= base_watermark))) if old else set()
    for ordinal, o in enumerate(db.scalars(obs_query.order_by(Observation.id).execution_options(yield_per=500)), 1):
        entry = {'kind': 'observation', 'observation': bridge.observation_view(o, snapshots[o.snapshot_id], aware(o.retrieved_at))}
        raw = canonical(entry)
        byte_count += len(raw)
        if stored_metadata + byte_count > MAX_CHECKPOINT_METADATA:
            raise HTTPException(503, 'Archive checkpoint metadata budget unavailable; retry later')
        if byte_count > MAX_METADATA:
            raise HTTPException(413, 'Archive checkpoint metadata bound')
        sha.update(raw + b'\n')
        send = o.id > base_watermark
        sent_observations += send
        transfer_bytes += len(raw) + 1 if send else 0
        db.add(ArchiveMember(checkpoint_id=checkpoint_id, phase=0, source_id=o.id, value_json=raw.decode(), transmit=send))
        if ordinal % 500 == 0:
            db.flush()
    for sid in ids:
        s = snapshots[sid]
        d = digests[sid]
        send = sid not in old_snapshots
        total_records += d.record_count
        sent_snapshots += send
        sent_records += d.record_count if send else 0
        entry = {'kind': 'snapshot', 'snapshot_id': str(sid), 'content_sha256': s.content_hash,
                 'record_count': d.record_count, 'records_sha256': d.records_sha256, 'records_bytes': d.records_bytes}
        raw = canonical(entry)
        byte_count += len(raw)
        if byte_count > MAX_METADATA or stored_metadata + byte_count > MAX_CHECKPOINT_METADATA:
            raise HTTPException(503, 'Archive checkpoint metadata budget unavailable; retry later')
        transfer_bytes += len(raw) + 1 + d.records_bytes if send else 0
        sha.update(raw + b'\n')
        db.add(ArchiveMember(checkpoint_id=checkpoint_id, phase=1, source_id=sid, value_json=raw.decode(), transmit=send))
    if total_records > MAX_RECORDS:
        raise HTTPException(413, 'Archive record bound')
    if transfer_bytes > 1024**4:
        raise HTTPException(413, 'Archive transfer byte bound')
    header = {'format': 'twichui-history-archive', 'protocol_version': protocol, 'checkpoint_id': checkpoint_id,
              'account_id': user.id, 'issuer_id': str(uuid.uuid5(uuid.NAMESPACE_URL, environment.SESSION_ORIGIN)),
              'market': identity, 'pricing_algorithm': algorithm,
              'history_basis': cp.HISTORY_BASIS if algorithm == cp.ALGORITHM else 'market_rolling_daily_means',
              'evidence_revision': protocol, 'watermark_observation_id': str(watermark),
              'base_checkpoint_id': base, 'base_watermark_observation_id': str(base_watermark),
              'generated_at': bridge.stamp(at), 'expires_at': bridge.stamp(row.expires_at),
              'server_checked_at': bridge.stamp(market.last_success) if market.last_success and aware(market.last_success) <= at else None,
              'server_build': (os.environ.get('APP_COMMIT') or 'development-archive-l2')[:80],
              'retention_basis': 'all_retained_observations_and_snapshot_summaries', 'archive_complete': True,
              'retained_from_day': aware(earliest).date().isoformat(), 'retained_through_day': aware(latest).date().isoformat(),
              'total_observations': count, 'total_snapshots': len(ids), 'total_records': total_records,
              'transfer_observations': sent_observations, 'transfer_snapshots': sent_snapshots, 'transfer_records': sent_records,
              'transfer_bytes': transfer_bytes,
              'metadata_sha256': sha.hexdigest()}
    row.header_json = canonical(header).decode()
    db.commit()
    return JSONResponse({'header': header, 'cursor': cursor(row)}, headers={'Cache-Control': 'no-store'})


@router.get('/markets/{market_id}/pages')
def pages(market_id: MarketId, request: Request, checkpoint: str = Query(min_length=64, max_length=64),
          cursor_value: str = Query(alias='cursor', min_length=1, max_length=2048), limit: int = Query(100, ge=1, le=100),
          user: User = Depends(bridge.device_identity), db: Session = Depends(session)):
    row = get_checkpoint(db, checkpoint, market_id, user, request.state.credential)
    bridge.lock(db)
    p = decode(cursor_value, row)
    header = json.loads(row.header_json)
    phase, after = p['phase'], p['after']
    entries = []
    size = 4096
    while phase < 3 and len(entries) < limit:
        if phase < 2:
            rows = list(db.scalars(select(ArchiveMember).where(ArchiveMember.checkpoint_id == checkpoint,
                   ArchiveMember.phase == phase, ArchiveMember.transmit.is_(True), ArchiveMember.source_id > after[0])
                   .order_by(ArchiveMember.source_id).limit(limit - len(entries))))
            candidates = [(json.loads(x.value_json), [x.source_id, 0, '']) for x in rows]
        else:
            sub = select(ArchiveMember.source_id).where(ArchiveMember.checkpoint_id == checkpoint, ArchiveMember.phase == 1, ArchiveMember.transmit.is_(True))
            q, model = record_query(sub, header['pricing_algorithm'], header['protocol_version'], header['market']['source_kind'])
            keys = list(db.execute(q.where(tuple_(model.snapshot_id, model.item_id, model.variant_key) > tuple(after))
                   .order_by(model.snapshot_id, model.item_id, model.variant_key).limit(limit - len(entries))))
            vals = bridge.record_batch(db, [(i, v) for _, i, v in keys], list({s for s, _, _ in keys}), header['pricing_algorithm']) if keys else {}
            coverage = coverage_batch(db, market_id, [(i, v) for _, i, v in keys]) if header['protocol_version'] == 2 else {}
            candidates = [(record_entry(s, i, v, vals[s, i, v], header['protocol_version'], coverage.get((i, v))), [s, i, v]) for s, i, v in keys]
        if not candidates:
            phase += 1
            after = [0, 0, '']
            continue
        for entry, next_after in candidates:
            raw = canonical(entry)
            if size + len(raw) > MAX_PAGE:
                if not entries:
                    raise HTTPException(413, 'Archive entry byte limit')
                break
            entries.append(entry)
            size += len(raw) + 1
            after = next_after
        else:
            continue
        break
    end = p['position'] + len(entries)
    expected = header['transfer_observations'] + header['transfer_snapshots'] + header['transfer_records']
    if end > expected or (phase == 3 and end != expected) or (not entries and end != expected):
        raise HTTPException(409, 'Archive evidence changed or incomplete; restart pending download')
    more = end < expected
    chain = hashlib.sha256(bytes.fromhex(p['chain']) + canonical(entries)).hexdigest()
    result = {'format': 'twichui-history-archive-page', 'protocol_version': header['protocol_version'], 'checkpoint_id': checkpoint,
              'account_id': user.id, 'market_id': market_id, 'offset': p['position'], 'entries': entries,
              'previous_sha256': p['chain'], 'page_sha256': hashlib.sha256(canonical(entries)).hexdigest(),
              'chain_sha256': chain, 'has_more': more,
              'next_cursor': cursor(row, phase, after, end, chain) if more else None}
    if len(canonical(result)) > MAX_PAGE:
        raise HTTPException(413, 'Archive page byte limit')
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})


# The approved pure L1 selection/hash/coverage checks remain authoritative. This
# loader uses the explicit contract bundle next to v1, never a caller's cwd.
@lru_cache(maxsize=1)
def scoped_contract():
    root = Path(contract().__file__).resolve().parent.parent / 'scoped-l1'
    if not (root / 'reference.py').is_file():
        raise HTTPException(503, 'Scoped contract bundle unavailable')
    spec = importlib.util.spec_from_file_location('market_scoped_contract', root / 'reference.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def scoped_generation(db, row, requested):
    from datetime import date, timedelta
    from types import SimpleNamespace
    c = scoped_contract()
    request = c.selection(requested, normalize=True)
    h = json.loads(row.header_json)
    if (request['market'] != h['market'] or request['issuer_id'] != h['issuer_id']
            or request['pricing_algorithm'] != h['pricing_algorithm'] or request['history_basis'] != h['history_basis']):
        raise HTTPException(409, 'Selection differs from authenticated checkpoint')
    if len(request['variants']) > 100:
        raise c.Refusal('capacity', {'sizes': {'records': len(request['variants'])},
            'exceeded': {'records': {'actual': len(request['variants']), 'limit': 100}}})
    at = c.v1.timestamp(h['generated_at'])
    today = at.date()
    if request['history_through_day'] > today.isoformat() or not 0 <= (today - date.fromisoformat(request['history_from_day'])).days < 60:
        raise HTTPException(422, 'Unsupported scoped history window')
    # Stream all checkpoint observation metadata but retain only current and <=60
    # daily winners; no all-market record materialization or per-variant query.
    daily = {}
    current = None
    synthetic = False
    for member in db.scalars(select(ArchiveMember).where(ArchiveMember.checkpoint_id == row.checkpoint_id,
                            ArchiveMember.phase == 0).order_by(ArchiveMember.source_id).execution_options(yield_per=500)):
        o = json.loads(member.value_json)['observation']
        synthetic |= o['synthetic']
        chronology = (c.v1.timestamp(o['observed_at']), int(o['observation_id']))
        if current is None or chronology > current[0]:
            current = (chronology, o)
        age = (today - date.fromisoformat(o['utc_day'])).days
        if 0 <= age < 60 and (h['pricing_algorithm'] != cp.ALGORITHM or o['scope_complete']):
            if o['utc_day'] not in daily or chronology > daily[o['utc_day']][0]:
                daily[o['utc_day']] = (chronology, o)
    if current is None:
        raise HTTPException(409, 'Checkpoint observations missing')
    selected = sorted({o['observation_id']: o for _, o in [*daily.values(), current]}.values(),
                      key=lambda o: (c.v1.timestamp(o['observed_at']), int(o['observation_id'])))
    refs = {o['observation_id']: i for i, o in enumerate(selected)}
    objects = {o['observation_id']: SimpleNamespace(id=int(o['observation_id']), snapshot_id=int(o['snapshot_id']), retrieved_at=c.v1.timestamp(o['observed_at'])) for o in selected}
    latest = objects[current[1]['observation_id']]
    closes = [objects[o['observation_id']] for _, o in sorted(daily.values(), key=lambda x: x[0])]
    keys = [(r['item_id'], r['variant_key']) for r in request['variants']]
    snapshot_ids = {o.snapshot_id for o in objects.values()}
    union_ids = select(ArchiveMember.source_id).where(ArchiveMember.checkpoint_id == row.checkpoint_id, ArchiveMember.phase == 1)
    q, model = record_query(union_ids, h['pricing_algorithm'], h['protocol_version'], h['market']['source_kind'])
    known = set(db.execute(q.with_only_columns(model.item_id, model.variant_key).where(tuple_(model.item_id, model.variant_key).in_(keys)).distinct()))
    if any(k not in known for k in keys):
        raise HTTPException(409, 'Requested exact identity unavailable in retained checkpoint')
    values = bridge.record_batch(db, keys, list(snapshot_ids), h['pricing_algorithm'])
    expected = {m.source_id: json.loads(m.value_json)['record_count'] for m in db.scalars(select(ArchiveMember).where(
        ArchiveMember.checkpoint_id == row.checkpoint_id, ArchiveMember.phase == 1, ArchiveMember.source_id.in_(snapshot_ids)))}
    count_query, model = record_query(snapshot_ids, h['pricing_algorithm'], h['protocol_version'], h['market']['source_kind'])
    actual = dict(db.execute(count_query.with_only_columns(model.snapshot_id, func.count()).group_by(model.snapshot_id)).all())
    if set(expected) != snapshot_ids or any(actual.get(sid, 0) != count for sid, count in expected.items()):
        raise HTTPException(409, 'Retained checkpoint evidence incomplete')
    remapped = {int(oid): ref for oid, ref in refs.items()}
    delivered = {o.id for o in closes if request['history_from_day'] <= bridge.utc(o.retrieved_at).date().isoformat() <= request['history_through_day']}
    records = []
    starts = coverage_batch(db, h['market']['server_market_id'], keys) if h['protocol_version'] == 2 else {}
    for key in keys:
        r = bridge.assemble_record(key, values, latest, closes, remapped, h['pricing_algorithm'], at, delivered, starts[key].first_observed_at if key in starts else None)
        r['distribution'], r['distribution_status'] = None, 'omitted_budget'
        records.append(r)
    missing_descriptors = [(r['item_id'], r['variant_key']) for r in records if r['variant_json'] is None]
    if missing_descriptors:
        descriptors = {}
        for derived in db.scalars(select(BridgeDerivedRecord).where(BridgeDerivedRecord.snapshot_id.in_(union_ids),
                BridgeDerivedRecord.algorithm == h['pricing_algorithm'], BridgeDerivedRecord.revision == bridge.REVISION,
                tuple_(BridgeDerivedRecord.item_id, BridgeDerivedRecord.variant_key).in_(missing_descriptors))
                .order_by(BridgeDerivedRecord.snapshot_id).execution_options(yield_per=500)):
            descriptor = json.loads(derived.record_json)['variant_json']
            if descriptor is not None:
                descriptors[derived.item_id, derived.variant_key] = descriptor
        for record in records:
            descriptor = descriptors.get((record['item_id'], record['variant_key']))
            if record['variant_json'] is None and descriptor is not None:
                record['variant_json'], record['identity_basis'] = descriptor, 'exact_upstream'
    days = len({o['utc_day'] for o in selected if request['history_from_day'] <= o['utc_day'] <= request['history_through_day']})
    g = {'format': 'twichui-market-bridge', 'contract_version': 1, 'schema_version': 3, 'transport_version': 1,
         'issuer_id': h['issuer_id'], 'producer': {'server_build': h['server_build'], 'desktop_build': 'not-applicable-server-export'},
         'required_features': c.FEATURES, 'market': h['market'], 'pricing_algorithm': h['pricing_algorithm'], 'history_basis': h['history_basis'], 'quality_policy': 1,
         'watermark_observation_id': h['watermark_observation_id'], 'current_observation_ref': refs[current[1]['observation_id']],
         'as_of_utc_day': today.isoformat(), 'generated_at': h['generated_at'], 'desktop_sync_completed_at': None, 'server_checked_at': h['server_checked_at'],
         'observations': selected, 'synthetic': synthetic, 'record_count': len(records), 'records': records,
         'coverage': {'scope': 'house_commodities' if h['market']['source_kind'] == 'commodities' else 'house_auctions',
             'generation_complete': False, 'current_complete': current[1]['scope_complete'], 'history_from_day': request['history_from_day'], 'history_through_day': request['history_through_day'],
             'available_observed_days': days, 'delivered_observed_days': days, 'history_complete': True, 'history_truncated': False,
             'distribution_complete': False, 'omitted_sections': ['distributions']}}
    g['scope'] = {'type': 'explicit_variants', 'selection_id': c.selection_id(request), 'request_digest': c.digest(request), 'request': request,
        'requested_count': len(keys), 'included': request['variants'], 'excluded': [], 'scope_complete': True, 'whole_market_complete': False,
        'date_coverage': c.date_coverage(g, request), 'record_sha256': [c.digest(r) for r in records]}
    g = c.seal(g)
    sizing_receipt = c.receipt(g, completed_at=bridge.stamp(at))
    sizing_receipt['desktop_build'] = 'X' * 80  # Conservative receipt upper bound; never published as a real receipt.
    c.preflight(g, sizing_receipt, {'canonical_bytes': 2 * 1024**2, 'lua_bytes': 3 * 1024**2, 'records': 100})
    c.validate(g, request)
    return g


@router.post('/markets/{market_id}/scoped')
async def scoped(market_id: MarketId, request: Request, checkpoint: str = Query(min_length=64, max_length=64),
                 user: User = Depends(bridge.device_identity), db: Session = Depends(session)):
    row = get_checkpoint(db, checkpoint, market_id, user, request.state.credential)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 128 * 1024:
            raise HTTPException(413, 'Scoped request byte limit')
    def unique(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    try:
        selected = json.loads(body, object_pairs_hook=unique)
        def produce():
            bridge.lock(db)
            return scoped_generation(db, row, selected)
        result = await run_in_threadpool(produce)
    except scoped_contract().Refusal as error:
        if error.code == 'capacity':
            return JSONResponse({'error': 'capacity', **error.diagnostics}, status_code=413, headers={'Cache-Control': 'no-store'})
        raise HTTPException(422, 'Invalid scoped request or generation')
    except (ValueError, TypeError, KeyError, __import__('jsonschema').ValidationError):
        raise HTTPException(422, 'Invalid scoped request or generation')
    return JSONResponse(result, headers={'Cache-Control': 'no-store'})
