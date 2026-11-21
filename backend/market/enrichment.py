"""Bounded metadata scheduler independent of auction collection.

One budgeted provider request and one independent artwork lookup per tick.
Provider failure never prevents collection; negative caches/backoff remain in adapters.
"""
import os
import logging
import signal
import time
from sqlalchemy import or_, select
from .db import Session
from .worker import BlizzardClient


def next_delay(factory=Session, *, at=None, worked=True):
    """Wake for eligible metadata work, at most four ticks/second; no new service."""
    from .db import now
    from .models import MetadataJob, MetadataProvider, MetadataTask
    from .provider_rates import rate_view
    at = at or now()
    with factory() as db:
        pending = select(MetadataTask.provider).join(MetadataJob).where(
            MetadataTask.state == 'queued', MetadataJob.state.in_(('queued','running')))
        rows = db.scalars(select(MetadataProvider).where(or_(
            MetadataProvider.validation_requested.is_(True),
            MetadataProvider.enabled.is_(True) & (MetadataProvider.automatic.is_(True) | MetadataProvider.provider.in_(pending)))))
        delays = []
        for row in rows:
            if row.provider == 'blizzard' and not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):continue
            if row.provider == 'foreverdb' and not (row.credential or row.pending_credential):continue
            due = rate_view(row,at)['next_eligible_at']
            delay = (due-at).total_seconds()
            delays.append(max(.25, delay) if delay > 0 or worked else 15)
    return min(15, min(delays, default=15))


def tick(factory=Session,client=None):
    from .metadata_recovery import tick as recover
    from .item_media import resolve_media_once
    client=client or BlizzardClient()
    from .metadata_recovery import reserve_budget
    from .models import MetadataProvider
    def budget(db,at):
        row=db.get(MetadataProvider,'blizzard',with_for_update=True)
        if not row or not row.enabled or not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):return False
        return reserve_budget(row,at) is None
    with factory() as db:
        settings=db.get(MetadataProvider,'blizzard')
        prefer_media=bool(settings and settings.hour_used%2)
    # Alternate first opportunity under the shared budget; a long name queue
    # must not consume every eligible request slot before artwork gets a turn.
    if prefer_media:
        media=resolve_media_once(factory,client,budget_guard=budget)
        recovery=recover(factory,provider_client=client)
    else:
        recovery=recover(factory,provider_client=client)
        media=resolve_media_once(factory,client,budget_guard=budget)
    return {'recovery':recovery,'media':media}


def main():
    logging.basicConfig(level=logging.INFO)
    stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    client=BlizzardClient()
    while not stopping:
        delay = 15
        try:
            result=tick(client=client)
            delay=next_delay(worked=any(result.values()))
        except Exception:logging.error('Metadata tick failed; collection is independent; retry remains bounded')
        deadline=time.monotonic()+delay
        while not stopping and time.monotonic()<deadline:
            time.sleep(min(.25,max(0,deadline-time.monotonic())))


if __name__=='__main__':main()
