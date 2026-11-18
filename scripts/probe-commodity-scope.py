"""Two sequential read-only house comparisons; no ingestion or configuration."""
import hashlib
import json
from types import SimpleNamespace
from market.worker import BlizzardClient


def main():
    client = BlizzardClient()
    result = {'scope':'Bounded US ruleset-2 Horde commodity scope comparison','responses':[]}
    ids = {}
    for house in (113, 114):
        meta, body = client.fetch(SimpleNamespace(region='us',ruleset_id=2,house_id=house,
            source_kind='commodities',etag=None,last_modified=None))
        if meta['status'] != 200 or meta['headers'].get('Battlenet-Namespace') != 'dynamic-forever-us':
            raise ValueError('Scope probe stopped')
        payload = json.loads(body)
        rows = payload['auctions']
        if len(rows)>150000 or any('unit_price' not in r or 'buyout' in r for r in rows):
            raise ValueError('Unverified commodity response contract')
        ids[house] = {r['id'] for r in rows}
        meta.update(house_id=house,self_link=payload['_links']['self']['href'],listing_count=len(rows),
            item_count=len({r['item']['id'] for r in rows}),
            samples={str(item): {'supply':sum(r['quantity'] for r in rows if r['item']['id']==item),
                'minimum_unit_copper':min((r['unit_price'] for r in rows if r['item']['id']==item),default=None)}
                for item in (4306,14342,6657,2589,2592,2318,2770)})
        result['responses'].append(meta)
        del body, payload, rows
    result['overlapping_listing_ids'] = len(ids[113] & ids[114])
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    try: main()
    except Exception: raise SystemExit('Scope probe stopped; no ingestion/configuration writes.') from None
