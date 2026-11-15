#!/usr/bin/env python3
"""Read-only offline comparison. No app imports, DB, network or active defaults.

--fixtures replays the approved research rows (real excerpts remain excerpts).
--snapshot accepts an explicitly supplied original Blizzard auction export with
market/source/timestamp/completeness provenance. It never fetches that data.
"""
import argparse
import ast
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from market import canonical_pricing as canonical


def legacy_calculator():
    path=ROOT/'backend/market/pricing.py'
    source=ast.parse(path.read_text())
    functions=[f for f in source.body if isinstance(f,ast.FunctionDef) and f.name in ('summarize','rounded')]
    if len(functions)!=2: raise ValueError('Legacy pure function audit required')
    environment={'Decimal':Decimal,'ROUND_HALF_UP':ROUND_HALF_UP}
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(path),'exec'),environment)
    return environment['summarize']


def compare(case,old):
    kind=case['source_kind'];item=case['item_id'];variant=case['variant_key'];rows=case['rows']
    before=old([SimpleNamespace(quantity=r['quantity'],buyout=int(r['total_copper']) if r['total_copper'] is not None else None,
                               unit_price=int(r['unit_copper']) if r['unit_copper'] is not None else None) for r in rows])
    after=canonical.snapshot(rows,item_id=item,variant_key=variant,source_kind=kind)
    previous=before['recent_price'];recent=after['recent_copper']
    return {'case':case['id'],'origin':case['origin'],'scope_complete':case['complete'],'synthetic':case['synthetic'],
            'market':case['market'],
            'item_id':item,'variant_key':variant,'observed_at':case['observed_at'],
            'legacy_algorithm':'asking-v1-provisional','legacy_recent_copper':str(previous) if previous is not None else None,
            'canonical_algorithm':canonical.ALGORITHM,'canonical_recent_copper':recent,
            'difference_copper':str(int(recent)-previous) if recent is not None and previous is not None else None,
            'canonical_state':after['state'],'supply':after['supply'],'priced_supply':after['priced_supply'],
            'priced_listings':after['priced_listing_count'],
            'farbelow':after['distribution']['farbelow'] if after['distribution'] else None}


def fixtures(path):
    document=json.loads(path.read_text())
    if document['fixture_version']!=1 or document['algorithm_proposal']!=canonical.ALGORITHM: raise ValueError('Fixture version')
    for c in document['cases']:
        provenance=c['provenance'];kind=provenance['source_kind'] if provenance else 'auctions'
        rows=[]
        for r in c['listings']:
            row={**r,'item_id':c['item']['id'],'variant_key':c['variant_key']}
            if kind=='auctions' and row['unit_copper'] is not None:
                row['total_copper']=str(int(row['unit_copper'])*row['quantity']);row['unit_copper']=None
            rows.append(row)
        yield {'id':c['id'],'origin':c['origin'],'complete':c['scope_complete'],'synthetic':c['origin']=='synthetic',
               'market':{k:provenance[k] for k in ['region','transport_ruleset_id','house_id','source_kind','player_ruleset']} if provenance else None,
               'observed_at':provenance['retrieved_at'] if provenance else None,
               'source_kind':kind,'item_id':c['item']['id'],'variant_key':c['variant_key'],'rows':rows}


def snapshot_export(path):
    data=json.loads(path.read_text())
    if set(data)!={'schema_version','market','source_kind','observed_at','scope_complete','synthetic','auctions'} or data['schema_version']!=1:
        raise ValueError('Snapshot envelope')
    expected_market={'game','region','player_ruleset','house_id','source_kind','server_market_id','transport_ruleset_id','mapping_verified','mapping_evidence_sha256','realm_scope'}
    if type(data['market']) is not dict or set(data['market'])!=expected_market or data['market']['source_kind']!=data['source_kind']:
        raise ValueError('Market provenance')
    import jsonschema
    market_schema=json.loads((ROOT/'contracts/bridge/v1/generation.schema.json').read_text())['properties']['market']
    jsonschema.validate(data['market'],market_schema)
    if data['source_kind'] not in ('auctions','commodities') or type(data['scope_complete']) is not bool or type(data['synthetic']) is not bool:
        raise ValueError('Source provenance')
    from datetime import datetime
    stamp=datetime.fromisoformat(data['observed_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None: raise ValueError('Observation timezone')
    if type(data['auctions']) is not list or len(data['auctions'])>canonical.MAX_LISTINGS: raise ValueError('Listing limit')
    groups=defaultdict(list);seen=set()
    for a in data['auctions']:
        aid=canonical.integer(a['id'],1,canonical.MAX_I64)
        if aid in seen: raise ValueError('Duplicate auction ID')
        seen.add(aid)
        descriptor=a['item']
        if type(descriptor) is not dict: raise ValueError('Item descriptor')
        raw=json.dumps(descriptor,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
        if len(raw)>4096: raise ValueError('Variant limit')
        variant=hashlib.sha256(raw.encode()).hexdigest();item=canonical.integer(descriptor['id'],1,2**31-1)
        def amount(name):
            v=a.get(name)
            return str(canonical.integer(v,1,canonical.MAX_I64)) if v is not None else None
        groups[item,variant].append({'item_id':item,'variant_key':variant,'quantity':a['quantity'],
                                    'total_copper':amount('buyout'),'unit_copper':amount('unit_price'),'bid_copper':amount('bid')})
    for (item,variant),rows in sorted(groups.items()):
        yield {'id':str(item)+':'+variant,'origin':'supplied_snapshot','complete':data['scope_complete'],'synthetic':data['synthetic'],
               'market':data['market'],
               'observed_at':data['observed_at'],'source_kind':data['source_kind'],'item_id':item,'variant_key':variant,'rows':rows}


def main():
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--fixtures',type=Path);group.add_argument('--snapshot',type=Path);args=parser.parse_args()
    path=args.fixtures or args.snapshot
    if path.stat().st_size>32*1024*1024:raise ValueError('Input file bound')
    started=time.perf_counter();old=legacy_calculator()
    cases=fixtures(path) if args.fixtures else snapshot_export(path)
    results=[compare(c,old) for c in cases]
    report={'mode':'offline_shadow','source_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'production_outputs_changed':False,'database_access':False,'network_access':False,
            'canonical_source_sha256':hashlib.sha256((ROOT/'backend/market/canonical_pricing.py').read_bytes()).hexdigest(),
            'legacy_source_sha256':hashlib.sha256((ROOT/'backend/market/pricing.py').read_bytes()).hexdigest(),
            'elapsed_ms':round((time.perf_counter()-started)*1000,3),'cases':results,
            'full_horizon_validation':False,'note':'Captured excerpts are not complete variant books; synthetic calendars do not establish live 14/60-day behavior.'}
    print(json.dumps(report,indent=2,allow_nan=False))


if __name__=='__main__':main()
