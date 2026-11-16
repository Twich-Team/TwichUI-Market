"""Small extension of the recovery scheduler, shared by every metadata caller.

Row locks serialize reservations. Minute buckets conservatively cover rolling
hours/days (at most 59 seconds extra wait); second buckets cover rolling minutes.
Legacy anchored counters remain an additional guard until their original expiry.
No entitlement is inferred from successful requests or administrator settings.
"""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import math
from time import monotonic
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import object_session
from .db import now
from .metadata_models import MetadataProvider, MetadataQuotaBucket
from .metadata_providers import PROVIDERS
from .security import aware

LEASE_SECONDS = 120
MAX_RETRY = 366 * 86400
DOCUMENTED = {
    'foreverdb': {'minute_budget': 30, 'daily_budget': 5000},
    'everloot': {'hourly_budget': 2000, 'page_size': 5000},
    'thewowdb': {'requests_per_second': 2, 'burst_capacity': 120},
    'blizzard': {},
}
DOC_URLS = {
    'foreverdb': 'https://foreverdb.net/developers',
    'everloot': 'https://everloot.app/docs/api/keys',
    'thewowdb': 'https://thewowdb.com/developers/',
    'blizzard': 'https://develop.battle.net/documentation',
}


class ProviderWaiting(ValueError):
    def __init__(self, until=None):
        self.until = until
        super().__init__('Provider disabled or waiting for its shared quota')


def reserved_request(factory, ident, callback, *, at=None):
    """Compatibility/diagnostic callers use the same commit-before-I/O pool."""
    at = at or now()
    from .metadata_recovery import ensure_providers
    with factory.begin() as db:
        ensure_providers(db)
        row = db.get(MetadataProvider, ident, with_for_update=True)
        if not row.enabled:
            raise ProviderWaiting()
        waiting = reserve_budget(row, at)
        if waiting:
            raise ProviderWaiting(waiting)
    status, headers = None, {}
    started = monotonic()
    try:
        meta, body = callback()
        status, headers = meta['status'], meta.get('headers', {})
        return meta, body
    finally:
        with factory.begin() as db:
            row = db.get(MetadataProvider, ident, with_for_update=True)
            received = at + timedelta(seconds=max(0,monotonic()-started))
            observe(row, status, headers, received, reserved_at=at)
            if status in (401,402,403,429,503):
                cooldown(row, status, headers, received)


class RateLimits(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    hourly_budget: int = Field(ge=1, le=72000)
    daily_budget: int = Field(ge=1, le=1000000)
    minute_budget: int | None = Field(default=None, ge=1, le=1200)
    minimum_interval: float = Field(ge=0.05, le=86400, allow_inf_nan=False)
    requests_per_second: float | None = Field(default=None, ge=0.05, le=2, allow_inf_nan=False)
    burst_capacity: int | None = Field(default=None, ge=1, le=120)
    max_concurrent: int = Field(default=1, ge=1, le=1)
    page_size: int | None = Field(default=None, ge=1, le=5000)
    entitlement_acknowledged: bool = False

    @model_validator(mode='after')
    def consistent(self):
        if (self.requests_per_second is None) != (self.burst_capacity is None):
            raise ValueError('Request pace and burst capacity must be configured together')
        return self


def keyed(row, at):
    return bool(row.credential and row.validated_at and (not row.expires_at or aware(row.expires_at) > at))


def configuration(row, at=None):
    if row.rate_config:
        return json.loads(row.rate_config)
    return dict(hourly_budget=row.hourly_budget, daily_budget=row.daily_budget,
        minute_budget=30 if row.provider == 'foreverdb' else None,
        minimum_interval=15 if row.provider == 'everloot' and keyed(row, at or now()) else PROVIDERS[row.provider].interval,
        requests_per_second=2 if row.provider == 'thewowdb' else None,
        burst_capacity=120 if row.provider == 'thewowdb' else None,
        max_concurrent=1, page_size=500 if row.provider == 'everloot' else None)


def effective(row, at):
    config = configuration(row, at)
    # Keyless/expired keys cannot acquire authenticated allowances. Candidate
    # validation is deliberately charged against the more conservative pool.
    if row.provider == 'everloot' and not keyed(row, at):
        config['hourly_budget'] = min(config['hourly_budget'], 20)
        config['daily_budget'] = min(config['daily_budget'], 100)
        config['minimum_interval'] = max(config['minimum_interval'], 180)
        config['page_size'] = min(config['page_size'], 500)
    if row.provider == 'blizzard':
        config['hourly_budget'] = min(config['hourly_budget'], 240)
        config['daily_budget'] = min(config['daily_budget'], 2000)
        config['minimum_interval'] = max(config['minimum_interval'], 15)
    if row.adaptive_until and aware(row.adaptive_until) > at:
        config['minimum_interval'] = max(config['minimum_interval'], min(60, 2 ** min(row.rate_streak or 0, 6)))
    return config


def validate_configuration(row, body, at):
    config = body.model_dump(exclude={'entitlement_acknowledged'})
    ident = row.provider
    if (ident == 'thewowdb') != (config['requests_per_second'] is not None):
        raise ValueError('Only TheWoWDB uses request pace and burst capacity')
    if (ident == 'everloot') != (config['page_size'] is not None):
        raise ValueError('Only Everloot uses a configurable page size')
    if (ident == 'foreverdb') != (config['minute_budget'] is not None):
        raise ValueError('ForeverDB requires a per-minute allowance')
    if ident == 'blizzard' and (config['hourly_budget'] > 240 or config['daily_budget'] > 2000 or config['minimum_interval'] < 15):
        raise ValueError('Blizzard metadata safeguards are 240/hour, 2000/day and at least 15 seconds; auction safeguards are separate')
    if ident in ('everloot', 'foreverdb') and not keyed(row, at):
        spec = PROVIDERS[ident]
        if config['hourly_budget'] > spec.hourly_limit or config['daily_budget'] > spec.daily_limit or config['minimum_interval'] < spec.interval or (ident == 'everloot' and config['page_size'] > 500):
            raise ValueError('Validate an unexpired API key before configuring an authenticated allowance')
    above = any(config.get(k) is not None and config[k] > v for k, v in DOCUMENTED[ident].items())
    if above and not body.entitlement_acknowledged:
        raise ValueError('Acknowledge that your provider contract grants these higher limits; configuration is not proof of entitlement')
    return config


def retry_delay(value, at, server_date=None):
    """Bound hostile values, HTTP-date overflow and clock skew without raw text."""
    if value is None or len(str(value)) > 128:
        return 0
    value = str(value).strip()
    try:
        if value.isascii() and value.isdigit():
            seconds = int(value)
        else:
            parsed = parsedate_to_datetime(value)
            seconds = math.ceil((aware(parsed) - at).total_seconds())
            if server_date:
                try: seconds = max(seconds, math.ceil((aware(parsed) - aware(parsedate_to_datetime(server_date))).total_seconds()))
                except (TypeError, ValueError, OverflowError, AttributeError): pass
        return max(0, min(seconds, MAX_RETRY))
    except (TypeError, ValueError, OverflowError, AttributeError):
        return 0


def headers_lower(headers):
    return {str(k).lower(): v for k, v in headers.items() if v is not None}


def integer(value, maximum=1000000000):
    if value is None or len(str(value)) > 12 or not str(value).isascii() or not str(value).isdigit():
        return None
    parsed = int(value)
    return parsed if 0 <= parsed <= maximum else None


def observe(row, status, headers, at, *, reserved_at=None):
    """Persist only allowlisted numeric observations; never credentials/raw headers."""
    safe = headers_lower(headers)
    observed = {'observed_at': at.isoformat(), 'remaining': None, 'limit': None, 'reset_at': None}
    observed['remaining'] = integer(safe.get('ratelimit-remaining'))
    observed['limit'] = integer(safe.get('ratelimit-limit'))
    reset = integer(safe.get('ratelimit-reset'), MAX_RETRY)
    if reset is not None:
        observed['reset_at'] = (at + timedelta(seconds=reset)).isoformat()
    if row.provider == 'thewowdb':
        remaining = integer(safe.get('x-ratelimit-remaining'), 120)
        if remaining is not None:
            observed['remaining'] = remaining
            row.rate_tokens = min(row.rate_tokens if row.rate_tokens is not None else remaining, remaining)
            row.rate_token_at = at
    if observed['remaining'] is not None or observed['limit'] is not None or observed['reset_at']:
        row.rate_observation = json.dumps(observed)
        if observed['remaining'] == 0 and observed['reset_at']:
            until = datetime.fromisoformat(observed['reset_at'])
            row.cooldown_until = max(aware(row.cooldown_until) if row.cooldown_until else at, until)
    if status is not None and (200 <= status < 300 or status == 304):
        row.last_http_success = at
        if row.adaptive_until and at >= aware(row.adaptive_until):
            row.rate_streak, row.adaptive_until = 0, None
    # A stale request must never release a newer reservation.
    if row.rate_inflight_until and aware(row.rate_inflight_until) == (reserved_at or at) + timedelta(seconds=LEASE_SECONDS):
        row.rate_inflight_until = None


def cooldown(row, status, headers, at):
    category = {401:'authorization', 402:'subscription_required', 403:'forbidden', 429:'rate_limited'}.get(status, 'upstream_error')
    row.last_error = category
    safe = headers_lower(headers)
    delay = retry_delay(safe.get('retry-after'), at, safe.get('date'))
    if status == 429:
        row.last_rate_limit = at
        previous = (row.rate_streak or 0) if row.adaptive_until and aware(row.adaptive_until) > at else 0
        row.rate_streak = min(10, previous + 1)
        delay = max(delay, min(3600, 60 * 2 ** (row.rate_streak - 1)))
        row.adaptive_until = at + timedelta(seconds=delay + 900)
        # Resume from one request, not a full burst after the cooldown.
        if row.provider == 'thewowdb':
            row.rate_tokens, row.rate_token_at = 0, at + timedelta(seconds=delay)
    elif status in (401, 402, 403):
        delay = max(delay, 3600)
    elif status == 503:
        delay = max(delay, 60)
    else:
        return category
    until = at + timedelta(seconds=delay)
    row.cooldown_until = max(aware(row.cooldown_until) if row.cooldown_until else at, until)
    row.next_request_at = max(aware(row.next_request_at) if row.next_request_at else at, until)
    return category


def bucket_start(at, resolution):
    return datetime.fromtimestamp(math.floor(at.timestamp() / resolution) * resolution, timezone.utc)


def accounting(row, at):
    db = object_session(row)
    rows = list(db.execute(select(MetadataQuotaBucket.resolution, MetadataQuotaBucket.started_at, MetadataQuotaBucket.used).where(MetadataQuotaBucket.provider == row.provider,
        MetadataQuotaBucket.started_at >= bucket_start(at - timedelta(days=1), 60)).order_by(MetadataQuotaBucket.started_at))) if db else []
    result = {}
    for name, seconds, resolution, start, used in [
        ('minute', 60, 1, None, 0),
        ('hour', 3600, 60, row.hour_start, row.hour_used or 0),
        ('day', 86400, 60, row.day_start, row.day_used or 0),
    ]:
        buckets = [b for b in rows if b.resolution == resolution and aware(b.started_at) + timedelta(seconds=seconds + resolution) > at]
        legacy = used if start and aware(start) + timedelta(seconds=seconds) > at else 0
        result[name] = {'used': max(legacy, sum(b.used for b in buckets)), 'legacy_used': legacy,
            'legacy_reset': aware(start) + timedelta(seconds=seconds) if legacy else None, 'buckets': buckets}
    return result


def tokens(row, config, at):
    capacity = config['burst_capacity']
    if capacity is None:
        return None
    elapsed = max(0, (at - aware(row.rate_token_at)).total_seconds()) if row.rate_token_at else 0
    return min(capacity, (row.rate_tokens if row.rate_tokens is not None else capacity) + elapsed * config['requests_per_second'])


def eligibility(row, at, config, usage):
    waits = [at]
    for stamp in (row.cooldown_until, row.next_request_at, row.rate_inflight_until):
        if stamp:
            waits.append(aware(stamp))
    for name, field, seconds, resolution in [('minute','minute_budget',60,1), ('hour','hourly_budget',3600,60), ('day','daily_budget',86400,60)]:
        limit = config.get(field)
        if limit is None:
            continue
        window = usage[name]
        if window['legacy_used'] >= limit:
            waits.append(window['legacy_reset'])
        count = sum(b.used for b in window['buckets'])
        for b in window['buckets']:
            if count < limit:
                break
            count -= b.used
            waits.append(aware(b.started_at) + timedelta(seconds=seconds + resolution))
    available = tokens(row, config, at)
    if available is not None and available < 1:
        waits.append(max(at, aware(row.rate_token_at) if row.rate_token_at else at) + timedelta(seconds=(1 - available) / config['requests_per_second']))
    return max(waits)


def reserve_budget(row, at):
    db = object_session(row)
    if db:
        # Refresh after the lock, so competing sessions cannot reserve stale state.
        db.flush()
        row = db.scalar(select(MetadataProvider).where(MetadataProvider.provider == row.provider).with_for_update().execution_options(populate_existing=True))
    config = effective(row, at)
    usage = accounting(row, at)
    waiting = eligibility(row, at, config, usage)
    if waiting > at:
        return waiting
    if not row.hour_start or at >= aware(row.hour_start) + timedelta(hours=1):
        row.hour_start, row.hour_used = at, 0
    if not row.day_start or at >= aware(row.day_start) + timedelta(days=1):
        row.day_start, row.day_used = at, 0
    row.hour_used += 1
    row.day_used += 1
    available = tokens(row, config, at)
    if available is not None:
        row.rate_tokens, row.rate_token_at = available - 1, at
    row.next_request_at = at + timedelta(seconds=config['minimum_interval'])
    row.rate_inflight_until = at + timedelta(seconds=LEASE_SECONDS)
    if db:
        db.execute(delete(MetadataQuotaBucket).where(MetadataQuotaBucket.provider == row.provider, or_(
            (MetadataQuotaBucket.resolution == 1) & (MetadataQuotaBucket.started_at <= at - timedelta(seconds=61)),
            (MetadataQuotaBucket.resolution == 60) & (MetadataQuotaBucket.started_at <= at - timedelta(seconds=86460)))))
        entries = [{'provider':row.provider,'resolution':r,'started_at':bucket_start(at,r),'used':1} for r in (1,60)]
        if db.bind.dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
            statement=insert(MetadataQuotaBucket).values(entries)
            db.execute(statement.on_conflict_do_update(index_elements=['provider','resolution','started_at'],set_={'used':MetadataQuotaBucket.used+1}))
        else:
            for entry in entries:
                bucket=db.get(MetadataQuotaBucket,(row.provider,entry['resolution'],entry['started_at']))
                if bucket is None:db.add(MetadataQuotaBucket(**entry))
                else:bucket.used+=1
    return None


def rate_view(row, at=None):
    at = at or now()
    config = configuration(row, at)
    current = effective(row, at)
    usage = accounting(row, at)
    observed = json.loads(row.rate_observation) if row.rate_observation else None
    estimates = {}
    for name, field in [('minute','minute_budget'), ('hour','hourly_budget'), ('day','daily_budget')]:
        limit = current.get(field)
        if limit is not None:
            estimates[name] = {'used':usage[name]['used'], 'limit':limit, 'remaining':max(0,limit-usage[name]['used']), 'source':'application_estimate'}
    sources = {}
    for field, value in config.items():
        legacy_setting = {'hourly_budget':'hourly_limit','daily_budget':'daily_limit'}.get(field)
        if row.rate_config or legacy_setting and value != getattr(PROVIDERS[row.provider],legacy_setting):
            sources[field]='administrator_configured'
        elif field in DOCUMENTED[row.provider] and value == DOCUMENTED[row.provider][field]:
            sources[field]='officially_documented'
        else:
            sources[field]='conservative_application_default'
    return {'configured':config, 'effective':current, 'limit_sources':sources,
        'documented': DOCUMENTED[row.provider], 'documentation_url':DOC_URLS[row.provider],
        'windows':estimates, 'provider_reported':observed,
        'available_tokens': tokens(row,current,at),
        'next_eligible_at':eligibility(row,at,current,usage),
        'cooling_down':bool(row.cooldown_until and aware(row.cooldown_until)>at),
        'cooldown_reason':row.last_error if row.cooldown_until and aware(row.cooldown_until)>at else None,
        'adaptive_active':bool(row.adaptive_until and aware(row.adaptive_until)>at),
        'adaptive_until':row.adaptive_until, 'last_rate_limit':row.last_rate_limit,
        'last_http_success':row.last_http_success, 'last_useful_recovery':row.last_recovery,
        'accounting_note':'Shared application reservations only; interruptions can overestimate sent requests. Other account keys/IP consumers are unknown. Rolling windows are conservative by up to 59 seconds; existing anchored usage remains guarded.'}
