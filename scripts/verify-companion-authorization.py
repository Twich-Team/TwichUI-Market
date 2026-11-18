"""Real native Rust -> API -> browser consent -> loopback -> renewal/revocation smoke.

Only a newly created temporary SQLite fixture and loopback listener are used. No
production credentials, databases or browser profiles are accepted. Windows uses
real Credential Manager; Linux uses process-memory-only test storage.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SEED = '''
import json
from market.db import Base,engine,Session
from market.models import Market,User,PlayerMarketMapping
from market.db import now
from market.ingest import ingest
from market.security import hasher
assert engine.url.database.endswith('native-authorization-fixture.db')
Base.metadata.create_all(engine)
with Session.begin() as db:
    db.add(User(username='native_fixture',password_hash=hasher.hash('synthetic browser fixture password'),role='member'))
    market=Market(region='us',ruleset_id=2,house_id=114,source_kind='auctions',label='Synthetic only',verified=True,enabled=True)
    db.add(market);db.flush()
    evidence=json.dumps({'region':'us','house_id':114,'ruleset':'Normal','faction':'Horde',
        'upstream_receipt':{'synthetic':True},'independent_observation':{'synthetic_player_scan':True},'independent_source_url':'https://example.test/fixture'})
    db.add(PlayerMarketMapping(region='us',ruleset='Normal',faction='Horde',house_id=114,transport_ruleset_id=2,source_kind='auctions',
        confidence='verified',evidence=evidence,evidence_hash=__import__('hashlib').sha256(evidence.encode()).hexdigest(),verified_at=now()))
    ingest(db,market.id,json.dumps({'auctions':[{'id':i,'item':{'id':i},'quantity':10,'buyout':1000} for i in [12363,13463]]}).encode(),request_key='native-auth-fixture',synthetic=True)
'''
SERVER = '''
import uvicorn
from market import companion_auth
from market.app import app
import os, asyncio
# Short-lived access is fixture-only; force the real native renewal path immediately.
companion_auth.ACCESS_SECONDS=60
if os.environ.get('MARKET_NATIVE_UI_TEST')=='true':
    from pathlib import Path
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    website=Path('web/dist').resolve()
    if not (website/'index.html').is_file():raise RuntimeError('Build the actual website before installed UI acceptance')
    app.mount('/assets',StaticFiles(directory=website/'assets'),name='fixture_website_assets')
    @app.get('/')
    @app.get('/companion')
    @app.get('/companion/authorize')
    @app.get('/account')
    def fixture_website():
        return FileResponse(website/'index.html')
    summary_fault={'corrupt':False}
    from fastapi import Request
    from fastapi.responses import JSONResponse
    @app.post('/__fixture__/workshop-source')
    async def fixture_workshop_source(request:Request):
        from market.db import Session,now
        from market.ingest import ingest
        import json
        action=(await request.json())['action']
        if action=='advance':
            with Session.begin() as db:
                ingest(db,1,json.dumps({'auctions':[{'id':i,'item':{'id':i},'quantity':10,'buyout':1000} for i in [12363,13463]]}).encode(),request_key='summary-fixture-'+str(now().timestamp()),retrieved_at=now(),synthetic=True)
        elif action=='corrupt':summary_fault['corrupt']=True
        elif action=='normal':summary_fault['corrupt']=False
        else:raise ValueError('unknown fixture action')
        return {'synthetic':True,'action':action}
    native_network={'bearer_requests':0,'token_requests':0,'sync_requests':0}
    @app.get('/__fixture__/native-network')
    def fixture_network():
        return native_network.copy()
    @app.middleware('http')
    async def observable_fixture_pages(request,call_next):
        if request.headers.get('authorization','').startswith('Bearer '):native_network['bearer_requests']+=1
        if request.url.path=='/api/v1/companion/token':native_network['token_requests']+=1
        if request.url.path.startswith('/api/v1/sync/markets/'):
            native_network['sync_requests']+=1
            await asyncio.sleep(.5)
            query=request.scope.get('query_string',b'')
            request.scope['query_string']=query+(b'&' if query else b'')+b'limit=1'
        response=await call_next(request)
        if request.url.path.endswith('/summary') and summary_fault['corrupt'] and response.status_code in (200,304):
            # Test-only post-authorization corruption; positive source is unchanged.
            return JSONResponse({'account_id':1,'manifest':{}},headers={'Cache-Control':'no-store'})
        return response
uvicorn.run(app,host='127.0.0.1',port=int(os.environ['MARKET_TEST_PORT']),access_log=False)
'''


def main():
    binary = Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'desktop'/'target'/'debug'/'examples'/('authorization_smoke.exe' if os.name=='nt' else 'authorization_smoke')
    with tempfile.TemporaryDirectory(prefix='twichui-native-auth-') as directory:
        env=os.environ.copy()
        env.update(PYTHONPATH=str(ROOT/'backend'), DATABASE_URL='sqlite:///'+str(Path(directory)/'native-authorization-fixture.db').replace('\\','/'),
            COOKIE_SECURE='false', SYNC_CURSOR_SECRET='synthetic-native-authorization-integration-key-over-32-characters')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        origin=f'http://127.0.0.1:{port}'
        env.update(APP_ORIGIN=origin, MARKET_TEST_SERVER=origin, MARKET_TEST_PORT=str(port), ALLOW_LEGACY_SESSIONS='false')
        if '--ui' in sys.argv or '--upgrade' in sys.argv:env['MARKET_NATIVE_UI_TEST']='true'
        subprocess.run([sys.executable,'-c',SEED],cwd=ROOT,env=env,check=True)
        jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        csrf=None
        def request(path, data=None, method=None):
            headers={'Origin':origin}
            if csrf:headers['x-csrf-token']=csrf
            if data is not None:headers['Content-Type']='application/json'
            with browser.open(urllib.request.Request(origin+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers),timeout=10) as response:
                body=response.read();return json.loads(body) if body else None
        with (Path(directory)/'api.log').open('w') as log:
            api=subprocess.Popen([sys.executable,'-c',SERVER],cwd=ROOT,env=env,stdout=log,stderr=log)
            native=None
            try:
                for _ in range(100):
                    try:
                        request('/api/v1/health');break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('Isolated authorization API did not become healthy')
                if '--ui' in sys.argv or '--upgrade' in sys.argv:
                    script='companion-upgrade.cjs' if '--upgrade' in sys.argv else 'companion-native.cjs'
                    subprocess.run(['node',str(ROOT/'web'/'e2e'/script)],cwd=ROOT,env=env,check=True)
                    print('Installed v2 native UI/API authorization and background synchronization smoke passed.')
                    return
                native=subprocess.Popen([str(binary.resolve())],cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                def stage():
                    line=native.stdout.readline()
                    if not line:
                        raise RuntimeError('Synthetic native fixture stopped: '+native.stderr.read(4096))
                    return json.loads(line)
                info=stage()
                assert info['stage']=='approval'
                url=urlsplit(info['info']['authorization_url'])
                assert url.scheme=='http' and url.netloc==f'127.0.0.1:{port}' and url.path=='/companion/authorize'
                ident=parse_qs(url.query)['request'][0]
                csrf=request('/api/v1/auth/login',{'username':'native_fixture','password':'synthetic browser fixture password'})['csrf_token']
                approval=request('/api/v1/companion/authorizations/'+ident)
                assert approval['application']=='TwichUI Market Companion' and approval['status']=='pending'
                result=request('/api/v1/companion/authorizations/'+ident+'/decision',{'decision':'approve','consent_token':approval['consent_token']})
                callback=urlsplit(result['redirect_uri'])
                assert callback.scheme=='http' and callback.hostname=='127.0.0.1' and callback.path=='/companion/callback'
                assert set(parse_qs(callback.query))=={'code','state'}
                with urllib.request.urlopen(result['redirect_uri'],timeout=10) as response:
                    assert response.status==200 and response.headers['Cache-Control']=='no-store'
                synced=stage();assert synced['stage']=='synced_and_renewed'
                devices=request('/api/v1/companion/devices')['devices'];device=next(d for d in devices if d['id']==synced['device_id'])
                assert device['last_sync_at'] and device['last_connection_at'] and device['selected_market_id']==1
                request('/api/v1/companion/devices/'+str(device['id']),method='DELETE')
                native.stdin.write('revoked\n');native.stdin.flush()
                final=stage();assert final['stage']=='revocation_verified_offline_cache_preserved'
                assert native.wait(timeout=10)==0
                print('Real Rust/API PKCE approval, strict loopback, secure storage, sync, renewal, revocation and offline cache preservation passed.')
            finally:
                if native is not None and native.poll() is None:
                    native.kill();native.wait()
                if env.get('MARKET_NATIVE_UI_TEST')=='true':
                    evidence=ROOT/'artifacts/companion-v2';evidence.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(Path(directory)/'api.log',evidence/'synthetic-native-api.log')
                api.terminate()
                try:api.wait(timeout=10)
                except subprocess.TimeoutExpired:api.kill();api.wait()


if __name__=='__main__':main()
