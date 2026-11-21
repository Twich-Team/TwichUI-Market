"""Sequential scheduled collector. Live verification is required per market."""
import base64
import json
import logging
import os
import signal
import time
import uuid
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.parse import urlencode
from sqlalchemy import select, text
from .db import Session, now
from .ingest import ingest, record_daily
from .models import CollectionRun, Market, Observation
from .probe import REGIONS, request
from .security import aware

log = logging.getLogger('market.worker')


class UpstreamFailure(Exception):
    def __init__(self, reason, status=None, retry_after=None):
        self.reason, self.status, self.retry_after = reason, status, retry_after
        super().__init__(reason)


def retry_seconds(value, at):
    if value is None:
        return 0
    try:
        seconds = int(value) if str(value).isdigit() else int((aware(parsedate_to_datetime(value)) - at).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return 0
    return max(0, min(seconds, 86400))


class BlizzardClient:
    def __init__(self, transport=request):
        self.transport = transport
        self.token = None
        self.expires = 0
        self.blocked_until = 0

    def throttle(self,metadata):
        if metadata['status']==429:
            self.blocked_until=time.monotonic()+max(300,retry_seconds(metadata['headers'].get('Retry-After'),now()))

    def authenticate(self):
        if time.monotonic()<self.blocked_until:
            raise UpstreamFailure('Upstream rate-limit cooldown',retry_after=str(int(self.blocked_until-time.monotonic())+1))
        if self.token and self.expires > time.monotonic():
            return self.token
        client_id, secret = os.environ.get('BLIZZARD_CLIENT_ID'), os.environ.get('BLIZZARD_CLIENT_SECRET')
        if not client_id or not secret:
            raise UpstreamFailure('Blizzard credentials missing')
        basic = base64.b64encode(f'{client_id}:{secret}'.encode()).decode()
        metadata, body = self.transport('https://oauth.battle.net/token', data=b'grant_type=client_credentials',
                                        authorization=f'Basic {basic}')
        self.throttle(metadata)
        if metadata['status'] != 200:
            raise UpstreamFailure('OAuth request failed', metadata['status'], metadata['headers'].get('Retry-After'))
        result = json.loads(body)
        if not isinstance(result, dict): raise UpstreamFailure('Invalid OAuth response')
        token, lifetime = result.get('access_token'), result.get('expires_in')
        if not isinstance(token, str) or not token or type(lifetime) is not int or lifetime < 60:
            raise UpstreamFailure('Invalid OAuth response')
        self.token, self.expires = token, time.monotonic() + min(lifetime - 30, 86400)
        return self.token

    def fetch(self, market):
        if market.region not in REGIONS or market.source_kind not in ('auctions', 'commodities'):
            raise UpstreamFailure('Invalid market mapping')
        if market.ruleset_id <= 0 or market.house_id <= 0:
            raise UpstreamFailure('Invalid market mapping')
        path = f'/data/wow/ruleset/{market.ruleset_id}/auctions/{market.house_id}'
        if market.source_kind == 'commodities':
            path += '/commodities'
        url = f'https://{market.region}.api.blizzard.com{path}?' + urlencode({
            'namespace':f'dynamic-forever-{market.region}', 'locale':'en_US'})
        metadata, body = self.transport(url, token=self.authenticate(), conditional={
            'If-None-Match':market.etag, 'If-Modified-Since':market.last_modified})
        self.throttle(metadata)
        if metadata['status'] == 401:
            self.token, self.expires = None, 0
        return metadata, body

    def fetch_item(self,region,item_id):
        if region not in REGIONS or type(item_id) is not int or not 1<=item_id<=2**31-1:
            raise UpstreamFailure('Invalid metadata mapping')
        url=f'https://{region}.api.blizzard.com/data/wow/item/{item_id}?'+urlencode({
            'namespace':f'static-forever-{region}','locale':'en_US'})
        metadata,body=self.transport(url,token=self.authenticate(),timeout=10,max_bytes=262144)
        self.throttle(metadata)
        if metadata['status']==401:
            self.token,self.expires=None,0
        return metadata,body

    def fetch_item_media(self,region,item_id):
        if region not in REGIONS or type(item_id) is not int or not 1<=item_id<=2**31-1:
            raise UpstreamFailure('Invalid metadata mapping')
        url=f'https://{region}.api.blizzard.com/data/wow/media/item/{item_id}?'+urlencode({
            'namespace':f'static-forever-{region}','locale':'en_US'})
        metadata,body=self.transport(url,token=self.authenticate(),timeout=10,max_bytes=262144)
        self.throttle(metadata)
        if metadata['status']==401:self.token,self.expires=None,0
        return metadata,body


def collect_once(factory=Session, client=None, *, at=None, max_database_bytes=None):
    at = at or now()
    client = client or BlizzardClient()
    with factory.begin() as db:
        if db.bind.dialect.name == 'postgresql':
            # Global lock keeps all collector processes sequential; released on crash/rollback.
            if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
                return False
        market = db.scalar(select(Market).where(Market.enabled.is_(True), Market.verified.is_(True),
            Market.next_check <= at).order_by(Market.next_check, Market.id).with_for_update(skip_locked=True).limit(1))
        if not market:
            return False
        started = time.monotonic()
        run = CollectionRun(market_id=market.id, checked_at=at, status='failed')
        db.add(run)
        metadata = None
        try:
            from .capacity import status as capacity_status
            capacity = capacity_status(db, limit=max_database_bytes)
            if capacity['paused_reason']:
                raise UpstreamFailure(capacity['paused_reason'])
            from .models import MarketFeed
            if market.unified_coverage:
                feeds = list(db.scalars(select(MarketFeed).where(MarketFeed.market_id == market.id,
                    MarketFeed.enabled.is_(True)).order_by(MarketFeed.source_kind)))
                from .feed_collection import collect_feeds
                collect_feeds(db, market, feeds, client, at, run)
                run.duration_seconds = int(time.monotonic() - started)
                return True
            if db.scalar(select(MarketFeed.market_id).where(MarketFeed.market_id==market.id).limit(1)) is not None:
                raise UpstreamFailure('Unified feed configuration requires a compatible collector; collection paused')
            metadata, body = client.fetch(market)
            run.http_status = metadata['status']
            run.payload_bytes = len(body)
            if metadata['status'] == 200:
                # A savepoint rolls back partially normalized data while preserving the failure record.
                with db.begin_nested():
                    ingest(db, market.id, body, request_key=uuid.uuid4().hex, retrieved_at=at,
                           modified=metadata['headers'].get('Last-Modified'))
                market.etag = metadata['headers'].get('ETag')
                run.status = 'collected'
            elif metadata['status'] == 304:
                latest = db.scalar(select(Observation).where(Observation.market_id == market.id)
                    .order_by(Observation.retrieved_at.desc(), Observation.id.desc()).limit(1))
                if not latest:
                    market.etag, market.last_modified = None, None
                    raise UpstreamFailure('304 without prior snapshot')
                observation=Observation(market_id=market.id, snapshot_id=latest.snapshot_id,
                    request_key=uuid.uuid4().hex, retrieved_at=at, upstream_modified=latest.upstream_modified,
                    namespace=latest.namespace, payload_hash=latest.payload_hash, payload_bytes=0,
                    synthetic=latest.synthetic)
                db.add(observation)
                db.flush()
                record_daily(db,observation)
                market.last_success = at
                run.status = 'unchanged'
            else:
                raise UpstreamFailure('Upstream HTTP failure', metadata['status'], metadata['headers'].get('Retry-After'))
            market.failures, market.last_error = 0, None
            market.next_check = at + timedelta(seconds=max(300, market.interval_seconds))
        except (UpstreamFailure, URLError, TimeoutError, ValueError, KeyError, UnicodeError) as exc:
            # Never store/log exception strings from network transports: they may contain secrets.
            market.failures += 1
            reason = exc.reason if isinstance(exc, UpstreamFailure) else 'Transport or payload validation failed'
            run.error = market.last_error = reason
            if isinstance(exc, UpstreamFailure):
                run.http_status = exc.status if exc.status else run.http_status
                retry = retry_seconds(exc.retry_after, at)
            else:
                retry = 0
            delay = max(300, min(300 * 2**min(market.failures - 1, 8), 86400), retry)
            market.next_check = at + timedelta(seconds=delay)
        run.duration_seconds = int(time.monotonic() - started)
        log.info('market=%s status=%s http=%s', market.id, run.status, run.http_status)
    return True


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    client = BlizzardClient()
    next_maintenance = 0
    next_metadata = 0
    while not stopping:
        try:
            if time.monotonic() >= next_maintenance:
                from .maintenance import maintain
                maintain(apply=True)
                next_maintenance = time.monotonic()+86400
            worked = collect_once(client=client)
            if os.environ.get("ITEM_ENRICHMENT_IN_COLLECTOR","true").lower()=="true" and time.monotonic() >= next_metadata:
                from .metadata import resolve_once
                resolve_once(client=client)
                from .item_media import resolve_media_once
                resolve_media_once(client=client)
                from .community_metadata import resolve_community_once
                resolve_community_once()
                next_metadata=time.monotonic()+15
        except Exception:
            # The transaction rolls back; safe generic message, no DSNs or response content.
            log.error('Collector transaction failed; will retry')
            worked = False
        for _ in range(2 if worked else 15):
            if stopping:
                break
            time.sleep(1)


if __name__ == '__main__':
    main()
