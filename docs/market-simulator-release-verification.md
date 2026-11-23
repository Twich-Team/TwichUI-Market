# Simulator environment and coordinated release verification

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
