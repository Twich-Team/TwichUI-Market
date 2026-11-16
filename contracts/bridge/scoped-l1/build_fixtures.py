"""Deterministic synthetic conformance inputs. Expectations live separately in tests."""
import copy
import json
import sys
from pathlib import Path
from reference import ROOT, v1, canonical, digest, project, receipt, identities, seal
sys.path.insert(0, str(ROOT.parents[2] / 'scripts'))
from bridge_workloads import generate


def request_for(source, records=None):
    return {'format': 'twichui-market-selection', 'contract_version': 1, 'expected_schema_version': 3,
            'issuer_id': source['issuer_id'], 'market': source['market'], 'scope_type': 'explicit_variants',
            'variants': identities(source['records'] if records is None else records),
            'history_from_day': source['coverage']['history_from_day'],
            'history_through_day': source['coverage']['history_through_day'],
            'pricing_algorithm': source['pricing_algorithm'], 'history_basis': source['history_basis'],
            'profile': 'daily_research_v1'}


SESSION = {'origin': 'https://synthetic.invalid/', 'account_id': 1, 'device_id': 2}


def examples():
    source, _ = generate(6, 'two-gap')
    # Item 10000 historical-only; 10001/10002 independently known 100 copper;
    # item 10003 bid-only; 10004 ordinary; 10005 intentionally not selected.
    bid = source['records'][3]
    for d in bid['daily']:
        d.update(minimum_copper=None, recent_copper=None, priced_supply=0)
    bid['current']['metrics'] = dict.fromkeys(bid['current']['metrics'])
    bid['current']['priced_supply'] = 0
    bid['current']['coverage'].update(priced_days_14=0, priced_days_60=0)
    bid['distribution'], bid['distribution_status'] = None, 'unavailable'
    source = v1.seal(source)
    v1.validate(source)
    request = request_for(source, source['records'][:5])
    good = project(source, request, SESSION, SESSION)
    partial = json.loads((ROOT.parent / 'v1/partial-unknown-generation.json').read_text())
    unknown_request = request_for(partial)
    unknown = project(partial, unknown_request, SESSION, SESSION)
    shorter = copy.deepcopy(request)
    shorter['history_from_day'] = '2026-11-15'
    alternate = project(source, shorter, SESSION, SESSION)
    large = copy.deepcopy(good)
    large['records'][1]['current']['metrics']['quantity_weighted_ask_copper'] = '9223372036854775807'
    large['scope']['record_sha256'] = [digest(r) for r in large['records']]
    large = seal(large)
    return {'large-money-scoped.json': large, 'source.json': source, 'selection.json': request, 'scoped.json': good,
            'receipt.json': receipt(good), 'unknown-source.json': partial,
            'unknown-selection.json': unknown_request, 'unknown-scoped.json': unknown,
            'short-window-selection.json': shorter, 'short-window-scoped.json': alternate,
            'legacy-schema2.json': json.loads((ROOT.parent / 'v1/source-canonical-generation.json').read_text())}


if __name__ == '__main__':
    target = ROOT / 'fixtures'
    target.mkdir(exist_ok=True)
    for name, value in examples().items():
        (target / name).write_bytes(canonical(value) + b'\n')
    print('Wrote 11 deterministic synthetic fixture documents')
