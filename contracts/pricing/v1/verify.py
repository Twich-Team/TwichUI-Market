#!/usr/bin/env python3
"""Offline M0.5 research checker. No network, databases, fixture writes or product imports.

Expectations are authored in JSON with arithmetic derivations. Fraction arithmetic
provides an independent specification check, not a production pricing engine.
Optional --market-source/--workshop-source compare pinned existing source functions.
"""
import argparse
import ast
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
MAX_PRICE = 99999999999
I64 = 9223372036854775807
def load(name):
    return json.loads((ROOT/name).read_text())
def stamp(s):
    return datetime.fromisoformat(s.replace('Z','+00:00'))
def half(x):
    return (2*x.numerator+x.denominator)//(2*x.denominator)
def copper(v):
    return isinstance(v,str) and v.isascii() and v.isdigit() and (v=='0' or not v.startswith('0')) and len(v)<=19 and int(v)<=I64
def med(values):
    ordered=sorted(values)
    total=sum(w for _,w in ordered)
    count=0
    for value,weight in ordered:
        count+=weight
        if 2*count>=total:return value
    return None
def tier_data(case):
    prices=defaultdict(lambda:[0,0])
    raw=[]
    for x in case['listings']:
        if x['unit_copper'] is not None: p=F(int(x['unit_copper']))
        elif x['total_copper'] is not None: p=F(int(x['total_copper']),x['quantity'])
        else: continue
        raw.append((p,x['quantity']))
        u=-(-p.numerator//p.denominator)
        prices[u][0]+=x['quantity'];prices[u][1]+=1
    return raw,[(p,*prices[p]) for p in sorted(prices)]
def band(tiers):
    total=sum(q for _,q,_ in tiers)
    seen=0
    for anchor,q,_ in tiers:
        seen+=q
        if 4*seen>total:break
    eligible=[(p,q) for p,q,_ in tiers if 2*p>=anchor]
    need=F(3*sum(q for _,q in eligible),10)
    remaining=need; numerator=F(0)
    for p,q in eligible:
        take=min(remaining,q);numerator+=p*take;remaining-=take
        if not remaining:break
    return half(numerator/need)
def trimmed(tiers):
    total=sum(q for _,q,_ in tiers)
    lo,hi=F(total,10),F(9*total,10)
    seen=0;value=F(0)
    for p,q,_ in tiers:
        overlap=max(F(0),min(F(seen+q),hi)-max(F(seen),lo))
        value+=p*overlap;seen+=q
    return half(value/(hi-lo))
def snapshot(case):
    raw,tiers=tier_data(case)
    if not raw:return {k:None for k in case['expected']},None,tiers
    mean=half(sum(p*q for p,q in raw)/sum(q for _,q in raw))
    supported=all(1<=p<=MAX_PRICE for p,_,_ in tiers)
    r={'market_minimum':half(min(p for p,_ in raw)),'market_recent':mean,
       'workshop_recent':band(tiers) if supported else None,
       'weighted_median':med([(p,q) for p,q,_ in tiers]) if supported else None,
       'canonical_minimum':tiers[0][0] if supported else None}
    total=sum(q for _,q,_ in tiers)
    for key,mult,strict in [('anchor',4,True),('q25',4,False),('q50',2,False),('q75',4,False)]:
        value=None;seen=0;target=3*total if key=='q75' else total
        if supported:
            for p,q,_ in tiers:
                seen+=q
                if (mult*seen>target if strict else mult*seen>=target): value=p;break
        r[key]=value
    return {k:None if v is None else str(v) for k,v in r.items()},trimmed(tiers) if supported else None,tiers
def temporal(case):
    at=stamp(case['as_of']);today=at.date()
    points=sorted(case['points'],key=lambda p:stamp(p['observed_at']))
    market={};workshop={};canonical={}
    for p in points:
        instant=stamp(p['observed_at']);day=instant.date()
        assert instant<=at
        if instant>=at-timedelta(days=60): market[day]=p
        # History2 keeps the last LISTED observation, including whole-read partial-info observations.
        if p['state']=='listed':workshop[day]=p
        if p['complete']: canonical[day]=p
    def avg(n):
        vals=[int(p['unit_copper']) for p in market.values()
              if p['unit_copper'] is not None and stamp(p['observed_at'])>=at-timedelta(days=n)]
        return half(F(sum(vals),len(vals))) if vals else None
    def digest(source,n,weighted,min_days):
        vals=[]
        for day,p in source.items():
            age=(today-day).days
            if 0<=age<n and p['unit_copper'] is not None:
                w=(4 if age<=2 else 2 if age<=6 else 1) if weighted else 1
                vals.append((int(p['unit_copper']),w))
        return med(vals) if len(vals)>=min_days else None
    r={'market_market_value':avg(14),'market_historical_value':avg(60),
       'workshop_market_value':digest(workshop,14,True,1),'workshop_historical_value':digest(workshop,60,False,3),
       'canonical_market_value':digest(canonical,14,True,1),'canonical_historical_value':digest(canonical,60,False,3)}
    r={k:None if v is None else str(v) for k,v in r.items()}
    r['canonical_priced_days_60']=sum(0<=(today-d).days<60 and p['unit_copper'] is not None for d,p in canonical.items())
    return r
def blocked(x):
    if x.get('synthetic'):return 'synthetic'
    if x['mixed_variants']:return 'mixedvariants'
    if not x['complete']:return 'incomplete'
    if x['farbelow']:return 'farbelow'
    if x['age_seconds'] is None:return 'unknown_age'
    if x['age_seconds']>259200:return 'stale'
    return None
def quality(x):
    if not x['has_price']:return 'none'
    if x['synthetic'] or not x['mapping_verified'] or x['age_seconds'] is None:return 'limited'
    fair=x['age_seconds']<=259200 and x['priced_listings']>=3 and not x['cut'] and not x['mixed_variants']
    good=fair and x['complete'] and x['age_seconds']<=86400 and x['priced_listings']>=5 and x['distribution'] and not x['wide_spread'] and x['observed_days_30']>=7 and not x['farbelow']
    return 'good' if good else 'fair' if fair else 'limited'
def purchase(case):
    rows=case['listings'];need=case['requested'];supply=sum(x['quantity'] for x in rows)
    if need>supply:return {'state':'few','low_copper':None,'high_copper':None,'available':supply}
    if case['source_kind']=='commodities':
        remain=need;cost=0
        for x in sorted(rows,key=lambda r:int(r['unit_copper'])):
            take=min(remain,x['quantity']);cost+=take*int(x['unit_copper']);remain-=take
        return {'state':'exact_observed','low_copper':str(cost),'high_copper':str(cost),'fulfilled':need}
    assert len(rows)==1 # fixture only; general whole-listing optimization is deliberately not modeled
    row=rows[0];low=F(int(row['total_copper'])*need,row['quantity'])
    assert low.denominator==1
    return {'state':'range','low_copper':str(int(low)),'high_copper':row['total_copper'],
            'whole_listing_plan_copper':row['total_copper'],'whole_listing_plan_units':row['quantity']}
def source_market(root, cases):
    # Extract exact existing pure functions without executing the module's DB imports.
    path=root/'backend/market/pricing.py'
    tree=ast.parse(path.read_text())
    selected=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in {'summarize','rounded'}]
    assert len(selected)==2
    env={'Decimal':Decimal,'ROUND_HALF_UP':ROUND_HALF_UP}
    exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),env)
    for c in cases:
        rows=[SimpleNamespace(quantity=x['quantity'],buyout=int(x['total_copper']) if x['total_copper'] else None,
                              unit_price=int(x['unit_copper']) if x['unit_copper'] else None) for x in c['listings']]
        actual=env['summarize'](rows)
        for key,fixture_key in [('recent_price','market_recent'),('lowest_buyout','market_minimum')]:
            v=actual[key];assert (None if v is None else str(v))==c['expected'][fixture_key],(c['id'],key,actual)
    return len(cases)
def source_workshop(root,cases):
    lua=shutil.which('lua5.1')
    if not lua:raise RuntimeError('lua5.1 required for --workshop-source')
    # A generated disposable harness contains only trusted fixture numbers and JSON-quoted paths.
    def quote(s):return json.dumps(str(s))
    lines=['TwichUI={Workshop={}}','local W=TwichUI.Workshop',
           'W.Int=function(v,lo,hi) if type(v)=="number" and v>=lo and v<=hi and math.floor(v)==v then return v end end',
           'W.Prices={}; W.Market={}; W.History2={}',
           'dofile('+quote(root/'TwichUI_Workshop/Dist.lua')+')',
           'dofile('+quote(root/'TwichUI_Workshop/Valuation.lua')+')']
    count=0
    for c in cases:
        if c['expected']['workshop_recent'] is None:continue
        _,tiers=tier_data(c)
        arrays=[','.join(str(x[i]) for x in tiers) for i in range(3)]
        lines+=['do local p,q,l={'+arrays[0]+'},{'+arrays[1]+'},{'+arrays[2]+'}',
                'local r,a,q25,q50,q75=W.Dist.Stats(p,q,l,#p); assert(r=='+c['expected']['workshop_recent']+','+quote(c['id'])+')',
                'assert(a=='+c['expected']['anchor']+' and q25=='+c['expected']['q25']+' and q50=='+c['expected']['q50']+' and q75=='+c['expected']['q75']+','+quote(c['id']+' distribution')+')',
                'local m=W.Valuation.WeightedMedian(p,q,#p); assert(m=='+c['expected']['weighted_median']+','+quote(c['id'])+') end']
        count+=1
    lines+=['print("PASSED existing Workshop arithmetic: '+str(count)+' cases")']
    with tempfile.TemporaryDirectory(prefix='m05-lua-') as d:
        p=Path(d)/'check.lua';p.write_text('\n'.join(lines)+'\n')
        subprocess.run([lua,str(p)],check=True)
    return count
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--market-source',type=Path);ap.add_argument('--workshop-source',type=Path)
    args=ap.parse_args()
    import jsonschema
    schema=load('fixture.schema.json');jsonschema.Draft202012Validator.check_schema(schema)
    for name in ['snapshots.json','temporal.json','boundaries.json']:jsonschema.validate(load(name),schema)
    # Hash manifest is deliberately fixed; checker never rewrites expected fixtures.
    hashes=load('SHA256SUMS.json')
    for name,digest in hashes.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    cases=load('snapshots.json')['cases'];report=[]
    for c in cases:
        actual,trim,_=snapshot(c);assert actual==c['expected'],(c['id'],actual,c['expected'])
        descriptor=json.dumps(c['item'],sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
        assert hashlib.sha256(descriptor).hexdigest()==c['variant_key'],c['id']
        if c['origin']=='captured_excerpt':
            assert c['scope_complete'] is False and c['provenance']['observed_history_days']==0
            stamp(c['provenance']['retrieved_at'])
            if args.market_source:
                source=args.market_source/c['provenance']['source_path']
                assert hashlib.sha256(source.read_bytes()).hexdigest()==c['provenance']['source_file_sha256']
        report.append({'id':c['id'],'origin':c['origin'],**actual,'trimmed_mean_10_90':None if trim is None else str(trim)})
        for row in c['listings']:
            for key in ['unit_copper','total_copper','bid_copper']:
                assert row[key] is None or copper(row[key])
    for c in load('temporal.json')['cases']:assert temporal(c)==c['expected'],(c['id'],temporal(c),c['expected'])
    b=load('boundaries.json')
    for c in b['policy']:
        assert {'posting_allowed':blocked(c['input']) is None,'reason':blocked(c['input'])}==c['expected']
    for c in b['quality']:assert quality(c['input'])==c['expected'],c['id']
    for c in b['purchases']:assert purchase(c)==c['expected'],c['id']
    for c in b['identity']:
        raw=json.dumps(c['descriptor'],sort_keys=True,separators=(',',':')).encode()
        assert hashlib.sha256(raw).hexdigest()==c['expected_variant_key']
    assert len({c['expected_variant_key'] for c in b['identity']})==2
    for c in b['validation']:
        if c['field']=='copper':assert not copper(c['value'])
        elif c['field']=='algorithm':assert c['value']!='twichui-pricing-v1'
        elif c['field']=='observed_at':assert stamp(c['value'])>stamp('2026-11-15T12:00:00Z')
        elif c['field']=='historical_basis':assert c['value']!='canonical-daily-close'
        else:raise AssertionError(c)
    print(json.dumps({'result':'PASS','snapshot_cases':len(cases),'temporal_cases':len(load('temporal.json')['cases']),
                      'boundary_cases':sum(len(v) for k,v in b.items() if isinstance(v,list)),'comparisons':report},indent=2))
    if args.market_source:print('PASSED existing Market summarize:',source_market(args.market_source,cases),'cases')
    if args.workshop_source:source_workshop(args.workshop_source,cases)
if __name__=='__main__':main()
