from datetime import timedelta
from sqlalchemy import select
from market.db import now
from market.models import Credential, Invitation, User


def test_private_and_health(client):
    assert client.get('/api/v1/health').json()['status'] == 'ok'
    for path in ('/api/v1/auth/me', '/api/v1/admin/users', '/api/v1/devices'):
        assert client.get(path).status_code == 401


def test_invitation_lifecycle_and_permissions(owner):
    token = owner.post('/api/v1/admin/invitations').json()['token']
    body = {'username': 'friend', 'password': 'friend password long', 'invitation': token}
    assert owner.post('/api/v1/auth/register', json=body).status_code == 201
    assert owner.post('/api/v1/auth/register', json={**body, 'username': 'friend2'}).status_code == 400
    result = owner.post('/api/v1/auth/login', json={'username': 'friend', 'password': body['password']})
    owner.headers['x-csrf-token'] = result.json()['csrf_token']
    assert owner.get('/api/v1/auth/me').json()['role'] == 'member'
    assert owner.get('/api/v1/admin/users').status_code == 403
    assert owner.post('/api/v1/admin/invitations').status_code == 403


def test_csrf_origin_logout_and_cookie(owner):
    saved = owner.headers.pop('x-csrf-token')
    assert owner.post('/api/v1/admin/invitations').status_code == 403
    owner.headers['x-csrf-token'] = saved
    assert owner.post('/api/v1/admin/invitations', headers={'origin': 'https://evil.test'}).status_code == 403
    assert owner.post('/api/v1/auth/logout').status_code == 204
    assert owner.get('/api/v1/auth/me').status_code == 401


def test_device_tokens_hashed_scoped_revocable(owner, database):
    result = owner.post('/api/v1/devices', json={'name': 'Windows laptop'})
    assert result.status_code == 201
    device = result.json()
    with database() as db:
        assert db.get(Credential, device['id']).token_hash != device['token']
    headers = {'authorization': f"Bearer {device['token']}"}
    assert owner.get('/api/v1/auth/me', headers=headers).status_code == 200
    assert owner.post('/api/v1/devices', json={'name': 'nested'}, headers=headers).status_code == 403
    assert owner.delete(f"/api/v1/devices/{device['id']}").status_code == 204
    assert owner.get('/api/v1/auth/me', headers=headers).status_code == 401


def test_expired_disabled_and_login_throttle(owner, database):
    device = owner.post('/api/v1/devices', json={'name': 'old'}).json()
    with database.begin() as db:
        db.get(Credential, device['id']).expires_at = now() - timedelta(seconds=1)
    assert owner.get('/api/v1/auth/me', headers={'authorization': f"Bearer {device['token']}"}).status_code == 401
    for _ in range(10):
        assert owner.post('/api/v1/auth/login', json={'username': 'nobody', 'password': 'incorrect password'}).status_code == 401
    assert owner.post('/api/v1/auth/login', json={'username': 'nobody', 'password': 'incorrect password'}).status_code == 429
    with database.begin() as db:
        db.scalar(select(User).where(User.username == 'owner')).active = False
    assert owner.get('/api/v1/auth/me').status_code == 401


def test_duplicate_registration_does_not_consume_invite(owner):
    token = owner.post('/api/v1/admin/invitations').json()['token']
    body = {'username': 'owner', 'password': 'another long password', 'invitation': token}
    assert owner.post('/api/v1/auth/register', json=body).status_code == 409
    assert owner.post('/api/v1/auth/register', json={**body, 'username': 'newfriend'}).status_code == 201


def test_admin_management_preserves_owner(owner):
    assert owner.patch('/api/v1/admin/users/1', json={'role': 'member', 'active': True}).status_code == 409
    token = owner.post('/api/v1/admin/invitations').json()['token']
    friend = owner.post('/api/v1/auth/register', json={
        'username': 'friend', 'password': 'friend password long', 'invitation': token}).json()
    assert owner.patch(f"/api/v1/admin/users/{friend['id']}", json={'role': 'admin', 'active': True}).status_code == 200
    assert owner.patch('/api/v1/admin/users/1', json={'role': 'member', 'active': True}).status_code == 200
    assert owner.get('/api/v1/admin/users').status_code == 403


def test_browser_reload_recovers_csrf_and_password_revokes_all_credentials(owner):
    device=owner.post('/api/v1/devices',json={'name':'test'}).json()
    owner.headers.pop('x-csrf-token')
    session=owner.get('/api/v1/auth/session').json()
    owner.headers['x-csrf-token']=session['csrf_token']
    assert owner.post('/api/v1/admin/invitations').status_code==201
    assert owner.post('/api/v1/auth/password',json={'current_password':'wrong old password','new_password':'new correct password'}).status_code==403
    assert owner.post('/api/v1/auth/password',json={'current_password':'correct horse battery','new_password':'new correct password'}).status_code==204
    assert owner.get('/api/v1/auth/me').status_code==401
    assert owner.get('/api/v1/auth/me',headers={'authorization':f"Bearer {device['token']}"}).status_code==401
    assert owner.post('/api/v1/auth/login',json={'username':'owner','password':'new correct password'}).status_code==200


def test_invitation_revocation_and_admin_device_listing(owner):
    invitation=owner.post('/api/v1/admin/invitations').json()
    rows=owner.get('/api/v1/admin/invitations').json()
    assert 'token_hash' not in rows[0]
    assert owner.delete(f"/api/v1/admin/invitations/{rows[0]['id']}").status_code==204
    assert owner.post('/api/v1/auth/register',json={'username':'friend','password':'friend password long','invitation':invitation['token']}).status_code==400
    owner.post('/api/v1/devices',json={'name':'fixture'})
    assert owner.get('/api/v1/admin/devices').json()[0]['name']=='fixture'
