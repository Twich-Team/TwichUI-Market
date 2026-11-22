# Market Opportunities deployment preflight — blocked, 2026-11-22

No production replacement, build, migration, signing, publication, backup creation,
account grant, client installation or game-file change occurred. This is an
operational discovery checkpoint, not deployment acceptance.

## Blocking result and concrete repair decision

The actual live API's full ordered 25-file Compose command, project directory and
two environment-file paths were recovered from its labels. Running that command
with `config --quiet` returned **1**. Five referenced files are missing. Across
the 11 production containers' labels there are 27 distinct paths, seven missing.
The sanitized [command and missing paths](evidence/opportunities-deployment-preflight-20261122/compose-preflight.json)
and [per-service runtime inventory](evidence/opportunities-deployment-preflight-20261122/runtime.json)
record today's state. No snapshots were executed as a replacement stack.

The owner instruction requires: “If the actual full chain cannot be reproduced
with config --quiet and sanitized effective-configuration comparison, stop
replacement and present the smallest operational repair for separate approval.”
The [baseline rule](production-baseline.md#reconstructing-the-deployment-inventory)
also says: “Missing old path references are operational debt; repairing or
simplifying production Compose paths needs a separately authorized operational task.”

**Proposed approval scope:** restore only the seven missing regular overlay files
at the exact absolute historical paths in the
[repair manifest](evidence/opportunities-deployment-preflight-20261122/missing-path-repair.json).
This needs an explicit exception to the repository-only write boundary because
those paths are under two historical `.codex/worktrees` directories. Do not
recreate Git worktrees, alter existing files, simplify/reorder overlays or restart
services. Each proposed byte sequence was independently compared with its recorded
Git source `3b59f0f34617cbcf12a43baddfeed7a1e668feb2`; hashes and Git blobs are recorded.
They remain reconstructed candidates, not proof of today's effective configuration.

After approval, first refuse existing files/symlink destinations, restore only
those exact files, then rerun the actual chain's `config --quiet`. Supply private
interpolation inputs through their existing protected interfaces; never print
rendered environment values. Compare the effective configuration against current
containers, including environments, mounts, ports, networks, resources, restart
and logging. Stop on any discrepancy. Successful restoration alone does not
authorize a different configuration or replacement.

## Verified source and current runtime

Frozen Market `29fa95b569cc3834ed2c17490d251a2a4ac6b4f5` was fetched as an actual
commit. Its producer merge `4df46eee3626dc9f6e8e82420ce293da9492439b` and recorded
baseline `5d16179` are ancestors. The original checkout remains on its existing
beta.5 release branch with its original untracked overlays; it was not reset.
Preparation uses a separate repository worktree/branch.

Both exact addon objects were fetched into this repository's object database;
no addon checkout was modified. Runtime pin
`d93d253ac31b89e953a8853ee2ce7b25adaedcc7` is an ancestor of frozen final main
`8e25ceea2a542a3e67b1dd586c3b4cdd00a70374`. Every changed path is documentation.
All 11 addon source/capability hashes and 13 Market source/contract hashes in the
pinned native compatibility evidence match, and the checked addon files match
final main byte-for-byte. [Hash verification](evidence/opportunities-deployment-preflight-20261122/source-pin-verification.json).
This qualifies the retained evidence's source; no native test was rerun here.

Operator is `marketdev`, UID 1002, using the verified `rootless` Docker context
at `/run/user/1002/docker.sock`; Docker reports rootless security. Project is
`twichui-market`. Both APIs remain healthy on immutable image
`sha256:428f0acfa92ec42fcc40d467e072ad3d14f7175c02ad76303d141d6824b983af`.
That image and the historical offline publisher image
`sha256:c8686b5be272bcef4589df5a99a539cf9311dc111d0ba31ac8eee6c31f3802ec`
are present locally. A stopped historical migrate container references an absent
image; it is not a rollback target and was not changed.

All 64 Python modules in both API module locations were hashed for each API.
Compared with frozen Market, only `security.py` and `workshop_summary.py` differ.
The security change admits authenticated `history/{bucket}` reads alongside
`parts/{bucket}`. This is evidence for a narrow future image scope, not an image
acceptance result. [Module hashes](evidence/opportunities-deployment-preflight-20261122/api-module-comparison.json).

## Live preservation and health findings

Read-only, repeatable-read PostgreSQL queries with three-second statement and
250 ms lock deadlines observed schema `retention_20261118`, approximately
10.73 GB database allocation, retention enabled and zero retention batches.
Original account/credential/preference/device/mapping and retention fingerprints,
recovery-file hashes and immutable distribution-file hashes are in the
[sanitized live receipt](evidence/opportunities-deployment-preflight-20261122/live-state.json).
These are initial fingerprints, not before/after release preservation proof.

**Collector is degraded before deployment.** Sole enabled market remains
2 / house 114 / 300 seconds. At inspection it had 121 failures and last complete
success/observation at `2026-11-22 00:16:24.758782+00:00`. Auctions had seven
failures; commodities had zero and succeeded at `10:26:46.232097+00:00`.
Observation 1936 is genuine, not synthetic. No setting/schedule was rewritten,
no provider request was triggered, and no collector repair is bundled here.

Host snapshot: about 132 GiB available, 5% inode use, about 11.6 GiB available
RAM and 16 logical CPUs. The database filesystem reported 140,644,749,312 free
bytes at its later inspection. These preliminary readings do not certify build,
backup/restore or WAL headroom; no resources were allocated for those steps.

## Existing Companion and remaining release gates

Live `current.json` still selects **2.0.0-beta.10**, source
`be09ff9f8adc1d5c8b8c12d04032b954863aa553`. Its actual installer is 4,891,346 bytes,
SHA256 `16adc59355cb99c1ec56322941f0a219f877c39fb2030584358044aa0fde527f`,
matching its manifest. Beta.2 through beta.10 directories remain retained.
This is server-store evidence, not owner-PC installation evidence.

Configured public key and frozen source public key both hash to
`5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`.
Existing encrypted key, separate passphrase and key archive exist, owned by UID
1002 with mode 0600. Only public key bytes and private-file metadata were read;
no private signing input was opened. [Signing metadata](evidence/opportunities-deployment-preflight-20261122/signing-preflight.json).
Signer execution, publisher compatibility and Windows artifact access are not
certified by file/image presence and remain pending.

No new Companion version was selected or payload frozen. Beta.10 cannot be reused
for changed bytes. Version approval/preparation PR, exact-payload canonical CI,
original artifact download, signing, independent verification, signed original-byte
SDK install/upgrade, retained-data proof and exact-artifact final owner consent
remain required under [release operations](companion-v2-release-operations.md#final-approval-and-private-admission).
No historical approval was reused.

No protected recovery point or isolated restore was created in this blocked
session. No schedule or retention policy changed. No executable production rollback
is certified: the missing chain also prevents its validation. Before any later
activation, prepare and validate exact full-chain API rollback to the retained
`428f0acf…` image and audited private-pointer rollback to observed beta.10 with
an explicit operator identity, plus compatible complete-generation recovery.

All contracts 1/2/3 live negotiation/integrity checks, resulting-image tests,
native publication, installed-artifact compatibility and actual production-Lua
consumption remain **unrun in this session**. No task-created grants need revocation.
Physical-PC/UAC/Forever/tray/frame-time/GC acceptance remains open. Request the
owner's prescribed Opportunities perf capture after an approved actual release;
the current blocked state is not a candidate to install or accept.
