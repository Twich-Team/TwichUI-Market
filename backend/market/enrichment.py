"""Bounded metadata scheduler independent of auction collection.

One primary item, one artwork lookup and one optional community item per tick.
Provider failure never prevents collection; negative caches/backoff remain in adapters.
"""
import logging
import signal
import time
from .db import Session
from .worker import BlizzardClient


def tick(factory=Session,client=None):
    from .metadata import resolve_once
    from .item_media import resolve_media_once
    from .community_metadata import resolve_community_once
    client=client or BlizzardClient()
    return {'primary':resolve_once(factory,client),
            'media':resolve_media_once(factory,client),
            'community':resolve_community_once(factory)}


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
