"""Real offline signature + store rehearsal inside a disposable no-network container.

This is a signed text fixture, NOT Windows Authenticode or release acceptance.
All files stay in this process's temporary directory. No live store/database.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime,timezone
from market.companion_releases import REQUIRED_TESTS
from market.release_publisher import publish,pointer

root=Path(__file__).resolve().parents[1]
fixtures=root/'desktop'/'src-tauri'/'tests'/'fixtures'
with tempfile.TemporaryDirectory(prefix='companion-publisher-fixture-') as temporary:
    temporary=Path(temporary);bundle=temporary/'incoming'/'2.0.0';bundle.mkdir(parents=True)
    key=(fixtures/'synthetic-public.key').read_text().strip()
    os.environ.update(COMPANION_UPDATER_PUBLIC_KEY=key,COMPANION_PUBLISHER_THUMBPRINT='A'*40)
    payload=(fixtures/'synthetic-update.txt').read_bytes()
    filename='TwichUI-Market-Companion-2.0.0-windows-x64.exe'
    (bundle/filename).write_bytes(payload)
    receipt={'schema_version':1,'channel':'stable','version':'2.0.0','filename':filename,'bytes':len(payload),
        'sha256':hashlib.sha256(payload).hexdigest(),'source_commit':'b'*40,'workflow_run_id':123,
        'published_at':datetime.now(timezone.utc).isoformat(),'publisher_thumbprint':'A'*40,'authenticode_status':'Valid',
        'updater_public_key_sha256':hashlib.sha256(key.encode()).hexdigest(),
        'updater_signature':(fixtures/'synthetic-update.txt.sig').read_text().strip(),
        'visual_approval_commit':'c'*40,'acceptance':dict.fromkeys(REQUIRED_TESTS,True),
        'notes':'SYNTHETIC SIGNED TEXT fixture; no Windows or owner release acceptance is implied.'}
    (bundle/'manifest.json').write_text(json.dumps(receipt))
    store=temporary/'store'
    result=publish(store,bundle,'synthetic-owner')
    assert result['changed'] and pointer(store)=='2.0.0'
    assert publish(store,bundle,'synthetic-owner')['changed'] is False
    assert (store/'2.0.0'/filename).read_bytes()==payload
    assert len(list((store/'audit').glob('*.json')))==2
    print(json.dumps({'synthetic_only':True,'actual_offline_signature_verifier':True,'atomic_publication':True,
        'immutable_copy':True,'idempotent_retry':True,'durable_intent_and_commit_audit':True,'temporary_store_destroyed_on_exit':True}))
