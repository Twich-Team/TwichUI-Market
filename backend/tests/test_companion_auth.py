"""Native approvals/credentials use isolated synthetic accounts and market_test only."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
import secrets
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select

from market.app import app
from market import companion_auth, environment
from market.db import now
from market.ingest import ingest
from market.models import CompanionAuthorization, CompanionDevice, Credential, Market, User
from market.security import hasher
from test_market_configuration import verified_player_mapping

BASE = '/api/v1/companion'


@pytest.fixture(autouse=True)
def signing(monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET', 'synthetic-native-authorization-key-over-32-characters')


def start(client, **changes):
    verifier = secrets.token_urlsafe(48)
    body = {'client_id': companion_auth.CLIENT_ID, 'redirect_uri': 'http://127.0.0.1:43123/companion/callback',
        'state': secrets.token_urlsafe(32), 'code_challenge_method': 'S256',
        'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),
        'device_name': 'Synthetic Windows PC', 'platform': 'Windows', 'app_version': '2.0.0-beta.1', **changes}
    return body, verifier, client.post(BASE+'/authorizations', json=body)


def approve(client, started, decision='approve'):
    ident = started.json()['request_id']
    details = client.get(BASE+'/authorizations/'+ident)
    assert details.status_code == 200, details.text
    result = client.post(BASE+'/authorizations/'+ident+'/decision', json={
        'decision': decision, 'consent_token': details.json()['consent_token']})
    assert result.status_code == 200, result.text
    return result


def exchange(client, body, verifier, approved, **changes):
    query = parse_qs(urlsplit(approved.json()['redirect_uri']).query)
    form = {'client_id': companion_auth.CLIENT_ID, 'grant_type': 'authorization_code', 'code': query['code'][0],
        'code_verifier': verifier, 'redirect_uri': body['redirect_uri'], 'state': body['state'], **changes}
    return client.post(BASE+'/token', data=form)


def authorize(client):
    body, verifier, started = start(client)
    assert started.status_code == 201, started.text
    approved = approve(client, started)
    response = exchange(client, body, verifier, approved)
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens): return {'Authorization': 'Bearer '+tokens['access_token']}
def refresh_form(tokens, nonce=None): return {'client_id': companion_auth.CLIENT_ID, 'grant_type': 'refresh_token',
    'refresh_token': tokens['refresh_token'], 'rotation_nonce': nonce or secrets.token_urlsafe(32)}


def seed_market(database):
    with database.begin() as db:
        market = Market(id=2, region='us', ruleset_id=2, house_id=114, source_kind='auctions', label='Synthetic only',
            enabled=True, verified=True, last_success=now(), last_modified='Sat, 14 Nov 2026 12:00:00 GMT')
        db.add(market);db.flush()
        verified_player_mapping(db, 114, 'Horde')
        ingest(db, market.id, json.dumps({'auctions':[
            {'id':i, 'item':{'id':i}, 'quantity':1, 'buyout':100} for i in (25,35)]}).encode(),
            request_key='synthetic-native-data', synthetic=True, modified=market.last_modified)


def test_full_approval_bootstrap_and_server_confirmed_sync(owner, database):
    seed_market(database)
    assert owner.patch('/api/v1/me/preferences', json={'schema_version':1,'expected_revision':0,
        'changes':{'market_id':2,'explorer_days':60}}).status_code == 200
    old_session = owner.get('/api/v1/auth/session').json()
    tokens = authorize(owner)
    assert tokens['token_type'] == 'Bearer' and 3500 <= tokens['expires_in'] <= 3600
    assert tokens['access_token'] != tokens['refresh_token']
    boot = owner.get(BASE+'/bootstrap', headers=bearer(tokens))
    assert boot.status_code == 200, boot.text
    data = boot.json();assert data['account']['id'] == 1
    assert data['suggested_market_id'] == data['preferred_market_id'] == 2
    assert data['markets'][0]['label'] == 'US — Normal — Horde'
    assert data['markets'][0]['source']['synthetic'] is True
    assert data['markets'][0]['source']['upstream_updated_at'] == '2026-11-14T12:00:00+00:00'
    assert owner.get('/api/v1/auth/session').json() == old_session
    first = owner.get('/api/v1/sync/markets/2?limit=1', headers=bearer(tokens)).json()
    assert first['has_more'] and first['synthetic']
    profiles = owner.get(BASE+'/devices').json()['devices']
    assert profiles[0]['last_sync_at'] is None
    final = owner.get('/api/v1/sync/markets/2', params={'cursor':first['cursor']}, headers=bearer(tokens)).json()
    assert final['has_more'] is False
    profiles = owner.get(BASE+'/devices').json()['devices']
    assert profiles[0]['last_sync_at'] is not None
    metadata = owner.get(BASE+'/markets/2/observations/'+final['target_observation_id'], headers=bearer(tokens)).json()
    assert metadata['generation'] and metadata['synthetic'] is True
    assert owner.post(BASE+'/activity', headers=bearer(tokens), json={'market_id':2,'app_version':'2.0.0','last_sync_at':'made up'}).status_code == 422
    assert owner.post(BASE+'/activity', headers=bearer(tokens), json={'market_id':2,'app_version':'2.0.0'}).status_code == 204
    assert owner.post(BASE+'/activity', headers=bearer(tokens), json={'market_id':2,'app_version':'<script>'}).status_code == 422
    serialized = json.dumps(owner.get(BASE+'/devices').json())
    assert tokens['access_token'] not in serialized and tokens['refresh_token'] not in serialized
    assert 'refresh_hash' not in serialized and 'token_hash' not in serialized
    with database() as db:
        device = db.get(CompanionDevice, tokens['device']['id'])
        assert device.refresh_hash != tokens['refresh_token']
        credential = db.get(Credential, device.access_credential_id)
        assert credential.token_hash != tokens['access_token']
        assert credential.kind == 'companion'  # Old APIs reject this kind rather than broadening its scope.
        assert db.get(Market,2).enabled


@pytest.mark.parametrize('uri',[
    'https://127.0.0.1:43123/companion/callback','http://localhost:43123/companion/callback',
    'http://[::1]:43123/companion/callback','http://127.0.0.1.evil.test:43123/companion/callback',
    'http://evil@127.0.0.1:43123/companion/callback','http://127.0.0.1:80/companion/callback',
    'http://127.0.0.1:0/companion/callback','http://127.0.0.1:65536/companion/callback',
    'http://127.0.0.1:043123/companion/callback','http://127.0.0.1:43123/other',
    'http://127.0.0.1:43123/companion/callback?extra=1','http://127.0.0.1:43123/companion/callback#fragment',
    'http://127.0.0.1:43123/companion/%63allback'])
def test_redirects_are_exact_loopback_only(owner, database, uri):
    assert start(owner, redirect_uri=uri)[2].status_code == 422
    with database() as db:assert db.scalar(select(func.count()).select_from(CompanionAuthorization)) == 0


@pytest.mark.parametrize('changes',[{'client_id':'other'},{'code_challenge_method':'plain'},
    {'state':'short'},{'code_challenge':'bad'},{'device_name':'bad\nname'},
    {'app_version':'bad version'},{'platform':'Untrusted'},{'user_id':99},{'scope':'administrator'}])
def test_strict_native_request_fields(owner, changes):
    assert start(owner, **changes)[2].status_code == 422


def test_codes_are_one_use_and_pkce_state_redirect_cannot_be_substituted(owner, database):
    body, verifier, started = start(owner);approved = approve(owner, started)
    rejected = exchange(owner, body, 'x'*43, approved)
    assert rejected.status_code == 400 and rejected.json()['error'] == 'invalid_grant'
    assert rejected.headers['cache-control'] == 'no-store'
    assert body['state'] not in rejected.text and verifier not in rejected.text
    assert exchange(owner, body, verifier, approved, state='y'*43).status_code == 400
    assert exchange(owner, body, verifier, approved, redirect_uri='http://127.0.0.1:43124/companion/callback').status_code == 400
    valid = exchange(owner, body, verifier, approved);assert valid.status_code == 200, valid.text
    assert exchange(owner, body, verifier, approved).status_code == 400
    with database() as db:assert db.scalar(select(func.count()).select_from(CompanionDevice)) == 1


def test_five_wrong_verifiers_lock_a_code_even_if_correct_proof_arrives_later(owner, database):
    body, verifier, started = start(owner);approved = approve(owner, started)
    for _ in range(5):assert exchange(owner, body, 'x'*43, approved).status_code == 400
    assert exchange(owner, body, verifier, approved).status_code == 400
    with database() as db:assert db.scalar(select(func.count()).select_from(CompanionDevice)) == 0


def test_denial_and_expiration_never_issue_a_credential(owner, database, monkeypatch):
    body, verifier, started = start(owner);denied = approve(owner, started, 'deny')
    query = parse_qs(urlsplit(denied.json()['redirect_uri']).query)
    assert query == {'error':['access_denied'],'state':[body['state']]}
    assert owner.post(BASE+'/authorizations/'+started.json()['request_id']+'/decision', json={'decision':'approve','consent_token':'a'*64}).status_code == 409
    body, verifier, started = start(owner);approved = approve(owner, started)
    stamp = now();monkeypatch.setattr(companion_auth,'now',lambda:stamp+timedelta(seconds=61))
    assert exchange(owner, body, verifier, approved).status_code == 400
    monkeypatch.setattr(companion_auth,'now',lambda:stamp+timedelta(minutes=6))
    assert owner.get(BASE+'/authorizations/'+started.json()['request_id']).status_code == 410
    with database() as db:assert db.scalar(select(func.count()).select_from(CompanionDevice)) == 0


def member_client(database):
    with database.begin() as db:
        member = User(username='native_member',password_hash=hasher.hash('synthetic member password'),role='member')
        db.add(member)
    client = TestClient(app);session = client.post('/api/v1/auth/login',json={'username':'native_member','password':'synthetic member password'}).json()
    client.headers['x-csrf-token'] = session['csrf_token']
    return client


def test_consent_is_bound_to_account_and_session_and_devices_are_owned(owner, database):
    body, verifier, started = start(owner);ident = started.json()['request_id']
    screen = owner.get(BASE+'/authorizations/'+ident).json()
    with member_client(database) as other:
        assert other.post(BASE+'/authorizations/'+ident+'/decision',json={'decision':'approve','consent_token':screen['consent_token']}).status_code == 403
        approved = approve(owner, started)
        assert other.get(BASE+'/authorizations/'+ident).status_code == 404
        tokens = exchange(owner, body, verifier, approved).json();device_id = tokens['device']['id']
        assert other.get(BASE+'/devices').json()['devices'] == []
        assert other.patch(BASE+f'/devices/{device_id}',json={'name':'stolen'}).status_code == 404
        assert other.delete(BASE+f'/devices/{device_id}').status_code == 404
        assert other.get(BASE+'/admin/devices').status_code == 403
    assert owner.patch(BASE+f'/devices/{device_id}',json={'name':'My PC'}).json()['name'] == 'My PC'
    assert owner.delete(BASE+f'/devices/{device_id}').status_code == 204
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 401
    assert owner.post(BASE+'/token',data=refresh_form(tokens)).status_code == 400


def test_native_scope_does_not_inherit_administrator_browser_permissions(owner):
    tokens = authorize(owner)
    for path in ['/api/v1/admin/users','/api/v1/devices','/api/v1/me/preferences','/api/v1/auth/session',BASE+'/devices',BASE+'/admin/devices']:
        assert owner.get(path,headers=bearer(tokens)).status_code == 403,path
    assert owner.post('/api/v1/devices',headers=bearer(tokens),json={'name':'not allowed'}).status_code == 403
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 200
    assert owner.get(BASE+'/bootstrap',headers=bearer(tokens)).status_code == 200
    assert owner.post(BASE+'/devices/self/revoke',headers=bearer(tokens)).status_code == 204
    assert owner.get(BASE+'/bootstrap',headers=bearer(tokens)).status_code == 401


def test_csrf_origin_size_form_and_rate_limits(owner, database):
    body, verifier, started = start(owner);ident = started.json()['request_id'];screen = owner.get(BASE+'/authorizations/'+ident).json()
    assert owner.post(BASE+'/authorizations/'+ident+'/decision',headers={'x-csrf-token':''},json={'decision':'approve','consent_token':screen['consent_token']}).status_code == 403
    assert owner.post(BASE+'/authorizations/'+ident+'/decision',headers={'origin':'https://wrong.test'},json={'decision':'approve','consent_token':screen['consent_token']}).status_code == 403
    assert owner.post(BASE+'/authorizations',content=iter([b'x'*4096,b'x'*4097])).status_code == 413
    assert owner.post(BASE+'/token',json={}).status_code == 415
    assert owner.post(BASE+'/token',content='grant_type=refresh_token&client_id=x&client_id=y',headers={'content-type':'application/x-www-form-urlencoded'}).status_code == 400
    for _ in range(9):assert start(owner)[2].status_code == 201
    assert start(owner)[2].status_code == 429


def test_refresh_rotates_and_recovers_identical_pending_operation_without_affecting_legacy(owner, database):
    legacy = owner.post('/api/v1/devices',json={'name':'existing client'}).json()
    tokens = authorize(owner);form = refresh_form(tokens)
    first = owner.post(BASE+'/token',data=form);assert first.status_code == 200,first.text
    renewed = first.json();retry = owner.post(BASE+'/token',data=form)
    assert retry.status_code == 200 and retry.json()['access_token'] == renewed['access_token']
    assert retry.json()['refresh_token'] == renewed['refresh_token']
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 401
    assert owner.get('/api/v1/auth/me',headers=bearer(renewed)).status_code == 200
    assert owner.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+legacy['token']}).status_code == 200
    assert owner.get('/api/v1/auth/session').status_code == 200
    assert owner.post(BASE+'/token',data={**form,'rotation_nonce':secrets.token_urlsafe(32)}).status_code == 400
    assert owner.get('/api/v1/auth/me',headers=bearer(renewed)).status_code == 401
    with database() as db:assert db.get(CompanionDevice,tokens['device']['id']).revoked


def test_replay_of_an_older_refresh_generation_revokes_the_entire_family(owner):
    original = authorize(owner)
    second = owner.post(BASE+'/token',data=refresh_form(original)).json()
    third = owner.post(BASE+'/token',data=refresh_form(second)).json()
    assert owner.get('/api/v1/auth/me',headers=bearer(third)).status_code == 200
    assert owner.post(BASE+'/token',data=refresh_form(original)).status_code == 400
    assert owner.get('/api/v1/auth/me',headers=bearer(third)).status_code == 401


@pytest.mark.parametrize('expired',['access','refresh','authorization'])
def test_expiration_and_access_renewal(owner, database, expired):
    tokens = authorize(owner)
    with database.begin() as db:
        device = db.get(CompanionDevice,tokens['device']['id'])
        if expired == 'access':db.get(Credential,device.access_credential_id).expires_at = now()-timedelta(seconds=1)
        elif expired == 'refresh':device.refresh_expires_at = now()-timedelta(seconds=1)
        else:device.expires_at = now()-timedelta(seconds=1)
    renewed = owner.post(BASE+'/token',data=refresh_form(tokens))
    assert renewed.status_code == (200 if expired == 'access' else 400)
    if expired == 'access':assert owner.get('/api/v1/auth/me',headers=bearer(renewed.json())).status_code == 200


def test_password_change_revokes_refresh_as_well_as_access(owner):
    tokens = authorize(owner)
    assert owner.post('/api/v1/auth/password',json={'current_password':'correct horse battery','new_password':'new synthetic password'}).status_code == 204
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 401
    assert owner.post(BASE+'/token',data=refresh_form(tokens)).status_code == 400


def test_an_approved_code_cannot_outlive_the_authorizing_session(owner):
    body, verifier, started = start(owner);approved = approve(owner, started)
    assert owner.post('/api/v1/auth/logout').status_code == 204
    assert exchange(owner, body, verifier, approved).status_code == 400


def test_native_authorizations_and_tokens_are_bound_to_their_issuer_origin(owner, monkeypatch):
    body, verifier, started = start(owner);approved = approve(owner, started)
    tokens = authorize(owner)
    monkeypatch.setattr(environment,'SESSION_ORIGIN','https://other-listener.test')
    assert exchange(owner, body, verifier, approved).status_code == 400
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 401
    assert owner.post(BASE+'/token',data=refresh_form(tokens)).status_code == 400


def test_preview_only_allows_own_pairing_not_administrative_changes(owner, monkeypatch):
    monkeypatch.setattr(environment,'READ_ONLY',True)
    tokens = authorize(owner)
    assert owner.post('/api/v1/devices',json={'name':'forbidden'}).status_code == 403
    assert owner.delete(BASE+'/admin/devices/'+str(tokens['device']['id'])).status_code == 403
    assert owner.delete(BASE+'/devices/'+str(tokens['device']['id'])).status_code == 204


def test_postgresql_concurrent_refresh_same_nonce_is_one_rotation_with_recoverable_response(owner, database):
    with database() as db:
        if db.bind.dialect.name != 'postgresql':pytest.skip('PostgreSQL row-lock test')
    original = authorize(owner);form = refresh_form(original)
    def refresh(_):
        with TestClient(app) as client:return client.post(BASE+'/token',data=form)
    with ThreadPoolExecutor(max_workers=2) as pool:responses = list(pool.map(refresh,[1,2]))
    assert [r.status_code for r in responses] == [200,200]
    assert responses[0].json()['refresh_token'] == responses[1].json()['refresh_token']
    with database() as db:
        device = db.get(CompanionDevice,original['device']['id'])
        assert device.generation == 1
        assert db.scalar(select(func.count()).select_from(Credential).where(Credential.companion_device_id==device.id,Credential.revoked.is_(False))) == 1


def test_postgresql_concurrent_code_exchange_cannot_issue_two_devices(owner, database):
    with database() as db:
        if db.bind.dialect.name != 'postgresql':pytest.skip('PostgreSQL row-lock test')
    body, verifier, started = start(owner);approved = approve(owner, started)
    def consume(_):
        with TestClient(app) as client:return exchange(client, body, verifier, approved).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:statuses = list(pool.map(consume,[1,2]))
    assert sorted(statuses) == [200,400]
    with database() as db:assert db.scalar(select(func.count()).select_from(CompanionDevice)) == 1


def test_concurrent_distinct_refresh_operations_detect_reuse_and_revoke(owner, database):
    with database() as db:
        if db.bind.dialect.name != 'postgresql':pytest.skip('PostgreSQL row-lock test')
    original = authorize(owner)
    forms = [refresh_form(original),refresh_form(original)]
    def renew(form):
        with TestClient(app) as client:return client.post(BASE+'/token',data=form)
    with ThreadPoolExecutor(max_workers=2) as pool:responses = list(pool.map(renew,forms))
    assert sorted(r.status_code for r in responses) == [200,400]
    successful = next(r.json() for r in responses if r.status_code==200)
    assert owner.get('/api/v1/auth/me',headers=bearer(successful)).status_code == 401


def test_consent_screen_cannot_be_reused_in_another_session_even_for_the_same_account(owner):
    body, verifier, started = start(owner);ident = started.json()['request_id']
    screen = owner.get(BASE+'/authorizations/'+ident).json()
    with TestClient(app) as other:
        login = other.post('/api/v1/auth/login',json={'username':'owner','password':'correct horse battery'}).json()
        other.headers['x-csrf-token'] = login['csrf_token']
        assert other.post(BASE+'/authorizations/'+ident+'/decision',json={'decision':'approve','consent_token':screen['consent_token']}).status_code == 403
        approved = approve(other, started)
    assert exchange(owner,body,verifier,approved).status_code == 200


def test_deactivation_and_owner_revocation_cannot_leave_refresh_access_active(owner, database):
    with member_client(database) as member:
        tokens = authorize(member);member_id = member.get('/api/v1/auth/me').json()['id']
    assert owner.patch(f'/api/v1/admin/users/{member_id}',json={'role':'member','active':False}).status_code == 200
    assert owner.patch(f'/api/v1/admin/users/{member_id}',json={'role':'member','active':True}).status_code == 200
    assert owner.post(BASE+'/token',data=refresh_form(tokens)).status_code == 400
    own = authorize(owner)
    assert owner.delete(BASE+'/devices/'+str(own['device']['id'])).status_code == 204
    assert owner.post(BASE+'/token',data=refresh_form(own)).status_code == 400


def test_refresh_retry_grace_is_bounded_and_old_issuer_cannot_revoke_a_family(owner, monkeypatch):
    original = authorize(owner);form = refresh_form(original)
    renewed = owner.post(BASE+'/token',data=form).json()
    stamp = now();monkeypatch.setattr(companion_auth,'now',lambda:stamp+timedelta(minutes=6))
    assert owner.post(BASE+'/token',data=form).status_code == 400
    assert owner.get('/api/v1/auth/me',headers=bearer(renewed)).status_code == 401
    # New independent grant; an older token presented to a different issuer is rejected without mutating it.
    monkeypatch.setattr(companion_auth,'now',now)
    original = authorize(owner);second = owner.post(BASE+'/token',data=refresh_form(original)).json()
    third = owner.post(BASE+'/token',data=refresh_form(second)).json()
    monkeypatch.setattr(environment,'SESSION_ORIGIN','https://other.test')
    assert owner.post(BASE+'/token',data=refresh_form(original)).status_code == 400
    monkeypatch.setattr(environment,'SESSION_ORIGIN',third['issuer'])
    assert owner.get('/api/v1/auth/me',headers=bearer(third)).status_code == 200


def test_missing_server_key_or_duplicate_transaction_state_fails_without_a_partial_grant(owner, database, monkeypatch):
    body, verifier, started = start(owner)
    assert owner.post(BASE+'/authorizations',json=body).status_code == 400
    monkeypatch.delenv('SYNC_CURSOR_SECRET')
    unavailable = start(owner)[2]
    assert unavailable.status_code == 503 and 'SYNC_CURSOR_SECRET' not in unavailable.text
    with database() as db:
        assert db.scalar(select(func.count()).select_from(CompanionAuthorization)) == 1
        assert db.scalar(select(func.count()).select_from(CompanionDevice)) == 0


def test_explicitly_accepted_legacy_browser_sessions_can_approve_without_reset(owner, database, monkeypatch):
    monkeypatch.setattr(environment,'ALLOW_LEGACY_SESSIONS',True)
    with database.begin() as db:
        credential = db.scalar(select(Credential).where(Credential.kind=='session',Credential.user_id==1))
        credential.audience = None
    tokens = authorize(owner)
    assert owner.get('/api/v1/auth/session').status_code == 200
    assert owner.get('/api/v1/auth/me',headers=bearer(tokens)).status_code == 200


def test_bootstrap_fallback_never_rewrites_the_saved_website_market(owner, database):
    seed_market(database)
    with database.begin() as db:
        db.add(Market(id=1,region='us',ruleset_id=2,house_id=110,source_kind='auctions',label='Historical synthetic',verified=True,enabled=False))
    assert owner.patch('/api/v1/me/preferences',json={'schema_version':1,'expected_revision':0,'changes':{'market_id':1,'explorer_days':365}}).status_code == 200
    tokens = authorize(owner)
    boot = owner.get(BASE+'/bootstrap',headers=bearer(tokens)).json()
    assert boot['preferred_market_id'] == 1 and boot['suggested_market_id'] == 2 and boot['preference_fallback']
    assert 'explorer_days' not in json.dumps(boot)
    with database.begin() as db:db.get(Market,2).enabled = False
    unavailable = owner.get(BASE+'/bootstrap',headers=bearer(tokens)).json()
    assert unavailable['suggested_market_id'] is None
    assert owner.get('/api/v1/me/preferences').json()['values']['market_id'] == 1


def test_legacy_device_rename_remains_owned_browser_only_and_backward_compatible(owner, database):
    legacy = owner.post('/api/v1/devices',json={'name':'Old PC'}).json();ident=legacy['id']
    renamed = owner.patch(f'/api/v1/devices/{ident}',json={'name':'Renamed PC'})
    assert renamed.status_code == 200 and renamed.json()['name'] == 'Renamed PC'
    assert owner.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+legacy['token']}).status_code == 200
    assert owner.patch(f'/api/v1/devices/{ident}',headers={'Authorization':'Bearer '+legacy['token']},json={'name':'no'}).status_code == 403
    with member_client(database) as other:
        assert other.patch(f'/api/v1/devices/{ident}',json={'name':'stolen'}).status_code == 404
    assert owner.patch(f'/api/v1/devices/{ident}',json={'name':'PC','user_id':99}).status_code == 422
