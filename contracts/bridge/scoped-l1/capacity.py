"""Targeted synthetic sizing only. No game timing, DB, network or publication."""
import json
import hashlib
import platform
import sys
import time
from reference import ROOT, DEFAULT_BUDGET, canonical, digest, project, receipt, sizes, lua_source, Refusal
from build_fixtures import request_for, SESSION
sys.path.insert(0, str(ROOT.parents[2] / 'scripts'))
from bridge_workloads import generate

rows = []
for profile in ('sixty', 'sparse-sixty'):
    for n in (10, 100, 500, 1000):
        source, _ = generate(n, profile)
        request = request_for(source)
        began = time.process_time_ns()
        for _ in range(20):
            digest(request)
        hash_us = (time.process_time_ns() - began) / 20000
        try:
            # Empty policy measures contract feasibility, never bypasses hard bounds.
            g = project(source, request, SESSION, SESSION, budget={})
        except Refusal as e:
            assert e.code == 'capacity'
            rows.append({'variants': n, 'profile': profile, 'result': 'refused_hard_bound',
                         **e.diagnostics, 'selection_hash_cpu_us_mean_20': round(hash_us, 3)})
            continue
        measured = sizes(g, receipt(g))
        assert measured['lua_bytes'] == len(lua_source(g, receipt(g)))
        assert measured['canonical_bytes'] == len(canonical(g))
        exceeded = [k for k, maximum in DEFAULT_BUDGET.items() if measured[k] > maximum]
        rows.append({'variants': n, 'profile': profile, 'result': 'refused_policy' if exceeded else 'eligible_policy',
                     'exceeded_policy': exceeded, 'sizes': measured,
                     'selection_hash_cpu_us_mean_20': round(hash_us, 3),
                     'preflight_exact_length_crosscheck': True})
output = {'origin': 'synthetic', 'python': platform.python_version(),
          'sources_sha256': {str(p.relative_to(ROOT.parents[2])): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                             (ROOT / 'reference.py', ROOT / 'selection.schema.json', ROOT / 'generation-schema3.schema.json', ROOT.parents[2] / 'scripts/bridge_workloads.py')}, 'runtime': 'Python offline sizing, not Lua or Forever timing',
          'budgets': DEFAULT_BUDGET, 'cases': rows}
print(json.dumps(output, indent=2))
