"""Independent approved fixtures plus permutation, scaling and temporal boundaries."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import random

import pytest
from market import canonical_pricing as cp

FIXTURES = Path(__file__).resolve().parents[2] / 'contracts/pricing/v1'
SNAPSHOTS = json.loads((FIXTURES/'snapshots.json').read_text())['cases']
TEMPORAL = json.loads((FIXTURES/'temporal.json').read_text())['cases']
BOUNDARIES = json.loads((FIXTURES/'boundaries.json').read_text())
KEY = 'a'*64
NOW = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)


def rows(case):
    source = case['provenance']['source_kind'] if case['provenance'] else 'auctions'
    result = []
    for row in case['listings']:
        total, unit = row['total_copper'], row['unit_copper']
        if source == 'auctions' and unit is not None:
            total, unit = str(int(unit)*row['quantity']), None
        result.append({**row, 'total_copper': total, 'unit_copper': unit,
                       'item_id': case['item']['id'], 'variant_key': case['variant_key']})
    return source, result


@pytest.mark.parametrize('case', SNAPSHOTS, ids=lambda c:c['id'])
def test_snapshot_conformance(case):
    source, inputs = rows(case)
    got = cp.snapshot(inputs, item_id=case['item']['id'], variant_key=case['variant_key'], source_kind=source)
    expected = case['expected']
    assert got['algorithm'] == cp.ALGORITHM
    assert got['minimum_listing_copper'] == expected['canonical_minimum']
    assert got['recent_copper'] == expected['workshop_recent']
    assert got['quantity_weighted_ask_copper'] == expected['market_recent']
    assert got['supply'] == sum(r['quantity'] for r in inputs)
    if got['distribution']:
        for target, key in [('anchor_copper','anchor'),('q25_copper','q25'),('q50_copper','q50'),('q75_copper','q75')]:
            assert got['distribution'][target] == expected[key]
    assert got['state'] == ('unsupported' if case['id'] in ('above-lua-exact','signed64-maximum')
                            else 'unpriced' if not got['priced_supply'] else 'priced')


def observations(case):
    return [{'observation_id': i+1, 'market_key': 'fixture-market', 'item_id': 2589, 'variant_key': KEY,
             'algorithm': cp.ALGORITHM, 'observed_at': datetime.fromisoformat(p['observed_at'].replace('Z','+00:00')),
             'complete': p['complete'], 'state': p['state'], 'recent_copper': p['unit_copper'],
             'synthetic': True, 'content_id': 'fixture-content-'+str(i)} for i,p in enumerate(case['points'])]


def history(points, **kwargs):
    return cp.history(points, market_key='fixture-market', item_id=2589, variant_key=KEY, as_of=NOW, **kwargs)


@pytest.mark.parametrize('case', TEMPORAL, ids=lambda c:c['id'])
def test_history_conformance(case):
    got = history(observations(case))
    assert got['market_value_copper'] == case['expected']['canonical_market_value']
    assert got['historical_value_copper'] == case['expected']['canonical_historical_value']
    assert got['coverage']['priced_days_60'] == case['expected']['canonical_priced_days_60']
    assert got['history_basis'] == cp.HISTORY_BASIS


@pytest.mark.parametrize('case', BOUNDARIES['quality'], ids=lambda c:c['id'])
def test_quality_conformance(case):
    assert cp.quality(case['input']) == case['expected']


def test_properties_against_independent_fraction_oracle():
    spec = importlib.util.spec_from_file_location('pricing_reference', FIXTURES/'verify.py')
    oracle = importlib.util.module_from_spec(spec); spec.loader.exec_module(oracle)
    rng = random.Random(947203)
    for _ in range(250):
        fixture = copy.deepcopy(SNAPSHOTS[4])
        fixture['listings'] = [{'quantity': rng.randint(1,10000), 'total_copper': str(rng.randint(1,99999999999)),
                                'unit_copper': None, 'bid_copper': None} for _ in range(rng.randint(1,20))]
        fixture['expected'] = SNAPSHOTS[4]['expected']
        expected, _, _ = oracle.snapshot(fixture)
        source, inputs = rows(fixture)
        got = cp.snapshot(inputs, item_id=2589, variant_key=fixture['variant_key'], source_kind=source)
        assert got['recent_copper'] == expected['workshop_recent']
        rng.shuffle(inputs)
        assert cp.snapshot(inputs, item_id=2589, variant_key=fixture['variant_key'], source_kind=source) == got
        assert int(got['minimum_listing_copper']) <= int(got['recent_copper']) <= int(got['distribution']['q50_copper'])


def test_temporal_permutation_watermark_and_id_tie():
    points = observations(TEMPORAL[0])
    later = {**points[-1], 'observation_id': 3, 'recent_copper': '200'}
    points.append(later)
    assert history(points)['days'][-1]['recent_copper'] == '200'
    assert history(list(reversed(points))) == history(points)
    assert history(points, watermark=2)['days'][-1]['recent_copper'] == '120'
    # A newer ID with older chronology must not replace the current close.
    points.append({**later, 'observation_id':4, 'observed_at':NOW-timedelta(hours=1),'recent_copper':'999'})
    assert history(points)['days'][-1]['recent_copper'] == '200'


def test_absence_is_not_missing_and_unchanged_content_is_not_new_content():
    points = observations(TEMPORAL[0])
    points[-1].update(state='absent',recent_copper=None,content_id=points[0]['content_id'])
    got = history(points)
    assert got['coverage']['observed_days_60'] == 2
    assert got['coverage']['priced_days_60'] == 1
    assert got['coverage']['distinct_content_count'] == 1
    assert '2026-11-15' not in got['coverage']['missing_utc_days']
    assert '2026-11-13' in got['coverage']['missing_utc_days']


@pytest.mark.parametrize('field,value', [('variant_key','b'*64),('market_key','other'),('algorithm','asking-v1-provisional'),
                                      ('observed_at',NOW+timedelta(seconds=1)),('observed_at',NOW.replace(tzinfo=None)),
                                      ('synthetic',1),('complete',1),('item_id',True),('recent_copper','01')])
def test_reject_history_identity_version_and_shape(field,value):
    point=observations(TEMPORAL[0])[0]; point[field]=value
    with pytest.raises(ValueError): history([point])


def test_duplicate_observation_rejected():
    point=observations(TEMPORAL[0])[0]
    with pytest.raises(ValueError): history([point,point])


@pytest.mark.parametrize('bad', ['01','-1','1e3','1.5','9223372036854775808',100,True,''])
def test_exact_copper_rejection(bad):
    with pytest.raises(ValueError): cp.copper(bad)


def test_variant_and_listing_semantics():
    source, inputs=rows(SNAPSHOTS[4])
    for changed in [{'variant_key':'b'*64},{'item_id':True},{'quantity':True},{'unit_copper':'1'}]:
        bad=copy.deepcopy(inputs);bad[0].update(changed)
        with pytest.raises(ValueError):cp.snapshot(bad,item_id=2589,variant_key=inputs[0]['variant_key'],source_kind=source)
    assert cp.copper('9007199254740993') == 9007199254740993


def test_legacy_path_is_not_selected_or_mutated():
    from market.pricing import ALGORITHM
    assert ALGORITHM == 'asking-v1-provisional'
    root=Path(__file__).resolve().parents[1]/'market'
    for name in ['app.py','pricing.py','sync_api.py','sync_generation.py','worker.py']:
        assert 'canonical_pricing' not in (root/name).read_text()


def test_half_anchor_and_wide_intermediate_are_exact():
    def row(p,q):return {'item_id':2589,'variant_key':KEY,'quantity':q,'unit_copper':str(p),'total_copper':None,'bid_copper':None}
    half=cp.snapshot([row(2500,5),row(5000,20)],item_id=2589,variant_key=KEY,source_kind='commodities')
    assert half['recent_copper']=='3333'
    # Commodity totals remain signed-64 per listing; quantities produce a wide
    # band accumulator. Split each large quantity into bounded raw totals.
    inputs=[row(50000000000,100000000)]+[row(90000000000,100000000) for _ in range(10)]
    wide=cp.snapshot(inputs,item_id=2589,variant_key=KEY,source_kind='commodities')
    assert wide['recent_copper']=='77878787879'


def test_market_window_coverage_excludes_age_fourteen_even_when_median_is_unchanged():
    got=history(observations(TEMPORAL[3]))
    assert got['coverage']['priced_days_14']==1
    assert got['coverage']['priced_days_60']==2


@pytest.mark.parametrize('find,replace', [
    ('4*cumulative > priced_supply','4*cumulative >= priced_supply'),
    ('if 2*p >= anchor','if 2*p > anchor'),
    ('if 2 * cumulative >= total:','if 2 * cumulative > total:'),
    ('if age < 14:','if age <= 14:'),
    ('if len(hv) >= 3 else None','if len(hv) >= 2 else None'),
    ("if not observation['complete'] or not 0 <= age < 60:","if not 0 <= age < 60:"),
    ("if observation['algorithm'] != ALGORITHM:","if False:"),
])
def test_critical_mutations_are_killed(find,replace):
    import types
    source=Path(cp.__file__).read_text()
    assert source.count(find)==1
    mutant=types.ModuleType('isolated_canonical_mutant')
    exec(compile(source.replace(find,replace),'<disposable pricing mutant>','exec'),mutant.__dict__)
    killed=False
    for c in SNAPSHOTS:
        kind,inputs=rows(c)
        try:
            got=mutant.snapshot(inputs,item_id=c['item']['id'],variant_key=c['variant_key'],source_kind=kind)
            killed |= got['recent_copper']!=c['expected']['workshop_recent']
        except (ValueError,AssertionError):killed=True
    for c in TEMPORAL:
        try:
            got=mutant.history(observations(c),market_key='fixture-market',item_id=2589,variant_key=KEY,as_of=NOW)
            killed |= got['market_value_copper']!=c['expected']['canonical_market_value'] or got['historical_value_copper']!=c['expected']['canonical_historical_value']
        except (ValueError,AssertionError):killed=True
    if '2*p > anchor' in replace:
        inputs=[{'item_id':2589,'variant_key':KEY,'quantity':q,'unit_copper':str(p),'total_copper':None,'bid_copper':None} for p,q in [(2500,5),(5000,20)]]
        killed |= mutant.snapshot(inputs,item_id=2589,variant_key=KEY,source_kind='commodities')['recent_copper']!='3333'
    if 'if False:' in replace:
        p=observations(TEMPORAL[0])[0];p['algorithm']='asking-v1-provisional'
        try:mutant.history([p],market_key='fixture-market',item_id=2589,variant_key=KEY,as_of=NOW)
        except ValueError:pass
        else:killed=True
    if 'if age <= 14:' in replace:
        p=mutant.history(observations(TEMPORAL[3]),market_key='fixture-market',item_id=2589,variant_key=KEY,as_of=NOW)
        killed |= p['coverage']['priced_days_14']!=1
    assert killed,(find,replace)
