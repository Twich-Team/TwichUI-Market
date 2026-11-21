import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]


def test_shadow_cli_is_offline_and_preserves_real_excerpt_scope():
    output=subprocess.check_output([sys.executable,str(ROOT/'scripts/compare-pricing-shadow.py'),
                                    '--fixtures',str(ROOT/'contracts/pricing/v1/snapshots.json')],text=True)
    report=json.loads(output)
    assert report['production_outputs_changed'] is False
    assert report['database_access'] is False and report['network_access'] is False
    assert len(report['cases'])==23
    real=[c for c in report['cases'] if c['origin']=='captured_excerpt']
    assert len(real)==4 and not any(c['scope_complete'] for c in real)
    high=next(c for c in report['cases'] if c['case']=='high-outlier')
    assert high['legacy_recent_copper']=='912727' and high['canonical_recent_copper']=='5000'


def test_supplied_snapshot_keeps_variants_isolated(tmp_path):
    market=json.loads((ROOT/'contracts/bridge/v1/canonical-generation.json').read_text())['market']
    source={'schema_version':1,'market':market,'source_kind':'auctions','observed_at':'2026-11-15T12:00:00Z',
            'scope_complete':True,'synthetic':True,'auctions':[
                {'id':1,'item':{'id':2,'bonus_lists':[10]},'quantity':1,'buyout':100},
                {'id':2,'item':{'id':2,'bonus_lists':[20]},'quantity':1,'buyout':900}]}
    path=tmp_path/'snapshot.json';path.write_text(json.dumps(source))
    output=subprocess.check_output([sys.executable,str(ROOT/'scripts/compare-pricing-shadow.py'),'--snapshot',str(path)],text=True)
    rows=json.loads(output)['cases']
    assert len(rows)==2 and len({r['variant_key'] for r in rows})==2
    assert {r['canonical_recent_copper'] for r in rows}=={'100','900'}
