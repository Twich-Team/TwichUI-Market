"""Synthetic actual authenticated API -> native summary -> production Lua/Market.
No provider calls, collection, production DB, credentials or real game files.
Windows publication mode uses the real versioned-PE/paired-addon fixture, not a
product validation bypass. Linux staging is explicitly not installed acceptance.
"""
import argparse,gc,hashlib,json,os,platform,secrets,shutil,socket,subprocess,sys,tempfile,threading,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--rust-client',type=Path,required=True);p.add_argument('--addon-root',type=Path,required=True);p.add_argument('--lua',default='lua5.1');p.add_argument('--lua-cpath');p.add_argument('--variants',type=int,default=129);p.add_argument('--out',type=Path,required=True);p.add_argument('--publish',action='store_true');p.add_argument('--history',action='store_true',help='Negotiate the installed paired history reader in staging mode');p.add_argument('--skip-lua',action='store_true',help='Windows producer only; paired Linux artifact consumer is mandatory in CI')
 a=p.parse_args()
 if not 129<=a.variants<=45125 or a.publish and (os.name!='nt' or os.environ.get('GITHUB_ACTIONS')!='true'):p.error('bounded synthetic count; installed publication only on disposable Windows')
 a.out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='twichui-summary-e2e-',dir=os.environ.get('RUNNER_TEMP') if os.name=='nt' else None) as directory:
  temp=Path(directory);os.environ.update(DATABASE_URL='sqlite:///'+str(temp/'summary-market_test.sqlite'),APP_ORIGIN='https://synthetic-summary.invalid',SYNC_CURSOR_SECRET='synthetic-summary-authorization-'+'a'*40,BRIDGE_CONTRACT_ROOT=str(ROOT/'contracts/bridge/v1'))
  sys.path.insert(0,str(ROOT/'backend'))
  from market.app import app
  from market.db import Base,engine,Session
  from market.models import User,Market,PlayerMarketMapping,CompanionDevice
  from market.ingest import ingest
  from market.companion_auth import _access
  import uvicorn
  assert engine.url.database.endswith('summary-market_test.sqlite')
  Base.metadata.create_all(engine);at=datetime.now(timezone.utc)-timedelta(minutes=1)
  def book(price,historical=False):
   rows=[{'id':j+1,'item':{'id':2589},'quantity':q,'buyout':q*price}for j,q in enumerate([3,3,4])]
   rows +=[{'id':20,'item':{'id':2589,'bonus_lists':[9]},'quantity':1,'buyout':999},{'id':21,'item':{'id':123},'quantity':2,'bid':50}]
   if historical:rows.append({'id':22,'item':{'id':2},'quantity':10,'buyout':500})
   rows +=[{'id':1000+i,'item':{'id':10000+i},'quantity':10,'buyout':10*price}for i in range(a.variants-3)]
   return json.dumps({'auctions':rows}).encode()
  with Session.begin() as db:
   u=User(username='synthetic_summary',password_hash='not-a-login',role='member');db.add(u);db.flush();account=u.id
   device=CompanionDevice(user_id=account,name='Synthetic scoped summary fixture',platform='Windows',app_version='2.0.0-beta.7',issuer_origin='https://synthetic-summary.invalid',expires_at=at+timedelta(days=1),refresh_expires_at=at+timedelta(days=1),refresh_hash=hashlib.sha256(b'fixture-unused-refresh').hexdigest())
   db.add(device);db.flush();token=secrets.token_urlsafe(32);_access(db,device,token)
   m=Market(region='us',ruleset_id=1,house_id=114,source_kind='auctions',label='Synthetic summary E2E only',verified=True,enabled=True);db.add(m);db.flush();mid=m.id
   proof=json.dumps({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde','upstream_receipt':'synthetic','independent_observation':'synthetic','independent_source_url':'https://example.invalid/fixture'})
   db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,source_kind='auctions',transport_ruleset_id=1,confidence='verified',evidence=proof,evidence_hash=hashlib.sha256(proof.encode()).hexdigest(),verified_at=at))
   ingest(db,mid,book(100,True),request_key='summary-e2e-previous',retrieved_at=at-timedelta(days=2),synthetic=True)
   ingest(db,mid,book(120),request_key='summary-e2e-current',retrieved_at=at,synthetic=True)
  gc.collect();requests=[]
  @app.middleware('http')
  async def measure(request,call_next):
   start=time.perf_counter();response=await call_next(request)
   requests.append({'path':request.url.path,'status':response.status_code,'elapsed_ms':(time.perf_counter()-start)*1000})
   return response
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='error'))
  thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
  for _ in range(1000):
   if server.started:break
   time.sleep(.01)
  else:raise RuntimeError('Synthetic API startup deadline')
  base=temp/'native';base.mkdir(mode=0o700);env=os.environ.copy();env['TWICHUI_SUMMARY_TEST_TOKEN']=token
  if os.name=='nt':
   sid=subprocess.check_output(['powershell','-NoProfile','-Command','[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True).strip()
   # Reset Python's explicit mode=0700 Windows ACEs before applying the same
   # private fixture ACL used by archive acceptance. Removing inheritance alone
   # leaves explicit ACEs in place; production ownership checks must stay strict.
   subprocess.run(['icacls',str(base),'/reset'],check=True,capture_output=True)
   subprocess.run(['icacls',str(base),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'],check=True,capture_output=True)
  game=base/'not-a-game';publication=base/'publication'
  if a.publish:
   env['MARKET_TEST_APP_DATA']=str(base)
   fixture=json.loads(subprocess.check_output(['powershell','-NoProfile','-File',str(ROOT/'scripts/windows/workshop-fixtures.ps1'),'-Action','Setup'],env=env,text=True))
   game=Path(fixture['first']);publication=game/'Interface/AddOns'
  if a.history and not a.publish:
   cap=game/'Interface/AddOns/TwichUI_Workshop/MarketDelivery.json';cap.parent.mkdir(parents=True);shutil.copyfile(a.addon_root/'TwichUI_Workshop/MarketDelivery.json',cap)
  start=time.perf_counter();calls=[]
  try:
   for _ in range(150):
    result=subprocess.run([str(a.rust_client.resolve()),f'http://127.0.0.1:{port}',str(account),str(mid),str(base),str(game),'publish'if a.publish else'stage'],env=env,capture_output=True,text=True,timeout=90)
    if result.returncode:raise RuntimeError('Native summary acceptance failed: '+result.stderr[:2000])
    info=json.loads(result.stdout);calls.append(info)
    if info['ready']:break
    time.sleep(.05) # Fixture driver only; installed acceptance tests the real schedule.
   else:raise RuntimeError('Bounded source preparation did not complete')
   assert not(base/'history-archive-v1.sqlite').exists()
   if a.publish:
    assert info['status']['summary_records']==a.variants
    raw=(publication/'TwichUI_MarketData/Data.lua').read_text();assert raw.startswith('TwichUIMarketData = { summary_version = 1')
   else:assert info['manifest']['record_count']==a.variants
   original=info
   before_hash=hashlib.sha256((publication/'TwichUI_MarketData/Data.lua').read_bytes()).hexdigest()
   before_mtime=(publication/'TwichUI_MarketData/Data.lua').stat().st_mtime_ns
   warm=subprocess.run([str(a.rust_client.resolve()),f'http://127.0.0.1:{port}',str(account),str(mid),str(base),str(game),'publish'if a.publish else'stage'],env=env,capture_output=True,text=True,timeout=90)
   if warm.returncode:raise RuntimeError('Native no-change verification failed: '+warm.stderr[:2000])
   info=json.loads(warm.stdout);calls.append(info);assert info['ready']
   if a.publish:
    assert info['status']['download_requests']==1 and info['status']['download_bytes']==0
    assert (publication/'TwichUI_MarketData/Data.lua').stat().st_mtime_ns==before_mtime
    assert hashlib.sha256((publication/'TwichUI_MarketData/Data.lua').read_bytes()).hexdigest()==before_hash
   else:assert info['requests']==1 and info['download_bytes']==0 and info['manifest']==original['manifest']
   destination=a.out/'publication';destination.mkdir(exist_ok=True)
   for folder in publication.iterdir():
    if folder.name=='TwichUI_MarketData' or folder.name.startswith('TwichUI_MarketPart'):shutil.copytree(folder,destination/folder.name)
   lua_env=os.environ.copy();lua_env.update(WORKSHOP_SUMMARY_ARTIFACT=str(destination.resolve()/'TwichUI_MarketData/Data.lua'),WORKSHOP_SUMMARY_PARTS=str(destination.resolve()),WORKSHOP_SUMMARY_EXPECTED_ITEM='10000')
   if a.lua_cpath:lua_env['LUA_CPATH']=a.lua_cpath
   lua=None
   if not a.skip_lua:
    lua=subprocess.run([a.lua,'-e','require("bit"); ROOT="../!!!TwichUI/"; REPO="../"; TESTS="./"','test_workshop_auction_market_summary.lua'],cwd=a.addon_root/'tests',env=lua_env,text=True,capture_output=True,timeout=300)
    (a.out/'production-lua.log').write_text(lua.stdout+lua.stderr)
    if lua.returncode:raise RuntimeError('Production Workshop Market consumer failed; see production-lua.log')
   assert any(r['path'].endswith('/summary')and r['status']==200 for r in requests)
   assert not any('/archive' in r['path'] for r in requests)
   paths=['backend/market/workshop_summary.py','backend/market/bridge_api.py','desktop/core/src/workshop_summary.rs','desktop/core/src/client.rs','contracts/workshop-summary/v1/manifest.schema.json','contracts/workshop-summary/v1/row.schema.json']
   report={'credential_kind':'companion','synthetic':True,'real_game':False,'platform':platform.platform(),'mode':'actual Windows publication'if a.publish else'Linux native staging; not installed Windows acceptance','variants':a.variants,'native_calls':calls,'http_requests':requests,'total_seconds':time.perf_counter()-start,'mandatory_archive':False,'no_change_http_304':True,'no_change_game_mtime_preserved':True if a.publish else None,'production_lua_market_passed':lua is not None and lua.returncode==0,'native_binary_sha256':hashlib.sha256(a.rust_client.read_bytes()).hexdigest(),'source_sha256':{q:hashlib.sha256((ROOT/q).read_bytes()).hexdigest()for q in paths},'game_consumption':'pending actual Forever'}
   (a.out/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
   print(json.dumps({'synthetic':True,'variants':a.variants,'native_calls':len(calls),'http_requests':len(requests),'seconds':report['total_seconds'],'production_lua_market_passed':report['production_lua_market_passed'],'mode':report['mode']}))
  finally:
   server.should_exit=True;thread.join(timeout=10);sock.close();engine.dispose()
if __name__=='__main__':main()
