#!/usr/bin/env python3
"""Bounded synthetic CPU/allocation probe; no database, network or activation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time
import tracemalloc
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shadow', ROOT/'scripts/compare-pricing-shadow.py')
shadow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shadow)


def main():
    key = 'a'*64
    rows = [{'item_id':2589, 'variant_key':key, 'quantity':i%20+1,
             'total_copper':str((5000+i%32)*(i%20+1)), 'unit_copper':None,
             'bid_copper':None} for i in range(150000)]
    legacy_rows = [SimpleNamespace(quantity=r['quantity'], buyout=int(r['total_copper']), unit_price=None) for r in rows]
    old = shadow.legacy_calculator()
    operations = {'legacy_prevalidated_summary':lambda:old(legacy_rows),
                  'canonical_validation_and_summary':lambda:shadow.canonical.snapshot(rows,item_id=2589,variant_key=key,source_kind='auctions')}
    samples = {name:[] for name in operations}
    results = {}
    for round_id in range(3):
        for name in (list(operations) if round_id%2 == 0 else list(reversed(operations))):
            wall, cpu = time.perf_counter(), time.process_time()
            results[name] = operations[name]()
            samples[name].append({'wall_ms':round((time.perf_counter()-wall)*1000,3),
                                  'cpu_ms':round((time.process_time()-cpu)*1000,3)})
    measurements = {}
    for name, operation in operations.items():
        tracemalloc.start()
        operation()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        walls = [r['wall_ms'] for r in samples[name]]
        measurements[name] = {'samples':samples[name], 'median_wall_ms':statistics.median(walls),
                              'median_cpu_ms':statistics.median(r['cpu_ms'] for r in samples[name]),
                              'wall_spread_percent':round(100*(max(walls)-min(walls))/statistics.median(walls),2),
                              'peak_auxiliary_traced_bytes':peak}
    assert str(results['legacy_prevalidated_summary']['recent_price']) == results['canonical_validation_and_summary']['quantity_weighted_ask_copper']
    print(json.dumps({'case':'synthetic 150000 auctions, one exact variant, 32 price tiers, quantities 1..20',
        'origin':'synthetic', 'rounds':3,
        'measurement':'interleaved legacy/canonical order; input allocation excluded; other verification processes active',
        'scope_difference':'legacy takes prevalidated rows; canonical includes strict identity/type/range validation',
        'no_speedup_or_client_performance_claim':True,'results':measurements,
        'legacy_recent_copper':str(results['legacy_prevalidated_summary']['recent_price']),
        'canonical_recent_copper':results['canonical_validation_and_summary']['recent_copper'],
        'canonical_source_sha256':hashlib.sha256((ROOT/'backend/market/canonical_pricing.py').read_bytes()).hexdigest()},indent=2))


if __name__ == '__main__': main()
