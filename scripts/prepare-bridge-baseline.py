"""Append only the identical opt-in test harness to a clean baseline worktree.

Production source remains byte-for-byte the requested frozen commit. Build the
release library tests in that disposable worktree, then pass the executable to
bridge_capacity.py. No deployment, dependencies or compiled artifacts are added.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--baseline-root",type=Path,required=True)
p.add_argument("--expected-commit",required=True)
a=p.parse_args()
root=a.baseline_root.resolve()
assert subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()==a.expected_commit
assert not subprocess.check_output(["git","status","--porcelain"],cwd=root,text=True).strip(),"use a clean disposable worktree"
path=Path("desktop/core/src/bridge/export.rs")
source=(Path(__file__).resolve().parents[1]/path).read_text()
start=source.index(" /// Opt-in synthetic benchmark.")
end=source.index(" fn completed()",start)
harness=source[start:end]
baseline=(root/path).read_text()
assert baseline.rstrip().endswith("}") and "fn profile_workload()" not in baseline
before=baseline.split("#[cfg(test)]")[0]
patched=baseline.rstrip()[:-1]+harness+"}\n"
assert patched.split("#[cfg(test)]")[0]==before
(root/path).write_text(patched)
print("Appended benchmark-only harness SHA256:",hashlib.sha256(harness.encode()).hexdigest())
print("Unchanged production-prefix SHA256:",hashlib.sha256(before.encode()).hexdigest())
