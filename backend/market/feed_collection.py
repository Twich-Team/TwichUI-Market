"""Bounded sequential source capture and conservative complete-market publication.

Successes survive a peer failure. No mixed-age logical observation is published.
All configuration is opt-in and bound to a reviewed exact source identity.
"""
import gzip
import hashlib
import json
import re
import uuid
from collections import defaultdict
from datetime import timedelta
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from sqlalchemy import delete, insert, select, tuple_
from .db import now
from .ingest import (MAX_LISTINGS, ListingCapacityExceeded, canonical, listing_digest,
                     normalize, record_daily)
from .models import (FeedCapture, FeedCheck, ItemSourceCoverage, Listing, MarketFeed,
                     Observation, Snapshot, SnapshotStatistic)
from .pricing import ALGORITHM, summarize
from .security import aware

KINDS = ('auctions', 'commodities')
MAX_PAYLOAD = 32 * 1024 * 1024


def verified_identity(market, feed):
    expected = {'region': market.region, 'ruleset_id': market.ruleset_id,
                'house_id': market.house_id, 'source_kind': feed.source_kind,
                'namespace': f'dynamic-forever-{market.region}', 'scope': 'ruleset_house'}
    proof = json.loads(feed.verification)
    if not isinstance(proof, dict): raise ValueError('Invalid feed verification object')
    if feed.source_kind not in KINDS or proof.get('identity') != expected:
        raise ValueError('Feed verification does not match market')
    if not isinstance(proof.get('evidence_sha256'), str) or re.fullmatch('[0-9a-f]{64}', proof['evidence_sha256']) is None:
        raise ValueError('Missing reviewed feed evidence')
    return expected


def decode(capture):
    # Reject a corrupted oversized/decompression-bomb capture before allocation.
    import io
    if capture.compressed_payload is None: raise ValueError('Source payload was compacted')
    with gzip.GzipFile(fileobj=io.BytesIO(capture.compressed_payload)) as stream:
        body = stream.read(MAX_PAYLOAD + 1)
    if len(body) > MAX_PAYLOAD or len(body) != capture.payload_bytes:
        raise ValueError('Capture byte bound')
    if hashlib.sha256(body).hexdigest() != capture.payload_hash:
        raise ValueError('Capture integrity failure')
    return json.loads(body)


def capture_feed(db, market, feed, client, at):
    from .worker import UpstreamFailure, retry_seconds
    check = FeedCheck(market_id=market.id, source_kind=feed.source_kind, checked_at=at, status='failed')
    db.add(check)
    feed.last_check = at
    try:
        verified_identity(market, feed)
        if feed.retry_after and aware(feed.retry_after) > at:
            check.status, check.error = 'deferred', 'Feed is waiting for its persisted retry window'
            db.flush()
            return check
        transport = SimpleNamespace(region=market.region, ruleset_id=market.ruleset_id,
            house_id=market.house_id, source_kind=feed.source_kind, etag=feed.etag, last_modified=feed.last_modified)
        meta, body = client.fetch(transport)
        check.http_status = meta['status']
        if meta['status'] == 200:
            if len(body) > MAX_PAYLOAD:
                raise ValueError('Payload byte bound')
            headers = meta['headers']
            if headers.get('Battlenet-Namespace') != f'dynamic-forever-{market.region}':
                raise ValueError('Namespace mismatch')
            payload = json.loads(body)
            if not isinstance(payload, dict): raise ValueError('Expected source object')
            # The commodity feed has no house/name fields; bind its self link to
            # the same-house commodities link established by the reviewed receipt.
            path = f'/data/wow/ruleset/{market.ruleset_id}/auctions/{market.house_id}'
            path += '/commodities' if feed.source_kind == 'commodities' else ''
            links = payload.get('_links')
            source = links.get('self') if isinstance(links, dict) else None
            href = source.get('href') if isinstance(source, dict) else None
            if not isinstance(href, str): raise ValueError('Missing source identity link')
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(href)
            if (parsed.scheme != 'https' or parsed.netloc != f'{market.region}.api.blizzard.com'
                    or parsed.path != path or parse_qs(parsed.query).get('namespace') != [f'dynamic-forever-{market.region}']):
                raise ValueError('Response source identity mismatch')
            if feed.source_kind == 'auctions' and payload.get('id') != market.house_id:
                raise ValueError('House identity mismatch')
            rows = normalize(payload, feed.source_kind)
            del payload
            # Commodity canonical identity is the observed base item descriptor.
            # Do not silently collapse newly introduced variants.
            if feed.source_kind == 'commodities' and any(json.loads(r['variant']) != {'id': r['item_id']} for r in rows):
                raise ValueError('Unverified commodity variant contract')
            payload_hash = hashlib.sha256(body).hexdigest()
            capture = db.scalar(select(FeedCapture).where(FeedCapture.market_id == market.id,
                FeedCapture.source_kind == feed.source_kind, FeedCapture.payload_hash == payload_hash))
            if capture is None:
                capture = FeedCapture(market_id=market.id, source_kind=feed.source_kind, observed_at=at,
                    payload_hash=payload_hash, content_hash=listing_digest(rows),
                    payload_bytes=len(body), compressed_payload=gzip.compress(body, mtime=0), payload_retained_at=at,
                    listing_count=len(rows), item_count=len({r['item_id'] for r in rows}))
                db.add(capture)
                db.flush()
            if capture.compressed_payload is None:
                capture.compressed_payload = gzip.compress(body, mtime=0)
                capture.payload_retained_at = at
            feed.capture_id = capture.id
            feed.last_modified, feed.etag = headers.get('Last-Modified'), headers.get('ETag')
            check.status = 'collected'
        elif meta['status'] == 304:
            if feed.capture_id is None:
                feed.etag = feed.last_modified = None
                raise ValueError('304 without prior capture')
            check.status = 'unchanged'
        else:
            raise UpstreamFailure('Upstream HTTP failure', meta['status'], meta['headers'].get('Retry-After'))
        check.capture_id, check.upstream_modified, check.etag = feed.capture_id, feed.last_modified, feed.etag
        feed.last_success, feed.failures, feed.last_error, feed.retry_after = at, 0, None, None
    except (UpstreamFailure, OSError, ValueError, KeyError, TypeError) as error:
        feed.failures += 1
        if isinstance(error, ListingCapacityExceeded):
            reason = f'Feed exceeds collector listing capacity ({MAX_LISTINGS}); last valid data retained'
        else:
            reason = (f'Upstream HTTP {error.status}' if error.status else error.reason) if isinstance(error, UpstreamFailure) else 'Feed transport, identity or payload validation failed'
        check.error = feed.last_error = reason
        retry = retry_seconds(error.retry_after, at) if isinstance(error, UpstreamFailure) else 0
        feed.retry_after = at + timedelta(seconds=max(300, min(300 * 2**min(feed.failures - 1, 8), 86400), retry))
    db.flush()
    return check


def publish(db, market, checks, at):
    """Normalize one feed at a time; no second copy of original listing tables."""
    captures = [db.get(FeedCapture, check.capture_id) for check in checks]
    if any(c is None or c.market_id != market.id or c.source_kind != check.source_kind for c, check in zip(captures, checks)):
        raise ValueError('Source capture identity mismatch')
    content_hash = hashlib.sha256(canonical([[c.source_kind, c.content_hash] for c in captures]).encode()).hexdigest()
    snapshot = db.scalar(select(Snapshot).where(Snapshot.market_id == market.id, Snapshot.content_hash == content_hash))
    needs_raw = snapshot is None or not snapshot.raw_retained
    needs_statistics = snapshot is None or not snapshot.statistics_retained
    if snapshot is None:
        snapshot = Snapshot(market_id=market.id, content_hash=content_hash,
                            listing_count=sum(c.listing_count for c in captures))
        db.add(snapshot)
        db.flush()
    if needs_raw or needs_statistics:
        if needs_raw: db.execute(delete(Listing).where(Listing.snapshot_id == snapshot.id))
        if needs_statistics: db.execute(delete(SnapshotStatistic).where(SnapshotStatistic.snapshot_id == snapshot.id))
        seen_ids, seen_variants = set(), set()
        for capture in captures:
            rows = normalize(decode(capture), capture.source_kind)
            current_ids = {r['auction_id'] for r in rows}
            current_variants = {(r['item_id'], r['variant_key']) for r in rows}
            # Same listing/variant in both feeds would need independently
            # verified overlap semantics. Fail closed, never double-count it.
            if seen_ids & current_ids or seen_variants & current_variants:
                raise ValueError('Unverified cross-feed overlap')
            seen_ids.update(current_ids)
            seen_variants.update(current_variants)
            for offset in range(0, len(rows) if needs_raw else 0, 1000):
                db.execute(insert(Listing), [dict(snapshot_id=snapshot.id, source_kind=capture.source_kind, **row)
                    for row in rows[offset:offset+1000]])
            groups = defaultdict(list)
            for row in rows:
                groups[row['item_id'], row['variant_key']].append(row)
            stats = [dict(snapshot_id=snapshot.id, item_id=item, variant_key=variant, algorithm=ALGORITHM, source_kind=capture.source_kind, **summarize([SimpleNamespace(**row) for row in entries]))
                     for (item, variant), entries in groups.items()]
            for offset in range(0, len(stats) if needs_statistics else 0, 1000):
                db.execute(insert(SnapshotStatistic), stats[offset:offset+1000])
            # New coverage is recorded only for genuinely observed commodity
            # identities. Ordinary historical absence behavior stays unchanged.
            if capture.source_kind == 'commodities':
                existing = set(db.execute(select(ItemSourceCoverage.item_id, ItemSourceCoverage.variant_key).where(
                    ItemSourceCoverage.market_id == market.id)))
                additions = sorted(current_variants - existing)
                for offset in range(0, len(additions), 1000):
                    prior = db.scalar(select(SnapshotStatistic.item_id).join(Snapshot, Snapshot.id==SnapshotStatistic.snapshot_id).where(
                        Snapshot.market_id==market.id, SnapshotStatistic.source_kind=='auctions',
                        tuple_(SnapshotStatistic.item_id, SnapshotStatistic.variant_key).in_(additions[offset:offset+1000])).limit(1))
                    if prior is not None: raise ValueError('Unverified historical source transition')
                db.add_all([ItemSourceCoverage(market_id=market.id, item_id=item, variant_key=variant,
                    source_kind='commodities', first_observed_at=capture.observed_at)
                    for item, variant in current_variants - existing])
            del rows, groups, stats
    snapshot.raw_retained = snapshot.statistics_retained = True
    manifest = [{'source_kind': c.source_kind, 'check_id': check.id, 'capture_id': c.id,
        'payload_sha256': c.payload_hash, 'checked_at': at.isoformat(),
        'region': market.region, 'ruleset_id': market.ruleset_id, 'house_id': market.house_id,
        'namespace': f'dynamic-forever-{market.region}', 'status': check.status, 'http_status': check.http_status,
        'verification_sha256': json.loads(db.get(MarketFeed, (market.id, c.source_kind)).verification)['evidence_sha256'],
        'upstream_modified': check.upstream_modified} for c, check in zip(captures, checks)]
    # The logical source time is the older feed, never the newer peer's time.
    modified = [check.upstream_modified for check in checks]
    try:
        oldest = min(modified, key=lambda value: aware(parsedate_to_datetime(value))) if all(modified) else None
    except (ValueError, TypeError, OverflowError):
        oldest = None
    raw_manifest = canonical(manifest)
    observation = Observation(market_id=market.id, snapshot_id=snapshot.id, request_key=uuid.uuid4().hex,
        retrieved_at=at, upstream_modified=oldest, namespace=f'dynamic-forever-{market.region}',
        payload_hash=hashlib.sha256(raw_manifest.encode()).hexdigest(), payload_bytes=sum(c.payload_bytes for c, check in zip(captures, checks) if check.status=='collected'),
        synthetic=False, source_manifest=raw_manifest)
    db.add(observation)
    db.flush()
    record_daily(db, observation)
    market.last_success, market.last_modified = at, oldest
    return observation


def collect_feeds(db, market, feeds, client, at, run):
    if [f.source_kind for f in feeds] != list(KINDS):
        raise ValueError('Unified coverage requires both verified enabled feeds')
    checks = [capture_feed(db, market, feed, client, at) for feed in feeds]
    if all(c.status in ('collected', 'unchanged') for c in checks):
        try:
            with db.begin_nested():
                publish(db, market, checks, at)
            run.status = 'unchanged' if all(c.status == 'unchanged' for c in checks) else 'collected'
            market.failures, market.last_error = 0, None
        except (ValueError, OSError) as error:
            run.status = 'partial'
            reason = str(error) if str(error) in ('Unverified cross-feed overlap', 'Unverified historical source transition', 'Source capture identity mismatch', 'Capture integrity failure', 'Capture byte bound') else 'unified publication validation failed'
            market.last_error = 'Source captures retained; ' + reason
            market.failures += 1
    else:
        run.status = 'partial'
        market.failures += 1
        market.last_error = 'Partial collection; last complete market observation retained'
    run.error = market.last_error
    run.payload_bytes = sum(db.get(FeedCapture, c.capture_id).payload_bytes for c in checks if c.status == 'collected')
    market.next_check = at + timedelta(seconds=max(300, market.interval_seconds))


def coverage_start(db, market_id, item_id, variant_key):
    row = db.get(ItemSourceCoverage, (market_id, item_id, variant_key))
    return aware(row.first_observed_at) if row else None


def feed_health(db, market):
    rows = db.scalars(select(MarketFeed).where(MarketFeed.market_id == market.id).order_by(MarketFeed.source_kind))
    result = []
    for row in rows:
        capture = db.get(FeedCapture, row.capture_id) if row.capture_id else None
        age = (now() - aware(row.last_success)).total_seconds() if row.last_success else None
        try:
            source_age = (now() - aware(parsedate_to_datetime(row.last_modified))).total_seconds() if row.last_modified else None
        except (ValueError, TypeError, OverflowError):
            source_age = None
        stale = age is None or age > max(600, market.interval_seconds*2) or source_age is None or source_age < -300 or source_age > max(3600, market.interval_seconds*2)
        result.append({'source_kind': row.source_kind, 'enabled': row.enabled,
            'status': 'disabled' if not row.enabled else 'unavailable' if capture is None else
                'failed' if row.failures else 'stale' if stale else 'healthy',
            'last_check': row.last_check, 'last_success': row.last_success,
            'upstream_modified': row.last_modified, 'failures': row.failures, 'last_error': row.last_error,
            'listing_count': capture.listing_count if capture else None,
            'item_count': capture.item_count if capture else None,
            'captured_at': capture.observed_at if capture else None, 'retry_after': row.retry_after})
    return result
