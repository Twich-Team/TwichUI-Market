# Simulator environment and coordinated release verification

**Stopped safely at the environment gate, November23 09:57UTC.** Namespace
policy is identified and a nonroot namespace setup passes on Ubuntu22.04, but
that image lacks the pinned simulator's required glibc2.39. Ubuntu24.04 and
26.04 deny namespace/capability use. No fully suitable permitted environment
is available through the connected access. Full verification has not passed;
no coordinated PR is merged and no release is deployed/published.
[Exact final attempts, sources and CI snapshot](evidence/market-simulator-unblock/final-blocker.json).
Earlier pending observations below are chronological evidence.


The owner approved25 addons as the final architecture. No packaging comparison
or architecture work is reopened. Only environment preparation and ordinary
release metadata changed. Existing collector repair and valid data are preserved.

The production host permits unprivileged user-namespace creation but applies
`unprivileged_userns (enforce)` when entering one;
`kernel.apparmor_restrict_unprivileged_userns=1`. A direct probe retains full
namespaced effective/permitted capability bits yet network-namespace creation
fails EPERM. The unchanged Bubblewrap clone creates all requested namespaces,
but its loopback RTM_NEWADDR fails EPERM: CAP_NET_ADMIN use is denied by the
AppArmor user-namespace policy. Parent/direct probe has Seccomp0; namespace quotas
are positive. This is not solved by dropping network isolation or changing
production policy. Kernel audit logs are not accessible to this unprivileged user.
[Direct capability/profile evidence](evidence/market-simulator-unblock/direct-userns-capability.json).
Ubuntu documents this capability restriction in its
[24.04 release notes](https://documentation.ubuntu.com/release-notes/24.04/).

The existing disposable GitHub Ubuntu22.04 VM permits the same namespace/network
operations without changing any policy; the Ubuntu24.04 comparison reproduces
the denial. Ubuntu22 lacks the sandbox's fixed/mnt/c directory. A private
user/mount namespace maps the runner's current nonzero UID, mounts a bounded1MiB
tmpfs at its private/mnt and creates/mnt/c there. Setup capabilities are dropped
before executing the existing command. No host mount, root/sudo, security policy,
simulator launcher, isolation flag or assertion is changed. The exact unchanged
Bubblewrap command passes on this prepared runner. Initial missing-directory and
retained-capability failures remain recorded; they are not passes.
[Exact runner comparison and failed attempts](evidence/market-simulator-unblock/runner-comparison.json).

Full attempt f7f4242 gets through setup but correctly fails because luac5.1 was
not exposed on PATH. The already-downloaded package contains it; the workflow
now exposes that compiler without test changes. The failed report/artifact remains.
Full suite is running at addon03b1dc3, run45148721970, unchanged command:
`bash tests/run.sh full --profile cloud --jobs 2 --sim-jobs 1 --measure`.
This cloud profile never claims local/native release flags or real Forever
verification. No full pass is claimed while it is pending.

Market candidate5f8a6d9 prepares beta.12 consistently across all version/lock
metadata and pins exact addon03b1dc3 for integration. Production is unchanged:
private beta.11 remains current; house114/300seconds/both feeds have zero failures
at09:40UTC. No coordinated PR has merged or deployed; all gates remain required.


## Exact final blocker and safe handoff

The run at03b1dc3 exits1:328 offline modules and845 Lua syntax checks pass;
lab-guard35 checks pass. The other nine catalog commands exit before launch,
looking for the default lab path. Exporting the existing WOWSIM_LAB setting
corrects that environment wiring. A sandboxed runtime preflight at final
addon **f7ba519cc3320f375b3220edb2a64a1b7b4dac42** then proves the remaining
ABI error: pinned wow-sim requires GLIBC_2.39 and pinned ICU/ALSA require
GLIBC_2.38, unavailable on Ubuntu22.04. No simulator binary, loader, assertions,
network-isolation flags or full catalog were replaced or removed. The full
result remains FAIL; no local/native milestone flag is asserted.

Ubuntu24.04 has no preinstalled system Bubblewrap; its extracted ordinary
binary is denied by the existing AppArmor user-namespace policy. Ubuntu26.04
has a non-setuid preinstalled Bubblewrap, but its direct sandbox attempt also
fails namespace permission. No sysctl, AppArmor profile, host capability,
seccomp policy or production host setting was modified. There is no VM
provisioner or accessible self-hosted runner administration/discovery capability
in the connected tools; unavailable discovery is not evidence that no private
runner exists. No unknown machine was selected or reconfigured.

Required next input is access to an approved nonproduction VM/runner with
**glibc2.39 or newer and working unprivileged user/mount/network namespaces**,
including namespaced CAP_NET_ADMIN/CAP_SYS_ADMIN use for the unchanged sandbox.
Its existing fixed/mnt/c path must be present or prepared privately, as the
positive Ubuntu22 diagnostic demonstrates. Do not grant host capabilities,
remove sandbox flags, replace the runtime loader or alter production policy.
Then run the existing unchanged full cloud command (with its stated coverage
limitations), retain the actual report/exit and recheck current mains/immutable
CI before the authorized merge/deployment sequence.

Market candidate **d463ee15d0ddcc52e322218970510143a4bd2e3c** prepares only
beta.12 metadata and exact03b1dc3 integration pins after the earlier25-addon
implementation. A strict pin-declaration mismatch at5f8a6d9 was corrected,
preserving its assertion and failed artifact. Addon runtime is byte-identical
to daa674f; only workflow setup changed. Architecture/benchmarks were not
reopened. Market ordinary checks are passing except the repeated Windows
comparison still running at this snapshot; no final all-green claim is made.

At09:56UTC production health is HTTP200, house114/300seconds/both feeds have
zero failures, latest scheduled success09:51:48. Worker ec94420d / repair3f0421a
and API a3f82264 retain their exact container IDs/images with no restarts/OOM.
Private Companion remains **2.0.0-beta.11**; beta.12 is prepared only, with no
new signing/publication/update offer. Both main tips remain Market
3f0421a2221e424df751b963f5b66b445e319018 and addon
364c4c28889d621335bc4b3a7b61d234c0b04ce0. No coordinated merge/deployment,
provider request, backoff/schedule/data change or local installation occurred.
Original rollback images/archive and collector-repair worktree remain intact.
[Final production health receipt](evidence/market-simulator-unblock/final-production-health.json).
