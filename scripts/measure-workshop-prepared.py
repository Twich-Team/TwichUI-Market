"""Separate opt-in native-publication / production-Opportunities comparison.
Reuses PR127 fixtures, full-field oracle and benchmark; never a routine test group.
"""
import argparse,hashlib,importlib.util,json,os,platform,statistics,subprocess,sys,tempfile,time
from pathlib import Path
from prepared_fixture_driver import installation,run as native
ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--addon-root',type=Path,required=True);p.add_argument('--rust-test-driver',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--recipes',type=int,nargs='+',default=[120,500,1000,5000]);p.add_argument('--reps',type=int,choices=range(1,6),default=3);p.add_argument('--layouts',type=int,nargs='+',choices=[64,16,32],default=[64,16,32]);p.add_argument('--view',choices=['session','ui'],default='session');p.add_argument('--history-probe',action='store_true');p.add_argument('--scenario',choices=['none','reopen'],default='none')
 p.add_argument('--containers',action='store_true',help='Compare the 193-addon baseline with the fixed 13-addon transport; both use 32 current partitions')
 p.add_argument('--baseline-addon-root',type=Path);p.add_argument('--native-codec',type=Path,help='Offline system-zlib adapter, never actual Forever timing')
 a=p.parse_args();a.addon_root=a.addon_root.resolve();a.out.mkdir(parents=True,exist_ok=True)
 sys.path.insert(0,str(a.addon_root/'tools/experiments'));from measure_game_ready import numeric_metrics
 from market_game_ready import build
 sys.path.insert(0,str(ROOT/'backend'));os.environ.setdefault('DATABASE_URL','sqlite://')
 from market import workshop_prepared as producer
 def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
 def revision(root):return subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
 files=['desktop/core/src/workshop_containers.rs','scripts/codec_zlib_offline.c','scripts/measure-workshop-prepared.py','scripts/bench_workshop_prepared.lua','desktop/core/src/workshop_prepared.rs','desktop/core/src/workshop_summary.rs','desktop/core/src/workshop_prepared_tests.rs','backend/market/workshop_prepared.py']
 addon_files=['TwichUI_Workshop/Containers.lua','TwichUI_Workshop/Prepared.lua','TwichUI_Workshop/Summary.lua','TwichUI_Workshop/Pricing.lua','TwichUI_Workshop/OpportunityEngine.lua','TwichUI_Workshop/Session.lua','tests/bench_market_opportunities.lua']
 identity={f:sha(ROOT/f)for f in files};identity.update({'addon/'+f:sha(a.addon_root/f)for f in addon_files})
 report=dict(synthetic=True,real_game=False,market_commit=revision(ROOT),addon_commit=revision(a.addon_root),market_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),addon_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=a.addon_root,text=True)),source_sha256=identity,native_driver_sha256=sha(a.rust_test_driver),host=platform.platform(),cpu=platform.processor(),clock='Lua CPU os.clock; modeled After minimum 60Hz frame; warm filesystem cache, fresh Lua process; root admission excluded identically',repeats=a.reps,discarded_warmups=1,history_days=60,view=a.view,cases=[])
 cpuinfo=Path('/proc/cpuinfo');report['cpu']=next((line.split(':',1)[1].strip()for line in cpuinfo.read_text().splitlines()if line.startswith('model name')),report['cpu'])if cpuinfo.exists()else report['cpu']
 def save():(a.out/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
 with tempfile.TemporaryDirectory(prefix='prepared-campaign-')as directory:
  temp=Path(directory)
  if a.source:source=a.source.resolve()
  else:
   fixture=temp/'source';build(ROOT,fixture,16384,60,'mixed',counts=());source=fixture/'upstream.json'
  source_value=json.loads(source.read_bytes());h=source_value['manifest'];assert len(h['observations'])==60
  report.update(fixture_sha256=sha(source),records=h['record_count'],fixture_source_generation=h['generation_id']);save()
  plans=[(layout,a.addon_root,False)for layout in a.layouts]
  if a.containers:
   assert a.baseline_addon_root and a.native_codec
   plans=[(32,a.baseline_addon_root.resolve(),False),(32,a.addon_root,True)]
   report['codec']='offline system zlib/OpenSSL; not native Forever'
   report['baseline_addon_commit']=revision(a.baseline_addon_root)
   report['baseline_source_sha256']={f:sha(a.baseline_addon_root/f)for f in addon_files if (a.baseline_addon_root/f).exists()}
   report['offline_codec_sha256']=sha(a.native_codec)
  for layout,reader,containers in plans:
   with tempfile.TemporaryDirectory(prefix='prepared-fixture-')as fixture_dir:
    base=Path(fixture_dir);game=installation(base,reader,None if layout==64 else layout,containers=containers)
    value=dict(source_value)
    if layout!=64:value['prepared']=producer.prepare(h,{int(k):v for k,v in value['parts'].items()},layout)[0]
    input_file=base/'source.json';input_file.write_text(json.dumps(value,separators=(',',':')))
    began=time.perf_counter();publication=native(a.rust_test_driver,base,dict(server='http://127.0.0.1:1/',account_id=1,market_id=h['market']['server_market_id'],source=str(input_file)))
    assert publication['ready'];native_ms=(time.perf_counter()-began)*1000
    config=base/'bench.json';config.write_text(json.dumps(dict(publication=str(game/'Interface/AddOns'),layout=layout,history_probe=a.history_probe,native_codec=str(a.native_codec.resolve())if containers else None)))
    for count in a.recipes:
     case=dict(layout=layout,packaging=13 if containers else (193 if layout==32 else None),recipes=count,native_validation_publication_ms=native_ms,samples=[]);report['cases'].append(case);save()
     for repeat in range(a.reps+1):
      snapshot=base/'oracle.bin';env=dict(os.environ,BENCH_ORACLE_SNAPSHOT=str(snapshot));command=['lua5.1','tests/bench_market_opportunities.lua','opps',a.view,str(count),'60','3','1','off',a.scenario,'off','20',str(ROOT/'scripts/bench_workshop_prepared.lua'),str(config)]
      start=time.perf_counter();proc=subprocess.run(command,cwd=reader,env=env,capture_output=True,text=True,timeout=300)
      if proc.returncode:
       case.update(status='failed',stderr=proc.stderr[:4000]);save();raise RuntimeError('Production benchmark failed; see report')
      result=json.loads(proc.stdout);result['process_elapsed_seconds']=time.perf_counter()-start;result['result_sha256']=sha(snapshot)
      assert result['oracle_passed']and result['warm_crafts']==0 and result['warm_record_calls']==0 and result['warm_estimator_reused']
      if repeat:case['samples'].append(result)
     case.update(status='measured',metrics=numeric_metrics(case['samples']));save();print(json.dumps(dict(layout=layout,recipes=count,cpu_ms=case['metrics']['cpu_ms']['median'],settlement=case['metrics']['opportunities_settlement_model_seconds']['median'])),flush=True)
  hashes={}
  for case in report['cases']:
   n=case['recipes'];values={s['result_sha256']for s in case['samples']};assert len(values)==1
   if n in hashes:assert values==hashes[n]
   hashes[n]=values
  report['economic_results_equal']=True
  report['packaging_comparison']=a.containers
  control=next((c for c in report['cases']if c['layout']==64 and c['recipes']==5000),None)
  report['dense_regression_limit']=.15
  if control:
   report['dense_comparisons']={str(c['layout']):c['metrics']['cpu_ms']['median']/control['metrics']['cpu_ms']['median']-1 for c in report['cases']if c['recipes']==5000 and c['layout']!=64}
   report['dense_passed']=all(v<=.15 for v in report['dense_comparisons'].values())
  assert identity=={**{f:sha(ROOT/f)for f in files},**{'addon/'+f:sha(a.addon_root/f)for f in addon_files}};report['source_unchanged']=True;save()
  if report.get('dense_passed')is False:raise SystemExit('Dense regression exceeds unchanged 15% limit; inspect report')
if __name__=='__main__':main()
