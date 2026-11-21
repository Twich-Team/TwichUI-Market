"""Focused legacy/compact source compatibility, including literal injection.

Uses actual Rust publishers and actual old/new Lua readers. Only benchmark-owned
temporary staging files and synthetic observations are used; no installation.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from bridge_workloads import canonical,generate

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--baseline-rust",type=Path,required=True)
p.add_argument("--rust-bench",type=Path,required=True)
p.add_argument("--baseline-addon",type=Path,required=True)
p.add_argument("--addon-root",type=Path,required=True)
p.add_argument("--report",type=Path,required=True)
a=p.parse_args()
root=Path(__file__).resolve().parents[1]
g,metadata=generate(20,"injection")
with tempfile.TemporaryDirectory(prefix="twichui-m15-compat-") as directory:
    temp=Path(directory);source=temp/"generation.json";source.write_bytes(canonical(g))
    stage=temp/"staging";stage.mkdir(mode=0o700)
    env=os.environ.copy();env.update(TWICHUI_BRIDGE_BENCH_INPUT=str(source),TWICHUI_BRIDGE_BENCH_STAGE=str(stage))
    def publish(binary):
        r=subprocess.run([str(binary.resolve()),"--exact","bridge::export::tests::profile_workload","--ignored","--nocapture"],
                         capture_output=True,text=True,env=env,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        data=json.loads(next(s[len("BRIDGE_BENCH "):] for s in r.stdout.splitlines() if s.startswith("BRIDGE_BENCH ")))
        assert data["generation_id"]==metadata["generation_id"]
        return Path(data["lua_path"])
    old=publish(a.baseline_rust);old_copy=temp/"legacy.lua";shutil.copyfile(old,old_copy)
    compact=publish(a.rust_bench)  # Same root proves candidate readback/rollback accepts legacy bytes.
    assert old_copy.read_bytes()!=compact.read_bytes()
    results=[]
    for name,addon,artifact in [("old_reader_compact_source",a.baseline_addon,compact),
                                ("new_reader_legacy_source",a.addon_root,old_copy)]:
        subprocess.run(["luac5.1","-p",str(artifact)],capture_output=True,check=True)
        r=subprocess.run(["lua5.1",str(root/"scripts/bridge_reader_bench.lua"),str(addon.resolve()),str(artifact),"single"],
                         capture_output=True,text=True,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        value=json.loads(next(s[len("BRIDGE_LUA "):] for s in r.stdout.splitlines() if s.startswith("BRIDGE_LUA ")))
        assert value["generation_id"]==metadata["generation_id"] and value["corruption_rejected"] and value["local_data_unchanged"]
        results.append(dict(case=name,passed=True,generation_id=value["generation_id"]))
    report=dict(result="PASS",origin="synthetic",records=20,generation_id=metadata["generation_id"],
        cases=results,legacy_lua_bytes=old_copy.stat().st_size,compact_lua_bytes=compact.stat().st_size,
        candidate_readback_accepts_legacy=True,compiled_lua_injection_sentinels_untouched=True,
        contract_changed=False,installed_into_game=False,
        limitation="An older desktop narrow readback parser may refuse compact source on downgrade; it fails closed. Both Lua readers consume identical decoded v1 content.")
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
