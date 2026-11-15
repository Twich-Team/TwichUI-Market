"""Verify local TLS, secure authentication and administration without logging secrets."""
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import ssl
import subprocess
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPSHandler,HTTPCookieProcessor,Request

ROOT=Path(__file__).resolve().parents[1]
certificate=ROOT/'artifacts'/'tls-root.crt'
certificate.parent.mkdir(exist_ok=True)
subprocess.run(['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml','cp',
                'proxy:/data/caddy/pki/authorities/local/root.crt',str(certificate)],cwd=ROOT,check=True)
credentials={}
path=ROOT/'.local'/'bootstrap.env'
if path.exists():
    credentials=dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line)
username=os.environ.get('MARKET_ADMIN_USERNAME',credentials.get('MARKET_ADMIN_USERNAME'))
password=os.environ.get('MARKET_ADMIN_PASSWORD',credentials.get('MARKET_ADMIN_PASSWORD'))
if not username or not password:
    raise SystemExit('Set administrator credentials in environment or provision the initial owner first.')
opener=build_opener(HTTPSHandler(context=ssl.create_default_context(cafile=certificate)),HTTPCookieProcessor(CookieJar()))
origin='https://localhost:18443'
def call(path,method='GET',body=None,csrf=None):
    headers={'Content-Type':'application/json','Origin':origin}
    if csrf: headers['X-CSRF-Token']=csrf
    return opener.open(Request(origin+path,data=json.dumps(body).encode() if body is not None else None,
                               method=method,headers=headers),timeout=15)
with call('/') as response:
    assert response.status==200 and "script-src 'self'" in response.headers['Content-Security-Policy']
with call('/api/v1/health') as response:
    assert json.load(response)['status']=='ok'
with call('/api/v1/auth/login','POST',{'username':username,'password':password}) as response:
    cookie=response.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=strict' in cookie
    session=json.load(response)
    assert session['user']['role']=='admin'
with call('/api/v1/auth/session') as response:
    restored=json.load(response)
    assert restored['csrf_token']==session['csrf_token']
with call('/api/v1/admin/users') as response:
    assert any(row['username']==username and row['role']=='admin' for row in json.load(response))
if os.environ.get('MARKET_TLS_SMOKE_BINARY'):
    with call('/api/v1/devices','POST',{'name':'Temporary native TLS verification'},csrf=session['csrf_token']) as response:
        device=json.load(response)
    try:
        env=os.environ.copy()
        env['MARKET_TEST_SERVER']=origin
        env['MARKET_TEST_TOKEN']=device['token']
        env.pop('SSL_CERT_FILE',None)
        env.pop('SSL_CERT_DIR',None)
        env['MARKET_EXPECT_UNTRUSTED']='true'
        subprocess.run([env['MARKET_TLS_SMOKE_BINARY']],env=env,check=True)
        env['SSL_CERT_FILE']=str(certificate)
        env['MARKET_EXPECT_UNTRUSTED']='false'
        subprocess.run([env['MARKET_TLS_SMOKE_BINARY']],env=env,check=True)
        print('Native client rejects untrusted TLS and authenticates with explicit project CA trust.')
    finally:
        with call(f"/api/v1/devices/{device['id']}",'DELETE',csrf=session['csrf_token']) as response:
            assert response.status==204
with call('/api/v1/auth/logout','POST',csrf=session['csrf_token']) as response:
    assert response.status==204
try:
    call('/api/v1/auth/me')
except HTTPError as error:
    assert error.code==401
else:
    raise AssertionError('Logout did not invalidate the session')
print('Verified trusted localhost HTTPS, static CSP, secure cookies, owner authentication, session recovery, administrator access and logout. No host trust changes made.')
