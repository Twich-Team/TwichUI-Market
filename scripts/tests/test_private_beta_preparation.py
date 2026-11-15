"""Synthetic private-beta preparation tests, not Windows or owner acceptance."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('private_beta_preparation',ROOT/'scripts/prepare-companion-private-beta.py')
private=importlib.util.module_from_spec(spec);spec.loader.exec_module(private)


def pe_bytes(signed=False):
    value=bytearray(2048);value[:2]=b'MZ';struct.pack_into('<I',value,60,128);value[128:132]=b'PE\0\0'
    struct.pack_into('<H',value,148,224);struct.pack_into('<H',value,152,0x10b);struct.pack_into('<I',value,244,16)
    if signed:struct.pack_into('<II',value,280,1024,128)
    return value


class PrivateBetaPreparation(unittest.TestCase):
    def setUp(self):
        (ROOT/'artifacts').mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='private-beta-gate-test-',dir=ROOT/'artifacts');self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def test_real_pe_security_directory_is_checked_without_running_the_installer(self):
        path=self.root/'synthetic.exe';path.write_bytes(pe_bytes());private.unsigned_pe(path)
        path.write_bytes(pe_bytes(True))
        with self.assertRaisesRegex(ValueError,'unsigned'):private.unsigned_pe(path)
        for raw in [b'MZ'+b'x'*2046,b'x'*2048]:
            path.write_bytes(raw)
            with self.assertRaises(ValueError):private.unsigned_pe(path)

    def test_design_approval_alone_cannot_authorize_beta_preparation(self):
        record=self.root/'owner.json';record.write_text('{"schema_version":1,"owner_statement":"Design approval only"}')
        with patch.object(private,'source_config') as source:
            with self.assertRaisesRegex(ValueError,'authorization'):private.prepare(None,None,record,'b'*40,{},self.root/'output')
            source.assert_not_called()
        self.assertFalse((self.root/'output').exists())

    def test_canonical_public_ci_needs_no_paid_identity_and_never_serializes_a_token(self):
        base={'head_sha':'b'*40,'path':private.WORKFLOWS['windows'],'repository':{'full_name':private.REPO},'status':'completed','conclusion':'success'}
        with patch.dict(os.environ,{'GITHUB_TOKEN':'SYNTHETIC-READ-TOKEN'}):
            with patch.object(private.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(base).encode())):
                result=private.workflow('123',base['path'],'b'*40)
                self.assertNotIn('SYNTHETIC-READ-TOKEN',json.dumps(result))
        for change in [{'head_sha':'d'*40},{'path':'.github/workflows/other.yml'},{'conclusion':'failure'},{'status':'in_progress'}]:
            with patch.object(private.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps({**base,**change}).encode())):
                with self.assertRaises(ValueError):private.workflow('123',base['path'],'b'*40)

    def test_authorized_beta_notice_keeps_other_visual_changes_gated(self):
        config=json.dumps({'version':'2.0.0-beta.1','app':{'windows':[{'devtools':False}]}}).encode()
        for changed in ['web/src/companion.tsx\nweb/src/companion-downloads.ts\n','desktop/ui/styles.css\n','web/src/styles.css\n']:
            with patch.object(private.subprocess,'check_output',side_effect=lambda args,**kwargs:changed if '--name-only' in args else config):
                if 'companion.tsx' in changed:self.assertEqual(private.source_config('b'*40,'c'*40)['version'],'2.0.0-beta.1')
                else:
                    with self.assertRaisesRegex(ValueError,'approval'):private.source_config('b'*40,'c'*40)

    def fixture(self):
        # This shared policy fixture is synthetic; a positive gate test does not
        # attest actual Windows, GitHub or human action.
        import pytest
        sys.path.insert(0,str(ROOT/'backend/tests'))
        from test_companion_private_beta import fixture_beta,change_evidence
        monkeypatch=pytest.MonkeyPatch();self.addCleanup(monkeypatch.undo)
        _,directory,manifest,_=fixture_beta(self.root,monkeypatch)
        asset=directory/manifest['filename'];asset.write_bytes(pe_bytes())
        change_evidence(directory,manifest,'windows-signature.json',{'sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'bytes':asset.stat().st_size})
        change_evidence(directory,manifest,'launch-metrics.json',{'installer_bytes':asset.stat().st_size})
        digest=hashlib.sha256(asset.read_bytes()).hexdigest()
        change_evidence(directory,manifest,'signed-update-acceptance.json',{'installer_sha256':digest})
        change_evidence(directory,manifest,'owner-release-approval.json',{'installer_sha256':digest})
        Path(str(asset)+'.sig').write_text(manifest['updater_signature'])
        return directory,asset,manifest

    def test_complete_private_candidate_keeps_original_receipts_and_cannot_overwrite(self):
        directory,asset,manifest=self.fixture();output=self.root/'prepared'
        with patch.object(private,'source_config',return_value={'version':manifest['version']}),patch.object(private,'workflow',side_effect=lambda run,path,source:next(value for value in manifest['ci'].values() if value['path']==path)):
            result=private.prepare(asset,directory,directory/'owner-release-approval.json','b'*40,{name:value['id'] for name,value in manifest['ci'].items()},output)
            receipt=json.loads((result/'manifest.json').read_text())
            self.assertFalse(receipt['acceptance']['tray']);self.assertEqual(receipt['updates'],'signed')
            self.assertEqual((result/manifest['filename']).read_bytes(),asset.read_bytes())
            for name in private.EVIDENCE:self.assertEqual((result/name).read_bytes(),(directory/name).read_bytes())
            with self.assertRaisesRegex(ValueError,'overwrites'):private.prepare(asset,directory,directory/'owner-release-approval.json','b'*40,{name:value['id'] for name,value in manifest['ci'].items()},output)

    def test_wrong_installed_or_signature_evidence_leaves_no_admissible_prepared_bundle(self):
        directory,asset,manifest=self.fixture();path=directory/'installed-smoke.json';record=json.loads(path.read_text());record['updater_disabled']=True;path.write_text(json.dumps(record))
        output=self.root/'prepared'
        with patch.object(private,'source_config',return_value={'version':manifest['version']}),patch.object(private,'workflow',side_effect=lambda run,path,source:next(value for value in manifest['ci'].values() if value['path']==path)):
            with self.assertRaises(ValueError):private.prepare(asset,directory,directory/'owner-release-approval.json','b'*40,{name:value['id'] for name,value in manifest['ci'].items()},output)
        self.assertFalse((output/manifest['version']).exists());self.assertEqual(list(output.iterdir()),[])


if __name__=='__main__':unittest.main()
