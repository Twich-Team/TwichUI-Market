"""Cross-platform native price sync comparison on an isolated synthetic market.

Runs identical inputs through baseline/current native binaries, including a
separately labelled injected request delay. Never accepts a remote API or DB.
"""
import argparse,asyncio,hashlib,json,os,platform,socket,subprocess,sys,tempfile,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--variants',type=int,default=26342);p.add_argument('--runs',type=int,default=3);p.add_argument('--delay-ms',type=int,default=0)
a=p.parse_args();assert 1<=a.runs<=3 and 0<=a.delay_ms<=100
with tempfile.TemporaryDirectory(prefix='sync-performance-',dir=os.environ.get('RUNNER_TEMP')) as directory:
    temp=Path(directory);os.environ.update(DATABASE_URL='sqlite:///'+str(temp/'market_test.sqlite'),APP_ORIGIN='https://synthetic-performance.invalid',SYNC_CURSOR_SECRET='synthetic-price-performance-secret-over32',BRIDGE_CONTRACT_ROOT=str(ROOT/'contracts/bridge/v1'),SYNC_PERFORMANCE_DIAGNOSTICS='true')
    sys.path.insert(0,str(ROOT/'backend'))
    from market.app import app
    from sync_performance_fixture import Fixture
    import uvicorn
    fixture=Fixture(a.variants)
    @app.middleware('http')
    async def injected_latency(request,call_next):
        if a.delay_ms:await asyncio.sleep(a.delay_ms/1000)
        return await call_next(request)
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='error'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);thread.start()
    for _ in range(1000):
        if server.started:break
        time.sleep(.01)
    else:raise RuntimeError('Fixture startup deadline')
    results=[]
    try:
        for label,binary,limit in [('baseline',a.baseline,50),('candidate',a.candidate,100)]:
            for repeat in range(a.runs):
                fixture.reset();cache=temp/f'{label}-{repeat}.sqlite'
                for scenario in ['full','unchanged','incremental','unchanged_advance']:
                    if scenario=='incremental':fixture.publish(1)
                    if scenario=='unchanged_advance':fixture.publish(1,fixture.at+__import__('datetime').timedelta(seconds=2))
                    env=dict(os.environ,SYNC_PERF_SERVER=f'http://127.0.0.1:{port}',SYNC_PERF_TOKEN=fixture.token,SYNC_PERF_CACHE=str(cache),SYNC_PERF_LIMIT=str(limit))
                    proc=subprocess.run([str(binary.resolve())],env=env,text=True,capture_output=True,timeout=240)
                    if proc.returncode:raise RuntimeError('Native sync fixture failed: '+proc.stderr[:1000])
                    row=json.loads(proc.stdout);row.update(label=label,repeat=repeat,scenario=scenario);results.append(row)
                    print(json.dumps({k:row[k] for k in ['label','repeat','scenario','seconds','item_count']}),flush=True)
        for scenario in ['full','unchanged','incremental','unchanged_advance']:
            hashes={r['cache_values_sha256'] for r in results if r['scenario']==scenario};assert len(hashes)==1,'Different exact cache values'
        a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({'synthetic':True,'production':False,'platform':platform.platform(),'database':'disposable SQLite market_test','variants':a.variants,'commodity_variants':(a.variants+19)//20,'injected_delay_ms':a.delay_ms,'clock_note':'Injected latency is simulated; process-lifetime peak RSS is not per-run incremental allocation','binary_sha256':{label:hashlib.sha256(b.read_bytes()).hexdigest() for label,b in [('baseline',a.baseline),('candidate',a.candidate)]},'runs':results},indent=2)+'\n')
    finally:server.should_exit=True;thread.join(timeout=10)
