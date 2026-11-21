"""Explicitly synthetic Lua reader benchmark; not a client or production capacity claim."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import hashlib

ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--addon-root',type=Path,required=True);p.add_argument('--records',type=int,default=1000);p.add_argument('--runs',type=int,default=3);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 assert 1<=a.records<=10000 and 1<=a.runs<=3
 spec=importlib.util.spec_from_file_location('bridge_contract',ROOT/'contracts/bridge/v1/validate.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 g=v.read(ROOT/'contracts/bridge/v1/source-canonical-generation.json');template=g['records'][1];g['records']=[];g['record_count']=a.records;g['synthetic']=True
 for o in g['observations']:o['synthetic']=True
 for i in range(a.records):
  r=copy.deepcopy(template);r['item_id']=10000+i;r['variant_json']=v.canonical({'id':r['item_id']}).decode();r['variant_key']=hashlib.sha256(r['variant_json'].encode()).hexdigest();g['records'].append(r)
 g=v.seal(g);v.validate(g)
 def q(s):return '"'+''.join('\\%03d'%b for b in s.encode())+'"'
 h=copy.deepcopy(g);records=h.pop('records');receipt=dict(schema_version=1,generation_id=g['generation_id'],desktop_build='synthetic-benchmark',completed_at='2026-11-15T13:00:00Z')
 source='TwichUIMarketData = { transport_version = 1, manifest = '+q(v.canonical(h).decode())+', records = {\n'+',\n'.join(q(v.canonical(r).decode()) for r in records)+',\n}, receipt = '+q(v.canonical(receipt).decode())+' }\n'
 runs=[]
 with tempfile.TemporaryDirectory(prefix='twichui-bridge-benchmark-') as d:
  temp=Path(d);artifact=temp/'Data.lua';artifact.write_text(source)
  subprocess.run(['luac5.1','-p',str(artifact)],check=True,capture_output=True)
  lines=['require("bit")','TwichUI={Workshop={}}','GetTimePreciseSec=function()return os.clock()end']
  for name in ['Data','BridgeCodec','BridgeSchema','BridgeValidate','Bridge']:lines+=['dofile('+q(str(a.addon_root/'TwichUI_Workshop'/(name+'.lua')))+')']
  lines+=['local B,J=TwichUI.Workshop.Bridge,TwichUI.Workshop.BridgeCodec','collectgarbage("collect");local before=collectgarbage("count")*1024','local t=os.clock();dofile('+q(str(artifact))+');local loadUS=math.floor((os.clock()-t)*1e6+.5)','B.Begin(TwichUIMarketData)','for i=1,10000000 do local ok,why=B.Step(3);if why~="loading" then assert(ok);break end;assert(i<10000000)end',
  'collectgarbage("collect");local retained=collectgarbage("count")*1024-before','local r=J.Parse(TwichUIMarketData.records[1]);t=os.clock();assert(B.Record(r.item_id,r.variant_key));local lookupUS=math.floor((os.clock()-t)*1e6+.5)','t=os.clock();local h=B.History(r.item_id,r.variant_key,"recent",{days=2});assert(#h.points==2);local historyUS=math.floor((os.clock()-t)*1e6+.5)',
  'local rows={};for i=1,100 do local x=J.Parse(TwichUIMarketData.records[1+(i-1)%#TwichUIMarketData.records]);rows[i]={x.item_id,x.variant_key}end','collectgarbage("collect");local startHeap=collectgarbage("count")*1024;t=os.clock()','for loop=1,2 do for _,x in ipairs(rows)do assert(B.Record(x[1],x[2]));assert(B.History(x[1],x[2],"recent",{days=2}))end end','local nav=math.floor((os.clock()-t)*1e6+.5);collectgarbage("collect");local growth=collectgarbage("count")*1024-startHeap;local s=B.Status();assert(s.cache_entries<=24)',
  'print(J.Encode(setmetatable({load_us=loadUS,validation_us=math.floor(s.validation_ms*1000+.5),largest_slice_us=math.floor(s.largest_slice_ms*1000+.5),slices=s.slices,retained_heap_bytes=math.floor(retained),first_lookup_us=lookupUS,history_us=historyUS,navigation_200_us=nav,navigation_growth_bytes=math.floor(growth),cache_entries=s.cache_entries},J.OBJECT)))']
  script=temp/'reader.lua';script.write_text('\n'.join(lines))
  for i in range(a.runs):runs.append(json.loads(subprocess.run(['lua5.1',str(script)],check=True,capture_output=True,text=True,timeout=300).stdout))
 result=dict(origin='synthetic',scope='Offline Lua 5.1 CPU, no game assets, two dates per variant; not full capacity or real-client acceptance',records=a.records,generation_id=g['generation_id'],payload_bytes=len(v.canonical(g)),lua_bytes=len(source),runs=runs)
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
