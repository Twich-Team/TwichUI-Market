"""Prepare the frozen legacy algorithms with the same measurement-only harness.

Only the opt-in performance module/examples and Windows measurement feature are
shared. Assert client, cache, synchronizer, archive and publisher stay byte-exact.
"""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='fe854b0'
paths=['desktop/core/src/client.rs','desktop/core/src/cache.rs','desktop/core/src/synchronizer.rs','desktop/core/src/archive/store.rs','desktop/core/src/delivery.rs','desktop/core/src/workshop_summary.rs','backend/market/workshop_summary.py','backend/market/sync_api.py']
target=ROOT/'.local/sync-performance/baseline-source';target.parent.mkdir(parents=True,exist_ok=True)
subprocess.run(['git','worktree','add','--detach',str(target),BASE],cwd=ROOT,check=True)
assert "'Retry-After': '5'" in (target/'backend/market/workshop_summary.py').read_text(), 'Baseline retry policy changed'
sha={p:hashlib.sha256((target/p).read_bytes()).hexdigest() for p in paths}
for p in ['desktop/core/src/performance.rs','desktop/core/examples/sync_performance.rs','desktop/core/examples/delivery_performance.rs']:
 shutil.copyfile(ROOT/p,target/p)
p=target/'desktop/core/Cargo.toml';s=p.read_text();s=s.replace('"Win32_System_Threading",','"Win32_System_Threading", "Win32_System_ProcessStatus",');p.write_text(s)
assert sha=={p:hashlib.sha256((target/p).read_bytes()).hexdigest() for p in paths}
report={'algorithm_baseline':subprocess.check_output(['git','rev-parse',BASE],cwd=ROOT,text=True).strip(),'unmodified_algorithm_sha256':sha,'common_measurement_harness_sha256':hashlib.sha256((ROOT/'desktop/core/src/performance.rs').read_bytes()).hexdigest(),'changes_in_baseline':'measurement module/examples and Windows process-metrics feature only; no algorithm/protocol/cache/durability edits'}
out=ROOT/'artifacts/sync-performance';out.mkdir(parents=True,exist_ok=True);(out/'baseline-source.json').write_text(json.dumps(report,indent=2)+'\n')
print(str(target))
