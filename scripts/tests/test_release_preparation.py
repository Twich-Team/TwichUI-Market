"""Synthetic gate fixtures; no Windows trust/signing or owner acceptance is implied."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('release_preparation',ROOT/'scripts'/'prepare-companion-release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


class ReleasePreparation(unittest.TestCase):
    def setUp(self):
        (ROOT/'artifacts').mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='release-gate-test-',dir=ROOT/'artifacts')
        self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        self.source='a'*40;self.visual='b'*40;self.key='SYNTHETIC-PUBLIC-KEY-NOT-TRUST'
        self.environment=patch.dict(os.environ,{'GITHUB_ACTIONS':'true','RUNNER_OS':'Windows','GITHUB_REPOSITORY':release.REPO,
            'GITHUB_ACTOR':'fixture_owner','COMPANION_RELEASE_OWNER':'fixture_owner','RELEASE_VERSION':'2.0.0',
            'RELEASE_SOURCE_COMMIT':self.source,'RELEASE_VISUAL_COMMIT':self.visual,'RELEASE_WINDOWS_RUN_ID':'1','RELEASE_BACKEND_RUN_ID':'2',
            'RELEASE_WEBSITE_RUN_ID':'3','GITHUB_RUN_ID':'456','COMPANION_UPDATER_PUBLIC_KEY':self.key,
            'COMPANION_PUBLISHER_THUMBPRINT':'A'*40,'COMPANION_TIMESTAMP_URL':'https://timestamp.example.test',
            'RELEASE_CANDIDATE_RUN_ID':'456','RELEASE_MANUAL_COMMIT':'c'*40,'TAURI_SIGNING_PRIVATE_KEY':'SYNTHETIC-PRIVATE-MUST-NOT-BE-WRITTEN'})
        self.environment.start();self.addCleanup(self.environment.stop)
        self.root_patch=patch.object(release,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.identity_patch=patch.object(release,'identity',return_value=('2.0.0',self.source,self.visual));self.identity_patch.start();self.addCleanup(self.identity_patch.stop)
        for directory in ['desktop/core','desktop/src-tauri','desktop/src-tauri/target/release/bundle/nsis','desktop']:(self.root/directory).mkdir(parents=True,exist_ok=True)
        for path in ['desktop/core/Cargo.toml','desktop/src-tauri/Cargo.toml']:(self.root/path).write_text('[package]\nversion="2.0.0"\n')
        (self.root/'desktop/package.json').write_text('{"version":"2.0.0"}')
        (self.root/'desktop/src-tauri/tauri.conf.json').write_text('{"version":"2.0.0","app":{"windows":[]}}')
        self.output=self.root/'output';self.output.mkdir()
        (self.output/'source-provenance.json').write_text(json.dumps({'source_commit':self.source,'owner':'fixture_owner','version':'2.0.0'}))
        self.acceptance=self.root/'acceptance';self.acceptance.mkdir()
        flags=('native_browser_approval_ui native_thread_hidden_sync single_instance_restore preferences_saved credential_and_cache_restart '
            'hidden_startup current_user_autostart_enable_disable native_minimize_close_to_tray export_valid server_revocation '
            'offline_cache_preserved website_approval_ui_verified uninstall_settings_and_cache_preserved').split()
        (self.acceptance/'installed-smoke.json').write_text(json.dumps({'source_commit':self.source,**dict.fromkeys(flags,True)}))
        flags=('actual_old_installer actual_new_installer legacy_credentials_preserved cache_preserved connection_settings_preserved '
            'legacy_metadata_migrated new_native_sync export_contract_preserved signed_updater_sdk_install uninstall_data_preservation_verified_by_parent').split()
        (self.acceptance/'legacy-upgrade.json').write_text(json.dumps({'source_commit':self.source,**dict.fromkeys(flags,True)}))
        (self.acceptance/'performance.json').write_text(json.dumps({'source_commit':self.source,'resources':{'synthetic':True},'idle_market_api_requests':{'before':{'fixture_requests':0},'after':{'fixture_requests':0}}}))
        (self.acceptance/'launch-metrics.json').write_text('{"fixture":true,"cold_start_to_native_window_ms":1}')
        installer=self.root/'desktop/src-tauri/target/release/bundle/nsis/synthetic-setup.exe';installer.write_bytes(b'MZ'+b'x'*1024)
        Path(str(installer)+'.sig').write_text('A'*64)
        self.signing=self.root/'signing.json';self.signing.write_text(json.dumps({'status':'Valid','thumbprint':'A'*40,'sha256':release.sha(installer),'timestamped':True}))

    def candidate(self):
        release.candidate(self.output,self.acceptance,self.signing)
        return self.output/'bundle/2.0.0/manifest.json'

    def manual(self,manifest):
        return {'schema_version':1,'owner':'fixture_owner','source_commit':self.source,'version':'2.0.0',
            'installer_sha256':json.loads(manifest.read_text())['sha256'],'tray_screenshot_sha256':'f'*64,
            'windows_version':'Synthetic Windows fixture','display_scaling':'100%','observations':'Synthetic gate test, not actual PC evidence',
            'tray_actions_verified':True,'checks':dict.fromkeys(['notification_menu','open','settings','sync','pause_resume','close_restore',
                'minimize_restore','hidden_sync','startup','single_instance','quit'],True)}

    def test_candidate_cannot_be_published_before_exact_manual_acceptance(self):
        manifest=self.candidate();value=json.loads(manifest.read_text())
        self.assertFalse(value['acceptance']['tray']);self.assertFalse(json.loads((self.output/'candidate-provenance.json').read_text())['stable_publication_permitted'])
        manual=self.manual(manifest)
        producer={'id':456,'actor':'fixture_owner','event':'workflow_dispatch'}
        with patch.object(release,'workflow',return_value=producer),patch.object(release.subprocess,'check_output',return_value=json.dumps(manual).encode()):
            release.approve(self.output,Path('docs/evidence/manual.json'))
        self.assertTrue(json.loads(manifest.read_text())['acceptance']['tray'])
        self.assertTrue((manifest.parent/'publication-proof.json').exists())

    def test_wrong_installer_or_incomplete_manual_record_cannot_complete_candidate(self):
        manifest=self.candidate();original=manifest.read_bytes()
        for wrong in ['installer','checks','actor','producer']:
            manual=self.manual(manifest);producer={'id':456,'actor':'fixture_owner','event':'workflow_dispatch'}
            if wrong=='installer':manual['installer_sha256']='0'*64
            elif wrong=='checks':manual['checks']['quit']=False
            elif wrong=='actor':manual['owner']='another_owner'
            else:producer['actor']='another_owner'
            with patch.object(release,'workflow',return_value=producer),patch.object(release.subprocess,'check_output',return_value=json.dumps(manual).encode()):
                with self.assertRaises(ValueError):release.approve(self.output,Path('docs/evidence/manual.json'))
            self.assertEqual(manifest.read_bytes(),original)

    def test_changed_candidate_acceptance_or_unexpected_idle_requests_are_rejected(self):
        path=self.acceptance/'performance.json';data=json.loads(path.read_text());data['idle_market_api_requests']['after']['fixture_requests']=1;path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.candidate()
        data['idle_market_api_requests']['after']['fixture_requests']=0;path.write_text(json.dumps(data))
        manifest=self.candidate();original=manifest.read_bytes()
        (self.output/'installed-acceptance/performance.json').write_text('{}')
        with patch.object(release,'workflow',return_value={'id':456,'actor':'fixture_owner','event':'workflow_dispatch'}),patch.object(release.subprocess,'check_output',return_value=json.dumps(self.manual(manifest)).encode()):
            with self.assertRaises(ValueError):release.approve(self.output,Path('docs/evidence/manual.json'))
        self.assertEqual(manifest.read_bytes(),original)

    def test_canonical_exact_source_completed_ci_is_required(self):
        import io
        base={'head_sha':self.source,'status':'completed','conclusion':'success','path':release.WORKFLOWS['windows'],'repository':{'full_name':release.REPO}}
        with patch.dict(os.environ,{'GITHUB_TOKEN':'synthetic-read-only-token'}):
            with patch.object(release.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(base).encode())):
                self.assertEqual(release.workflow('123',release.WORKFLOWS['windows'],self.source)['id'],123)
            for change in [{'head_sha':'f'*40},{'status':'in_progress'},{'conclusion':'failure'},{'path':'.github/workflows/another.yml'},{'repository':{'full_name':'another/repository'}}]:
                with patch.object(release.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps({**base,**change}).encode())):
                    with self.assertRaises(ValueError):release.workflow('123',release.WORKFLOWS['windows'],self.source)

    def test_missing_installed_acceptance_or_actual_signature_proof_blocks_candidate(self):
        installed=self.acceptance/'installed-smoke.json';data=json.loads(installed.read_text());data['hidden_startup']=False;installed.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.candidate()
        data['hidden_startup']=True;installed.write_text(json.dumps(data))
        proof=json.loads(self.signing.read_text());proof['status']='NotSigned';self.signing.write_text(json.dumps(proof))
        with self.assertRaises(ValueError):self.candidate()
        self.assertFalse((self.output/'bundle').exists())

    def test_owner_dispatch_and_stable_version_are_required_without_writing_private_material(self):
        with patch.dict(os.environ,{'GITHUB_ACTOR':'not_the_owner'}):
            with self.assertRaises(ValueError):release.owner()
        with patch.object(release.subprocess,'run'),patch.object(release,'workflow',return_value={'synthetic':True}):
            release.preflight(self.output)
        self.assertNotIn('SYNTHETIC-PRIVATE-MUST-NOT-BE-WRITTEN',(self.output/'tauri-signing.json').read_text())
        (self.root/'desktop/core/Cargo.toml').write_text('[package]\nversion="2.0.0-beta.1"\n')
        with patch.object(release.subprocess,'run'):
            with self.assertRaises(ValueError):release.preflight(self.output)


if __name__=='__main__':unittest.main()
