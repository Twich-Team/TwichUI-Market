"""Synthetic receipts test atomic store mechanics, not real Windows signing/CI."""
import json
from pathlib import Path
import pytest
from market import release_publisher as publisher
from test_companion_releases import fixture_release


def fixture(tmp_path,monkeypatch):
    root,directory,asset,receipt,payload=fixture_release(tmp_path,monkeypatch)
    calls=[]
    def verify(manifest,installer):
        # Actual cryptographic verifier has separate real-signature Rust coverage.
        data=json.loads(Path(manifest).read_text())
        assert Path(installer).read_bytes()==payload
        assert data['sha256']==receipt['sha256']
        calls.append(str(installer))
    monkeypatch.setattr(publisher,'verify_installer',verify)
    return tmp_path/'published',root,directory,receipt,payload,calls


def test_immutable_import_idempotency_and_audited_rollback_keep_both_versions(tmp_path,monkeypatch):
    store,source,bundle,receipt,payload,calls=fixture(tmp_path,monkeypatch)
    first=publisher.publish(store,bundle,'synthetic-owner')
    assert first['changed'] and first['version']=='2.0.0' and first['previous_version'] is None
    assert publisher.publish(store,bundle,'synthetic-owner')=={'changed':False,'version':'2.0.0'}
    version='2.0.1';other=source/version;other.mkdir()
    updated={**receipt,'version':version,'filename':f'TwichUI-Market-Companion-{version}-windows-x64.exe'}
    (other/'manifest.json').write_text(json.dumps(updated));(other/updated['filename']).write_bytes(payload)
    second=publisher.publish(store,other,'synthetic-owner');assert second['previous_version']=='2.0.0'
    assert publisher.pointer(store)=='2.0.1'
    rolled=publisher.rollback(store,'2.0.0','synthetic-owner');assert rolled['previous_version']=='2.0.1'
    assert publisher.pointer(store)=='2.0.0'
    for value in ['2.0.0','2.0.1']:
        assert (store/value/f'TwichUI-Market-Companion-{value}-windows-x64.exe').read_bytes()==payload
    assert len(list((store/'audit').glob('*.json')))==6
    assert json.loads((store/'audit'/'00000001.json').read_text())['phase']=='prepared'
    assert calls


def test_version_overwrite_and_invalid_actor_are_rejected_without_changing_active_release(tmp_path,monkeypatch):
    store,_,bundle,receipt,_,_=fixture(tmp_path,monkeypatch)
    publisher.publish(store,bundle,'synthetic-owner');original=(store/'current.json').read_bytes()
    receipt['notes']='Changed immutable receipt';(bundle/'manifest.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError,match='immutable'):publisher.publish(store,bundle,'synthetic-owner')
    with pytest.raises(ValueError,match='operator'):publisher.publish(store,bundle,'')
    assert (store/'current.json').read_bytes()==original


def test_capacity_and_missing_signature_never_remove_existing_assets_or_pointer(tmp_path,monkeypatch):
    store,_,bundle,_,payload,_=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(publisher,'MAX_STORE_BYTES',1024)
    with pytest.raises(ValueError,match='budget'):publisher.publish(store,bundle,'synthetic-owner')
    assert not (store/'current.json').exists()
    monkeypatch.setattr(publisher,'MAX_STORE_BYTES',256*1024*1024)
    publisher.publish(store,bundle,'synthetic-owner');original=(store/'current.json').read_bytes()
    def reject(*arguments):raise ValueError('Independent release signature verification failed')
    monkeypatch.setattr(publisher,'verify_installer',reject)
    with pytest.raises(ValueError,match='signature'):publisher.rollback(store,'2.0.0','synthetic-owner')
    assert (store/'current.json').read_bytes()==original
    assert next((store/'2.0.0').glob('*.exe')).read_bytes()==payload


def test_interrupted_pointer_transition_leaves_durable_intent_and_all_assets(tmp_path,monkeypatch):
    store,_,bundle,_,payload,_=fixture(tmp_path,monkeypatch)
    original=publisher.atomic_json
    def interrupt(path,value):
        if path.name=='current.json':raise OSError('Synthetic pointer interruption')
        original(path,value)
    monkeypatch.setattr(publisher,'atomic_json',interrupt)
    with pytest.raises(OSError):publisher.publish(store,bundle,'synthetic-owner')
    assert not (store/'current.json').exists()
    assert next((store/'2.0.0').glob('*.exe')).read_bytes()==payload
    assert json.loads((store/'audit'/'00000001.json').read_text())['phase']=='prepared'
    monkeypatch.setattr(publisher,'atomic_json',original)
    assert publisher.publish(store,bundle,'synthetic-owner')['changed']
    assert publisher.pointer(store)=='2.0.0'
    assert (store/'audit'/'00000001.json').exists()


def test_unrelated_directory_and_symlink_store_are_never_initialized(tmp_path,monkeypatch):
    store,_,bundle,_,_,_=fixture(tmp_path,monkeypatch)
    store.mkdir();(store/'unrelated.txt').write_text('Must remain')
    with pytest.raises(ValueError,match='identity'):publisher.publish(store,bundle,'synthetic-owner')
    assert (store/'unrelated.txt').read_text()=='Must remain'
    alias=tmp_path/'alias';alias.symlink_to(store)
    with pytest.raises(ValueError,match='symlink'):publisher.publish(alias,bundle,'synthetic-owner')
