"""Bounded US/region discovery, cross-ruleset comparison and conditional HTTP evidence."""
import argparse
import hashlib
import json
import time
from urllib.parse import urlencode
from .probe import REGIONS, summarize
from .worker import BlizzardClient


def discover(region,house,*,client=None,pause=time.sleep):
    if region not in REGIONS or not 1<=house<=2**31-1:raise ValueError('Invalid discovery mapping')
    client=client or BlizzardClient()
    def fetch(path,conditional=None):
        url=f'https://{region}.api.blizzard.com{path}?'+urlencode({'namespace':f'dynamic-forever-{region}','locale':'en_US'})
        meta,body=client.transport(url,token=client.authenticate(),conditional=conditional)
        client.throttle(meta)
        if meta['status'] not in (200,304):raise ValueError('Discovery HTTP '+str(meta['status']))
        pause(1)
        return meta,json.loads(body) if meta['status']==200 else None
    meta,index=fetch('/data/wow/ruleset/index')
    rulesets=index.get('rulesets',[])
    if not 1<=len(rulesets)<=16:raise ValueError('Ruleset discovery bound exceeded')
    yield {'evidence':meta,'rulesets':[{'id':r['id']} for r in rulesets]}
    seen={}
    first=None
    for entry in rulesets:
        ident=entry['id']
        if type(ident) is not int or not 1<=ident<=2**31-1:raise ValueError('Invalid upstream ruleset')
        meta,data=fetch(f'/data/wow/ruleset/{ident}')
        yield {'evidence':meta,'identity':{k:data[k] for k in ('id','name','status') if k in data}}
        meta,data=fetch(f'/data/wow/ruleset/{ident}/auctions/')
        houses=data.get('auctions',[])
        if not 1<=len(houses)<=64:raise ValueError('House discovery bound exceeded')
        yield {'evidence':meta,'houses':[{'id':r['id'],'name':r['name']} for r in houses]}
        if not any(r['id']==house for r in houses):continue
        for kind in ('auctions','commodities'):
            path=f'/data/wow/ruleset/{ident}/auctions/{house}'+('/commodities' if kind=='commodities' else '')
            meta,data=fetch(path)
            auctions=data.get('auctions')
            digest=hashlib.sha256(json.dumps(auctions,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            aliases=seen.get((kind,digest),[])
            yield {'evidence':meta,'mapping':{'region':region,'ruleset_id':ident,'house_id':house,'source_kind':kind},
                   'keys':sorted(data),'listing_count':len(auctions) if isinstance(auctions,list) else None,
                   'listing_fields':sorted(auctions[0]) if auctions else [],'listings_sha256':digest,
                   'identical_ruleset_payloads':list(aliases),'sample':auctions[:2] if auctions else []}
            seen.setdefault((kind,digest),[]).append(ident)
            if first is None and kind=='auctions':first=(path,meta,digest)
    if first:
        path,previous,digest=first
        conditional={k:v for k,v in [('If-Modified-Since',previous['headers'].get('Last-Modified')),('If-None-Match',previous['headers'].get('ETag'))] if v}
        meta,data=fetch(path,conditional)
        yield {'evidence':meta,'conditional_request':conditional,'previous_listings_sha256':digest,
               'same_listings':hashlib.sha256(json.dumps(data.get('auctions'),sort_keys=True,separators=(',',':')).encode()).hexdigest()==digest if data is not None else None}


def compare_houses(region,ruleset,*,client=None,pause=time.sleep):
    if region not in REGIONS or type(ruleset) is not int or not 1<=ruleset<=2**31-1:raise ValueError('Invalid mapping')
    client=client or BlizzardClient()
    def fetch(path):
        url=f'https://{region}.api.blizzard.com{path}?'+urlencode({'namespace':f'dynamic-forever-{region}','locale':'en_US'})
        meta,body=client.transport(url,token=client.authenticate())
        client.throttle(meta)
        if meta['status']!=200:raise ValueError('Comparison HTTP '+str(meta['status']))
        pause(1)
        return meta,json.loads(body)
    _,index=fetch(f'/data/wow/ruleset/{ruleset}/auctions/')
    houses=index.get('auctions',[])
    if not 1<=len(houses)<=16:raise ValueError('Comparison house budget exceeded')
    sets={}
    total=0
    for house in houses:
        ident=house['id']
        if type(ident) is not int or not 1<=ident<=2**31-1:raise ValueError('Invalid upstream house')
        meta,data=fetch(f'/data/wow/ruleset/{ruleset}/auctions/{ident}')
        auctions=data.get('auctions')
        if isinstance(auctions,list):
            ids={row['id'] for row in auctions}
            total+=len(ids)
            if total>1000000:raise ValueError('Comparison identifier budget exceeded')
            sets[ident]=ids
        yield {'evidence':meta,'house_id':ident,'house_name':house['name'],'listing_count':len(auctions) if isinstance(auctions,list) else None,
               'missing_auctions':not isinstance(auctions,list)}
        del data,auctions
    overlaps=[{'first_house':a,'second_house':b,'shared_auction_ids':len(sets[a]&sets[b])}
              for a in sets for b in sets if a<b]
    yield {'house_id_overlaps':overlaps,'scope':'Sequential upstream feed samples; disjoint IDs do not establish player-facing ruleset routing.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--region',choices=REGIONS,required=True)
    parser.add_argument('--house',type=int,default=110)
    parser.add_argument('--compare-houses',type=int,metavar='RULESET',help='Compare bounded discovered house listing ID sets')
    args=parser.parse_args()
    try:
        for result in (compare_houses(args.region,args.compare_houses) if args.compare_houses is not None else discover(args.region,args.house)):print(json.dumps(result),flush=True)
    except Exception:
        parser.exit(1,'Discovery stopped: upstream/transport/structure failure; credentials and response errors suppressed.\n')


if __name__=='__main__':main()
