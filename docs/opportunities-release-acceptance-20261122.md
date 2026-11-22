# Market Opportunities deployment and Companion publication acceptance

**Backend deployed and verified; signed Companion 2.0.0-beta.11 is published through
the existing private website/updater. Beta.10 remains retained and downloadable.**
Physical-PC and game acceptance remain open; they are not established by this release.

## Deployed server and recovery

Only `api local-api` were replaced, using the original 25-file chain, both original
environment files and the narrow immutable-image overlay appended last:
`up -d --no-deps --no-build --pull never --wait api local-api`.

- Live image: `sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c`.
- Retained prior image: `sha256:428f0acfa92ec42fcc40d467e072ad3d14f7175c02ad76303d141d6824b983af`.
- Reviewed module/contract source: frozen Market `29fa95b569cc3834ed2c17490d251a2a4ac6b4f5`.
- Scope: only `security.py`, `workshop_summary.py` in both runtime locations, plus
  v3 contracts. All base layers, dependencies, other modules and schema are preserved.

This is the layered mixed-deployment workflow, not a rebuild of all components
from main. The actual image passed **150 focused PostgreSQL checks**, including
authentication, Workshop, sync, retention and migration preservation. All three
exact frozen-main workflows passed. [Image provenance](evidence/opportunities-release-20261122/image-provenance.json),
[test result](evidence/opportunities-release-20261122/image-tests-with-filesystem.json),
[actual scoped deployment](evidence/opportunities-release-20261122/promotion-result.json).

Both APIs are healthy. All nine other container IDs/images/start times and
configurations match the post-VM/pre-rollout snapshot. API environments, actual
mounts/read-only flags, ports, networks, resources, restart and logging are
preserved. Only unset DNS null/empty-array representation and bind-list ordering
are normalized in comparison. Legacy backup stays stopped/restart `no`; migrate
stays stopped with its original reference/defaults. Neither historical discrepancy
was repaired. [Replacement preservation](evidence/opportunities-release-20261122/deployment-preservation.json).

Protected archive: `market-release-20261122T132338795686Z-6e2bb3d9483d.dump`,
**1,662,789,332 bytes**, SHA256
`5bc9f1b3047b1911a7525e1f6cfa7a29c1f8ad5239ea5975373710106798dbee`.
It was created by the existing manager under `.backup.lock` and is protected by
`release:opportunities-20261122` plus `restore-recovery-gate`. Prior archives remain.
The frozen `scripts/backups.py` operator procedure actually restored it, including
constraints, into a dedicated disk-backed PostgreSQL with no ports, one CPU,
1 GiB memory and no swap. Original readback matches **27,696,379 listings,
4,598,744 snapshot-statistic rows, 1,964 observations and 173 snapshots** at pinned
pre-dump cutoffs. Candidate schema and original provider-envelope decryption pass;
no migration or provider request occurred. Only the disposable restore target was
retired. [Actual restore](evidence/opportunities-release-20261122/restore.json),
[post-deployment original rows](evidence/opportunities-release-20261122/original-after.json).

Two VM interruptions are retained as interrupted attempts, not restore evidence.
Production services restarted with the VM before the scoped rollout; those start
times are not attributed to the operator. The externally changed RAM allocation
was reassessed and not reset. [Preparation and interruption record](opportunities-release-20261122.md).

## Authenticated contracts and source-qualified reader

Trusted public HTTPS validates **30,303 genuine exact variants** through contracts
**1, 2 and 3**; the default remains **1**. Schemas, canonical bytes, generation and
partition hashes, bounds, exact variants and source/market identity validate.
Contract 3's 64 current and 64 history partitions are complete, with every history
projection reproducing its current digest. Authenticated summary 304s remain
bound; anonymous conditional requests are 401. Immutable parts preserve their
reviewed 200 semantics. A different contract validator may return 202 while a new
source prepares, and must not falsely return 304. [Live contract proof](evidence/opportunities-release-20261122/live-contracts.json).

The unchanged native core from payload `b39a35c…` independently downloads and
validates genuine production data. A separate operator example stages and reads
back both projections before emitting a staging root. Generation:
`a76befe8a8a897fe4d6339dc47b19c35924781f6637e67f0c20dcd1f04e9f7a0`.
Warm readback is one bound 304, zero payload bytes, unchanged native cache mtimes.
[Native readback](evidence/opportunities-release-20261122/native-live.json),
[warm reuse](evidence/opportunities-release-20261122/native-live-warm.json),
[frozen native runtime hashes](evidence/opportunities-release-20261122/native-core-provenance.json).

The unchanged pinned production Lua reader consumes these genuine staged files:
**6,712 item IDs / 30,303 exact variants**, zero history loads for current queries,
missing prices settled without invention, then exactly one rich partition and
**nine actual dated chart points** on an explicit chart request.
[Reader result](evidence/opportunities-release-20261122/production-lua-readback.json),
[separate operator driver](evidence/opportunities-release-20261122/genuine-reader.lua).

This is **Linux core download/staging plus source-qualified production Lua**, not
ordinary installed Windows publication against production or actual Forever
execution. The Windows installation guard was not bypassed. The actual installer
and Windows publication/compatibility proofs are separate below. Addon runtime
pin `d93d253ac31b89e953a8853ee2ce7b25adaedcc7` is an ancestor of frozen addon main
`8e25ceea2a542a3e67b1dd586c3b4cdd00a70374`; their non-documentation bytes and
current/history schema/capability hashes were rechecked. Existing native-only
compatibility and simulator limitations remain; no new physical-PC matrix is
claimed. No real AddOns, SavedVariables or client configuration was changed.

Operator harness setup/assumption failures are retained privately: missing test
extension, insufficient fixture filesystem reserve, immutable-part conditional
semantics, a valid 202 during source preparation, and asynchronous Lua lookup.
Drivers were corrected to the existing protocol and cooperative API. Production
tests/assertions/thresholds and runtime retry policy were not weakened. One native
attempt encountered the existing preparation-unavailable response while work was
serialized; subsequent bounded readback passed. No collector repair was bundled.

## Current signed Companion candidate

The owner approved unused/unreserved **2.0.0-beta.11** for version-only preparation.
[Draft PR45](https://github.com/Twich-Team/TwichUI-Market/pull/45) changes only seven
consistent version/package metadata files and public signature proof; runtime,
contracts and dependency choices match the frozen tested implementation.

| Identity | Exact value |
| --- | --- |
| Original payload | `b39a35c01676b50dbc159f4793e0ad547676acfc` |
| Later public-proof harness | `fa9f494ec9ae822f305dd406a5174942d503776c` |
| Original Windows run / artifact | `45027451323` / `14756114202` |
| Original archive SHA256 | `783821c57bf882c17cf0ea8d90f063af07cf6770e59ffbd49720e3a0a8a04b38` |
| Original signed installer bytes | `4,885,541` |
| Original signed installer SHA256 | `84dacad168dc212d8dda7d06f15ddc5a918f170ba1af0e9ece4e6373cd883129` |
| Installed executable SHA256 | `91f595fcc9a5d9779a2f7054c7469359da915a30b9a39b14fa6ab1e4620f817d` |
| Updater public-key SHA256 | `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf` |
| Genuine signed-SDK run | `45028815202` |

Original exact-payload canonical push runs all passed: Windows **45027451323**,
Backend **45027451269**, Private website **45027451254**. Proof-harness push runs
also passed: Windows **45028815202**, Backend **45028815130**, website **45028815157**.
Affected performance workflow **45028820651** passed. Historical failures remain
in their development evidence; a passed pending-only old-candidate job was not
used to certify beta.11.

The original CI archives were digest-checked before bounded safe extraction.
`prepare-companion-signing-input.py` verified original installed receipts and
canonical source CI through its normal public API path. The unchanged wrapper
used existing private inputs only inside the bounded no-network rootless signer,
pinned Tauri **2.12.4**, read-only inputs and suppressed internal output. Original
installer bytes are unchanged. Existing independent native verification confirms
the exact signature, version and hash. No replacement key, credential extraction,
commercial signing, private input in Git/GitHub, or security bypass occurred.

The supported Windows SDK installed **those original signed bytes**, verified the
final executable, reconnected/synced/exported, preserved authorization/cache/settings
and uninstall data, and rejected corrupt bytes and incorrect signed versions.
Installer-process exit itself was not observed; final installed identity/state
was independently verified. The later harness rebuild is not the release artifact.
[Actual SDK receipt](evidence/opportunities-release-20261122/signed-update-acceptance.json).
Windows publisher status remains **NotSigned**, separate from the valid mandatory
Tauri signature. Physical-PC/UAC/tray/Forever/frame-time/GC acceptance remains open.

## Preserved state, rollback and stopping point

Final public health is 200; both feeds and sole market 2 / house 114 remain healthy
at **300 seconds**, zero failures, schema `retention_20261118`, zero retention
batches. Backup scheduling stays disabled. The historical auction HTTP-200
validation cause remains unresolved as documented in the [read-only investigation](opportunities-overlay-repair-20261122.md).
There was no retry reset, instrumentation, provider campaign, retention approval
refresh, pricing-default activation or unrelated infrastructure change.
[Final health](evidence/opportunities-release-20261122/final-health.json).

Stable account/preferences/mapping/retention authorization/keyring/recovery/store
fingerprints match. Original archive credential static columns and provider
envelopes, key IDs, budgets, rate configuration and other stable settings match
production, using a metadata-only archive read under the same lock.
[Static archive comparison](evidence/opportunities-release-20261122/archive-static-preservation.json).
Normal Companion renewals added credentials during verification. The earlier
whole-row credential hash differs, and a bounded revoked-flag reconstruction did
not reproduce it; **unqualified whole-row equality is not claimed**. Those owner
changes were not reset. [Comparison limit and renewal events](evidence/opportunities-release-20261122/credential-refresh-comparison.json),
[final fingerprints](evidence/opportunities-release-20261122/stable-final.json).

For backend acceptance, only task grant **398** was revoked. Independent trusted HTTPS now returns 401 for
its bootstrap and Contract-3 requests. Task-created raw secret snapshots and
retired fixture credentials were removed; concurrent owner sessions/renewals remain.
[Revocation receipt](evidence/opportunities-release-20261122/grant-revocation.json).

Executable, check-only-verified rollback files:

- [API rollback](../deploy/opportunities-20261122/rollback-api.sh): retains the
  actual full chain, pins prior `428f0acf…`, replaces only `api local-api`.
- [Private pointer rollback](../deploy/opportunities-20261122/rollback-private-release.sh):
  audited `rollback 2.0.0-beta.10 --actor marketdev`, existing pinned offline operator,
  current reviewed read-only policy and independently pinned verifier.

Neither rollback was executed. Prior images, all signed releases, archives,
metadata/restore receipts and updater keys remain. Keep this worktree: live API
labels reference its final release overlay. A pointer rollback cannot force an
installed SemVer downgrade. Pause automatic delivery and restore a complete
supported 1/2 generation with the compatible new Companion before downgrading
consumer support; never splice banks, hand-edit active roots or delete history.

## Approved publication and independent readback

The owner subsequently instructed **“publish companion.”** in the exact-artifact
approval context above. The [new owner receipt](evidence/opportunities-release-20261122/owner-release-approval.json)
was committed at `17743db` before admission. The pending template remains historical;
it was not used as consent. This satisfies the separate exact-hash receipt required
by the [release rule](companion-v2-release-operations.md#final-approval-and-private-admission).
No historical or broad deployment approval was substituted.

PR45 was merged through the normal workflow at
`e2882dd822b356ffa081efebbff167827f9bf364`; its tree equals the verified public-proof
commit `fa9f494ec9ae822f305dd406a5174942d503776c`. The installer remains the original
payload artifact identified above. No later build was substituted.
[Source and operator identities](evidence/opportunities-release-20261122/publication-source.json).

The existing audited atomic publisher used retained operator image
`sha256:c8686b5be272bcef4589df5a99a539cf9311dc111d0ba31ac8eee6c31f3802ec`
with current reviewed read-only policy and verifier. Publication had no network,
Docker socket or database credentials; only the dedicated distribution volume was
writable. Actor `marketdev` published beta.11 over beta.10 with durable intent
`audit/00000010.json` and completion `audit/00000010.complete.json`.
All **99 prior immutable files** are byte-identical; only the existing current
pointer changed, with 11 new bundle/audit files. Updater keys and retained releases
remain intact. [Publication](evidence/opportunities-release-20261122/publication.json),
[store preservation](evidence/opportunities-release-20261122/publication-store-preservation.json),
[admitted manifest](evidence/opportunities-release-20261122/published-manifest.json).

Actual trusted HTTPS website-offer and native-download requests return the exact
original installer SHA256/size above. The downloaded bytes independently verify
against the existing updater key and exact version. Anonymous downloads are 401;
native credentials cannot access the browser-only current-release endpoint (403).
Supported beta.5 through beta.10 clients receive beta.11 offers; equal beta.11,
newer beta.12 and stable 2.0.0 receive 204, preserving no-downgrade behavior.
Beta.10 downloads remain intact. This is real website-offer API evidence, not a
claim of a new browser screenshot or owner-PC installation.
[HTTPS readback](evidence/opportunities-release-20261122/publication-https.json),
[independent signature verification](evidence/opportunities-release-20261122/https-downloaded-signature.json).

All **11 production container identities, images, configuration, mounts and start
times** remain unchanged by publication. Both collector feeds remain healthy with
the original schedule; schema and retention state are preserved.
[Publication preservation](evidence/opportunities-release-20261122/publication-runtime-preservation.json).
Only the publication verification grants **401 and 402** were revoked, each
independently returning HTTPS 401 afterward. Their temporary private snapshots
were removed; owner accounts/devices/sessions were not reset.
[Cleanup receipt](evidence/opportunities-release-20261122/publication-grant-cleanup.json).

## Minimum owner game acceptance

Select/consent to the real verification PC/game destination. Install the approved
addon (frozen runtime/final main or verified compatible release); restart Forever
if new folders need discovery. Then:

1. Run `/tui perf start workshop 3` and `/tui perf mark opportunities-open`.
2. Open Opportunities without scrolling until visible/all rows settle; warm reopen.
3. Separately sort/filter/scroll and inspect one historical chart.
4. Run `/tui perf stop`; export Diagnostics Quick summary and JSON.

Record client/build, contract/generation, recipe count, first/visible/all timing,
callback/batch/source tails, decode/load/cache counts, queue wait and memory.
No purchase, post or sell action is needed. Offline measurements do not establish
native frame-time guarantees. No new addon release or owner-PC installation was
performed by this operational session.
