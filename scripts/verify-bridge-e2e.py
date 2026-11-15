"""Disposable authenticated HTTP → actual Rust cache/export → actual Workshop Lua reader.

All seeded scopes are explicitly synthetic. No production connection, worker,
installation, owner credentials or SavedVariables are used.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'contracts/bridge/v1'

def quoted(s):return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,92) else '\\%03d'%b for b in s.encode())+'"'
def main():
 p=argparse.ArgumentParser();p.add_argument('--rust-client',type=Path,required=True);p.add_argument('--addon-root',type=Path,required=True);p.add_argument('--report',type=Path);args=p.parse_args()
 source=json.loads((FIXTURES/'e2e-observations.json').read_text());expected=json.loads((FIXTURES/'e2e-expected.json').read_text())
 assert source['origin']=='synthetic' and all(o['synthetic'] and o['scope_complete'] for o in source['observations'])
 assert args.rust_client.is_file() and (args.addon_root/'TwichUI_Workshop/Bridge.lua').is_file()
 with tempfile.TemporaryDirectory(prefix='twichui-bridge-test-') as directory:
  temp=Path(directory);os.environ['DATABASE_URL']='sqlite:///'+str(temp/'market_test.sqlite');os.environ['APP_ORIGIN']='https://bridge-fixture.example.invalid';os.environ['SYNC_CURSOR_SECRET']='synthetic-e2e-cursor-secret-'+'a'*32;os.environ['BRIDGE_CONTRACT_ROOT']=str(FIXTURES)
  sys.path.insert(0,str(ROOT/'backend'))
  from market.app import app
  from market.db import Base,engine,Session
  from market import bridge_api
  from market.models import User,Market,PlayerMarketMapping
  from market.security import issue
  from market.ingest import ingest
  import uvicorn
  instant=datetime.fromisoformat(source['as_of'].replace('Z','+00:00'));bridge_api.now=lambda:instant;bridge_api.MAX_PAGE_RECORDS=1
  Base.metadata.create_all(engine)
  with Session.begin() as db:
   u=User(username='synthetic_bridge_account',password_hash='not-a-login',role='member');db.add(u);db.flush();token,_,_=issue(db,u,'device');account=u.id
   m=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic fixture only',verified=True,enabled=True);db.add(m);db.flush();mid=m.id
   evidence=json.dumps({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde','upstream_receipt':'synthetic','independent_observation':'synthetic','independent_source_url':'https://fixtures.example.invalid/synthetic'},sort_keys=True)
   db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,source_kind='auctions',transport_ruleset_id=1,confidence='verified',evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),verified_at=instant))
   for i,o in enumerate(source['observations']):ingest(db,mid,json.dumps(o['payload']).encode(),request_key='synthetic-e2e-'+str(i),retrieved_at=datetime.fromisoformat(o['observed_at'].replace('Z','+00:00')),modified=o['upstream_modified'],synthetic=True)
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
  try:
   until=time.monotonic()+10
   while not server.started:
    if not thread.is_alive() or time.monotonic()>until:raise RuntimeError('Disposable HTTP server did not start')
    time.sleep(.02)
   origin=f'http://127.0.0.1:{port}'
   request=urllib.request.Request(origin+f'/api/v1/bridge/markets/{mid}/manifest',headers={'Authorization':'Bearer '+token})
   with urllib.request.urlopen(request,timeout=10) as response:envelope=json.load(response)
   generation=envelope['manifest']['generation_id']
   stage=temp/'staging';stage.mkdir(mode=0o700)
   env=os.environ.copy();env['TWICHUI_BRIDGE_TEST_TOKEN']=token
   run=subprocess.run([str(args.rust_client.resolve()),origin,str(account),str(mid),str(temp/'bridge-v1.sqlite'),str(stage)],capture_output=True,text=True,env=env,timeout=120)
   if run.returncode:raise RuntimeError('Rust bridge client failed: '+run.stderr)
   rust=json.loads(run.stdout);assert rust['generation_id']==generation and rust['market']==envelope['manifest']['market']
   artifact=Path(rust['lua_path']);assert artifact.resolve().is_relative_to(stage.resolve())
   subprocess.run(['luac5.1','-p',str(artifact)],check=True,capture_output=True)
   subprocess.run(['lua5.1','-e','assert(TwichUI==nil);dofile('+quoted(str(artifact))+');assert(TwichUI==nil and TwichUIMarketData~=nil)'],check=True,capture_output=True)
   lines=['require("bit")','TwichUI={Workshop={}}','TwichUIDB={profile="local-preserved"}','TwichUIWorkshopDB={v=2,markets={original={items={[2589]="999,1,1,1,0"},h2={[2589]="original-history"}}}}',
    'local function fingerprint(v)if type(v)~=\"table\" then return tostring(v)end local k={} for x in pairs(v)do k[#k+1]=x end table.sort(k,function(a,b)return tostring(a)<tostring(b)end)local out={} for _,x in ipairs(k)do out[#out+1]=tostring(x)..\"=\"..fingerprint(v[x])end return \"{\"..table.concat(out,\",\")..\"}\"end','local original,profile=TwichUIWorkshopDB,TwichUIDB;local savedBefore=fingerprint(original)..fingerprint(profile)','CreateFrame=function()error(\"unexpected frame\")end;C_AddOns={LoadAddOn=function()error(\"unexpected addon load\")end};C_AuctionHouse=setmetatable({},{__index=function()return function()error(\"unexpected AH action\")end end})','GetTimePreciseSec=function()return os.clock()end']
   for name in ['Data','BridgeCodec','BridgeSchema','BridgeValidate','Bridge']:lines+=['dofile('+quoted(str(args.addon_root/'TwichUI_Workshop'/(name+'.lua')))+')']
   lines+=['local B,J=TwichUI.Workshop.Bridge,TwichUI.Workshop.BridgeCodec','collectgarbage("collect");local before=collectgarbage("count")*1024',
    'local started=os.clock();dofile('+quoted(str(artifact))+');local loadUS=math.floor((os.clock()-started)*1000000+0.5)',
    'assert(not B.Status().ready,"data addon unexpectedly loads Workshop reader")','B.Begin(TwichUIMarketData)',
    'for i=1,200000 do local ok,why=B.Step(3);if why~="loading" then assert(ok,"generated artifact rejected");break end;assert(i<200000)end',
    'assert(B.Status().generation=='+quoted(generation)+')','assert(B.Status().records=='+str(expected['record_count'])+')',
    'assert(B.Market().house_id==114 and B.Market().server_market_id=='+str(mid)+')',
    'local key='+quoted(expected['variant_key']),
    'local v=B.Value(2589,key,"recent");assert(v.copper=="120" and v.algorithm=="twichui-pricing-v1")',
    'assert(B.Value(2589,key,"market").copper=="100");assert(B.Value(2589,key,"historical")==nil)',
    'local h=B.History(2589,key,"recent",{days=3});assert(#h.points==2 and #h.gaps==1)',
    'assert(h.points[1].copper=="100" and h.points[2].copper=="120")',
    'assert(h.points[1].at=="2026-11-13T12:00:00.123456Z" and h.points[2].at=="2026-11-15T12:00:00.123456Z")',
    'assert(h.points[2].from-h.points[1].from==2 and h.gaps[1].from==h.points[1].from+1)',
    'local supply=B.History(2589,key,"supply",{days=3});assert(supply.points[1].v==10 and supply.points[2].v==10)',
    'local variants=B.Variants(2589);assert(#variants==2);for _,other in ipairs(variants)do if other~=key then assert(B.Value(2589,other,"recent").copper=="999")end end',
    'local old=B.Variants(2)[1];assert(B.Record(2,old).current.state=="absent")',
    'local bid=B.Variants(123)[1];assert(B.Value(123,bid,"recent")==nil and B.Record(123,bid).current.supply==2)',
    'assert(TwichUIWorkshopDB==original and TwichUIDB==profile and original.markets.original.items[2589]=="999,1,1,1,0" and original.markets.original.h2[2589]=="original-history" and profile.profile=="local-preserved")',
    'collectgarbage("collect");local retained=collectgarbage("count")*1024;local baseline=retained',
    'local lookupStart=os.clock();for i=1,100 do B.Record(2589,key);B.History(2589,key,"recent",{days=3})end;local navigationUS=math.floor((os.clock()-lookupStart)*1000000+0.5)',
    'collectgarbage("collect");local growth=collectgarbage("count")*1024-baseline;assert(growth<131072 and B.Status().cache_entries<=B.CACHE_MAX)',
    'local bad={transport_version=1,manifest=TwichUIMarketData.manifest,records={},receipt=TwichUIMarketData.receipt};for i,s in ipairs(TwichUIMarketData.records)do bad.records[i]=s end;bad.records[1]=bad.records[1].."x"',
    'B.Begin(bad);for i=1,200000 do local ok,why=B.Step(3);if why~="loading" then assert(not ok);break end end;assert(B.Status().generation=='+quoted(generation)+')',
    'assert(B.Value(2589,key,"recent").copper=="120" and original.markets.original.h2[2589]=="original-history");assert(savedBefore==fingerprint(original)..fingerprint(profile))',
    'local stats=B.Status();assert(stats.bytes=='+str(rust['payload_bytes'])+')',
    'io.write(J.Encode(setmetatable({generation_id=stats.generation,record_count=stats.records,payload_bytes=stats.bytes,load_us=loadUS,validation_us=math.floor(stats.validation_ms*1000+0.5),largest_slice_us=math.floor(stats.largest_slice_ms*1000+0.5),slices=stats.slices,retained_heap_bytes=math.floor(retained-before+0.5),navigation_100_us=navigationUS,navigation_growth_bytes=math.floor(growth+0.5),cache_entries=stats.cache_entries,corruption_rejected=true,local_saved_data_unchanged=true},J.OBJECT)))']
   lua=temp/'verify.lua';lua.write_text('\n'.join(lines)+'\n');result=subprocess.run(['lua5.1',str(lua)],capture_output=True,text=True,timeout=120)
   if result.returncode:raise RuntimeError('Workshop reader failed: '+result.stdout+result.stderr)
   observed=json.loads(result.stdout);assert observed['generation_id']==generation and observed['record_count']==expected['record_count']
   report={'result':'PASS','origin':'synthetic','fixture_input_sha256':hashlib.sha256((FIXTURES/'e2e-observations.json').read_bytes()).hexdigest(),'independent_expected_sha256':hashlib.sha256((FIXTURES/'e2e-expected.json').read_bytes()).hexdigest(),'http_authenticated':True,'page_record_limit':1,'generation_id':generation,'market':rust['market'],'schema_version':2,'contract_version':1,'transport_version':1,'available_dates':expected['dates'],'missing_dates':expected['missing_dates'],'rust':{k:v for k,v in rust.items() if k not in ('lua_path','receipt')},'lua':observed,'production_access':False,'installed_into_game':False,'real_client_acceptance':False,'bridge_only_does_not_load_workshop':True,'no_frames_or_auction_requests':True}
   if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
   print(json.dumps(report,indent=2))
  finally:
   server.should_exit=True;thread.join(timeout=10);sock.close();engine.dispose()
if __name__=='__main__':main()
