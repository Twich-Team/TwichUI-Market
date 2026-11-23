"""Bounded A/B/C packaging experiment using the existing publisher and benchmark.

The native thirteen-addon publisher produces the immutable source once. Trials B
and C regroup those exact logical assignment lines (no re-encoding); an independent
non-executing parser requires identical decompressed data/proofs in all layouts.
Only the physical lookup divisor changes in disposable reader snapshots. This is
selection evidence, not native publication/migration acceptance for a new layout.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from container_artifact import read as inspect
from prepared_fixture_driver import installation, run as native

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(root):
    paths = ['TwichUI_Workshop/Containers.lua', 'TwichUI_Workshop/Prepared.lua',
             'TwichUI_Workshop/Summary.lua', 'TwichUI_Workshop/Pricing.lua',
             'TwichUI_Workshop/OpportunityEngine.lua', 'tests/bench_market_opportunities.lua']
    return {p: sha(root / p) for p in paths if (root / p).exists()}


def revision(root):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--addon-root', type=Path, required=True)
    p.add_argument('--baseline-addon-root', type=Path, required=True)
    p.add_argument('--rust-test-driver', type=Path, required=True)
    p.add_argument('--native-codec', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--reps', type=int, default=30)
    p.add_argument('--records', type=int, choices=[16384, 35116], default=16384,
                   help='Original comparable fixture or observed production cardinality; both synthetic')
    p.add_argument('--recipes', type=int, nargs='+', default=[120, 1000, 5000])
    p.add_argument('--view', choices=['session', 'ui'], default='session')
    p.add_argument('--scenario', choices=['none', 'reopen'], default='none')
    a = p.parse_args()
    assert 1 <= a.reps <= 40 and set(a.recipes) <= {120, 1000, 5000}
    a.out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.addon_root / 'tools/experiments'))
    from market_game_ready import build
    from measure_game_ready import numeric_metrics
    sys.path.insert(0, str(ROOT / 'backend'))
    os.environ.setdefault('DATABASE_URL', 'sqlite://')
    from market import workshop_prepared as producer

    identities = {str(root): fingerprint(root) for root in [a.addon_root, a.baseline_addon_root]}
    harness = {p: sha(ROOT / p) for p in ['scripts/compare-current-containers.py',
                'scripts/bench_workshop_prepared.lua', 'scripts/container_artifact.py',
                'scripts/prepared_fixture_driver.py', 'scripts/codec_zlib_offline.c']}
    report = dict(synthetic=True, real_client=False, host=platform.platform(),
                  market_commit=revision(ROOT), addon_commit=revision(a.addon_root),
                  baseline_addon_commit=revision(a.baseline_addon_root),
                  sources=identities, harness=harness, native_driver_sha256=sha(a.rust_test_driver),
                  native_codec_sha256=sha(a.native_codec), repetitions=a.reps,
                  clock='Lua os.clock actual CPU; perf_counter actual process elapsed; scheduler seconds modeled at 60Hz',
                  caches='fresh Lua process and cold reader/pricing caches; warm filesystem cache; one discarded warmup per case',
                  codec='offline system zlib/OpenSSL, not native Forever',
                  selection_only_regrouping=True, view=a.view, scenario=a.scenario, cases=[])

    def save():
        (a.out / 'benchmark.json').write_text(json.dumps(report, indent=2) + '\n')

    save()
    with tempfile.TemporaryDirectory(prefix='prepared-campaign-') as directory:
        temp = Path(directory)
        build(ROOT, temp / 'fixture', a.records, 60, 'mixed', counts=())
        source = temp / 'fixture/upstream.json'
        value = json.loads(source.read_bytes())
        h = value['manifest']
        value['prepared'] = producer.prepare(h, {int(k): v for k, v in value['parts'].items()}, 32)[0]
        report.update(fixture_sha256=sha(source), source_generation=h['generation_id'], records=h['record_count'])
        publications = {}
        for packed in [False, True]:
            base = temp / ('prepared-fixture-packed' if packed else 'prepared-fixture-baseline')
            base.mkdir()
            game = installation(base, a.addon_root, 32, containers=packed)
            path = base / 'source.json'
            path.write_text(json.dumps(value, separators=(',', ':')))
            result = native(a.rust_test_driver, base, dict(server='http://127.0.0.1:1/',
                            account_id=1, market_id=h['market']['server_market_id'], source=str(path)))
            assert result['ready']
            publications[13 if packed else 193] = game / 'Interface/AddOns'
        expected = inspect(publications[13], 'A', h['generation_id'], 2)
        readers = {193: a.baseline_addon_root, 13: a.addon_root}
        for count in [4, 8]:
            footprint = 1 + 2 * (count + 4)
            destination = temp / f'publication-{footprint}'
            shutil.copytree(publications[13], destination)
            for bank in ['A', 'B']:
                lines = []
                for group in range(2):
                    folder = destination / f'TwichUI_MarketCurrentContainer{bank}{group:02}'
                    lines.extend((folder / 'Data.lua').read_text().splitlines()[1:])
                    shutil.rmtree(folder)  # disposable, generated fixture only
                for group in range(count):
                    folder = destination / f'TwichUI_MarketCurrentContainer{bank}{group:02}'
                    folder.mkdir()
                    selected = [line for line in lines if int(re.search(r'\["[AB]([0-9]{2})"\]', line)[1]) // (32 // count) == group]
                    (folder / 'Data.lua').write_text('TwichUIMarketCompressedCurrent = TwichUIMarketCompressedCurrent or {}\n' + ''.join(line + '\n' for line in selected))
            assert inspect(destination, 'A', h['generation_id'], count) == expected
            publications[footprint] = destination
            reader = temp / f'reader-{footprint}'
            reader.mkdir()
            for entry in a.addon_root.iterdir():
                if entry.name in ('.git', '.local', 'test-output'):
                    continue
                if entry.name != 'TwichUI_Workshop':
                    (reader / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
            workshop = reader / 'TwichUI_Workshop'
            workshop.mkdir()
            for entry in (a.addon_root / 'TwichUI_Workshop').iterdir():
                if entry.name == 'Containers.lua':
                    original = entry.read_text()
                    assert original.count('math.floor(bucket/16)') == 1
                    (workshop / entry.name).write_text(original.replace('math.floor(bucket/16)', f'math.floor(bucket/(kind==\'Current\'and {32//count} or 16))'))
                else:
                    (workshop / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
            readers[footprint] = reader
        report['reader_fingerprints'] = {str(k): fingerprint(v) for k, v in readers.items()}
        report['logical_streams_identical'] = True
        for footprint, reader in readers.items():
            for recipes in a.recipes:
                case = dict(packaging=footprint, recipes=recipes, samples=[])
                report['cases'].append(case)
        # Interleave fixed-seed order so a changing host cannot favor a layout.
        randomizer = random.Random(20261123)
        for repeat in range(a.reps + 1):
            order = list(report['cases'])
            randomizer.shuffle(order)
            for case in order:
                footprint, recipes = case['packaging'], case['recipes']
                config = temp / 'bench.json'
                config.write_text(json.dumps(dict(publication=str(publications[footprint]), layout=32,
                     history_probe=True, native_codec=str(a.native_codec) if footprint != 193 else None)))
                snapshot = temp / 'oracle.bin'
                command = ['lua5.1', 'tests/bench_market_opportunities.lua', 'opps', a.view,
                           str(recipes), '60', '3', '1', 'off', a.scenario, 'normal', '20',
                           str(ROOT / 'scripts/bench_workshop_prepared.lua'), str(config)]
                began = time.perf_counter()
                proc = subprocess.run(command, cwd=readers[footprint], env=dict(os.environ,
                      BENCH_ORACLE_SNAPSHOT=str(snapshot)), text=True, capture_output=True, timeout=300)
                if proc.returncode:
                    case.update(status='failed', stderr=proc.stderr, returncode=proc.returncode)
                    save()
                    raise RuntimeError(f'Failed {footprint}/{recipes}; see retained report')
                result = json.loads(proc.stdout)
                result['process_elapsed_seconds'] = time.perf_counter() - began
                result['result_sha256'] = sha(snapshot)
                assert result['oracle_passed'] and result['warm_crafts'] == 0 and result['warm_record_calls'] == 0 and result['warm_estimator_reused']
                if repeat:
                    case['samples'].append(result)
                    case['metrics'] = numeric_metrics(case['samples'])
                save()
                print(json.dumps(dict(repeat=repeat, packaging=footprint, recipes=recipes,
                      cpu_ms=result['cpu_ms'], worst_load_ms=result['prepared_worst_load_ms'],
                      worst_callback_ms=result['worst_callback_ms'])), flush=True)
        hashes = {}
        for case in report['cases']:
            values = {s['result_sha256'] for s in case['samples']}
            assert len(values) == 1
            if case['recipes'] in hashes:
                assert hashes[case['recipes']] == values
            hashes[case['recipes']] = values
            case['status'] = 'measured'
        assert identities == {str(root): fingerprint(root) for root in [a.addon_root, a.baseline_addon_root]}
        assert harness == {p: sha(ROOT / p) for p in harness}
        report.update(economic_results_equal=True, source_unchanged=True)
        save()


if __name__ == '__main__':
    main()
