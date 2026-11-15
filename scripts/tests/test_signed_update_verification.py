"""Synthetic public-proof policy fixtures; never actual Windows acceptance."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('signed_update_verify',ROOT/'scripts/verify-signed-update-candidate.py')
verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)


class SignedUpdateVerification(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='signed-update-proof-test-',dir=ROOT/'artifacts');self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        key=(ROOT/'desktop/src-tauri/updater-public-key.txt').read_text().strip()
        self.proof={'schema_version':1,'version':'2.0.0-beta.1','payload_source_commit':'b'*40,
            'windows_run_id':123,'backend_run_id':124,'website_run_id':125,'installer_artifact_id':456,
            'installer_sha256':'c'*64,'installer_bytes':2048,'executable_sha256':'d'*64,
            'updater_public_key_sha256':hashlib.sha256(key.encode()).hexdigest(),
            'updater_signature':base64.b64encode(b'SYNTHETIC-NOT-A-REAL-CRYPTOGRAPHIC-SIGNATURE').decode()}
        self.path=self.root/'proof.json';self.write()

    def write(self):self.path.write_text(json.dumps(self.proof))

    def test_only_public_exact_candidate_identity_is_accepted(self):
        proof,key=verify.read_proof(self.path);self.assertEqual(proof,self.proof)
        for field,value in [('schema_version',True),('version','2.0.0-beta.01'),('installer_bytes',64*1024*1024+1),
                ('payload_source_commit','b'*39),('updater_public_key_sha256','f'*64),('installer_artifact_id',True),
                ('updater_signature','invalid!'),('private_key','must never be accepted')]:
            original=self.proof.copy();self.proof[field]=value;self.write()
            with self.assertRaises(ValueError):verify.read_proof(self.path)
            self.proof=original
        self.write()

    def test_all_canonical_payload_source_runs_checked_and_no_signing_secret_needed(self):
        output=self.root/'output';calls=[]
        with patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}),patch.object(verify.prepare,'workflow',side_effect=lambda *args:calls.append(args)):
            verify.preflight(self.path)
        self.assertEqual(len(calls),3)
        self.assertEqual({args[2] for args in calls},{self.proof['payload_source_commit']})
        self.assertEqual(output.read_text(),'windows_run_id=123\ninstaller_artifact_id=456\n')
        with patch.object(verify.prepare,'workflow',side_effect=ValueError('Synthetic failed canonical CI')):
            with self.assertRaises(ValueError):verify.preflight(self.path)

    def test_only_matching_completed_installer_evidence_avoids_repeating_expiring_artifact_download(self):
        root=self.root/'isolated-root';target=root/'docs/evidence';target.mkdir(parents=True)
        archive=target/'companion-v2-signed-update-acceptance.json'
        receipt={name:self.proof[name] for name in ('payload_source_commit','version','installer_sha256','executable_sha256','updater_public_key_sha256')}
        receipt.update(workflow_run_id=999,**dict.fromkeys(('supported_sdk_signature_verified','corrupt_payload_rejected','wrong_signed_version_rejected',
            'actual_sdk_install','installed_executable_verified','reconnect_sync_export','uninstall_data_preserved'),True))
        with patch.object(verify,'ROOT',root),patch.object(verify,'read_proof',return_value=(self.proof,'synthetic-public')):
            self.assertTrue(verify.selection(self.path))
            archive.write_text(json.dumps(receipt));self.assertFalse(verify.selection(self.path))
            self.assertTrue(verify.selection(self.path,pending_only=False))
            for field,value in [('installer_sha256','f'*64),('actual_sdk_install',False),('workflow_run_id',True)]:
                changed={**receipt,field:value};archive.write_text(json.dumps(changed));self.assertTrue(verify.selection(self.path))

    def test_parent_record_requires_actual_sdk_install_and_retention(self):
        # A correct public signature alone cannot attest the parent-run installer.
        target=self.root/'artifacts/companion-v2';target.mkdir(parents=True)
        upgrade={name:True for name in ('actual_old_installer','actual_new_installer','legacy_credentials_preserved',
            'cache_preserved','connection_settings_preserved','new_native_sync','export_contract_preserved',
            'signed_updater_sdk_install','uninstall_data_preservation_verified_by_parent')}
        upgrade.update(source_commit='e'*40,to_version=self.proof['version'])
        receipt=target/'legacy-upgrade.json'
        with patch.object(verify,'ROOT',self.root),patch.object(verify,'read_proof',return_value=(self.proof,'synthetic-public')), \
             patch.object(verify.subprocess,'check_output',return_value='e'*40),patch.dict(os.environ,{'GITHUB_RUN_ID':'999'}):
            for missing in ('signed_updater_sdk_install','uninstall_data_preservation_verified_by_parent'):
                upgrade[missing]=False;receipt.write_text(json.dumps(upgrade))
                with self.assertRaises(ValueError):verify.record(self.path)
                upgrade[missing]=True
            receipt.write_text(json.dumps(upgrade));verify.record(self.path)
            recorded=json.loads((self.root/'artifacts/companion-signed-update-test/signed-update-acceptance.json').read_text())
            self.assertTrue(recorded['actual_sdk_install']);self.assertFalse(recorded['publication_approved'])
            self.assertEqual(recorded['payload_source_commit'],'b'*40);self.assertEqual(recorded['harness_source_commit'],'e'*40)


if __name__=='__main__':unittest.main()
