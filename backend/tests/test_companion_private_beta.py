"""Synthetic private-beta policy/store evidence; no real owner or Windows result."""
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
    payload=b'MZ'+b'SYNTHETIC NONEXECUTABLE PRIVATE BETA POLICY FIXTURE'*100
    filename=f'TwichUI-Market-Companion-{version}-windows-x64.exe';(directory/filename).write_bytes(payload)
    manifest={'schema_version':1,'channel':'private-beta','version':version,'filename':filename,'bytes':len(payload),
        'sha256':hashlib.sha256(payload).hexdigest(),'source_commit':source,'visual_approval_commit':'c'*40,'workflow_run_id':123,
        'published_at':datetime.now(timezone.utc).isoformat(),'authenticode_status':'NotSigned','updates':'manual',
        'acceptance':{name:name!='tray' for name in beta.REQUIRED_TESTS},'unverified_requirements':sorted(beta.GAPS),
        'ci':{name:{'id':123+index,'source_commit':source,'repository':'Twich-Team/TwichUI-Market','path':path,'status':'completed','conclusion':'success'} for index,(name,path) in enumerate(beta.WORKFLOWS.items())},
        'evidence_sha256':{},'notes':'SYNTHETIC policy fixture, not actual unsigned installer acceptance.'}
    installed={name:True for name in ('native_browser_approval_ui native_thread_hidden_sync single_instance_restore preferences_saved credential_and_cache_restart '
        'hidden_startup current_user_autostart_enable_disable native_minimize_close_to_tray export_valid server_revocation offline_cache_preserved '
        'website_approval_ui_verified uninstall_settings_and_cache_preserved updater_disabled').split()}
    installed.update(source_commit=source,version=version,tray_acceptance='unverified',tray_settings_sync_pause_open_quit=False)
    upgrade={name:True for name in ('actual_old_installer actual_new_installer legacy_credentials_preserved cache_preserved connection_settings_preserved '
        'legacy_metadata_migrated new_native_sync export_contract_preserved uninstall_data_preservation_verified_by_parent').split()}
    upgrade.update(source_commit=source,to_version=version,signed_updater_sdk_install=False)
    documents={'installed-smoke.json':installed,'legacy-upgrade.json':upgrade,
        'performance.json':{'source_commit':source,'resources':{'synthetic':True},'idle_market_api_requests':{'before':{'requests':1},'after':{'requests':1}}},
        'launch-metrics.json':{'installer_bytes':len(payload)},
        'windows-signature.json':{'source_commit':source,'status':'NotSigned','sha256':manifest['sha256'],'bytes':len(payload)},
        'owner-private-beta-approval.json':{'schema_version':1,'owner_authorized_private_beta':True,'scope':'private-unsigned-beta-with-manual-updates',
            'owner_statement':'SYNTHETIC authorization fixture; not actual owner consent','visual_approval_commit':'c'*40}}
    for name,value in documents.items():
        path=directory/name;path.write_text(json.dumps(value));manifest['evidence_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (directory/'manifest.json').write_text(json.dumps(manifest));(root/'current.json').write_text(json.dumps({'schema_version':1,'version':version}))
    monkeypatch.setenv('COMPANION_PRIVATE_BETA_DIRECTORY',str(root));monkeypatch.setenv('COMPANION_PRIVATE_BETA_USER_IDS','1')
    return root,directory,manifest,payload


def change_evidence(directory,manifest,name,changes):
    path=directory/name;value=json.loads(path.read_text());value.update(changes);path.write_text(json.dumps(value))
    manifest['evidence_sha256'][name]=hashlib.sha256(path.read_bytes()).hexdigest();(directory/'manifest.json').write_text(json.dumps(manifest))


def test_private_beta_needs_active_allowlisted_browser_session_and_never_becomes_public_update(client,owner,tmp_path,monkeypatch,database):
    _,_,manifest,payload=fixture_beta(tmp_path,monkeypatch)
    current=owner.get('/api/v1/companion/private-beta/current');assert current.status_code==200
    value=current.json();assert value['ready'] and value['channel']=='private-beta' and not value['signed']
    assert value['updates']=='manual' and value['tray_actions_verified'] is False
    downloaded=owner.get(value['download_url']);assert downloaded.content==payload
    assert downloaded.headers['x-installer-sha256']==manifest['sha256'] and downloaded.headers['cache-control']=='no-store'
    assert not owner.get('/api/v1/companion/releases/current').json()['ready']
    assert owner.get('/api/v1/companion/releases/update/windows-x86_64/0.1.0').status_code==204
    assert owner.get('/api/v1/companion/releases/'+manifest['version']+'/windows-x64').status_code==404
    token=owner.post('/api/v1/devices',json={'name':'Synthetic old client'}).json()['token']
    assert owner.get(value['download_url'],headers={'Authorization':'Bearer '+token}).status_code==403
    owner.cookies.clear()
    assert owner.get(value['download_url']).status_code==401
    assert owner.get('/api/v1/companion/private-beta/current').status_code==401


@pytest.mark.parametrize('allowlist',['','2','0','1,2,3,4','1,1','1, 2','1,invalid','1,'+'2'*130])
def test_missing_malformed_or_other_account_allowlist_denies_even_administrator(owner,tmp_path,monkeypatch,allowlist):
    fixture_beta(tmp_path,monkeypatch);monkeypatch.setenv('COMPANION_PRIVATE_BETA_USER_IDS',allowlist)
    assert owner.get('/api/v1/companion/private-beta/current').status_code==404


def test_individual_member_allowlist_and_revocation_are_checked_on_each_download(owner,tmp_path,monkeypatch,database):
    fixture_beta(tmp_path,monkeypatch)
    with database.begin() as db:
        user=User(username='pilot_member',role='member',password_hash=hasher.hash('synthetic pilot password'));db.add(user);db.flush();member_id=user.id
    owner.cookies.clear();assert owner.post('/api/v1/auth/login',json={'username':'pilot_member','password':'synthetic pilot password'}).status_code==200
    assert owner.get('/api/v1/companion/private-beta/current').status_code==404
    monkeypatch.setenv('COMPANION_PRIVATE_BETA_USER_IDS',str(member_id))
    url=owner.get('/api/v1/companion/private-beta/current').json()['download_url'];assert owner.get(url).status_code==200
    with database.begin() as db:
        for row in db.query(Credential).filter(Credential.user_id==member_id):row.revoked=True
    assert owner.get(url).status_code==401


@pytest.mark.parametrize('field,value',[
    ('schema_version',True),('channel','stable'),('version','2.0.0'),('filename','../../database'),('updates','automatic'),
    ('authenticode_status','Valid'),('unverified_requirements',[]),('sha256','0'*64),('unexpected','must not be accepted')])
def test_private_receipt_cannot_hide_gaps_or_change_identity(owner,tmp_path,monkeypatch,field,value):
    _,directory,manifest,_=fixture_beta(tmp_path,monkeypatch);manifest[field]=value;(directory/'manifest.json').write_text(json.dumps(manifest))
    assert owner.get('/api/v1/companion/private-beta/current').json()['ready'] is False
    assert owner.get('/api/v1/companion/private-beta/2.0.0-beta.1/windows-x64').status_code==404


@pytest.mark.parametrize('name,changes',[
    ('owner-private-beta-approval.json',{'owner_authorized_private_beta':False}),
    ('owner-private-beta-approval.json',{'scope':'design-approval-only'}),
    ('windows-signature.json',{'status':'Valid'}),('windows-signature.json',{'source_commit':'d'*40}),
    ('installed-smoke.json',{'updater_disabled':False}),('installed-smoke.json',{'credential_and_cache_restart':False}),
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
    proof=json.loads((store/'audit/00000001.json').read_text());assert proof['tray_actions_verified'] is False and proof['updates']=='manual'
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
    change_evidence(bundle,manifest,'owner-private-beta-approval.json',{'owner_statement':'Changed synthetic statement'})
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
