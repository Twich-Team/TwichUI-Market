"""Bounded metadata scheduler independent of auction collection.

One budgeted provider request and one independent artwork lookup per tick.
Provider failure never prevents collection; negative caches/backoff remain in adapters.
"""
import os
import logging
import signal
import time
from .db import Session
from .worker import BlizzardClient


def tick(factory=Session,client=None):
    from .metadata_recovery import tick as recover
    from .item_media import resolve_media_once
    client=client or BlizzardClient()
    from .metadata_recovery import reserve_budget,cooldown
    from .models import MetadataProvider
    def budget(db,at):
        row=db.get(MetadataProvider,'blizzard',with_for_update=True)
        if not row or not row.enabled or not (os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')):return False
        return reserve_budget(row,at) is None
    def failed(db,status,headers,at):
        if status in (401,402,403,429):cooldown(db.get(MetadataProvider,'blizzard'),status,headers,at)
    with factory() as db:
        settings=db.get(MetadataProvider,'blizzard')
        prefer_media=bool(settings and settings.hour_used%2)
    # Alternate first opportunity under the shared budget; a long name queue
    # must not consume every eligible request slot before artwork gets a turn.
    if prefer_media:
        media=resolve_media_once(factory,client,budget_guard=budget,failure_guard=failed)
        recovery=recover(factory,provider_client=client)
    else:
        recovery=recover(factory,provider_client=client)
        media=resolve_media_once(factory,client,budget_guard=budget,failure_guard=failed)
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
        try:tick(client=client)
        except Exception:logging.error('Metadata tick failed; collection is independent; retry remains bounded')
        for _ in range(15):
            if stopping:break
            time.sleep(1)


if __name__=='__main__':main()
