"""Separate archive/automatic-Workshop baseline comparison on synthetic unified data.

The automatic path uses the real price synchronizer, delivery dispatcher, durable
stores and publisher, including actual server-directed preparation retry waits. Windows
uses versioned synthetic PE plus the pinned addon fixture, never a real game.
"""
import argparse,hashlib,json,os,platform,socket,subprocess,sys,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--runs',type=int,default=3);p.add_argument('--variants',type=int,default=26342);p.add_argument('--mode',choices=['archive','auto'],required=True)
a=p.parse_args();assert 1<=a.runs<=3
with tempfile.TemporaryDirectory(prefix='delivery-performance-',dir=os.environ.get('RUNNER_TEMP')) as directory:
 temp=Path(directory);os.environ.update(DATABASE_URL='sqlite:///'+str(temp/'market_test.sqlite'),APP_ORIGIN='https://synthetic-performance.invalid',SYNC_CURSOR_SECRET='synthetic-delivery-performance-secret-over32',BRIDGE_CONTRACT_ROOT=str(ROOT/'contracts/bridge/v1'))
 sys.path.insert(0,str(ROOT/'backend'))
 from market.app import app
 from market.db import Session
 from market.models import BridgeGeneration,BridgeRecord,BridgeDerivation,BridgeDerivedRecord,ArchiveCheckpoint,ArchiveMember,ArchiveDigest
 from sync_performance_fixture import Fixture
 from sqlalchemy import delete,event
 import uvicorn
 requests=[];in_flight={};sql_count=[0];phase={"baseline":False}
 from market.db import engine
 @event.listens_for(engine,'before_cursor_execute')
 def count_sql(*_):sql_count[0]+=1
 @app.middleware('http')
 async def measure(request,call_next):
  path=request.url.path
  started=time.perf_counter();cpu=time.process_time();key=id(request)
  in_flight[key]={'operation': 'workshop' if '/workshop/' in path else 'other', 'started':started}
  try:response=await call_next(request)
  except Exception as error:
   requests.append({'operation':in_flight[key]['operation'],'exception_type':type(error).__name__,'server_ms':1000*(time.perf_counter()-started)})
   raise
  finally:in_flight.pop(key,None)
  if phase['baseline'] and response.status_code==202 and '/workshop/' in path:response.headers['Retry-After']='5'
  kind=('archive_pages' if '/archive/' in path and path.endswith('/pages') else 'archive_checkpoint' if '/archive/' in path else 'workshop_parts' if '/parts/' in path else 'workshop_summary' if '/workshop/' in path else 'prices' if '/sync/' in path else 'bootstrap' if path.endswith('/bootstrap') else 'activity' if path.endswith('/activity') else 'provenance')
  requests.append({'operation':kind,'status':response.status_code,'body_bytes':int(response.headers.get('content-length',0)),'server_ms':1000*(time.perf_counter()-started),'server_process_cpu_ms':1000*(time.process_time()-cpu),'retry_after':response.headers.get('retry-after')})
  return response
 fixture=Fixture(a.variants);fixture.publish(1)
 from market import archive_api,bridge_api
 at=fixture.at+__import__("datetime").timedelta(seconds=3)
 archive_api.now=lambda:at;bridge_api.now=lambda:at
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='error'));thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
 for _ in range(1000):
  if server.started:break
  time.sleep(.01)
 else:raise RuntimeError('Fixture startup deadline')
 results=[]
 try:
  for label,binary in [('baseline',a.baseline),('candidate',a.candidate)]:
   for repeat in range(a.runs):
    phase['baseline']=label=='baseline'
    # Disposable export caches only, in the asserted market_test fixture.
    with Session.begin() as db:
     for model in [BridgeRecord,BridgeGeneration,ArchiveMember,ArchiveCheckpoint,ArchiveDigest,BridgeDerivedRecord,BridgeDerivation]:db.execute(delete(model))
    base=temp/f'{label}-{repeat}';base.mkdir(mode=0o700);game=base/'Forever';env=dict(os.environ,SYNC_PERF_TOKEN=fixture.token)
    if os.name=='nt':
     sid=subprocess.check_output(['powershell','-NoProfile','-Command','[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True).strip()
     subprocess.run(['icacls',str(base),'/reset'],check=True,capture_output=True)
     subprocess.run(['icacls',str(base),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F','*S-1-5-32-544:(OI)(CI)F'],check=True,capture_output=True)
     if a.mode=='auto':
      env['MARKET_TEST_APP_DATA']=str(base)
      setup=json.loads(subprocess.check_output(['powershell','-NoProfile','-File',str(ROOT/'scripts/windows/workshop-fixtures.ps1'),'-Action','Setup'],env=env,text=True));game=Path(setup['first'])
    requests.clear();sql_count[0]=0
    proc=subprocess.run([str(binary.resolve()),f'http://127.0.0.1:{port}',str(base),str(game),a.mode],env=env,capture_output=True,text=True,timeout=900)
    if proc.returncode:
     # Retain bounded, credential-free failure evidence before TemporaryDirectory
     # removes the fixture. Do not retry or hide a failed baseline/candidate run.
     a.report.parent.mkdir(parents=True,exist_ok=True)
     failure={'synthetic':True,'production':False,'physical_game':False,'label':label,'repeat':repeat,'mode':a.mode,'exit_code':proc.returncode,'server_thread_alive':thread.is_alive(),'sql_queries':sql_count[0],'requests':list(requests),'in_flight':[{'operation':r['operation'],'elapsed_ms':1000*(time.perf_counter()-r['started'])} for r in in_flight.copy().values()]}
     a.report.with_name(a.report.stem+'-failure.json').write_text(json.dumps(failure,indent=2)+'\n')
     print(json.dumps(failure),flush=True)
     raise RuntimeError('Native delivery fixture failed: '+proc.stderr[:1000])
    result=json.loads(proc.stdout);result.update(label=label,repeat=repeat,server={'http_requests':len(requests),'sql_queries':sql_count[0],'body_bytes':sum(r['body_bytes'] for r in requests),'request_wall_ms':sum(r['server_ms'] for r in requests),'process_cpu_ms':sum(r['server_process_cpu_ms'] for r in requests),'requests':list(requests)});results.append(result);print(json.dumps({k:result[k] for k in ['label','repeat','mode','seconds','values_sha256']}),flush=True)
  assert len({r['values_sha256'] for r in results})==1,'Different exact semantic archive/Workshop values'
  a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'synthetic':True,'production':False,'physical_game':False,'platform':platform.platform(),'database':'disposable SQLite market_test','variants':a.variants,'commodity_variants':(a.variants+19)//20,'mode':a.mode,'preparation_wait_policy':'baseline fixed 5s; candidate 5s derivation/1s bounded projection; actual native sleeps','binary_sha256':{label:hashlib.sha256(b.read_bytes()).hexdigest() for label,b in [('baseline',a.baseline),('candidate',a.candidate)]},'runs':results},indent=2)+'\n')
 finally:server.should_exit=True;thread.join(timeout=10);engine.dispose()
