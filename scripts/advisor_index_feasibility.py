"""L2-only synthetic Tier A interface/sizing proof; no production reader or addon.

All data is disposable. A separate format prevents detailed-history membership
from controlling broad summary coverage or masquerading as local competition.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('frozen_bridge',ROOT/'contracts/bridge/v1/validate.py')
v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)
canonical=v1.canonical
STATES=['priced','supply_only','absent','unknown','unsupported']
# Exact identity, availability, three ask-derived metrics, supply, age, quality.
COLUMNS=['item_id','variant_key','state','recent_copper','market_value_copper','minimum_copper','supply','age_seconds','confidence']


def generate(count, all_priced=False):
    rows=[]
    for i in range(count):
        item=10000+i;variant=hashlib.sha256(canonical({'id':item})).hexdigest();state=0 if all_priced else i%5
        prices=([str(99_000_000_001-i*3),str(99_000_000_002-i*3),str(99_000_000_000-i*3)] if all_priced else [str(10000+i),str(11000+i),str(9000+i)]) if state==0 else [None]*3
        rows.append([item,variant,state,*prices,12 if state in (0,1) else 0 if state==2 else None,300,0 if state==0 else 1])
    source=json.loads((ROOT/'contracts/bridge/v1/source-canonical-generation.json').read_bytes())
    g={'format':'twichui-market-summary-index','schema_version':1,'experimental':True,
       'market':source['market'],'issuer_id':source['issuer_id'],'pricing_algorithm':'twichui-pricing-v1','history_basis':'canonical_complete_scope_close',
       'source_kind':'market_server_asking_summary','confidence_ceiling':'limited','can_satisfy_local_competition':False,
       'source_observation':{'observation_id':'902','observed_at':'2026-11-15T12:00:00Z','scope_complete':True},'source_watermark':'902','generated_at':'2026-11-15T12:02:00Z','identity_basis':'exact_variant_hash',
       'columns':COLUMNS,'states':STATES,'confidence_states':['limited','unavailable'],
       'coverage':{'type':'all_retained_exact_identity_summaries','complete':True,'missing':'unavailable','detailed_history':'independent'},
       'record_count':count,'records':rows,'records_sha256':hashlib.sha256(canonical(rows)).hexdigest()}
    g['generation_id']=hashlib.sha256(canonical(g)).hexdigest();return g


def validate(g):
    import jsonschema
    schema=json.loads((ROOT/'contracts/market-summary-index-proposal/schema.json').read_bytes())
    jsonschema.Draft202012Validator(schema).validate(g)
    assert g['record_count']==len(g['records'])
    assert g['records_sha256']==hashlib.sha256(canonical(g['records'])).hexdigest()
    assert g['generation_id']==hashlib.sha256(canonical({k:v for k,v in g.items() if k!='generation_id'})).hexdigest()
    prior=None
    for r in g['records']:
        ident=(r[0],r[1]);assert prior is None or prior<ident;prior=ident
        assert r[2]==0 or r[3:6]==[None]*3
        assert r[2]!=2 or r[6]==0
        assert r[2] not in (3,4) or r[6] is None
        for copper in r[3:6]:
            if copper is not None:assert 1<=int(copper)<=99_999_999_999
    return True


def lookup(g,item,variant):
    row=next((r for r in g['records'] if (r[0],r[1])==(item,variant)),None)
    return {'state':'unavailable','price':None} if row is None else {'state':STATES[row[2]],'price':row[3]}


def lua(value):
    # Experimental assignment-only representation. False is an explicit null
    # sentinel inside fixed tuples; it is never a copper value or absence proof.
    if value is None:return 'false'
    if isinstance(value,bool):return 'true' if value else 'false'
    if isinstance(value,int):return str(value)
    if isinstance(value,str):return json.dumps(value,ensure_ascii=True)
    return '{'+','.join(lua(v) for v in value)+'}'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lua',default='lua5.1');p.add_argument('--report',type=Path);a=p.parse_args()
    g=generate(45125,all_priced=True);validate(g);samples=[]
    with tempfile.TemporaryDirectory(prefix='advisor-index-proof-') as root:
        for label,rows in [('whole',g['records']),('one_of_16_item_id_partitions',[r for r in g['records'] if r[0]%16==0])]:
            raw=canonical(rows);source=('TwichUIAdvisorIndexProof = '+lua(rows)+'\n').encode();path=Path(root)/'proof.lua';path.write_bytes(source)
            harness=Path(root)/'measure.lua';harness.write_text('''collectgarbage('collect');local baseline=collectgarbage('count');local start=os.clock()
local chunk=assert(loadfile(arg[1]));local compile=(os.clock()-start)*1000;start=os.clock();chunk();local assign=(os.clock()-start)*1000
start=os.clock();local rows=TwichUIAdvisorIndexProof;local by={};for i,r in ipairs(rows) do assert(type(r[1])=='number' and type(r[2])=='string' and #r[2]==64);assert(r[3]>=0 and r[3]<=4);for j=4,6 do assert(r[j]==false or type(r[j])=='string')end;by[r[2]]=r end
local validate=(os.clock()-start)*1000;start=os.clock();collectgarbage('collect');local gc=(os.clock()-start)*1000
local retained=(collectgarbage('count')-baseline)*1024;start=os.clock();for i=1,10000 do assert(by[rows[(i-1)%#rows+1][2]])end;local lookup=(os.clock()-start)*1000
print(string.format('%.3f %.3f %.3f %.3f %.0f %.3f',compile,assign,validate,gc,retained,lookup))
''')
            run=subprocess.run([a.lua,str(harness),str(path)],check=True,text=True,capture_output=True,timeout=120)
            c,assignment,validation,gc,heap,lookup_ms=map(float,run.stdout.split())
            samples.append({'case':label,'records':len(rows),'canonical_row_bytes':len(raw),'lua_row_source_bytes':len(source),'compile_ms':c,'assignment_ms':assignment,'minimal_structure_index_ms':validation,'explicit_global_gc_ms':gc,'retained_heap_with_compiled_chunk_and_index_bytes':int(heap),'lookup_10000_ms':lookup_ms})
    result={'origin':'synthetic','production_distribution':False,'assumptions':'all 45,125 exact variants priced, three distinct 11-digit copper strings each, supply 12 and age 300 seconds; synthetic capacity shape','python':platform.python_version(),'runtime':'offline Lua 5.1, one sample each; not Forever acceptance','columns':COLUMNS,
      'whole_envelope_canonical_bytes':len(canonical(g)),'manifest_overhead_bytes':len(canonical(g))-len(canonical(g['records'])),'cases':samples,
      'limitations':['Row validation benchmark excludes complete future cryptographic consumer validation.','All 16 partitions eventually retained would retain the whole index plus overhead.','Compile, assignment, global GC and startup must be measured in the real client.','Proposal is not advertised, installed or accepted by production consumers.']}
    if a.report:a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
