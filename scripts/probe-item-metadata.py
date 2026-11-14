"""Bounded live item/media probe; public item payload only, never OAuth output."""
import argparse,hashlib,json,time
from urllib.parse import urlencode
from market.worker import BlizzardClient
from market.probe import REGIONS
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--region',choices=REGIONS,default='us')
parser.add_argument('--item',type=int,default=25)
args=parser.parse_args()
if not 1<=args.item<=2**31-1:parser.error('Invalid item ID')
client=BlizzardClient()
for kind in ['item','media/item']:
    url=f'https://{args.region}.api.blizzard.com/data/wow/{kind}/{args.item}?'+urlencode({'namespace':f'static-forever-{args.region}','locale':'en_US'})
    meta,body=client.transport(url,token=client.authenticate())
    client.throttle(meta)
    if len(body)>262144:raise SystemExit('Metadata probe size limit exceeded')
    result={'request':meta,'payload':json.loads(body) if meta['status']==200 else None}
    print(json.dumps(result),flush=True)
    if meta['status'] in [401,403,429] or meta['status']>=500:break
    time.sleep(1)
