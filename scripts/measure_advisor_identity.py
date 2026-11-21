"""Small reproducible U2 resolver timing/allocation probe; synthetic-only.

No partition rebuild, DB, network or game. Python timings do not predict Lua.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parent / 'tests'))
import advisor_identity as a
from advisor_identity_support import source_context, observed, candidate, bundle, equivalence, resolver


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    rows = [candidate({'id': 2589, 'synthetic_variant': n}) for n in range(128)]
    game = observed(suffix_id=-15, random_property_id=7)
    proof = equivalence(game, rows[63])
    data = bundle(rows)
    r = resolver(data, [proof])
    expected = {'item_id': 2589, 'variant_key': rows[63]['variant_key']}
    assert r.resolve(game)['identity'] == expected
    runs = []
    for _ in range(3):
        wall, cpu = time.perf_counter(), time.process_time()
        built = resolver(data, [proof])
        construction = {'wall_seconds': time.perf_counter()-wall, 'cpu_seconds': time.process_time()-cpu}
        wall, cpu = time.perf_counter(), time.process_time()
        for _ in range(10000):
            assert built.resolve(game)['identity'] == expected
        runs.append({'construction': construction, 'lookup_10000': {
            'wall_seconds': time.perf_counter()-wall, 'cpu_seconds': time.process_time()-cpu}})
    # Separate allocation pass; timing above excludes tracemalloc overhead.
    tracemalloc.start()
    built = resolver(data, [proof])
    retained, construction_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    for _ in range(10000):
        assert built.resolve(game)['identity'] == expected
    after, lookup_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    measured = ['scripts/advisor_identity.py', 'scripts/measure_advisor_identity.py',
                'scripts/tests/advisor_identity_support.py', 'contracts/market-summary-index-proposal/u2/corpus.json']
    result = {'origin': 'synthetic-only Python; not Forever acceptance', 'python': platform.python_version(),
              'platform': platform.platform(), 'shape': {'item_ids': 1, 'candidates': 128,
                 'trusted_synthetic_equivalences': 1, 'iterations_per_run': 10000, 'timing_runs': 3},
              'candidate_bundle_bytes': len(a.u1.canonical(data)),
              'trusted_equivalence_bytes': len(a.u1.canonical(proof)), 'runs': runs,
              'allocations': {'method': 'tracemalloc; separate pass; excludes pre-existing caller inputs, imports and native allocator/RSS',
                  'construction_retained_bytes': retained, 'construction_peak_bytes': construction_peak,
                  'after_10000_lookups_retained_bytes': after, 'lookup_pass_peak_bytes': lookup_peak},
              'lookup_model': 'One prevalidated per-item hash table and exact game-signature table; no partition or cross-market scan. '
                              'Each call bounds/copies the <=4 KiB identity, serializes it and allocates a small result.',
              'source_sha256': {p: hashlib.sha256((a.u1.ROOT / p).read_bytes()).hexdigest() for p in measured},
              'limitations': ['Synthetic equivalence proves mechanics only; no production/native mapping is authorized.',
                  'Allocation figures exclude the original input objects and process memory; not a client heap budget.',
                  'Lookup timing includes identity validation/serialization/result allocation, excludes file loading and candidate construction.',
                  'All candidates are for one item; construction is bounded by 128 records / 64 KiB and 32 proofs / 64 KiB.']}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
