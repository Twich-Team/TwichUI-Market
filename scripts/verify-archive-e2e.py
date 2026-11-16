"""Synthetic authenticated HTTP -> actual Rust archive/projector/publisher -> L1 Lua proof.

Only disposable SQLite, test credentials and owned staging. No collector, metadata
provider, production database, game installation or real SavedVariables.
"""
import argparse
from datetime import datetime, timedelta, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def key(item):return hashlib.sha256(json.dumps(item,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def rss():
 try:
  return int(next(x.split()[1] for x in Path('/proc/self/status').read_text().splitlines() if x.startswith('VmRSS:')))*1024
 except (OSError,StopIteration):return None

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rust-client',type=Path,required=True);p.add_argument('--addon-root',type=Path);p.add_argument('--skip-lua',action='store_true',help='CI-only: explicitly leave the independent Lua gate untested');p.add_argument('--algorithm',choices=['twichui-pricing-v1','asking-v1-provisional'],default='twichui-pricing-v1');p.add_argument('--variants',type=int,default=129);p.add_argument('--report',type=Path);args=p.parse_args()
 if not args.skip_lua and not args.addon_root:p.error('--addon-root is required unless --skip-lua is explicit')
 if not 105<=args.variants<=45125:raise ValueError('bounded synthetic archive count 105..45125 required')
 with tempfile.TemporaryDirectory(prefix='twichui-archive-e2e-') as directory:
  temp=Path(directory);os.environ['DATABASE_URL']='sqlite:///'+str(temp/'market_test.sqlite');os.environ['APP_ORIGIN']='https://archive-fixture.invalid';os.environ['SYNC_CURSOR_SECRET']='synthetic-archive-secret-'+'a'*40;os.environ['BRIDGE_CONTRACT_ROOT']=str(ROOT/'contracts/bridge/v1')
  sys.path.insert(0,str(ROOT/'backend'))
  from market.app import app
  from market.db import Base,engine,Session
  from market import archive_api,bridge_api
  from market.models import User,Market,PlayerMarketMapping,ArchiveCheckpoint
  from market.ingest import ingest
  from market.security import issue
  from sqlalchemy import event
  import uvicorn
  at=datetime.now(timezone.utc)-timedelta(minutes=1)
  archive_api.now=lambda:at;bridge_api.now=lambda:at
  Base.metadata.create_all(engine)
  def book(price,historical):
   rows=[{'id':i+1,'item':{'id':2589},'quantity':q,'buyout':price*q} for i,q in enumerate([3,3,4])]
   if historical:rows +=[{'id':10+i,'item':{'id':2},'quantity':q,'buyout':50*q} for i,q in enumerate([3,3,4])]
   rows +=[{'id':20,'item':{'id':2589,'bonus_lists':[9]},'quantity':1,'buyout':999},{'id':21,'item':{'id':123},'quantity':2,'bid':50}]
   rows +=[{'id':1000+i,'item':{'id':10000+i},'quantity':1,'buyout':price} for i in range(args.variants-4)]
   return json.dumps({'auctions':rows}).encode()
  seed_started=time.perf_counter()
  with Session.begin() as db:
   u=User(username='synthetic_archive',password_hash='not-a-login',role='member');db.add(u);db.flush();token,_,_=issue(db,u,'device');account=u.id
   m=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic archive only',verified=True,enabled=True);db.add(m);db.flush();mid=m.id
   evidence=json.dumps({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde','upstream_receipt':'synthetic','independent_observation':'synthetic','independent_source_url':'https://fixtures.example.invalid/synthetic'})
   db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,source_kind='auctions',transport_ruleset_id=1,confidence='verified',evidence=evidence,evidence_hash=hashlib.sha256(evidence.encode()).hexdigest(),verified_at=at))
   ingest(db,mid,book(100,True),request_key='archive-first',retrieved_at=at-timedelta(days=2),synthetic=True)
   ingest(db,mid,book(120,False),request_key='archive-current',retrieved_at=at,synthetic=True)
  seed_seconds=time.perf_counter()-seed_started
  gc.collect();sql=[0];request_stats=[]
  @event.listens_for(engine,'before_cursor_execute')
  def count_sql(*_):sql[0]+=1
  @app.middleware('http')
  async def measure(request,call_next):
   before=sql[0];start=time.perf_counter();cpu=time.process_time();response=await call_next(request)
   request_stats.append({'path':request.url.path,'status':response.status_code,'sql':sql[0]-before,'ms':(time.perf_counter()-start)*1000,'process_cpu_ms':(time.process_time()-cpu)*1000,'sampled_rss_bytes':rss()})
   return response
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='error',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
  measured_files=[ROOT/'backend/market/archive_api.py',ROOT/'backend/market/bridge_api.py',ROOT/'backend/market/models.py',ROOT/'desktop/core/src/client.rs',ROOT/'desktop/core/src/bridge/export.rs',ROOT/'contracts/archive/v1/archive.schema.json',ROOT/'contracts/bridge/scoped-l1/SHA256SUMS.json',*sorted((ROOT/'desktop/core/src/archive').glob('*.rs'))]
  fingerprints={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in measured_files}
  native_sha=hashlib.sha256(args.rust_client.read_bytes()).hexdigest()
  origin=f'http://127.0.0.1:{port}';stage=temp/'staging';stage.mkdir(mode=0o700);cache=temp/'history.sqlite'
  if os.name=='nt':
   # Python's temporary-directory ACL is not guaranteed private on every runner.
   # Configure only this newly created empty fixture directory; production
   # ownership/reparse checks stay strict and are independently negative-tested.
   sid=subprocess.check_output(['powershell','-NoProfile','-Command','[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True).strip()
   subprocess.run(['icacls',str(stage),'/reset'],check=True,capture_output=True)
   subprocess.run(['icacls',str(stage),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'],check=True,capture_output=True)
  env=os.environ.copy();env['TWICHUI_ARCHIVE_TEST_TOKEN']=token;env['TWICHUI_ARCHIVE_TEST_ALGORITHM']=args.algorithm
  def native(action,request=None,expected=True,account_override=None):
   command=[str(args.rust_client.resolve()),origin,str(account_override or account),str(mid),str(cache),str(stage),action]
   if request:command.append(str(request))
   began=time.perf_counter();process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
   peak=0
   while True:
    try:
     status=Path(f'/proc/{process.pid}/status').read_text()
     peak=max(peak,int(next(x.split()[1] for x in status.splitlines() if x.startswith('VmHWM:')))*1024)
    except (OSError,StopIteration):pass
    try:output,errors=process.communicate(timeout=.02);break
    except subprocess.TimeoutExpired:
     if time.perf_counter()-began>1200:process.kill();process.communicate();raise RuntimeError('native acceptance deadline')
   if not expected:
    assert process.returncode!=0,'negative native operation unexpectedly succeeded';return {'refused':True}
   if process.returncode:raise RuntimeError('Native archive client failed: '+errors)
   result=json.loads(output);result['process_wall_ms']=(time.perf_counter()-began)*1000
   result['native_sampled_peak_rss_bytes']=peak or None
   return result
  def http(path,body=None):
   req=urllib.request.Request(origin+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
   with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=60) as response:return json.load(response)
  try:
   until=time.monotonic()+10
   while not server.started:
    if not thread.is_alive() or time.monotonic()>until:raise RuntimeError('disposable archive server did not start')
    time.sleep(.02)
   partial=native('step');assert not partial['complete'] and partial['pending'] and partial['header'] is None
   initial=native('sync');assert initial['complete'] and not initial['pending'];h=initial['header']
   assert h['total_records']==2*args.variants-1 and h['total_observations']==2
   native('sync',expected=False,account_override=account+1)
   def selection(header,count):
    pairs=[(2,key({'id':2})),(123,key({'id':123})),(2589,key({'id':2589}))]+[(10000+i,key({'id':10000+i})) for i in range(count-3)]
    return {'format':'twichui-market-selection','contract_version':1,'expected_schema_version':3,'issuer_id':header['issuer_id'],'market':header['market'],'scope_type':'explicit_variants',
     'variants':[{'item_id':i,'variant_key':v} for i,v in sorted(pairs)],'history_from_day':(at.date()-timedelta(days=59)).isoformat(),'history_through_day':at.date().isoformat(),
     'pricing_algorithm':header['pricing_algorithm'],'history_basis':header['history_basis'],'profile':'daily_research_v1'}
   def export(header,count):
    request=selection(header,count);path=temp/'request.json';path.write_text(json.dumps(request));result=native('export',path);g=json.loads(Path(result['generation_path']).read_text());archive_api.scoped_contract().validate(g,request);archive_api.scoped_contract().validate_receipt(g,result["receipt"])
    exact=http(f'/api/v1/archive/markets/{mid}/scoped?checkpoint='+header['checkpoint_id'],request)
    assert exact==g,'actual Rust and server scoped generation bytes differ'
    return result,g,request,path
   ten,g,request,request_path=export(h,10)
   expected_mv='100' if args.algorithm=='twichui-pricing-v1' else '110'
   expected_updated_mv='100' if args.algorithm=='twichui-pricing-v1' else '120'
   priced=next(r for r in g['records'] if r['item_id']==2589)
   assert [d['recent_copper'] for d in priced['daily']]==['100','120'] and priced['current']['metrics']['market_value_copper']==expected_mv
   assert g['records'][0]['current']['state']=='absent' and g['records'][1]['current']['metrics']['recent_copper'] is None and g['records'][1]['current']['supply']==2
   assert len([d for d in g['scope']['date_coverage'] if d['state']=='no_observation'])==58
   hundred,g,request,request_path=export(h,100)
   artifact=Path(hundred['lua_path']);before=artifact.read_bytes();native('refuse',request_path,expected=False);assert artifact.read_bytes()==before
   # Apply a new same-day snapshot, preserving the first close and old archive.
   at=at+timedelta(seconds=1)
   with Session.begin() as db:ingest(db,mid,book(140,False),request_key='archive-next',retrieved_at=at,synthetic=True)
   partial_update=native('step');assert not partial_update['complete'] and partial_update['header']['checkpoint_id']==h['checkpoint_id']
   updated=native('sync');nh=updated['header'];assert nh['total_observations']==3 and nh['transfer_observations']==1 and nh['transfer_records']==args.variants-1
   final,final_g,final_request,_=export(nh,100)
   priced=next(r for r in final_g['records'] if r['item_id']==2589)
   assert [d['recent_copper'] for d in priced['daily']]==['100','140']
   assert priced['current']['metrics']['market_value_copper']==expected_updated_mv
   # Schema-3 output passes the L1 test-only consumer, never a production L3 reader.
   lua_proof='NOT RUN (explicit --skip-lua)'
   if not args.skip_lua:
    sys.path.insert(0,str(args.addon_root/'tests'))
    import test_workshop_scoped_bridge_l1 as proof
    import test_workshop_bridge as legacy
    q=legacy.lua;plan=legacy.lua(proof.expanded_plan())
    lines=['require("bit")','TwichUI={Workshop={}}','TwichUIWorkshopDB={keep="local"}','TwichUIDB={keep="profile"}']
    for name in ('Data','BridgeCodec','BridgeSchema','BridgeValidate'):lines.append('dofile('+q(str(args.addon_root/'TwichUI_Workshop'/(name+'.lua')))+')')
    lines+=['local J=TwichUI.Workshop.BridgeCodec','local P=dofile('+q(str(args.addon_root/'tests/prototypes/scoped_bridge_l1.lua'))+')','local plan='+plan,
     'dofile('+q(str(final['lua_path']))+')','local raw=TwichUIMarketData;local g=J.Parse(raw.manifest);g.records=J.Array();for _,text in ipairs(raw.records)do g.records[#g.records+1]=J.Parse(text)end',
     'local state={};P.Accept(state,g,plan,g.scope.request)','assert(g.scope.scope_complete and not g.coverage.generation_complete)',
     'local priced=P.Lookup(g,2589,'+q(key({'id':2589}))+');assert(P.Value(priced,"recent_copper")==140)',
     'local missing,why=P.Lookup(g,2589,'+q(key({'id':2589,'bonus_lists':[9]}))+');assert(missing==nil and why=="outside_scope")',
     'local bad=J.Copy(g);bad.generation_id=string.rep("0",64);assert(not pcall(P.Accept,state,bad,plan,g.scope.request));assert(state.active.generation_id==g.generation_id)',
     'assert(TwichUIWorkshopDB.keep=="local" and TwichUIDB.keep=="profile");print("L1 scoped artifact proof PASS")']
    script=temp/'proof.lua';script.write_text('\n'.join(lines)+'\n');subprocess.run(['luac5.1','-p',str(final['lua_path'])],check=True,capture_output=True)
    lua=subprocess.run(['lua5.1',str(script)],capture_output=True,text=True,timeout=120)
    if lua.returncode:raise RuntimeError('L1 Lua proof failed: '+lua.stdout+lua.stderr)
    lua_proof=lua.stdout.strip()
   noop=native('sync');assert noop['header']['checkpoint_id']==nh['checkpoint_id'],'same-day unchanged evidence replaced recovery generation'
   before=artifact.read_bytes();Path(final['lua_path']).write_bytes(before+b' injected()')
   # Readback refuses a corrupted existing file; it does not overwrite recovery data.
   native('export',request_path,expected=False);Path(final['lua_path']).write_bytes(before)
   page_stats=[s for s in request_stats if s['path'].endswith('/pages')]
   try:
    import resource
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
   except ImportError:peak=None
   assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in fingerprints.items()),'measured implementation changed during acceptance'
   assert hashlib.sha256(args.rust_client.read_bytes()).hexdigest()==native_sha,'native binary changed during acceptance'
   report={'result':'PASS','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_sha256':fingerprints,'native_binary_sha256':native_sha,'synthetic_seed_seconds':seed_seconds,'server_sqlite_bytes':(temp/'market_test.sqlite').stat().st_size,'origin':'synthetic','variants':args.variants,'algorithm':args.algorithm,'python':platform.python_version(),'production_access':False,'real_client_acceptance':False,
    'initial_step':partial,'initial_resume':initial,'incremental_step':partial_update,'incremental_resume':updated,'ten_variant_export':ten,'hundred_variant_export':hundred,'updated_export':final,
    'server_request_process_cpu_ms_total':sum(s['process_cpu_ms'] for s in request_stats),'page_process_cpu_ms_total':sum(s['process_cpu_ms'] for s in page_stats),'cpu_measurement':'Python server process CPU across each request; includes small coordinator polling overhead, excludes seed and native Rust subprocess',
    'server_sql_total':sql[0],'archive_page_requests':len(page_stats),'page_sql_max':max(s['sql'] for s in page_stats),'page_sql_total':sum(s['sql'] for s in page_stats),
    'server_process_peak_rss_bytes_including_seed':peak,'server_request_sampled_rss_bytes':max((s['sampled_rss_bytes'] or 0) for s in request_stats),'page_response_ms_max':max(s['ms'] for s in page_stats),
    'independent_expected':{'initial_recent':['100','120'],'updated_recent':['100','140'],'market_value':expected_mv,'updated_market_value':expected_updated_mv,'historical_value':None if args.algorithm=='twichui-pricing-v1' else '110','historical_current_state':'absent','bid_supply':2,'missing_days':58},
    'lua_proof':lua_proof,'same_day_noop_retains_checkpoint':True,'corrupt_existing_artifact_refused':True,'over_budget_preserves_artifact':True,'wrong_account_refused':True}
   # Temporary artifact paths are not reusable evidence and never identify game files.
   for name in ('ten_variant_export','hundred_variant_export','updated_export'):
    report[name]={k:v for k,v in report[name].items() if k not in ('lua_path','generation_path')}
   if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
   print(json.dumps(report,indent=2))
  finally:
   server.should_exit=True;thread.join(timeout=10);sock.close();engine.dispose()
if __name__=='__main__':main()
