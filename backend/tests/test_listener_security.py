from sqlalchemy import select
from market import environment as settings
from market.models import Credential


def test_cookie_names_and_origin_bound_sessions(client,monkeypatch):
    monkeypatch.setattr(settings,'SESSION_ORIGIN','https://localhost:18444')
    monkeypatch.setattr(settings,'SESSION_COOKIE_NAME','market_preview_session')
    result=client.post('/api/v1/auth/login',json={'username':'owner','password':'correct horse battery'})
    assert result.status_code==200 and 'market_preview_session=' in result.headers['set-cookie']
    assert client.get('/api/v1/auth/me').status_code==200
    monkeypatch.setattr(settings,'SESSION_ORIGIN','https://market.twich.gg')
    assert client.get('/api/v1/auth/me').status_code==401


def test_legacy_sessions_are_local_opt_in(owner,database,monkeypatch):
    with database.begin() as db:
        row=db.scalar(select(Credential).where(Credential.kind=='session'));row.audience=None
    assert owner.get('/api/v1/auth/me').status_code==401
    monkeypatch.setattr(settings,'ALLOW_LEGACY_SESSIONS',True)
    assert owner.get('/api/v1/auth/me').status_code==200


def test_preview_blocks_operational_mutations_but_allows_auth(owner,monkeypatch):
    monkeypatch.setattr(settings,'READ_ONLY',True)
    assert owner.get('/api/v1/environment').json()['read_only']
    assert owner.get('/api/v1/admin/users').status_code==200
    for method,path,body in [('POST','/api/v1/devices',{'name':'blocked'}),('POST','/api/v1/admin/invitations',{}),('PATCH','/api/v1/admin/users/1',{'role':'member','active':False}),('POST','/api/v1/markets/1/item-metadata-requests',{'item_ids':[25]})]:
        response=owner.request(method,path,json=body);assert response.status_code==403 and 'read-only' in response.text
    assert owner.post('/api/v1/auth/logout').status_code==204


def test_proxy_metadata_requires_exact_private_token(client,database,monkeypatch):
    monkeypatch.setattr(settings,'INGRESS_TOKEN','fixture-secret-'+'x'*40)
    assert client.get('/api/v1/auth/me',headers={'X-Forwarded-For':'1.2.3.4','X-Forwarded-Proto':'https'}).status_code==403
    assert client.get('/api/v1/auth/me',headers={'X-Market-Proxy-Token':'wrong','X-Market-Client-IP':'1.2.3.4'}).status_code==403
    headers={'X-Market-Proxy-Token':settings.INGRESS_TOKEN,'X-Market-Client-IP':'1.2.3.4'}
    assert client.post('/api/v1/auth/login',headers=headers,json={'username':'owner','password':'correct horse battery'}).status_code==200
    assert client.get('/api/v1/auth/me',headers=headers).status_code==200
    from market.models import LoginAttempt
    from market.security import digest
    with database() as db:
        assert db.get(LoginAttempt,digest('1.2.3.4:owner')) is not None
    redirect=client.get('/api/v1/markets/',headers={**headers,'Host':'market.twich.gg'},follow_redirects=False)
    assert redirect.status_code==307 and redirect.headers['location']=='https://market.twich.gg/api/v1/markets'
    headers['X-Market-Client-IP']='not an ip'
    assert client.get('/api/v1/auth/me',headers=headers).status_code==400


def test_device_access_survives_browser_origin_change(owner,monkeypatch):
    token=owner.post('/api/v1/devices',json={'name':'fixture'}).json()['token']
    monkeypatch.setattr(settings,'SESSION_ORIGIN','https://market.twich.gg')
    assert owner.get('/api/v1/markets',headers={'Authorization':'Bearer '+token}).status_code==200
    assert owner.get('/api/v1/admin/users',headers={'Authorization':'Bearer '+token}).status_code==403
