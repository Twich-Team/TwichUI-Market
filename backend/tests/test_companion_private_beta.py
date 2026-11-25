"""Synthetic private-beta policy/store evidence; no real owner or Windows result."""
import base64
from datetime import datetime,timezone
import hashlib
import json
import pytest
from market import companion_private_beta as beta
from market import private_beta_publisher as publisher
from market import release_publisher
from market.models import Credential,User
from market.security import digest,hasher


def fixture_beta(tmp_path,monkeypatch,version='2.0.0-beta.1',source='b'*40):
    root=tmp_path/('incoming-'+version);directory=root/version;directory.mkdir(parents=True)
    key='synthetic-only-updater-public-key';monkeypatch.setenv('COMPANION_UPDATER_PUBLIC_KEY',key)
    # Policy fixtures mock only the independent verifier. Actual cryptographic
    # verification is exercised by the Rust verifier and isolated store rehearsal.
    monkeypatch.setattr(release_publisher,'verify_installer',lambda *args:None)
    payload=b'MZ'+b'SYNTHETIC NONEXECUTABLE PRIVATE BETA POLICY FIXTURE'*100
    filename=f'TwichUI-Market-Companion-{version}-windows-x64.exe';(directory/filename).write_bytes(payload)
    manifest={'schema_version':2,'channel':'private-beta','version':version,'filename':filename,'bytes':len(payload),
        'sha256':hashlib.sha256(payload).hexdigest(),'source_commit':source,'visual_approval_commit':'c'*40,'workflow_run_id':123,
        'published_at':datetime.now(timezone.utc).isoformat(),'authenticode_status':'NotSigned','updates':'signed','updater_public_key_sha256':hashlib.sha256(key.encode()).hexdigest(),'updater_signature':base64.b64encode(b'synthetic-signature-not-cryptographic-proof').decode(),
        'acceptance':{name:name!='tray' for name in beta.REQUIRED_TESTS},'unverified_requirements':sorted(beta.GAPS),
        'ci':{name:{'id':123+index,'source_commit':source,'repository':'Twich-Team/TwichUI-Market','path':path,'status':'completed','conclusion':'success'} for index,(name,path) in enumerate(beta.WORKFLOWS.items())},
        'evidence_sha256':{},'notes':'SYNTHETIC policy fixture, not actual unsigned installer acceptance.'}
    installed={name:True for name in ('native_browser_approval_ui native_thread_hidden_sync single_instance_restore preferences_saved credential_and_cache_restart '
        'hidden_startup current_user_autostart_enable_disable native_minimize_close_to_tray export_valid server_revocation offline_cache_preserved '
        'website_approval_ui_verified uninstall_settings_and_cache_preserved update_checks_blocked_for_custom_server').split()}
    installed.update(source_commit=source,version=version,installed_executable_sha256='e'*64,updater_disabled=False,updater_public_key_sha256=manifest['updater_public_key_sha256'],tray_acceptance='unverified',tray_settings_sync_pause_open_quit=False)
    upgrade={name:True for name in ('actual_old_installer actual_new_installer legacy_credentials_preserved cache_preserved connection_settings_preserved '
        'legacy_metadata_migrated new_native_sync export_contract_preserved uninstall_data_preservation_verified_by_parent').split()}
    upgrade.update(source_commit=source,to_version=version,signed_updater_sdk_install=False)
    documents={'installed-smoke.json':installed,'legacy-upgrade.json':upgrade,
        'performance.json':{'source_commit':source,'resources':{'synthetic':True},'idle_market_api_requests':{'before':{'requests':1},'after':{'requests':1}}},
        'launch-metrics.json':{'installer_bytes':len(payload)},
        'windows-signature.json':{'source_commit':source,'status':'NotSigned','sha256':manifest['sha256'],'bytes':len(payload),'updater_public_key_sha256':manifest['updater_public_key_sha256'],'executable_sha256':'e'*64,'executable_reference':'actual-installed-windows-executable'},
        'signed-update-acceptance.json':{'payload_source_commit':source,'harness_source_commit':'f'*40,'version':version,'installer_sha256':manifest['sha256'],
            'executable_sha256':'e'*64,'updater_public_key_sha256':manifest['updater_public_key_sha256'],'workflow_run_id':456,
            **dict.fromkeys(('supported_sdk_signature_verified','corrupt_payload_rejected','wrong_signed_version_rejected',
                'actual_sdk_install','installed_executable_verified','reconnect_sync_export','uninstall_data_preserved'),True)},
        'owner-release-approval.json':{'schema_version':2,'owner_approved_publication':True,'owner_approved_deployment':True,
            'scope':'private-nsis-with-tauri-signed-updates','owner_statement':'SYNTHETIC authorization fixture; not actual owner consent',
            'visual_approval_commit':'c'*40,'source_commit':source,'version':version,'installer_sha256':manifest['sha256'],
            'windows_run_id':123,'signed_update_run_id':456,'updater_public_key_sha256':manifest['updater_public_key_sha256'],
            'tray_actions_verified':False,'acknowledges_unverified_tray':True}}

    for name,value in documents.items():
        path=directory/name;path.write_text(json.dumps(value));manifest['evidence_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(manifest));(root/'current.json').write_text(json.dumps({'schema_version':1,'version':version}))
    monkeypatch.setenv('COMPANION_PRIVATE_BETA_DIRECTORY',str(root))
    return root,directory,manifest,payload


def change_evidence(directory,manifest,name,changes):
    path=directory/name;value=json.loads(path.read_text());value.update(changes);path.write_text(json.dumps(value))
    manifest['evidence_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest();(directory/'manifest.json').write_text(json.dumps(manifest))


def test_private_beta_needs_active_browser_session_and_never_becomes_public_update(client,owner,tmp_path,monkeypatch,database):
    _,_,manifest,payload=fixture_beta(tmp_path,monkeypatch)
    current=owner.get('/api/v1/companion/private-beta/current');assert current.status_code==200
    value=current.json();assert value['ready'] and value['channel']=='private-beta' and not value['signed']
    assert value['updates']=='signed' and value['updater_signature_verified'] is True and value['tray_actions_verified'] is False
    downloaded=owner.get(value['download_url']);assert downloaded.content==payload
    assert downloaded.headers['x-installer-sha256']==manifest['sha256'] and downloaded.headers['cache-control']=='no-store'
    assert not owner.get('/api/v1/companion/releases/current').json()['ready']
    assert owner.get('/api/v1/companion/releases/update/windows-x86_64/0.1.0').status_code==204
    assert owner.get('/api/v1/companion/releases/'+manifest['version']+'/windows-x64').status_code==404
    token=owner.post('/api/v1/devices',json={'name':'Synthetic old client'}).json()['token']
    assert owner.get(value['download_url'],headers={'Authorization':'Bearer '+token}).content==payload
    assert owner.get('/api/v1/companion/private-beta/current',headers={'Authorization':'Bearer '+token}).status_code==403
    owner.cookies.clear()
    assert owner.get(value['download_url']).status_code==401
    assert owner.get('/api/v1/companion/private-beta/current').status_code==401


@pytest.mark.parametrize('legacy_pilot', [None, '1'])
def test_member_beta_access_stops_immediately_on_account_disable(owner,tmp_path,monkeypatch,database,legacy_pilot):
    _,_,manifest,payload = fixture_beta(tmp_path,monkeypatch)
    if legacy_pilot is None:
        monkeypatch.delenv('COMPANION_PRIVATE_BETA_USER_IDS',raising=False)
    else:
        monkeypatch.setenv('COMPANION_PRIVATE_BETA_USER_IDS',legacy_pilot)
    with database.begin() as db:
        member = User(username='beta_member',role='member',password_hash=hasher.hash('synthetic member password'))
        db.add(member)
        db.flush()
        member_id = member.id
    owner.cookies.clear()
    session = owner.post('/api/v1/auth/login',json={'username':'beta_member','password':'synthetic member password'})
    assert session.status_code == 200
    owner.headers['x-csrf-token'] = session.json()['csrf_token']
    prefix = '/api/v1/companion/private-beta'
    current = owner.get(prefix+'/current').json()
    assert current['ready'] and current['sha256'] == manifest['sha256']
    asset = current['download_url']
    assert owner.get(asset).content == payload
    token = owner.post('/api/v1/devices',json={'name':'Review update client'}).json()['token']
    bearer = {'Authorization':'Bearer '+token}
    feed = prefix+'/update/windows-x86_64/0.1.0'
    assert owner.get(feed,headers=bearer).json()['signature'] == manifest['updater_signature']
    assert owner.get(asset,headers=bearer).content == payload
    assert owner.get(prefix+'/current',headers=bearer).status_code == 403
    with database.begin() as db:
        db.get(User,member_id).active = False
    for path,headers in [(prefix+'/current',{}),(asset,{}),(asset,bearer),(feed,bearer)]:
        assert owner.get(path,headers=headers).status_code == 401


@pytest.mark.parametrize('field,value',[
    ('schema_version',True),('channel','stable'),('version','2.0.0'),('filename','../../database'),('updates','manual'),
    ('authenticode_status','Valid'),('unverified_requirements',[]),('sha256','0'*64),('unexpected','must not be accepted')])
def test_private_receipt_cannot_hide_gaps_or_change_identity(owner,tmp_path,monkeypatch,field,value):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch);manifest[field]=value;(directory/'manifest.json').write_text(json.dumps(manifest))
    assert owner.get('/api/v1/companion/private-beta/current').json()['ready'] is False
    assert owner.get('/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64').status_code==404


@pytest.mark.parametrize('name,changes',[
    ('owner-release-approval.json',{'owner_approved_publication':False}),
    ('owner-release-approval.json',{'scope':'design-approval-only'}),
    ('windows-signature.json',{'status':'Valid'}),('windows-signature.json',{'source_commit':'d'*40}),
    ('installed-smoke.json',{'updater_disabled':True}),('installed-smoke.json',{'credential_and_cache_restart':False}),
    ('legacy-upgrade.json',{'uninstall_data_preservation_verified_by_parent':False}),
    ('performance.json',{'idle_market_api_requests':{'before':{'requests':1},'after':{'requests':2}}})])
def test_original_owner_windows_and_installed_evidence_cannot_be_replaced_by_manifest_claims(owner,tmp_path,monkeypatch,name,changes):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch);change_evidence(directory,manifest,name,changes)
    assert owner.get('/api/v1/companion/private-beta/current').json()['ready'] is False


def test_changed_or_noncanonical_ci_fails_closed(owner,tmp_path,monkeypatch):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch)
    for field,value in [('source_commit','d'*40),('path','.github/workflows/different.yml'),('conclusion','failure'),('status','in_progress')]:
        original=manifest['ci']['windows'][field];manifest['ci']['windows'][field]=value;(directory/'manifest.json').write_text(json.dumps(manifest))
        assert not owner.get('/api/v1/companion/private-beta/current').json()['ready'];manifest['ci']['windows'][field]=original


def test_symlink_oversized_changed_and_nonobject_evidence_never_streams(owner,tmp_path,monkeypatch):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch);path=directory/'installed-smoke.json';original=path.read_bytes()
    for content in [b'x'*16385,b'[]',b'{"changed":true}']:
        path.write_bytes(content);assert not owner.get('/api/v1/companion/private-beta/current').json()['ready']
    path.unlink();outside=tmp_path/'outside.json';outside.write_bytes(original);path.symlink_to(outside)
    assert not owner.get('/api/v1/companion/private-beta/current').json()['ready']


def test_audited_private_import_retry_and_rollback_preserve_both_versions(tmp_path,monkeypatch):
    _,first,manifest,payload=fixture_beta(tmp_path,monkeypatch);store=tmp_path/'published'
    assert publisher.publish(store,first,'synthetic-owner')['changed']
    assert publisher.publish(store,first,'synthetic-owner')['changed'] is False
    _,second,_,_=fixture_beta(tmp_path,monkeypatch,'2.0.0-beta.2','d'*40)
    assert publisher.publish(store,second,'synthetic-owner')['previous_version']==manifest['version']
    assert publisher.rollback(store,manifest['version'],'synthetic-owner')['changed']
    assert publisher.pointer(store)==manifest['version']
    for original in [first,second]:
        for path in original.iterdir():assert (store/original.name/path.name).read_bytes()==path.read_bytes()
    audits=list((store/'audit').glob('*.json'));assert len(audits)==6
    proof=json.loads((store/'audit/00000001.json').read_text());assert proof['tray_actions_verified'] is False and proof['updates']=='signed'
    assert proof['evidence_sha256']==manifest['evidence_sha256']


def test_private_store_cannot_initialize_or_replace_stable_store_identity(tmp_path,monkeypatch):
    _,bundle,_,_=fixture_beta(tmp_path,monkeypatch);store=tmp_path/'stable'
    with release_publisher.locked(store):pass
    with pytest.raises(ValueError,match='identity'):publisher.publish(store,bundle,'synthetic-owner')
    assert not (store/'current.json').exists()
    with pytest.raises(ValueError):release_publisher.publish(tmp_path/'other-stable',bundle,'synthetic-owner')


def test_changed_immutable_evidence_and_capacity_never_remove_previous_assets(tmp_path,monkeypatch):
    _,bundle,manifest,payload=fixture_beta(tmp_path,monkeypatch);store=tmp_path/'published';publisher.publish(store,bundle,'synthetic-owner')
    original=(store/'current.json').read_bytes()
    change_evidence(bundle,manifest,'owner-release-approval.json',{'owner_statement':'Changed synthetic statement'})
    with pytest.raises(ValueError,match='immutable'):publisher.publish(store,bundle,'synthetic-owner')
    monkeypatch.setattr(publisher,'MAX_STORE_BYTES',1024)
    _,other,_,_=fixture_beta(tmp_path,monkeypatch,'2.0.0-beta.2','d'*40)
    with pytest.raises(ValueError,match='budget'):publisher.publish(store,other,'synthetic-owner')
    assert (store/'current.json').read_bytes()==original
    assert (store/manifest['version']/manifest['filename']).read_bytes()==payload


def test_interrupted_private_pointer_has_durable_intent_and_idempotent_recovery(tmp_path,monkeypatch):
    _,bundle,manifest,payload=fixture_beta(tmp_path,monkeypatch);store=tmp_path/'published';original=release_publisher.atomic_json
    def interrupt(path,value):
        if path.name=='current.json':raise OSError('Synthetic interrupted pointer')
        return original(path,value)
    monkeypatch.setattr(release_publisher,'atomic_json',interrupt)
    with pytest.raises(OSError):publisher.publish(store,bundle,'synthetic-owner')
    assert not (store/'current.json').exists() and (store/'audit/00000001.json').exists()
    assert (store/manifest['version']/manifest['filename']).read_bytes()==payload
    monkeypatch.setattr(release_publisher,'atomic_json',original)
    assert publisher.publish(store,bundle,'synthetic-owner')['changed']


@pytest.mark.parametrize('installed,status',[('0.1.0',200),('2.0.0-beta.1',204),('2.0.0-beta.2',204),('2.0.0',204),('3.0.0',204),('2.00.0',404),('2.0.0-beta.01',404),('2.0.0-beta.0',404),('invalid',404)])
def test_private_update_feed_is_owned_signed_and_never_downgrades(owner,tmp_path,monkeypatch,installed,status):
    _,_,manifest,_=fixture_beta(tmp_path,monkeypatch)
    token=owner.post('/api/v1/devices',json={'name':'Synthetic update client'}).json()['token']
    endpoint='/api/v1/companion/private-beta/update/windows-x86_64/'+installed
    owner.cookies.clear()
    assert owner.get(endpoint).status_code==401
    response=owner.get(endpoint,headers={'Authorization':'Bearer '+token});assert response.status_code==status
    if status==200:
        assert response.json()['signature']==manifest['updater_signature']
        assert response.json()['url']=='https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64'



@pytest.mark.parametrize('proof,changes',[
    ('signed-update-acceptance.json',{'actual_sdk_install':False}),
    ('signed-update-acceptance.json',{'wrong_signed_version_rejected':False}),
    ('signed-update-acceptance.json',{'installer_sha256':'f'*64}),
    ('signed-update-acceptance.json',{'payload_source_commit':'f'*40}),
    ('owner-release-approval.json',{'installer_sha256':'f'*64}),
    ('owner-release-approval.json',{'owner_approved_deployment':False}),
    ('owner-release-approval.json',{'signed_update_run_id':999}),
    ('owner-release-approval.json',{'acknowledges_unverified_tray':False}),
    ('installed-smoke.json',{'updater_public_key_sha256':'f'*64}),
    ('installed-smoke.json',{'installed_executable_sha256':'f'*64}),
    ('windows-signature.json',{'executable_reference':'build-directory-reference'})])
def test_signing_and_final_approval_cannot_be_substituted(owner,tmp_path,monkeypatch,proof,changes):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch)
    change_evidence(directory,manifest,proof,changes)
    assert not owner.get('/api/v1/companion/private-beta/current').json()['ready']


def test_private_publisher_requires_independent_signature_even_with_complete_receipts(tmp_path,monkeypatch):
    _,bundle,_,_=fixture_beta(tmp_path,monkeypatch)
    def reject(*args):raise ValueError('Independent release signature verification failed')
    monkeypatch.setattr(release_publisher,'verify_installer',reject)
    with pytest.raises(ValueError,match='signature'):publisher.publish(tmp_path/'published',bundle,'synthetic-owner')
    assert not (tmp_path/'published/current.json').exists()


def test_owned_native_update_scope_is_narrow_and_revocable(owner,tmp_path,monkeypatch):
    from test_companion_auth import authorize,bearer
    monkeypatch.setenv('SYNC_CURSOR_SECRET','synthetic-native-update-scope-secret-over-32-characters')
    _,_,manifest,payload=fixture_beta(tmp_path,monkeypatch)
    tokens=authorize(owner);headers=bearer(tokens)
    endpoint='/api/v1/companion/private-beta/update/windows-x86_64/0.1.0'
    assert owner.get(endpoint,headers=headers).json()['version']==manifest['version']
    asset='/api/v1/companion/private-beta/'+manifest['version']+'/windows-x64'
    assert owner.get(asset,headers=headers).content==payload
    for path in ('/api/v1/companion/private-beta/current','/api/v1/admin/users','/api/v1/me/preferences','/api/v1/companion/devices'):
        assert owner.get(path,headers=headers).status_code==403
    device=owner.get('/api/v1/companion/devices').json()['devices'][0]
    assert owner.delete('/api/v1/companion/devices/'+str(device['id'])).status_code==204
    assert owner.get(endpoint,headers=headers).status_code==401
    assert owner.get(asset,headers=headers).status_code==401
