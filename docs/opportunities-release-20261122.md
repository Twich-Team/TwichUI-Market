# Market Opportunities operational release checkpoint

**Backend recovery/image/preflight gates pass; production replacement has not yet run. Companion publication awaits final exact-artifact owner approval.**
Frozen Market source remains `29fa95b569cc3834ed2c17490d251a2a4ac6b4f5`;
addon main remains `8e25ceea2a542a3e67b1dd586c3b4cdd00a70374`, with coordinated
reader pin `d93d253ac31b89e953a8853ee2ce7b25adaedcc7`. Restoration authority is
`81f83a5c6b21cc7a7808adb27f52b3d51243b91a` and the later explicit resume instruction.

## Backend candidate and recovery preparation

Candidate image is
`sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c`.
It preserves all layers of live image
`sha256:428f0acfa92ec42fcc40d467e072ad3d14f7175c02ad76303d141d6824b983af`,
changing only `security.py` and `workshop_summary.py` in both runtime package
locations and adding the frozen v3 contract directory. No dependencies,
migrations, collector, retention, authentication implementation beyond the reviewed
history-read route admission, backup manager or other modules are replaced.
[Build inputs](evidence/opportunities-release-20261122/build-inputs.json),
[actual image contents](evidence/opportunities-release-20261122/image-provenance.json).

The actual candidate image passes **150 focused PostgreSQL checks** for Workshop,
authentication, sync, retention and migration preservation in an isolated
`market_test` database. Initial setup errors are retained privately: the first
database lacked the standard `pg_trgm` migration; the next run's 128 MiB `/tmp`
filesystem failed the unchanged retention reserve. Standard schema initialization
and a read-only view of the actual host filesystem resolved those setup issues.
No tests, assertions, deadlines or reserve thresholds were weakened.
[Final result](evidence/opportunities-release-20261122/image-tests-with-filesystem.json),
[test output](evidence/opportunities-release-20261122/image-tests.txt).
The first BuildKit attempt could not resolve a bare local image ID; the bounded
legacy Docker builder used the actual immutable local base without retagging it.

The protected release archive is
`market-release-20261122T132338795686Z-6e2bb3d9483d.dump`, **1,662,789,332 bytes**,
SHA256 `5bc9f1b3047b1911a7525e1f6cfa7a29c1f8ad5239ea5975373710106798dbee`.
The existing manager created it under the shared lock, fully decoded its custom
archive, and recorded `protected=true` and
`required_by=["release:opportunities-20261122"]`. Its schedule/policy is unchanged;
both prior protected archives remain. [Creation receipt](evidence/opportunities-release-20261122/backup.json).
The separate [actual restore receipt](evidence/opportunities-release-20261122/restore.json) now records completed isolated restoration, constraints and original-row readback; archive integrity alone was never treated as restore proof.

Two VM interruptions prevented the isolated restore and native Linux build from
completing. No acceptance is inferred from partial database files. Only task-owned
interrupted restore data and completed destructive-test fixtures were retired.
A fresh disk-backed isolated restore subsequently completed through the frozen
`scripts/backups.py` operator function, with the existing operation-specific Compose
binding, the actual shared backup lock, pinned PostgreSQL, no ports, 1 GiB memory,
no swap and one CPU. Its dataset is too large for the original 2 GiB tmpfs target.
It restored constraints, matched all 27,696,379 original listings, 4,598,744 snapshot-statistic rows, 1,964 observations and 173 snapshots at the pre-dump cutoffs, and passed candidate schema and original encrypted-provider-envelope decryption checks. No migration or upstream request occurred. Only its disposable database/network/volume were retired. The archive remains protected and now also carries the operator restore-recovery-gate reference.

The executable [backend rollback](../deploy/opportunities-20261122/rollback-api.sh)
has all 25 actual original overlays and both actual environment files in order,
selects the retained prior immutable image and scopes execution to `api local-api`.
Its check-only mode passed. The separate [private release rollback](../deploy/opportunities-20261122/rollback-private-release.sh) pins retained beta.10, actual operator `marketdev`, the existing offline operator image/current reviewed policy and independently pinned verifier. Its check-only verification passed with the store read-only. Neither rollback was executed. It refuses an enabled/running legacy backup or running
migrate container. The [candidate overlay](../deploy/opportunities-20261122/compose.api-release.yaml)
changes only the two API image fields and is **not active**. [Effective candidate configuration comparison](evidence/opportunities-release-20261122/candidate-compose-comparison.json) confirms exactly two image-field changes, with the full prior chain retained. [Final preflight](evidence/opportunities-release-20261122/final-preflight.json) reconfirms healthy collection, unchanged component settings, schema, retention and sufficient resources. Repeat health if execution is delayed.

## Signed Companion candidate, pending owner approval

The owner explicitly approved distinct **2.0.0-beta.11**, conditional on it being
unused/unreserved. No existing private-store directory, named release refs, GitHub
release or PR reservation was found before preparation. [Version-only draft PR45](https://github.com/Twich-Team/TwichUI-Market/pull/45)
contains seven consistent version/package metadata changes; runtime, contracts,
workflow and dependency selections remain unchanged from frozen Market.

- Original payload: `b39a35c01676b50dbc159f4793e0ad547676acfc`.
- Public signature/proof harness: `fa9f494ec9ae822f305dd406a5174942d503776c`.
- Original canonical push runs: Windows **45027451323**, Backend **45027451269**,
  Private website **45027451254**, all successful on the exact payload.
- Original installer artifact **14756114202**; archive SHA256
  `783821c57bf882c17cf0ea8d90f063af07cf6770e59ffbd49720e3a0a8a04b38`.
- Original installer **4,885,541 bytes**, SHA256
  `84dacad168dc212d8dda7d06f15ddc5a918f170ba1af0e9ece4e6373cd883129`.
- Actual installed executable SHA256
  `91f595fcc9a5d9779a2f7054c7469359da915a30b9a39b14fa6ab1e4620f817d`.
- Existing updater fingerprint
  `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`.

Original archives were downloaded through the GitHub connector, digest-checked
before bounded safe extraction. The existing active preparation verifier fetched
all exact-source canonical CI records normally through public GitHub API reads;
no host token was required. An earlier question about credentials came from
misreading an older helper and was explicitly withdrawn. No connector credentials,
SSH keys or signing keys were repurposed.

`prepare-companion-signing-input.py` passed on original bytes and original installed
receipts. The unchanged approved wrapper signed those bytes with pinned Tauri
**2.12.4** in the bounded, no-network rootless Node container, read-only private
inputs and internal output suppression. No API credential entered signing.
An initial container-start failure needed an empty nested mountpoint in the
public staging tree; no private input or trusted wrapper changed. Only public
signed-output permissions were subsequently made readable for the least-privilege
independent verifier. [Isolation receipt](evidence/opportunities-release-20261122/signing-isolation.json),
[independent verification](evidence/opportunities-release-20261122/independent-signature.json).

Proof-harness canonical push workflows passed: Windows **45028815202**, Backend
**45028815130**, Private website **45028815157**. The affected PR performance
workflow **45028820651** also passed. Historical simulator/transport failures and
native-only limitations remain in the development reports; they are not erased.
The supported Windows SDK installed the **original signed payload**, verified its
final executable, preserved credentials/cache/settings/uninstall state, reconnected,
synced/exported, and rejected corrupted bytes and incorrect signed versions.
[Actual signed-SDK receipt](evidence/opportunities-release-20261122/signed-update-acceptance.json).
Installer-process exit itself was not observed; final installed identity/state
were independently verified. A harness rebuild is not the release installer.

Windows Authenticode remains **NotSigned**, separately from the verified mandatory
Tauri signature. Physical PC/UAC/tray/Forever/frame-time/GC acceptance remains open.
There is no newly approved owner-release receipt, no staged publishable admission
bundle, and no private pointer transition. Beta.10 remains published. The final
exact-artifact approval must identify the version, original payload, installer
SHA256, key and actual CI evidence, with existing private-beta acknowledgements.
The [release rule](companion-v2-release-operations.md#final-approval-and-private-admission)
requires a separate owner receipt; the broad deployment instruction cannot fill it.

## Interruptions and preserved current state

The VM restarted twice during preparation; nine running production services have
new boot start times, **not operator rollout start times**. All 11 container IDs,
images and container configurations remain unchanged. Three unset DNS fields were
normalized by Docker from null to empty arrays; no DNS values changed and no host
network configuration was touched. Legacy backup remains stopped/restart-disabled;
migrate remains stopped with its original image reference/defaults. Neither old
historical discrepancy was corrected.

After the second restart, the host reported about **9 GiB total RAM** rather than
the earlier 14.5 GiB; approximately 7 GiB was available and disk had about 127 GiB
free. This is treated as concurrent external state, not reset. Heavy remaining
preparation is sequential and bounded. Both feeds completed successful checks
after the restart, market 2 / house 114 / 300 seconds unchanged and zero current
failures. [Fresh health](evidence/opportunities-release-20261122/health-after-second-vm.json).
The earlier auction HTTP-200 validation cause remains unresolved as documented
in the [read-only investigation](opportunities-overlay-repair-20261122.md).

Stable account, preference, mapping, retention authorization/policy, keyring,
recovery-file and signed-store fingerprints match the prior preparation baseline,
apart from one concurrent new browser session. All **395 original credential rows**
still match exactly; the additional session is preserved and was not created by
this task. [Credential preservation](evidence/opportunities-release-20261122/concurrent-credential.json).

No live API replacement, migration, collector repair, retry reset, instrumentation,
backup schedule change, retention activation, provider campaign, client/game
destination change, signed publication or task-created grant has occurred.
