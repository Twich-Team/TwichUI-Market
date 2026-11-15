"""Start a disposable real FastAPI fixture and run the native HTTP companion smoke test."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
TOKEN='synthetic-http-fixture-device-token-not-for-deployment'
SEED='''
import json
from datetime import timedelta
from market.db import Base,engine,Session,now
from market.models import Credential,Market,User
from market.ingest import ingest
from market.security import digest,hasher
assert engine.url.database.endswith('companion-fixture.db')
Base.metadata.create_all(engine)
with Session.begin() as db:
    user=User(username='fixture',password_hash=hasher.hash('synthetic fixture password'),role='member')
    db.add(user)
    db.flush()
    db.add(Credential(user_id=user.id,token_hash=digest(__import__('os').environ['MARKET_TEST_TOKEN']),kind='device',name='HTTP fixture',expires_at=now()+timedelta(days=1)))
    market=Market(region='eu',ruleset_id=2,house_id=113,source_kind='auctions',label='Synthetic HTTP fixture')
    db.add(market)
    db.flush()
    ingest(db,market.id,json.dumps({'auctions':[{'id':item,'item':{'id':item},'quantity':10,'buyout':1000} for item in [12363,13463]]}).encode(),request_key='http-fixture',synthetic=True)
'''


def main():
    binary=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'desktop'/'target'/'debug'/'examples'/('http_smoke.exe' if os.name=='nt' else 'http_smoke')
    with tempfile.TemporaryDirectory(prefix='twichui-companion-') as temporary:
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT/'backend')
        env['DATABASE_URL']='sqlite:///'+str(Path(temporary)/'companion-fixture.db').replace('\\','/')
        env['COOKIE_SECURE']='false'
        env['SYNC_CURSOR_SECRET']='synthetic-integration-signing-secret-32-characters'
        env['MARKET_TEST_TOKEN']=TOKEN
        env['MARKET_TEST_EXPORT_RECORD']=str(Path(temporary)/'export.json')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0))
            port=probe.getsockname()[1]
        env['MARKET_TEST_SERVER']=f'http://127.0.0.1:{port}'
        subprocess.run([sys.executable,'-c',SEED],cwd=ROOT,env=env,check=True)
        with (Path(temporary)/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','uvicorn','market.app:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(100):
                    try:
                        with urllib.request.urlopen(env['MARKET_TEST_SERVER']+'/api/v1/health',timeout=1) as response:
                            if response.status==200: break
                    except OSError:
                        time.sleep(.1)
                else:
                    raise RuntimeError('Fixture API did not become healthy')
                command=['node',str(ROOT/'web'/'e2e'/'companion-native.cjs')] if '--ui' in sys.argv else [str(binary.resolve())]
                subprocess.run(command,cwd=ROOT,env=env,check=True)
                import json
                from jsonschema import Draft202012Validator,FormatChecker
                from referencing import Registry,Resource
                schemas=[json.loads(path.read_text()) for path in (ROOT/'contracts'/'v1').glob('*.schema.json')]
                registry=Registry().with_resources((s['$id'],Resource.from_contents(s)) for s in schemas)
                checker=FormatChecker()
                checker.checks('copper-i64')(lambda value:value is None or (isinstance(value,str) and value.isascii() and value.isdigit() and int(value)<=2**63-1))
                schema=next(s for s in schemas if s['$id']=='urn:twichui-market:addon-export:v1')
                Draft202012Validator(schema,registry=registry,format_checker=checker).validate(json.loads(Path(env['MARKET_TEST_EXPORT_RECORD']).read_text()))
                print('Actual native export validates against shared data-only schema v1.')
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__=='__main__':
    main()
