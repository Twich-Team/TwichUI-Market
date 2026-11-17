"""Archive safety and reconciled counts, isolated market_test only."""
import pytest
from datetime import timedelta
from sqlalchemy import select, func
from market.db import now
from market.models import User, Credential, CompanionDevice, SecurityEvent, UserPreference
from market.security import hasher, issue
from test_companion_auth import authorize, bearer, refresh_form


@pytest.fixture(autouse=True)
def signing(monkeypatch):
    monkeypatch.setenv('SYNC_CURSOR_SECRET', 'synthetic-usability-signing-key-over-32-characters')


def test_summary_counts_logical_devices_not_rotated_tokens(owner, database):
    tokens = authorize(owner)
    with database.begin() as db:
        device = db.get(CompanionDevice, tokens['device']['id'])
        device.last_connection_at = now()
        account = db.get(User, 1)
        for expired, revoked in [(False, False), (True, False), (False, True)]:
            _, _, row = issue(db, account, 'device', 'Legacy fixture')
            row.expires_at = now() + timedelta(days=-1 if expired else 1)
            row.revoked = revoked
        # A superseded access credential belongs to the same logical PC.
        db.add(Credential(user_id=1, kind='companion', name='Old access', token_hash='a'*64,
                          companion_device_id=device.id, expires_at=now()+timedelta(hours=1), revoked=True))
    result = owner.get('/api/v1/companion/admin/device-summary')
    assert result.status_code == 200, result.text
    data = result.json()
    assert (data['authorized'], data['revoked'], data['expired'], data['recently_connected']) == (2, 1, 1, 1)
    assert data['currently_connected'] is None and data['companion']['authorized'] == 1
    assert data['authorized_names'] == ['Synthetic Windows PC']


def test_device_archive_requires_revocation_confirmation_ownership_and_retains_evidence(owner, database):
    tokens = authorize(owner)
    ident = tokens['device']['id']
    base = f'/api/v1/companion/devices/{ident}'
    assert owner.post(base+'/archive', json={'confirmation':'Synthetic Windows PC'}).status_code == 409
    assert owner.delete(base).status_code == 204
    assert owner.get('/api/v1/companion/bootstrap', headers=bearer(tokens)).status_code == 401
    assert owner.post('/api/v1/companion/token', data=refresh_form(tokens)).status_code == 400
    assert owner.post(base+'/archive', json={'confirmation':'wrong'}).status_code == 409
    assert owner.post(base+'/archive', json={'confirmation':'Synthetic Windows PC'}).status_code == 200
    assert owner.get('/api/v1/companion/devices').json()['devices'] == []
    assert owner.get('/api/v1/companion/devices?include_archived=true').json()['devices'][0]['archived_at']
    with database() as db:
        assert db.get(CompanionDevice, ident).revoked
        assert db.scalar(select(func.count()).select_from(Credential).where(Credential.companion_device_id == ident)) > 0
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.action == 'companion.device.archived'))
    assert owner.post(base+'/restore').json()['revoked']
    with database.begin() as db:
        other = User(username="other", password_hash="unusable", role="member")
        db.add(other); db.flush()
        db.get(CompanionDevice, ident).user_id = other.id
    assert owner.post(base+'/archive', json={'confirmation':'Synthetic Windows PC'}).status_code == 404


def test_member_archive_reversible_revokes_access_and_preserves_owned_records(owner, database):
    with database.begin() as db:
        target = User(username='obsolete_fixture', role='member', password_hash=hasher.hash('synthetic member password'))
        db.add(target); db.flush(); ident = target.id
        _, _, credential = issue(db, target, 'session')
        db.add(UserPreference(user_id=ident, values_json='{}'))
        db.add(SecurityEvent(actor_id=ident, action='synthetic.security.evidence'))
    base = f'/api/v1/admin/users/{ident}'
    assert owner.post(base+'/archive', json={'confirmation':'wrong'}).status_code == 409
    assert owner.post(base+'/archive', json={'confirmation':'obsolete_fixture'}).status_code == 200
    assert len(owner.get('/api/v1/admin/users').json()) == 1
    assert len(owner.get('/api/v1/admin/users?include_archived=true').json()) == 2
    assert owner.patch(base, json={'role':'member','active':True}).status_code == 409
    with database() as db:
        assert not db.get(User, ident).active
        assert db.get(Credential, credential.id).revoked
        assert db.get(UserPreference, ident)
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.actor_id == ident))
    assert owner.post(base+'/restore').json()['active'] is False
    assert len(owner.get('/api/v1/admin/users').json()) == 2
    assert owner.post('/api/v1/admin/users/1/archive', json={'confirmation':'owner'}).status_code == 409
    assert owner.patch('/api/v1/admin/users/1', json={'role':'admin','active':False}).status_code == 409


def test_archive_requires_admin_browser_and_csrf(owner, database):
    tokens = authorize(owner)
    assert owner.post('/api/v1/admin/users/1/archive', headers=bearer(tokens), json={'confirmation':'owner'}).status_code == 403
    owner.headers.pop('x-csrf-token')
    assert owner.post('/api/v1/admin/users/1/archive', json={'confirmation':'owner'}).status_code == 403


@pytest.mark.parametrize('operation', ['archive', 'update'])
@pytest.mark.parametrize('lost_access', ['disabled', 'demoted'])
def test_cached_administrator_cannot_remove_last_admin_after_concurrent_access_change(database, operation, lost_access):
    from fastapi import HTTPException
    from market.app import archive_member, update_user, ArchiveMember, UserUpdate
    with database.begin() as seed:
        target=User(username='remaining-admin', password_hash='fixture', role='admin')
        seed.add(target);seed.flush();target_id=target.id
    with database() as pending:
        actor=pending.get(User,1)
        pending.get(User,target_id)
        # Simulate a request authenticated before another committed transaction.
        # FOR UPDATE alone does not refresh an existing SQLAlchemy identity.
        with database.begin() as concurrent:
            changed=concurrent.get(User,1)
            if lost_access=='disabled':changed.active=False
            else:changed.role='member'
        with pytest.raises(HTTPException) as error:
            if operation=='archive':archive_member(target_id,ArchiveMember(confirmation='remaining-admin'),actor,pending)
            else:update_user(target_id,UserUpdate(role='member',active=False),actor,pending)
        assert error.value.status_code==403
        pending.rollback()
    with database() as check:
        retained=check.get(User,target_id)
        assert retained.active and retained.role=='admin' and retained.archived_at is None
