"""Reproducible synthetic U1 scale proof. Temporary files only; no services.

Exact bytes/hashes are deterministic. Timing/RSS are offline Python/Linux
measurements, never Forever acceptance. Run each workload in a fresh subprocess.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time

import advisor_summary as u
from advisor_index_feasibility import generate


def metadata():
    result = generate(0)
    for key in ('records', 'records_sha256', 'record_count', 'generation_id'):
        result.pop(key)
    result.update(format='twichui-market-summary-partitions-u1', generated_at='2026-11-15T12:05:00Z')
    return result


def records(count, *, change=False, skew=False):
    """45,125 variants / 45,124 item IDs; same-item pair, three 11-digit asks."""
    pair = sorted(hashlib.sha256(u.canonical({'id': 10000, 'synthetic_variant': n})).hexdigest()
                  for n in range(2))
    for i in range(count):
        item = 10000 if skew or i < 2 else 9999 + i
        variant = f'{i:064x}' if skew else pair[i] if i < 2 else hashlib.sha256(
            u.canonical({'id': item})).hexdigest()
        yield {'observation_id': '902', 'item_id': item, 'variant_key': variant,
               'current': {'algorithm': 'twichui-pricing-v1', 'complete': True, 'state': 'listed',
                           'arithmetic_status': 'exact', 'supply': 12,
                           'metrics': {'recent_copper': str(99_000_000_001 - i * 3 + (1 if change and i == 0 else 0)),
                                       'market_value_copper': str(99_000_000_002 - i * 3),
                                       'minimum_copper': str(99_000_000_000 - i * 3)}}}


def clocks():
    return time.perf_counter(), time.process_time()


def elapsed(start):
    return {'wall_seconds': time.perf_counter() - start[0], 'cpu_seconds': time.process_time() - start[1]}


def worker(count, skew=False):
    baseline = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    with tempfile.TemporaryDirectory(prefix='advisor-u1-benchmark-') as temp:
        root = Path(temp)
        start = clocks()
        try:
            m = u.write_index(records(count, skew=skew), metadata(), root / 'first')
        except ValueError as error:
            if not skew:
                raise
            assert not (root / 'first').exists()
            return {'records': count, 'scenario': 'same_item_skew', 'refused': str(error),
                    'partial_generation_published': False, 'generation': elapsed(start),
                    'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
        generation = elapsed(start)
        producer_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        start = clocks()
        index = u.Index(root / 'first', expected_generation_id=m['generation_id'])
        open_manifest = elapsed(start)
        start = clocks()
        index.verify_all()
        verify_all = elapsed(start)
        lookup = None
        if count:
            r = next(records(count))
            start = clocks()
            assert index.lookup(r['item_id'], r['variant_key'])['state'] == 'priced'
            cold = elapsed(start)
            start = clocks()
            for _ in range(10000):
                assert index.lookup(r['item_id'], r['variant_key'])['state'] == 'priced'
            warm = elapsed(start)
            lookup = {'cold_partition_and_lookup': cold, 'warm_10000_lookups': warm,
                      'cached_records': len(index.rows), 'partitions_retained': 1}
        rebuilt = u.write_index(records(count), metadata(), root / 'rebuilt')
        assert rebuilt == m
        for path in (root / 'first').iterdir():
            assert path.read_bytes() == (root / 'rebuilt' / path.name).read_bytes()
        modified = u.write_index(records(count, change=True), metadata(), root / 'modified')
        changed = [b for a, b in zip(m['partitions'], modified['partitions']) if a['sha256'] != b['sha256']]
        assert len(changed) == (1 if count else 0)
        # Time-only regeneration honestly changes every age-bearing partition.
        later = metadata()
        later['generated_at'] = '2026-11-15T12:06:00Z'
        aged = u.write_index(records(count), later, root / 'aged')
        age_changed = sum(a['sha256'] != b['sha256'] for a, b in zip(m['partitions'], aged['partitions']))
        return {'records': count, 'scenario': 'all_priced', 'generation_id': m['generation_id'],
                'total_bytes': sum(p.stat().st_size for p in (root / 'first').iterdir()),
                'manifest_bytes': (root / 'first/manifest.json').stat().st_size,
                'partition_count': len(m['partitions']),
                'largest_partition_bytes': max((p['bytes'] for p in m['partitions']), default=0),
                'generation': generation, 'producer_baseline_peak_rss_bytes': baseline,
                'producer_peak_rss_bytes': producer_peak,
                'producer_peak_rss_increase_bytes': max(0, producer_peak - baseline),
                'manifest_open': open_manifest, 'full_integrity_verification': verify_all,
                'lookup': lookup, 'deterministic_rebuild': 'all files byte-identical',
                'one_price_change': {'changed_partitions': len(changed),
                                     'changed_partition_bytes': sum(p['bytes'] for p in changed),
                                     'manifest_changed': modified['generation_id'] != m['generation_id']},
                'generation_time_advanced_60_seconds': {'changed_partitions': age_changed,
                    'reason': 'Tuple age_seconds is relative to generated_at; freshness is never reset by delivery.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--worker', type=int)
    parser.add_argument('--skew', action='store_true')
    args = parser.parse_args()
    if args.worker is not None:
        print(json.dumps(worker(args.worker, args.skew)))
        return
    cases = []
    for count, skew in ((0, False), (5, False), (45125, False), (5000, True)):
        command = [sys.executable, str(Path(__file__).resolve()), '--worker', str(count)]
        if skew:
            command.append('--skew')
        result = subprocess.run(command, check=True, text=True, capture_output=True, timeout=180)
        cases.append(json.loads(result.stdout))
    measured = ['scripts/advisor_summary.py', 'scripts/benchmark_advisor_summary.py',
                'scripts/advisor_index_feasibility.py', 'contracts/market-summary-index-proposal/schema.json',
                'contracts/market-summary-index-proposal/u1/manifest.schema.json']
    report = {'origin': 'synthetic; offline Python/Linux; not Forever or production data',
              'python': platform.python_version(), 'platform': platform.platform(),
              'cpu': platform.processor() or 'not reported', 'samples_per_shape': 1,
              'memory_method': 'Fresh subprocess ru_maxrss, Linux KiB converted to bytes; baseline includes imports. '
                               'Producer peak sampled before reader/rebuilds; delta is high-water growth, not allocation tracing.',
              'shape': 'all priced; 45,125 exact variants / 45,124 item IDs; three distinct 11-digit copper strings, supply 12, age 300',
              'producer_bound': '64 buffered disk spools, one input record and at most one 256 KiB encoded partition; no whole-market input list',
              'source_sha256': {p: hashlib.sha256((u.ROOT / p).read_bytes()).hexdigest() for p in measured},
              'cases': cases,
              'limitations': ['Single-host timings vary; exact bytes and IDs can be reproduced.',
                              'No Lua consumer, game addon loading, frame time, GC or Windows measurements.',
                              'A changed source observation or generated_at can change all age-bearing partitions.',
                              'Incremental result measures changed output content; producer still scans the full supplied stream.',
                              'SHA-256 integrity is not a trusted publisher signature.']}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
