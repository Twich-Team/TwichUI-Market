"""Bounded opt-in POSIX benchmark of actual Rust export and actual Lua readers.

Runs baseline/candidate interleaved against identical synthetic generations.
Never connects to a server, installs an addon or reads player SavedVariables.
Linux wait4 reports per-process CPU/RSS independently of Cargo/tool startup.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import statistics
import subprocess
import sys
import tempfile
import time

from bridge_workloads import canonical, generate, PROFILES

ROOT = Path(__file__).resolve().parents[1]


def process(command, env, log, timeout=1800):
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    started = time.monotonic()
    with log.open("wb") as output:
        p = subprocess.Popen(command, env=env, stdout=output, stderr=subprocess.STDOUT,
                             start_new_session=True, preexec_fn=limits)
        while True:
            pid, status, usage = os.wait4(p.pid, os.WNOHANG)
            if pid:
                p.returncode = os.waitstatus_to_exitcode(status)
                break
            if time.monotonic()-started > timeout:
                os.killpg(p.pid, signal.SIGKILL)
                _, status, usage = os.wait4(p.pid, 0)
                p.returncode = os.waitstatus_to_exitcode(status)
                raise RuntimeError("benchmark child timeout; retained log: "+str(log))
            time.sleep(.01)
    if p.returncode:
        raise RuntimeError(f"benchmark child exit {p.returncode}; {log.read_text(errors='replace')[-6000:]}")
    return dict(wall_us=round((time.monotonic()-started)*1e6), user_us=round(usage.ru_utime*1e6),
                system_us=round(usage.ru_stime*1e6), peak_rss_bytes=usage.ru_maxrss*1024)


def line(log, prefix):
    return json.loads(next(s[len(prefix):] for s in log.read_text().splitlines() if s.startswith(prefix)))


def aggregate(values):
    middle = statistics.median(values)
    return dict(median=middle, minimum=min(values), maximum=max(values),
                mad=statistics.median(abs(n-middle) for n in values))


def summarize(runs):
    result = {}
    for section in ("desktop", "lua", "desktop_process", "lua_process"):
        keys = set.intersection(*(set(r[section]) for r in runs))
        result[section] = {key:aggregate([r[section][key] for r in runs])
                          for key in sorted(keys) if all(type(r[section][key]) in (int, float) for r in runs)}
    return result


def comparisons(results):
    if "baseline" not in results:
        return {}
    out={}
    for section,key in [("lua","validation_total_us"),("lua","steps"),("lua","retained_heap_bytes"),
                        ("lua","compile_us"),("desktop","export_us"),("desktop","lua_bytes")]:
        before=[r[section][key] for r in results["baseline"]]
        after=[r[section][key] for r in results["candidate"]]
        a,b=aggregate(before),aggregate(after)
        threshold=max(3*max(a["mad"],b["mad"]),abs(a["median"])*.05)
        delta=a["median"]-b["median"]
        direction=all(y<x for x,y in zip(before,after))
        out[section+"."+key]=dict(delta=delta,noise_threshold=threshold,
            all_pairs_improved=direction,measurable_improvement=len(before)>=5 and direction and delta>threshold)
    return out


def run_case(g, metadata, variants, runs, keep, repeat):
    if g is None:
        return dict(workload=metadata, runs={}, result="REFUSED_FROZEN_CONTRACT_LIMIT")
    results = {name:[] for name,_,_ in variants}
    with tempfile.TemporaryDirectory(prefix="twichui-m15-capacity-") as directory:
        temp = Path(directory)
        source = temp/"generation.json"
        source.write_bytes(canonical(g))
        for repetition in range(runs):
            for name, rust, addon in variants:
                stage = temp/f"{name}-{repetition}"
                stage.mkdir(mode=0o700)
                env = os.environ.copy()
                env.update(TWICHUI_BRIDGE_BENCH_INPUT=str(source), TWICHUI_BRIDGE_BENCH_STAGE=str(stage))
                rust_log = stage/"desktop.log"
                desktop_process = process([str(rust), "--exact", "bridge::export::tests::profile_workload",
                                           "--ignored", "--nocapture"], env, rust_log)
                desktop = line(rust_log, "BRIDGE_BENCH ")
                artifact = Path(desktop.pop("lua_path"))
                assert artifact.resolve().is_relative_to(temp.resolve())
                assert desktop["generation_id"] == metadata["generation_id"]
                subprocess.run(["luac5.1", "-p", str(artifact)], capture_output=True, check=True)
                lua_log = stage/"reader.log"
                repeat_flag = "repeat" if repeat or repetition == 0 else "single"
                lua_process = process(["lua5.1", str(ROOT/"scripts/bridge_reader_bench.lua"),
                                       str(addon), str(artifact), repeat_flag], env, lua_log)
                lua = line(lua_log, "BRIDGE_LUA ")
                assert lua["generation_id"] == metadata["generation_id"] and lua["indexed_records"] == metadata["eligible_records"]
                assert lua["corruption_rejected"] and lua["local_data_unchanged"]
                results[name].append(dict(desktop=desktop, lua=lua,
                                          desktop_process=desktop_process, lua_process=lua_process))
                print(json.dumps(dict(event="sample", workload=f"{metadata['eligible_records']}:{metadata['profile']}",
                    variant=name, repetition=repetition+1, validation_us=lua["validation_total_us"],
                    worst_us=lua["worst_step_us"], steps=lua["steps"],
                    canonical_bytes=desktop["canonical_bytes"], lua_bytes=desktop["lua_bytes"])), flush=True)
                if keep:
                    keep.mkdir(parents=True, exist_ok=True)
                    # Explicit opt-in debug bytes only; never checked into the repository.
                    (keep/f"{metadata['eligible_records']}-{metadata['profile']}-{name}-{repetition}.desktop.log").write_text(rust_log.read_text())
                    (keep/f"{metadata['eligible_records']}-{metadata['profile']}-{name}-{repetition}.reader.log").write_text(lua_log.read_text())
                # Retain only one sample's artifact at a time, not N*large files.
                import shutil
                shutil.rmtree(stage)
    return dict(workload=metadata, result="PASS", runs=results,comparisons=comparisons(results),
                summary={name:summarize(samples) for name,samples in results.items()})


def context():
    def read(path):
        try:
            return Path(path).read_text().strip()
        except OSError:
            return None
    return dict(os=platform.platform(), python=platform.python_version(), cpus=os.cpu_count(),
                cpu_quota=read("/sys/fs/cgroup/cpu.max"), memory_limit=read("/sys/fs/cgroup/memory.max"),
                lua=subprocess.check_output(["lua5.1", "-v"], stderr=subprocess.STDOUT, text=True).strip(),
                child_address_limit_bytes=2*1024**3, timing="CPU plus monotonic child wall; no client frame-time claim")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--addon-root", type=Path, required=True)
    p.add_argument("--rust-bench", type=Path, required=True)
    p.add_argument("--baseline-addon", type=Path)
    p.add_argument("--baseline-rust", type=Path)
    p.add_argument("--cases", default="100:two-gap,1000:two-gap,5000:two-gap,10000:two-gap,25000:one,25000:historical-only,50000:historical-only,1000:fourteen,1000:sixty,1000:sparse-sixty,1000:mixed,1000:mixed-provisional")
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--repeat-every-sample", action="store_true")
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--keep-logs", type=Path)
    a=p.parse_args()
    assert hasattr(os,"wait4") and 1 <= a.runs <= 5
    assert bool(a.baseline_addon) == bool(a.baseline_rust)
    variants=[]
    if a.baseline_addon:
        variants.append(("baseline",a.baseline_rust.resolve(),a.baseline_addon.resolve()))
    variants.append(("candidate",a.rust_bench.resolve(),a.addon_root.resolve()))
    def source(path):
        return dict(commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=path,text=True).strip(),
                    tree=subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=path,text=True).strip(),
                    dirty=bool(subprocess.check_output(["git","status","--porcelain"],cwd=path,text=True).strip()))
    report=dict(origin="synthetic",context=context(),contract_max_bytes=32*1024*1024,
                sources=dict(market=source(ROOT),addons={n:source(addon) for n,_,addon in variants},
                    rust_executable_sha256={n:hashlib.sha256(rust.read_bytes()).hexdigest() for n,rust,_ in variants}),
                repetitions=a.runs,method="interleaved baseline then candidate, fresh processes, default GC, identical generation",
                cases=[])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    for case in a.cases.split(","):
        count,profile=case.split(":")
        assert profile in PROFILES
        g,metadata=generate(int(count),profile)
        report["cases"].append(run_case(g,metadata,variants,a.runs,a.keep_logs,a.repeat_every_sample))
        a.report.write_text(json.dumps(report,indent=2)+"\n")
        print(json.dumps(dict(event="case_complete",case=case,result=report["cases"][-1]["result"])),flush=True)


if __name__=="__main__":
    main()
