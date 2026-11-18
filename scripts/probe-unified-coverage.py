"""Bounded read-only Forever coverage receipt. No ingestion or configuration writes.

Run in the existing worker credential environment. At most eleven sequential
API requests plus OAuth; response limits/cooldowns use the existing transport.
"""
import hashlib
import json
from types import SimpleNamespace

from market.ingest import normalize
from market.worker import BlizzardClient


def main():
    client = BlizzardClient()
    result = {'scope': 'us / dynamic-forever-us / ruleset 2 / house 114', 'responses': []}
    ids = {}

    def fetch(path, namespace='dynamic-forever-us', conditional=None):
        url = 'https://us.api.blizzard.com' + path + '?namespace=' + namespace + '&locale=en_US'
        meta, body = client.transport(url, token=client.authenticate(), conditional=conditional)
        client.throttle(meta)
        result['responses'].append(meta)
        if meta['status'] not in (200, 304):
            raise ValueError('Probe stopped after non-success response')
        return meta, json.loads(body) if body else None

    for path in ('/data/wow/ruleset/index', '/data/wow/ruleset/2/auctions/'):
        meta, data = fetch(path)
        meta['index'] = data
    for kind in ('auctions', 'commodities'):
        path = '/data/wow/ruleset/2/auctions/114' + ('/commodities' if kind == 'commodities' else '')
        meta, data = fetch(path)
        rows = normalize(data, kind)
        ids[kind] = {r['auction_id'] for r in rows}
        meta.update(source_kind=kind, identity={k: data.get(k) for k in ('id', 'name', 'ruleset', 'commodities', '_links')},
                    listing_count=len(rows), item_count=len({r['item_id'] for r in rows}),
                    fields=sorted(data['auctions'][0]) if rows else [])
        from market.pricing import summarize
        meta['items'] = {str(item): summarize([SimpleNamespace(**r) for r in rows if r['item_id'] == item])
                         for item in (4306, 14342, 6657, 2589, 2592, 2318, 2770)}
        meta['item_shapes'] = [r['item'] for r in data['auctions'] if r['item']['id'] in (4306, 14342, 6657)][:12]
        conditional = {key: meta['headers'].get(header) for key, header in
                       (('If-Modified-Since', 'Last-Modified'), ('If-None-Match', 'ETag'))}
        fetch(path, conditional=conditional)
        del rows, data
    result['overlapping_listing_ids'] = len(ids['auctions'] & ids['commodities'])
    for item in (4306, 14342, 6657):
        meta, data = fetch('/data/wow/item/' + str(item), 'static-forever-us')
        meta['item_identity'] = {k: data.get(k) for k in ('id', 'name', 'quality', 'item_class', 'item_subclass')}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
