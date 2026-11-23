"""Windows-only acceptance of the private tools inside the existing native fixture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def verify(base, game, count, binary):
    assert os.name == 'nt' and os.environ.get('GITHUB_ACTIONS') == 'true'
    copies = base / 'private-market-source-fixture'
    caches = [p for p in base.glob('workshop-summary-*') if p.is_dir() and (p/'current.json').is_file()]
    assert len(caches) == 1
    shutil.copytree(caches[0], copies)
    snapshot = base / 'private-frozen-source'
    subprocess.run([sys.executable, str(ROOT/'scripts/prepare-private-current-snapshot.py'),
                    '--cache-copy', str(copies), '--configuration-copy', str(base/'workshop-delivery-v1.json'),
                    '--out', str(snapshot)], check=True, capture_output=True, text=True)
    private = base / 'team.twich.market.dev'
    private.mkdir()
    sid = subprocess.check_output(['powershell', '-NoProfile', '-Command',
                                  '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'], text=True).strip()
    subprocess.run(['icacls', str(private), '/reset'], check=True, capture_output=True)
    subprocess.run(['icacls', str(private), '/inheritance:r', '/grant:r', f'*{sid}:(OI)(CI)F',
                    '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'], check=True, capture_output=True)
    shutil.copyfile(base/'workshop-delivery-v1.json', private/'workshop-delivery-v1.json')
    marker = game / '.twichui-private-native-test'
    root = game / 'Interface/AddOns/TwichUI_MarketData/Data.lua'
    before = hashlib.sha256(root.read_bytes()).hexdigest()
    def invoke():
        return subprocess.run([str(binary.resolve()), str(private), str(snapshot), str(count)],
                              capture_output=True, text=True, timeout=90)
    # A normal/unguarded destination cannot be used by the private helper.
    refused = invoke()
    assert refused.returncode != 0 and hashlib.sha256(root.read_bytes()).hexdigest() == before
    marker.write_bytes(b'PRIVATE VM ONLY\n')
    subprocess.run(['powershell','-NoProfile','-File',str(ROOT/'scripts/select-private-current-layout.ps1'),
                    '-Layout',str(count),'-PrivateGameRoot',str(game),'-DevAppData',str(private)],
                   check=True,capture_output=True,text=True)
    valid = invoke()
    assert valid.returncode == 0, valid.stderr
    result = json.loads(valid.stdout)
    assert not result['changed'] and result['offline'] and result['layout'] == count
    assert hashlib.sha256(root.read_bytes()).hexdigest() == before
    lifecycle = None
    cap = json.loads((game/'Interface/AddOns/TwichUI_Workshop/MarketDelivery.json').read_text(encoding='utf-8-sig'))
    if count == 32 and 'container_packaging_version' not in cap:
        check = subprocess.run([str(binary.resolve()), str(private), str(snapshot), str(count), '--verify-container-lifecycle'],
                               capture_output=True, text=True, timeout=90)
        assert check.returncode == 0, check.stderr
        lifecycle = json.loads(check.stdout)
        assert lifecycle['container_lifecycle_verified'] and hashlib.sha256(root.read_bytes()).hexdigest() == before
    # Same metadata but damaged source must fail before any game publication.
    part = snapshot / 'parts/00.json'
    original = part.read_bytes(); part.write_bytes(b'[]')
    refused = invoke()
    assert refused.returncode != 0 and hashlib.sha256(root.read_bytes()).hexdigest() == before
    part.write_bytes(original)
    return {'fixture_synthetic': True, 'real_game': False, 'private_marker_enforced': True,
            'native_validation_enforced': True, 'same_layout_no_change': True,
            'isolated_endpoint_401_200_304': True, 'source_generation': result['generation'], 'windows_container_lifecycle': lifecycle}
