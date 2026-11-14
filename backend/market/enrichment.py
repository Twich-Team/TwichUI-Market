"""Bounded metadata scheduler independent of auction collection.

One budgeted provider request and one independent artwork lookup per tick.
Provider failure never prevents collection; negative caches/backoff remain in adapters.
"""
import logging
import signal
import time
from .db import Session
from .worker import BlizzardClient


def tick(factory=Session,client=None):
    from .metadata_recovery import tick as recover, fetch
    from .item_media import resolve_media_once
    client=client or BlizzardClient()
    def fetcher(provider,item_id,**kwargs):
        return fetch(provider,item_id,client=client,**kwargs)
    return {'recovery':recover(factory,fetcher=fetcher),
            'media':resolve_media_once(factory,client)}


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
