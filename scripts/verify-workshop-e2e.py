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
 p.add_argument('--current',action='store_true',help='Explicit split-projection paired-addon acceptance; no live service')
 p.add_argument('--prepared',type=int,choices=[16,32],help='Opt-in actual prepared publication with the pinned Stage C addon')
 p.add_argument('--fixture-as-of',help='Shared UTC source instant for matched synthetic 16/32 publications; never changes client time/admission')
 p.add_argument('--private-publisher',type=Path,help='Windows CI only: also verify the isolated DEV offline publisher and private endpoint adapter')
 p.add_argument('--test-driver',action='store_true',help='Linux only: --rust-client is the cfg(test) native publisher executable')
 p.add_argument('--legacy-native',action='store_true',help='Windows compatibility: pinned old native binary with the new prepared-capable addon')
 p.add_argument('--legacy-native-source-root',type=Path,help='Exact frozen source built into the legacy compatibility binary')
 p.add_argument('--ordinary-admission',action='store_true',help='Fabricated records with ordinary admission flags, for legacy Pricing acceptance')
 p.add_argument('--days',type=int,choices=[2,60],default=2)
 a=p.parse_args()
 if a.legacy_native and not a.legacy_native_source_root:p.error('--legacy-native requires exact --legacy-native-source-root')
 if a.legacy_native and not(a.publish and a.current and not a.prepared):p.error('--legacy-native requires Windows --publish --current and no prepared layout')
 if a.ordinary_admission and not(a.publish or a.test_driver):p.error('ordinary admission requires the actual or cfg(test) publisher')
 if a.prepared and not a.current:p.error('--prepared requires --current')
 if a.prepared and not(a.publish or a.test_driver):p.error('--prepared requires the actual Windows publisher or Unix cfg(test) publisher')
 if a.test_driver and (os.name=='nt' or a.publish):p.error('Unix ignored-test driver only; Windows uses actual publication')
 if a.current and a.history:p.error('choose one negotiated projection contract')
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
  if a.fixture_as_of:
   at=datetime.fromisoformat(a.fixture_as_of.replace('Z','+00:00'))
   if at.utcoffset()!=timedelta(0) or not timedelta(0)<=datetime.now(timezone.utc)-at<=timedelta(hours=1):
    p.error('Shared synthetic source instant must be UTC and within the past hour')
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
   for day in range(a.days-1,0,-1):
    ingest(db,mid,book(100,True),request_key=f'summary-e2e-previous-{day}',retrieved_at=at-timedelta(days=day),synthetic=not bool(a.prepared or a.legacy_native or a.ordinary_admission))
   ingest(db,mid,book(120),request_key='summary-e2e-current',retrieved_at=at,synthetic=not bool(a.prepared or a.legacy_native or a.ordinary_admission))
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
  base=temp/'prepared-fixture-native';base.mkdir(mode=0o700);env=os.environ.copy();env['TWICHUI_SUMMARY_TEST_TOKEN']=token
  if os.name=='nt':
   sid=subprocess.check_output(['powershell','-NoProfile','-Command','[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True).strip()
   # Reset Python's explicit mode=0700 Windows ACEs before applying the same
   # private fixture ACL used by archive acceptance. Removing inheritance alone
   # leaves explicit ACEs in place; production ownership checks must stay strict.
   subprocess.run(['icacls',str(base),'/reset'],check=True,capture_output=True)
   subprocess.run(['icacls',str(base),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'],check=True,capture_output=True)
  game=base/'not-a-game';publication=base/'publication'
  if a.test_driver:
   from prepared_fixture_driver import installation,run as native_driver
   game=installation(base,a.addon_root,a.prepared);publication=game/'Interface/AddOns'
   driver_config=dict(server=f'http://127.0.0.1:{port}',account_id=account,market_id=mid)
  if a.publish:
   env['MARKET_TEST_APP_DATA']=str(base)
   fixture=json.loads(subprocess.check_output(['powershell','-NoProfile','-File',str(ROOT/'scripts/windows/workshop-fixtures.ps1'),'-Action','Setup','-AddonRoot',str(a.addon_root.resolve())],env=env,text=True))
   game=Path(fixture['first']);publication=game/'Interface/AddOns'
  if (a.history or a.current) and not a.publish and not a.test_driver:
   cap=game/'Interface/AddOns/TwichUI_Workshop/MarketDelivery.json';cap.parent.mkdir(parents=True);shutil.copyfile(a.addon_root/'TwichUI_Workshop/MarketDelivery.json',cap)
   if a.current and json.loads(cap.read_text(encoding='utf-8-sig')).get('summary_current_contract')!=3:raise RuntimeError('paired addon must explicitly support contract 3')
  if a.prepared and a.publish:
   cap=game/'Interface/AddOns/TwichUI_Workshop/MarketDelivery.json';value=json.loads(cap.read_text(encoding='utf-8-sig'));value['prepared_current_partitions']=a.prepared;cap.write_text(json.dumps(value))
  start=time.perf_counter();calls=[]
  try:
   for _ in range(150):
    if a.test_driver:
     info=native_driver(a.rust_client,base,driver_config,{'TWICHUI_SUMMARY_TEST_TOKEN':token});calls.append(info)
     if info['ready']:break
     time.sleep(.05);continue
    result=subprocess.run([str(a.rust_client.resolve()),f'http://127.0.0.1:{port}',str(account),str(mid),str(base),str(game),'publish'if a.publish else'stage'],env=env,capture_output=True,text=True,timeout=90)
    if result.returncode:raise RuntimeError('Native summary acceptance failed: '+result.stderr[:2000])
    info=json.loads(result.stdout);calls.append(info)
    if info['ready']:break
    time.sleep(.05) # Fixture driver only; installed acceptance tests the real schedule.
   else:raise RuntimeError('Bounded source preparation did not complete')
   assert not(base/'history-archive-v1.sqlite').exists()
   if a.publish:
    assert info['status']['summary_records']==a.variants
    raw=(publication/'TwichUI_MarketData/Data.lua').read_text();assert raw.startswith('TwichUIMarketData = { summary_version = '+('2'if a.prepared else'1'))
   else:
    assert info['manifest']['record_count']==a.variants
    if a.current:assert info['manifest']['contract_version']==3
   if a.current:
    assert json.loads((game/'Interface/AddOns/TwichUI_Workshop/MarketDelivery.json').read_text(encoding='utf-8-sig'))['summary_current_contract']==3
    assert any(p.name.startswith('TwichUI_MarketHistoryPart')for p in publication.iterdir()),'paired history was not published'
   original=info
   before_hash=hashlib.sha256((publication/'TwichUI_MarketData/Data.lua').read_bytes()).hexdigest()
   before_mtime=(publication/'TwichUI_MarketData/Data.lua').stat().st_mtime_ns
   if a.test_driver:
    info=native_driver(a.rust_client,base,driver_config,{'TWICHUI_SUMMARY_TEST_TOKEN':token});calls.append(info)
    assert info['ready']and info['requests']==1 and info['download_bytes']==0 and not info['changed']
    assert (publication/'TwichUI_MarketData/Data.lua').stat().st_mtime_ns==before_mtime
    assert hashlib.sha256((publication/'TwichUI_MarketData/Data.lua').read_bytes()).hexdigest()==before_hash
   else:
    warm=subprocess.run([str(a.rust_client.resolve()),f'http://127.0.0.1:{port}',str(account),str(mid),str(base),str(game),'publish'if a.publish else'stage'],env=env,capture_output=True,text=True,timeout=90)
    if warm.returncode:raise RuntimeError('Native no-change verification failed: '+warm.stderr[:2000])
    info=json.loads(warm.stdout);calls.append(info);assert info['ready']
    if a.publish:
     assert info['status']['download_requests']==1 and info['status']['download_bytes']==0
     assert (publication/'TwichUI_MarketData/Data.lua').stat().st_mtime_ns==before_mtime
     assert hashlib.sha256((publication/'TwichUI_MarketData/Data.lua').read_bytes()).hexdigest()==before_hash
    else:assert info['requests']==1 and info['download_bytes']==0 and info['manifest']==original['manifest']
   if a.private_publisher:
    assert a.publish and a.prepared, 'private helper requires the actual Windows prepared fixture'
    from private_native_tools_fixture import verify
    (a.out/'private-tools.json').write_text(json.dumps(verify(base,game,a.prepared,a.private_publisher),indent=2)+'\n')
   destination=a.out/'publication';destination.mkdir(exist_ok=True)
   for folder in publication.iterdir():
    if folder.name=='TwichUI_MarketData' or folder.name.startswith(('TwichUI_MarketPart','TwichUI_MarketHistoryPart','TwichUI_MarketCurrentPart')):shutil.copytree(folder,destination/folder.name)
   lua_env=os.environ.copy();lua_env.update(WORKSHOP_SUMMARY_ARTIFACT=str(destination.resolve()/'TwichUI_MarketData/Data.lua'),WORKSHOP_SUMMARY_PARTS=str(destination.resolve()),WORKSHOP_SUMMARY_EXPECTED_ITEM='10000')
   if a.lua_cpath:lua_env['LUA_CPATH']=a.lua_cpath
   lua=None
   if not a.skip_lua:
    prepared_consumer=bool(a.prepared or a.legacy_native or a.ordinary_admission)
    lua_test='test_workshop_prepared_artifact.lua'if prepared_consumer else 'bench_workshop_summary.lua'if a.current else'test_workshop_auction_market_summary.lua'
    if prepared_consumer:lua_env['WORKSHOP_PREPARED_EXPECTED_LAYOUT']=str(a.prepared or 0)
    lua=subprocess.run([a.lua,'-e','require("bit"); ROOT="../!!!TwichUI/"; REPO="../"; TESTS="./"',
        str(ROOT/'scripts'/lua_test)if prepared_consumer else lua_test],cwd=a.addon_root/'tests',env=lua_env,text=True,capture_output=True,timeout=300)
    (a.out/'production-lua.log').write_text(lua.stdout+lua.stderr)
    if lua.returncode:raise RuntimeError('Production Workshop Market consumer failed; see production-lua.log')
   assert any(r['path'].endswith('/summary')and r['status']==200 for r in requests)
   assert not any('/archive' in r['path'] for r in requests)
   paths=['backend/market/workshop_summary.py','backend/market/bridge_api.py','desktop/core/src/workshop_summary.rs','desktop/core/src/client.rs','contracts/workshop-summary/v1/manifest.schema.json','contracts/workshop-summary/v1/row.schema.json','contracts/workshop-summary/v2/manifest.schema.json','contracts/workshop-summary/v2/row.schema.json','contracts/workshop-summary/v2/addon-source.txt']
   report={'credential_kind':'companion','synthetic':True,'real_game':False,'platform':platform.platform(),'mode':'actual Windows publication'if a.publish else'Unix cfg(test) executable identity; production publisher'if a.test_driver else'Linux native staging; not installed Windows acceptance','variants':a.variants,'native_calls':calls,'http_requests':requests,'total_seconds':time.perf_counter()-start,'mandatory_archive':False,'no_change_http_304':True,'no_change_game_mtime_preserved':True if a.publish else None,'production_lua_market_passed':lua is not None and lua.returncode==0,'native_binary_sha256':hashlib.sha256(a.rust_client.read_bytes()).hexdigest(),'source_sha256':{q:hashlib.sha256((ROOT/q).read_bytes()).hexdigest()for q in paths},'game_consumption':'pending actual Forever','paired_addon_commit':(ROOT/'contracts/workshop-summary/v2/addon-source.txt').read_text().strip(),'addon_source_sha256':{q:hashlib.sha256((a.addon_root/q).read_bytes()).hexdigest()for q in ['TwichUI_Workshop/Summary.lua','TwichUI_Workshop/SummarySchema.lua','TwichUI_Workshop/BridgeCodec.lua','TwichUI_Workshop/Bridge.lua','TwichUI_Workshop/auction/ViewMarket.lua','tests/test_workshop_auction_market_summary.lua']}}
   report['declared_addon_commit']=(ROOT/('contracts/workshop-summary/v3/addon-source.txt'if a.current else'contracts/workshop-summary/v2/addon-source.txt')).read_text().strip()
   if (a.addon_root/'.git').exists():
    report['paired_addon_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.addon_root,text=True).strip()
    report['paired_addon_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=a.addon_root,text=True))
   if a.current:
    report['negotiated_contract']=3
    report['paired_addon_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.addon_root,text=True).strip()
    report['paired_addon_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=a.addon_root,text=True))
    pin='contracts/workshop-summary/v3/addon-source.txt'
    if a.prepared or a.legacy_native or a.ordinary_admission:
     pin='contracts/workshop-prepared/v1/addon-source.txt'
     assert report['paired_addon_commit']==(ROOT/pin).read_text().strip(),'prepared acceptance must use the declared exact addon'
    else:assert report['paired_addon_commit']==(ROOT/pin).read_text().strip(),'current acceptance must use the declared merged addon'
    assert not report['paired_addon_dirty'],'current acceptance requires an unchanged addon checkout'
    for q in [pin,'contracts/workshop-summary/v3/manifest.schema.json','contracts/workshop-summary/v3/row.schema.json','desktop/core/examples/workshop_smoke.rs']:
     report['source_sha256'][q]=hashlib.sha256((ROOT/q).read_bytes()).hexdigest()
    for q in ['TwichUI_Workshop/Pricing.lua','TwichUI_Workshop/Estimate.lua','TwichUI_Workshop/OpportunityEngine.lua','TwichUI_Workshop/Session.lua','TwichUI_Workshop/MarketDelivery.json']:
     report['addon_source_sha256'][q]=hashlib.sha256((a.addon_root/q).read_bytes()).hexdigest()
   if a.prepared:
    assert any(r['path'].endswith('/prepared/1/'+str(a.prepared))and r['status']==200 for r in requests),'missing real authoritative metadata request'
    assert len(list(destination.glob('TwichUI_MarketCurrentPart*')))==a.prepared
    if a.test_driver:assert (game/'WTF/Account/SyntheticOnly/SavedVariables/TwichUI.lua').read_bytes()==b'unchanged synthetic player data'
    report['declared_addon_commit']=(ROOT/'contracts/workshop-prepared/v1/addon-source.txt').read_text().strip()
    report['no_change_game_mtime_preserved']=True
    report.update(prepared_layout=a.prepared,history_days=a.days,ordinary_admission_flags_on_fabricated_data=True,production_publisher=True)
    for q in ['backend/market/workshop_prepared.py','desktop/core/src/workshop_prepared.rs','scripts/prepared_fixture_driver.py','scripts/test_workshop_prepared_artifact.lua']:
     report['source_sha256'][q]=hashlib.sha256((ROOT/q).read_bytes()).hexdigest()
    for q in ['TwichUI_Workshop/Prepared.lua','tests/fixtures/workshop_prepared_v1/synthetic.json']:
     report['addon_source_sha256'][q]=hashlib.sha256((a.addon_root/q).read_bytes()).hexdigest()
   if a.legacy_native:
    legacy=a.legacy_native_source_root.resolve();revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=legacy,text=True).strip()
    assert revision=='e2882dd822b356ffa081efebbff167827f9bf364'and not subprocess.check_output(['git','status','--porcelain'],cwd=legacy,text=True),'legacy source must be exact and unchanged'
    report['legacy_native_source_commit']=revision
    report['legacy_native_source_sha256']={q:hashlib.sha256((legacy/q).read_bytes()).hexdigest()for q in ['desktop/core/src/workshop_summary.rs','desktop/core/src/client.rs','desktop/core/src/installation.rs','desktop/core/Cargo.toml','desktop/Cargo.lock','desktop/core/examples/workshop_smoke.rs']}
   if a.legacy_native or a.ordinary_admission:
    assert not any('/prepared/'in r['path']for r in requests),'legacy compatibility unexpectedly negotiated prepared format'
    assert not list(destination.glob('TwichUI_MarketCurrentPart*'))
    report.update(legacy_native_with_new_addon=a.legacy_native,ordinary_admission_flags_on_fabricated_data=True,prepared_layout=None)
    report['declared_addon_commit']=(ROOT/'contracts/workshop-prepared/v1/addon-source.txt').read_text().strip()
   (a.out/'evidence.json').write_text(json.dumps(report,indent=2)+'\n')
   print(json.dumps({'synthetic':True,'variants':a.variants,'native_calls':len(calls),'http_requests':len(requests),'seconds':report['total_seconds'],'production_lua_market_passed':report['production_lua_market_passed'],'mode':report['mode']}))
  finally:
   server.should_exit=True;thread.join(timeout=10);sock.close();engine.dispose()
if __name__=='__main__':main()
