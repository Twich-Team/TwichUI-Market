"""Observation-only clock hook around the committed fixed-population replay."""
import inspect,json,os,sys,tempfile
from pathlib import Path
sys.path.insert(0,'/workspace/backend/tests')
import pytest
import test_recovery_replay as replay
from market.db import Base,Session,engine
assert engine.url.database=='market_test'
source=inspect.getsource(replay.test_same_population_replay)
needle='calls.append((provider,item_id));'
assert source.count(needle)==1
clock=[]
# Only observe the existing fake transport; neither policy/response nor clock changes.
source=source.replace(needle,'clock.append((label,step,had_name,had_quality));'+needle)
namespace={**replay.__dict__,'clock':clock}
exec(compile(source,inspect.getsourcefile(replay), 'exec'),namespace)
patch=pytest.MonkeyPatch()
try:
 with tempfile.TemporaryDirectory() as directory:
  namespace['test_same_population_replay'](Session,patch,Path(directory))
finally:patch.undo()
report=json.loads(Path('/tmp/metadata-policy-replay.json').read_text())
for label in ('provider_first','item_centric'):
 events=[(step,had_name,had_quality) for kind,step,had_name,had_quality in clock if kind==label]
 names=[step*61 for step,n,q in events if not n]
 essentials=[step*61 for step,n,q in events if not q]
 report['results'][label].update(first_name_seconds=min(names),last_name_seconds=max(names),last_missing_priority_field_seconds=max(names+essentials))
report.update(container_memory_limit_bytes=201326592,clock_hook='Observation-only insertion in the committed replay fake transport; actual frozen/new worker code, fixed clock, population and responses unchanged.')
Base.metadata.drop_all(engine)
print('FINAL_REPLAY='+json.dumps(report,sort_keys=True))
