"""Administrator browser/CSRF boundary and safe transport; disposable market_test only."""
from io import BytesIO
from unittest.mock import patch
import urllib.error
import pytest
from sqlalchemy import select
from market import backup_management as backups
from market.models import SecurityEvent, User
from market.security import hasher, issue

KEY='a'*32


def test_inventory_requires_administrator_browser(client,database):
    assert client.get('/api/v1/admin/backups').status_code==401
    with database.begin() as db:
        member=User(username='member',password_hash=hasher.hash('a synthetic password'),role='member')
        db.add(member);db.flush()
        token,_,_=issue(db,member,'session')
        device,_,_=issue(db,db.get(User,1),'device')
    client.cookies.set('market_session',token)
    assert client.get('/api/v1/admin/backups').status_code in (401,403)
    assert client.get('/api/v1/admin/backups',headers={'Authorization':'Bearer '+device}).status_code==403


def test_mutations_require_csrf_and_valid_identifier(owner):
    with patch.object(backups,'connect') as boundary:
        owner.headers.pop('x-csrf-token')
        assert owner.post(f'/api/v1/admin/backups/{KEY}/delete',json={'confirmation':'market-A.dump'}).status_code==403
        boundary.assert_not_called()
    assert owner.get('/api/v1/admin/backups/not-an-id/download').status_code==422


def test_pagination_admin_auditing_and_deletion_results(owner,database):
    calls=[]
    def boundary(actor,path,body=None,**kwargs):
        calls.append((actor,path,body))
        return {'status':'partial_failure','archive_removed':True,'manifest_removed':False,'unlinked_bytes':123}
    with patch.object(backups,'connect',side_effect=boundary):
        assert owner.get('/api/v1/admin/backups?offset=10&limit=10').status_code==200
        response=owner.post(f'/api/v1/admin/backups/{KEY}/delete',json={'confirmation':'market-A.dump'})
        assert response.json()['status']=='partial_failure'
        assert owner.post(f'/api/v1/admin/backups/{KEY}/protect',json={'protected':True}).status_code==200
        assert owner.post('/api/v1/admin/backups/create',json={}).status_code==202
    assert calls[0][1]=='/overview?offset=10&limit=10'
    assert calls[1][2]=={'confirmation':'market-A.dump'}
    with database() as db:
        actions=list(db.scalars(select(SecurityEvent.action).where(SecurityEvent.action.like('backup.%'))))
    assert 'backup.delete.requested' in actions and 'backup.delete.accepted' in actions
    assert owner.get('/api/v1/admin/backups?limit=10000').status_code==422


def test_refused_operations_are_audited(owner,database):
    from fastapi import HTTPException
    with patch.object(backups,'connect',side_effect=HTTPException(409,'Recovery point protected')):
        assert owner.post(f'/api/v1/admin/backups/{KEY}/delete',json={'confirmation':'market-A.dump'}).status_code==409
    with database() as db:
        assert db.scalar(select(SecurityEvent).where(SecurityEvent.action=='backup.delete.refused')) is not None


def test_unconfigured_management_does_not_report_fake_disk_values(owner,monkeypatch):
    monkeypatch.delenv('BACKUP_MANAGEMENT_ENABLED',raising=False)
    response=owner.get('/api/v1/admin/backups')
    assert response.status_code==503
    assert 'not installed' in response.json()['detail']
    assert 'filesystem' not in response.json()


def test_download_stream_is_bounded_and_closed(owner):
    class Archive(BytesIO):
        headers={'Content-Disposition':'attachment; filename="market-A.dump"','Content-Length':'5'}
    stream=Archive(b'PGDMP')
    with patch.object(backups,'connect',return_value=stream):
        response=owner.get(f'/api/v1/admin/backups/{KEY}/download')
    assert response.content==b'PGDMP'
    assert stream.closed
    assert response.headers['cache-control']=='no-store'
    assert response.headers['content-disposition']=='attachment; filename="market-A.dump"'


def test_download_rejects_untrusted_response_filename(owner):
    class Archive(BytesIO):
        headers={'Content-Disposition':'attachment; filename="../../etc/passwd"','Content-Length':'5'}
    stream=Archive(b'PGDMP')
    with patch.object(backups,'connect',return_value=stream):
        assert owner.get(f'/api/v1/admin/backups/{KEY}/download').status_code==503
    assert stream.closed


def test_policy_bounds_and_unknown_fields_rejected(owner):
    values=dict(enabled=False,interval_seconds=86400,daily=2,weekly=0,monthly=0,max_bytes=None,minimum_recovery_points=1,warning_free_bytes=3*1024**3)
    for key,value in [('minimum_recovery_points',0),('warning_free_bytes',1),('daily',0),('root','/etc')]:
        with patch.object(backups,'connect') as boundary:
            assert owner.post('/api/v1/admin/backups/policy',json={'revision':1,'values':{**values,key:value}}).status_code==422
            boundary.assert_not_called()


def test_transport_hides_secrets_and_refuses_redirects(tmp_path,monkeypatch):
    token=tmp_path/'token';token.write_text('x'*40)
    monkeypatch.setenv('BACKUP_MANAGEMENT_ENABLED','true');monkeypatch.setenv('BACKUP_MANAGER_TOKEN_FILE',str(token))
    from fastapi import HTTPException
    for code in (302,500,401):
        error=urllib.error.HTTPError('http://backup-manager:8091/overview',code,'secret database password',{},BytesIO(b'secret'))
        with patch('urllib.request.OpenerDirector.open',side_effect=error):
            with pytest.raises(HTTPException) as result:backups.connect(1,'/overview')
        assert result.value.status_code==503
        assert 'secret' not in result.value.detail


@pytest.mark.parametrize('path,body',[
    ('/storage/save',dict(type='smb',name='NAS',host='192.168.1.20',username='backup',password='private-test-secret',share='Backups')),
    ('/storage/test',dict(id=KEY)),('/storage/browse',dict(id=KEY,directory='Market')),
    ('/storage/mkdir',dict(id=KEY,directory='Market')),
    ('/delete-selected',dict(items=[dict(id=KEY,confirmation='market-A.dump',confirm_protected=True,confirm_recovery_loss=True)])),
    ('/storage/migrate',dict(id=KEY,preview={'token':'fixture'})),
    ('/storage/remove-originals',dict(id=KEY,confirmation='REMOVE VERIFIED ORIGINALS')),
    ('/restore-test',dict(id=KEY)),('/storage/cleanup',{})])
def test_new_admin_actions_require_browser_csrf(client,path,body):
    with patch.object(backups,'connect') as boundary:
        assert client.post('/api/v1/admin/backups'+path,json=body).status_code in (401,403)
        boundary.assert_not_called()


def test_storage_credentials_not_copied_to_security_events(owner,database):
    with patch.object(backups,'connect',return_value={'id':KEY,'password_saved':True}) as boundary:
        response=owner.post('/api/v1/admin/backups/storage/save',json=dict(type='smb',name='NAS',host='192.168.1.20',username='backup',password='never-log-this-secret',share='Backups'))
        assert response.status_code==200
        assert 'never-log-this-secret' not in response.text
        assert boundary.call_args.args[2]['password']=='never-log-this-secret'
    with database() as db:
        for event in db.scalars(select(SecurityEvent)):
            assert 'never-log-this-secret' not in str(event.__dict__)


def test_maintenance_health_is_read_only_and_reports_paused_recovery(owner,database):
    from market.models import RetentionExecution
    from market.db import now
    with database.begin() as db:
        db.add(RetentionExecution(policy_hash='a'*64,status='paused',reason='Protected recovery verification expired',finished_at=now()))
    response=owner.get('/api/v1/admin/retention/health')
    assert response.status_code==200,response.text
    assert response.json()['recent_runs'][0]['reason']=='Protected recovery verification expired'
    assert response.json()['automation']['rows_by_stage']=={}
