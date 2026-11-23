# Simulator history, policy and CI correction

The simulator and Bubblewrap were introduced together on2026-10-30 by
f2a23cc3349cffd4b0f367871f1bb24adabc70b0. Setup already pinned v0.1.37 and
SHA25666e9afa95b61619fb15af335c74a8e9e2b0cc645d9bbf078dca492ec8bf8dfae;
the launcher already used --unshare-all and read-only root/home masking. The
upstream asset was published2026-10-27 and its digest is still identical. There
is no repository binary upgrade or new namespace requirement behind this failure.
Its current required glibc2.39 is a property of those unchanged bytes.

The original documented environment was Ubuntu26.04 x86_64 WSL2, with Mesa
software Vulkan, Lua5.1/bitop, rsync and isolated Ubuntu24 ICU74/ALSA dependencies.
Later prepared cloud runs used /workspace/twichui-env/activate.sh and the same
binary, assertions and Bubblewrap wrapper, with an existing supported elevated
execution path when the outer environment denied nested namespaces. Their
archived M1.5 report does not retain an OS/kernel/AppArmor snapshot, so it cannot
prove an exact cloud distro or a recent host-security change. This task moved
execution to a new GitHub runner rather than reproducing that prepared environment.

Actual committed full execution proof exists for frozen febed289d7db429d00d02fcff73cdbf262d541c2:
247 modules,10 catalogs,192 launches,30,552 structured checks,2446.279seconds,
PASS/exit0. Report and console are committed at4e08bdceec5d717ffe5855bd8351bd19bd06ae88.
The native WSL full pass at83050a2 and L3 cloud pass at9e00d8e are documented
with immutable source/counts, but their raw workspace artifacts are not committed;
that is a lower evidence grade. The6790-second cbb48c8 cloud run explicitly
failed and remains FAIL. None of these is current-source certification.
[Exact records and hashes](evidence/market-simulator-unblock/historical-audit.json).

The full-release/high-risk gate predates this Market work (already present in
003d0bb, November16). Ordinary existing GitHub verification runs offline tests;
it never proved a full simulator pass. The new market-simulator.yml is a new
execution mechanism, not an additional test catalog or branch-protection rule.
Real Forever acceptance remains owner-directed and is not invented as a blocker.
For this explicitly requested coordinated saved-data/publication release, run
the unchanged full cloud suite plus existing immutable source, Windows/signing,
compatibility, migration and production-health checks. Cloud passes do not set
local/native certification flags. If an installable addon archive is produced,
apply its existing archive validator separately; do not repeat the unchanged
full suite solely for archive metadata or perform an unrelated public release.

The newly authored workflow initially lacked runner provisioning for AppArmor,
then f7f4242 incorrectly selected Ubuntu22.04 despite the pinned binary's ABI.
That was an introduced CI error, not an upstream simulator regression. Missing
luac PATH and lab-environment wiring were also setup defects, now corrected.
The owner explicitly authorizes a narrow policy on a disposable Ubuntu24 runner.
The corrected existing workflow atdd28236 uses Ubuntu24/glibc2.39, loads only
a job-specific exact-executable AppArmor profile granting userns, keeps the
global restriction enabled, preserves all inner Bubblewrap flags/assertions,
and removes that policy after the job. It creates only the existing empty/mnt/c
path in the disposable VM. Production host security is untouched. No new runner
infrastructure, simulator framework, binary or loader is introduced.

The initial corrected-runner execution at run45176879766 failed the installation
handoff described below. A launcher preflight or old full pass is never
represented as a current full-suite pass.


## Read-only installation handoff correction

The corrected Ubuntu24 runner proves glibc2.39, native sandboxed help exit0,
loaded exact-executable policy with global restriction still1, and successful
policy removal. The first full attempt atdd28236 passes328 modules but exits1
before all nine native catalog launches: tools/simlab/run.sh reads
**WOWSIM_INSTALL**, while the newly authored workflow exported SIMLAB_INSTALL.
The full runner deliberately sanitizes SIMLAB_* and WOWSIM_LAB so stale pose
filters or mutable lab state cannot leak into catalogs. The supported
WOWSIM_INSTALL variable survives that sanitizer. A direct call to the existing
sanitizer verifies this behavior; no runner code or assertions changed.

At **d2c2e2ae69fc250050fbd8e7a1aecdef642cc563**, the workflow exports that
existing documented installation interface. Actual full run45178795859 is now
in progress. Market final integration pins match this exact source at275aa4f.
The prior full attempt remains FAIL and its31MiB exact artifact is retained
locally with checksum, alongside all earlier failures.


## Concurrent-main preservation

During the full run, main advanced independently from364c4c2 to
5824b73eaf169cf60e7eea06391aed7d392a57e1 through PR141 (RestedXP) and142
(Spoken menu). Their11 changed files are disjoint from Market changes. The
conflict-free merge c872d027bb78771cd50fbec9350a3df159c329e1 preserves both,
with tree7dda0a4d76238a2ea07a6653dfcf4612299f4584. The unchanged full command
is running again on that combined source in45185533044/job137730027480.
Fast Market checks pass; complete regression status remains pending. Market
e48e0eee828355ac1ed95c5be3eec46b032f9e82 pins this exact combined source
in both native consumer checks and prepared contracts. Original full run
45178795859 continues for retained evidence; its result cannot certify the new
combined tree by itself. No coordinated merge, backend deployment or beta.12
publication has occurred.


## Full execution after namespace/ABI repair

Run45178795859 completed the exact full cloud command at d2c2e2a with source
unchanged, exit1,3124.577seconds:328 offline modules passed,10 catalogs
attempted,136 native launches and35,611 structured assertion executions.
Only lab-guard and diagnose catalogs passed. Every rendering catalog encountered
`src/render/headless.rs:67: Failed to find GPU adapter` with active_backends0.
The new workflow had also omitted the documented Mesa software Vulkan runtime;
previously prepared WSL/cloud environments already supplied it.

The same disposable Ubuntu24 workflow is corrected at
8aa42c16b6896555cd3bc857cf7ab0482dbf4116 by installing Ubuntu libvulkan1 and
mesa-vulkan-drivers (with their package dependencies) and running the existing
smoke catalog before full. No binary, sandbox, fixture or assertions change.
Run45187769049/job137737762923 is pending. This is provisioning the documented
environment, not another execution framework.

The failed report also exposes genuine assertion mismatches before rendering:
Workshop hardcodes pre-existing older tooltip catalog/default/button behavior,
and TestLab records a structural label overflow (77pixels in74). These are not
excused by the graphics failure and must not be waived. WorthLayout, WorthTip,
Workshop/TestLab scenarios and TestLab product files have no diff between current
main5824b73 and the corrected candidate. Git history shows the custom-heading
change bc787b14 (November20) and outcome-catalog change208e0f9 (November19),
while documented full L3 source9e00d8e is November16 and lacks bc787b14. The
cloud-environment document already records baseline Workshop failures. Static
ancestry and exact mismatches establish older fixture expectations; this is not
a claim that a current-main baseline full suite has been executed. No assertions
are changed to manufacture success. Final release remains held on actual
verification.

The exact failed report is preserved losslessly as
[evidence/full-d2-failed-report.json.gz](evidence/market-simulator-unblock/full-d2-failed-report.json.gz),
with [catalog/exit/artifact identities](evidence/market-simulator-unblock/full-d2-failed-summary.json)
and the captured renderer panic. The87MB artifact remains local and on GitHub.
Private candidate backend image2de5aa76 independently passes193 focused
PostgreSQL checks and65 source-module hashes; it is not deployed.
