"""Read-only, bounded authenticated comparison. Run in the worker's credential environment.

Does not ingest data, create markets, or enable any feed. Public JSON only; no OAuth output.
"""
import hashlib
import json
import time
from market.db import now
from market.ingest import canonical
from market.worker import BlizzardClient

client=BlizzardClient()
result={'observed_at':now().isoformat(),'scope':'Read-only US Horde comparison','responses':[]}
identifiers={}
try:
    for ruleset,house,kind in ((2,113,'auctions'),(2,114,'auctions'),(1,113,'auctions'),
                              (1,114,'auctions'),(2,113,'commodities'),(2,114,'commodities')):
        url=f'https://us.api.blizzard.com/data/wow/ruleset/{ruleset}/auctions/{house}'
        if kind=='commodities':url+='/commodities'
        url+='?namespace=dynamic-forever-us&locale=en_US'
        meta,body=client.transport(url,token=client.authenticate())
        client.throttle(meta)
        if meta['status']!=200 or meta['headers'].get('Battlenet-Namespace')!='dynamic-forever-us':
            raise ValueError('Non-success response or incorrect namespace')
        data=json.loads(body)
        rows=data.get('auctions')
        if not isinstance(rows,list) or not 0<len(rows)<=150000:
            raise ValueError('Missing, empty or oversized listing array')
        identifiers[(ruleset,house,kind)]={r['id'] for r in rows}
        samples={}
        if kind=='commodities':
            for item in (2589,2592,2318,2770):
                listings=[r for r in rows if r['item']['id']==item and r.get('unit_price',0)>0]
                samples[item]={'quantity':sum(r['quantity'] for r in listings),
                    'minimum_unit_copper':min((r['unit_price'] for r in listings),default=None)}
        result['responses'].append({**meta,'mapping':{'region':'us','transport_ruleset_id':ruleset,
            'house_id':house,'source_kind':kind},'listing_count':len(rows),'id':data.get('id'),
            'name':data.get('name'),'listing_array_sha256':hashlib.sha256(canonical(rows).encode()).hexdigest(),
            'samples':samples})
        del data,rows,body
        time.sleep(1)
    result['shared_auction_ids']=len(identifiers[(2,113,'auctions')]&identifiers[(2,114,'auctions')])
    result['alias_hashes_equal']={str(h):len({r['listing_array_sha256'] for r in result['responses']
        if r['mapping']['house_id']==h and r['mapping']['source_kind']=='auctions'})==1 for h in (113,114)}
    print(json.dumps(result,indent=2))
except Exception:
    raise SystemExit('Research probe failed; no data or configuration written; transport details suppressed.')
