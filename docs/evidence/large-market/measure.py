"""Research sizing only: streams existing synthetic records; never connects to DB/API.
Run from repository root: python3 docs/evidence/large-market/measure.py > /tmp/sizing.json
Tuple bytes are an illustrative representation estimate, NOT a new bridge format.
"""
import sys, json, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from bridge_workloads import header, record, canonical, generate
COUNTS = (100, 1000, 5000, 10000, 25000, 45125)
PROFILES = ('one', 'two-gap', 'fourteen', 'sixty', 'sparse-sixty', 'historical-only')
result = {'origin':'synthetic', 'production_access':False, 'method':'stream existing M1.5 record generator, retain only size integers', 'profiles':[]}
for profile in PROFILES:
    h,t = header(profile); lengths=[]; tuple_lengths=[]; section={}; total=2
    rows=[]
    for i in range(max(COUNTS)):
        r=record(h,t,i,profile); raw=canonical(r); lengths.append(len(raw)); total+=len(raw)+(i>0)
        # Positional nested arrays remove field names only; all values stay exact,
        # including repeated algorithm values. Fixed sorted schema is assumed.
        def positional(x):
            if isinstance(x,dict):return [positional(x[k]) for k in sorted(x)]
            if isinstance(x,list):return [positional(v) for v in x]
            return x
        tuple_lengths.append(len(canonical(positional(r))))
        for k,v in r.items():section[k]=section.get(k,0)+len(canonical(v))
        n=i+1
        if n in COUNTS:
            hh={**h,'record_count':n,'generation_id':'0'*64}
            hh['integrity']={'records_bytes':total,'records_sha256':'0'*64,'manifest_sha256':'0'*64}
            manifest=len(canonical(hh)); size=manifest+total+11
            rows.append({'variants':n,'record_sum_bytes':sum(lengths),'canonical_bytes':size,
                         'manifest_bytes':manifest,'positional_records_bytes':sum(tuple_lengths)+n+1,
                         'exceeds_build_guard':sum(lengths)>64*1024**2,'exceeds_contract':size>32*1024**2})
    sorted_l=sorted(lengths)
    result['profiles'].append({'profile':profile,'counts':rows,'record_bytes':{'min':min(lengths),'p50':statistics.median(lengths),'p95':sorted_l[int(.95*(len(lengths)-1))],'max':max(lengths)},'value_section_bytes_full':section})
    # Check the streaming size equation against the actual existing generator.
    _,check=generate(100,profile)
    assert rows[0]['canonical_bytes']==check['canonical_bytes']
print(json.dumps(result,indent=2))
