"""Synthetic trusted-publisher receipts; these fixtures are not signed release evidence."""
import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import pytest
from market.companion_releases import REQUIRED_TESTS


def fixture_release(tmp_path,monkeypatch):
    root=tmp_path/'release-test';version='2.0.0';directory=root/version;directory.mkdir(parents=True)
    key='synthetic-only-updater-public-key'
    monkeypatch.setenv('COMPANION_RELEASE_DIRECTORY',str(root))
    monkeypatch.setenv('COMPANION_PUBLISHER_THUMBPRINT','A'*40)
    monkeypatch.setenv('COMPANION_UPDATER_PUBLIC_KEY',key)
    payload=b'MZ'+b'synthetic-only-not-a-real-installer'*100
    name=f'TwichUI-Market-Companion-{version}-windows-x64.exe';asset=directory/name;asset.write_bytes(payload)
    receipt={'schema_version':1,'channel':'stable','version':version,'filename':name,'bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest(),
        'source_commit':'b'*40,'workflow_run_id':123,'published_at':datetime.now(timezone.utc).isoformat(),'publisher_thumbprint':'A'*40,
        'authenticode_status':'Valid','updater_public_key_sha256':hashlib.sha256(key.encode()).hexdigest(),
        'updater_signature':base64.b64encode(b'synthetic-signature-not-cryptographic-proof').decode(),'visual_approval_commit':'c'*40,
        'acceptance':dict.fromkeys(REQUIRED_TESTS,True),'notes':'Synthetic release service fixture only'}
    (directory/'manifest.json').write_text(json.dumps(receipt));(root/'current.json').write_text(json.dumps({'schema_version':1,'version':version}))
    return root,directory,asset,receipt,payload


def test_missing_release_configuration_is_an_honest_unavailable_download(client,monkeypatch):
    monkeypatch.delenv('COMPANION_RELEASE_DIRECTORY',raising=False)
    response=client.get('/api/v1/companion/releases/current');assert response.status_code==200
    data=response.json();assert not data['ready'] and data['version'] is None and data['download_url'] is None
    assert client.get('/api/v1/companion/releases/2.0.0/windows-x64').status_code==404


def test_controlled_versioned_download_is_public_streamed_and_has_expected_digest(client,tmp_path,monkeypatch):
    _,_,asset,receipt,payload=fixture_release(tmp_path,monkeypatch)
    current=client.get('/api/v1/companion/releases/current').json();assert current['ready'] and current['version']=='2.0.0'
    assert current['source_commit']==receipt['source_commit'] and current['sha256']==receipt['sha256']
    assert str(tmp_path) not in json.dumps(current)
    download=client.get(current['download_url']);assert download.status_code==200 and download.content==payload
    assert download.headers['x-installer-sha256']==hashlib.sha256(download.content).hexdigest()
    assert 'attachment' in download.headers['content-disposition'] and asset.name in download.headers['content-disposition']
    assert download.headers['x-content-type-options']=='nosniff'
    # No session or GitHub credential is needed for an approved public installer.
    assert 'set-cookie' not in download.headers


@pytest.mark.parametrize('field,value',[
    ('channel','preview'),('version','2.0.0-beta.1'),('filename','../../market.db'),('authenticode_status','NotSigned'),
    ('publisher_thumbprint','F'*40),('updater_public_key_sha256','f'*64),('bytes',2**30),('sha256','f'*64),
    ('updater_signature','malformed! '*8),('published_at','2026-11-14T12:00:00'),('schema_version',99),
    ('visual_approval_commit',''),('unexpected_secret_field','must not be accepted')])
def test_unverified_or_malformed_receipts_never_become_a_stable_download(client,tmp_path,monkeypatch,field,value):
    _,directory,_,receipt,_=fixture_release(tmp_path,monkeypatch);receipt[field]=value
    (directory/'manifest.json').write_text(json.dumps(receipt))
    assert not client.get('/api/v1/companion/releases/current').json()['ready']
    assert client.get('/api/v1/companion/releases/2.0.0/windows-x64').status_code==404


def test_missing_windows_acceptance_or_public_trust_configuration_fails_closed(client,tmp_path,monkeypatch):
    _,directory,_,receipt,_=fixture_release(tmp_path,monkeypatch)
    receipt['acceptance']['tray']=False;(directory/'manifest.json').write_text(json.dumps(receipt))
    assert not client.get('/api/v1/companion/releases/current').json()['ready']
    receipt['acceptance']['tray']=True;(directory/'manifest.json').write_text(json.dumps(receipt))
    monkeypatch.delenv('COMPANION_UPDATER_PUBLIC_KEY');assert not client.get('/api/v1/companion/releases/current').json()['ready']


def test_corrupted_installer_and_symlinks_are_rejected_without_exposing_files(client,tmp_path,monkeypatch):
    root,directory,asset,receipt,payload=fixture_release(tmp_path,monkeypatch)
    assert client.get('/api/v1/companion/releases/current').json()['ready']
    asset.write_bytes(b'bad bytes same file'+b'x'*(len(payload)-19))
    assert not client.get('/api/v1/companion/releases/current').json()['ready']
    asset.unlink();outside=tmp_path/'outside.exe';outside.write_bytes(payload);asset.symlink_to(outside)
    assert client.get('/api/v1/companion/releases/2.0.0/windows-x64').status_code==404
    asset.unlink();asset.write_bytes(payload);(directory/'manifest.json').unlink();outside_manifest=tmp_path/'outside.json';outside_manifest.write_text(json.dumps(receipt))
    (directory/'manifest.json').symlink_to(outside_manifest);assert not client.get('/api/v1/companion/releases/current').json()['ready']
    assert client.get('/api/v1/companion/releases/%2E%2E/windows-x64').status_code==404


def test_stable_pointer_never_accepts_a_preview_or_oversized_document(client,tmp_path,monkeypatch):
    root,_,_,_,_=fixture_release(tmp_path,monkeypatch)
    for pointer in [{'schema_version':True,'version':'2.0.0'},{'schema_version':1,'version':'2.0.0-beta.1'},{'schema_version':1,'version':'../../outside'}]:
        (root/'current.json').write_text(json.dumps(pointer));assert not client.get('/api/v1/companion/releases/current').json()['ready']
    (root/'current.json').write_bytes(b'x'*16385);assert not client.get('/api/v1/companion/releases/current').json()['ready']
