"""Repeat actual native HTTP -> durable SQLite sync against explicit market_test.

Controls are supplied only by sync_perf_api; never point this at production.
No credentials, cursors or item values are written to the reports.
"""
import argparse, json, os, subprocess, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--label', required=True)
p.add_argument('--limits', default='50,100')
p.add_argument('--runs', type=int, default=3)
args = p.parse_args()
assert 1 <= args.runs <= 5 and args.label.replace('-', '').isalnum()
out = ROOT / 'artifacts/sync-performance'
out.mkdir(parents=True, exist_ok=True)
fixture = json.loads((ROOT / '.local/sync-performance/production-summary-slice.json').read_bytes())
targets = sorted(o['id'] for o in fixture['observations'] if o['id'] > fixture['full_target'])
assert len(targets) >= 2

def control(path, post=False):
    r = urllib.request.Request('http://127.0.0.1:18542/__sync_perf/' + path,
                               method='POST' if post else 'GET')
    with urllib.request.urlopen(r, timeout=30) as response:
        return json.load(response)

results = []
for limit in map(int, args.limits.split(',')):
    assert 1 <= limit <= 100
    for repeat in range(args.runs):
        control('reset', True)
        cache = f'{args.label}-{limit}-{repeat}.sqlite'
        for suffix in ['', '-wal', '-shm']:
            (out / (cache + suffix)).unlink(missing_ok=True)
        for scenario in ['full', 'unchanged', 'incremental', 'unchanged_advance']:
            if scenario == 'incremental': control(f'advance/{targets[0]}', True)
            if scenario == 'unchanged_advance': control(f'advance/{targets[-1]}', True)
            control('report')
            cmd = ['docker', 'run', '--rm', '--network', 'container:twichui-sync-perf-api',
                '--cap-drop', 'ALL', '--cpus', '2', '--memory', '1g', '--pids-limit', '256',
                '--log-opt', 'max-size=5m', '--mount', f'type=bind,src={ROOT},dst=/work',
                '--env-file', str(ROOT / '.local/sync-performance/fixture.env'),
                '-e', 'SYNC_PERF_SERVER=http://127.0.0.1:8000',
                '-e', f'SYNC_PERF_CACHE=/work/artifacts/sync-performance/{cache}',
                '-e', f'SYNC_PERF_LIMIT={limit}', 'rust:1-slim-bookworm',
                '/work/desktop/target/release/examples/sync_performance']
            result = json.loads(subprocess.check_output(cmd, text=True, timeout=180))
            result.update(label=args.label, scenario=scenario, repeat=repeat,
                          server=control('report'))
            results.append(result)
            (out / (args.label + '.json')).write_text(json.dumps(results, indent=2) + '\n')
            print(json.dumps({k: result[k] for k in ['label','scenario','repeat','page_limit','seconds','item_count','cache_values_sha256']}), flush=True)
