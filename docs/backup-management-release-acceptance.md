# Backup Management — production acceptance

Owner instruction: **“Merge and deploy.”** This explicitly approved PR #33 and its administration design/release plan. That release is complete at [market.twich.gg](https://market.twich.gg/administration). Earlier review-only holds are superseded for this exact scope. Scheduled backups remain disabled; no production backup policy, historical retention, collector/provider configuration or desktop distribution was activated or changed.

## Exact source and services

[PR #33](https://github.com/Twich-Team/TwichUI-Market/pull/33) merged into `integration/companion-v2-metadata-recovery` as **`e49de6a829b1c281e16a3da3c1baa377a1fb77d8`**. Its complete tree equals approved review `9984a71` (`ab706209a6dfcf5e8868a4352fab53bbf994489d`). Prepared immutable images were reused; no application rebuild or substitution occurred.

- API/local API: `sha256:6d764fbe8581680a4da806015d6a7f6f05483f0c57b8d64b89d55bd5a1812d86`.
- Frontend: `sha256:ff172a984cba5d20359fc5e18d18cac226f8858e9422eb7138b0e644f8a00dc1`.
- Private manager: `sha256:79cea119910ad3353f8a35ce21d079fafbcab0a757c0734bfe3bce6055c68565`.
- Live schema remains **`coverage_20261117`**. No PostgreSQL migration was introduced or applied.
- Original collector, PostgreSQL, enrichment, monitor and stopped legacy backup IDs/start times/environment remain unchanged. Market 2 / house 114 alone continues at **300 seconds**; subsequent source-feed health is recorded below. Destructive historical retention remains unauthorized with zero batches.

[Before](evidence/backup-release/containers-before.json), [after](evidence/backup-release/containers-after.json), [sanitized Compose preflight](evidence/backup-release/compose-preflight.json), [final state](evidence/backup-release/final-state.json).

## Merged-source verification

All exact merged-source checks pass: [Backend 44235190603](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44235190603), [Website 44235190763](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44235190763), [Windows 44235190866](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44235190866). This includes **670 PostgreSQL tests**, all eight populated migrations, **65 operational / 16 scoped checks**, real backup rotation/restore, build/dependency audit, **132 frontend tests / 74 browser scenarios**, native/installed Windows compatibility and existing signed-candidate selection. No new signing or publication occurred. [CI identities](evidence/backup-release/ci.json).

## Full production backup, isolated restore and preservation

The scoped release used a temporary **653,148,210-byte** custom archive, SHA-256 **`8f6fc1fb5eda8ce19f31b4b6fafa9b529506905f994724abf78d0e0011d1ee29`**. Streaming creation enforced the 2 GiB live-filesystem reserve and coordinated through the original shared lock. This temporary archive was outside the managed backup root; no existing archive/manifest was removed or adopted.

The complete database restored with constraints into a dedicated, no-port PostgreSQL instance on a **5 GiB RAM-backed filesystem**, capped at **6 GiB memory with swap disabled**. Host RAM availability was checked before allocation. This resolved the insufficient disk capacity for a second full database without consuming the live filesystem reserve. All **46 restored tables and every original field** had identical fingerprints before/after the candidate schema check. Both predecessor and candidate images decrypted both existing provider envelopes using the unchanged read-only keyring, with zero upstream provider requests. The disposable restore database/network and its private credentials are retired.

[Archive receipt](evidence/backup-release/backup.json), [full restore](evidence/backup-release/restore.json), [before](evidence/backup-release/restored-before.json), [after](evidence/backup-release/restored-after.json), [prior](evidence/backup-release/credential-continuity-prior.json) / [candidate](evidence/backup-release/credential-continuity-candidate.json) credential compatibility.

Production original-row checks preserve **11,933,839 original listings and 1,109 observations**, plus original snapshots/statistics, users, credentials and mapping/retention records. Provider flags/budgets/rate settings/encrypted envelopes and keyring fingerprints are unchanged. Real collection continues; newer rows are outside the pinned pre-release cutoffs.

The initial strict comparison detected a **concurrent owner Explorer-sort preference save**, revision 16→20, at **04:14:12 UTC**, before the temporary verification session was issued. It was not caused by the acceptance browser, and no preference repair/write was made. The original archive reproduces the exact initial preference projection. We retained that original baseline and separately pinned the concurrently saved preference for the second strict comparison; all remaining original projections match. This preserves the owner's newer choices instead of overwriting them or claiming the original preference row stayed byte-identical.

[Original production baseline](evidence/backup-release/preservation-original-before.json), [concurrent preference evidence](evidence/backup-release/preference-concurrency.json), [strict verification with that preserved save](evidence/backup-release/preservation-after-concurrent-preference.json), [provider/keyring preservation](evidence/backup-release/configuration-preservation.json).

After acceptance, only the task-created temporary archive and private temporary verification files were removed under the existing owner policy against accumulating retained dumps. Original backup-root file hashes remain identical. Original rollback images, signing material and signed Companion releases are retained. [Exact temporary cleanup](evidence/backup-release/temporary-release-cleanup.json).

## Actual public acceptance and schedule state

[Real desktop/mobile gallery](evidence/backup-release/review.html), [HTTPS results](evidence/backup-release/public-acceptance.json). These use actual production data/measurements, not synthetic fixtures.

Authenticated Backup Management returns **200**; anonymous inventory **401**, missing-CSRF creation **403**, and an unknown archive download fails closed **409**. Desktop/mobile rendering, local timestamps, storage cards/capacity display, empty inventory and advanced artifact/audit/retention preview pass; no page errors or mobile overflow. One audited 15-minute session on the existing owner account was used, then revoked and independently confirmed **401** over public HTTPS. No account or password was created/reset. No backup creation, deletion, protection toggle or policy save was exercised through production controls.

The new manager's disabled policy persists across its restart: daily 2, weekly/monthly off, minimum recovery points 1, no optional byte cap, 3 GiB warning, fixed 2 GiB reserve, **enabled=false**, no next due time. These are an inactive proposal, not an activated schedule. The original legacy worker stays stopped/restart `no`.

Current managed inventory is **zero archives / zero bytes**. The original root still has 29 orphan archive manifests, one stale status file and one empty lock (31 files / 16,809 bytes); the interface classifies the 30 JSON files as unmanaged/orphan artifacts. No cleanup of these files is proposed or performed. Filesystem availability after temporary cleanup is about **5.3 GiB**. There is no retained local recoverable database archive under the owner's current policy; historical restore receipts do not imply otherwise. An administrator can later explicitly create/protect an archive or approve a schedule using the new controls.

The manager alone has the verified archive root and private persistent state volume. APIs retain their existing read-only keyring/release/status mounts and get only the narrowly scoped service token; neither an archive directory nor Docker socket is mounted into them. Manager has no published host port. [Initial manager](evidence/backup-release/manager-initial.json), [restart persistence](evidence/backup-release/manager-restart.json), [session revocation](evidence/backup-release/session-revocation.json).

## Current operation and rollback

Keep the original production project directory, both original environment files and complete overlay chain. The exact observed chain is saved in [Compose preflight](evidence/backup-release/compose-preflight.json); after the owner-policy and unified-coverage overlays it appends this release worktree's `compose.backup-management.yaml` and `compose.backup-review-images.yaml`. Preserve the private token at the configured stable production location and the `backup-management-state` volume. Retain this worktree while production configuration labels refer to these overlay files. All actual container bind mounts, including the token and archive root, use stable production locations.

[Full scoped commands](backup-management-operations.md#prepared-commands-used-for-the-approved-release) document the actual promotion procedure. The owner approval gate is satisfied for this completed release, not for future schedule activation, deletion or unrelated work. No bare/unscoped Compose update, collector replacement, migration, infrastructure modernization or desktop release occurred.

Compatible rollback: stop only `backup-manager`, then append `compose.backup-review-rollback.yaml` last and replace only `api local-api proxy` with `--no-deps --no-build --pull never --wait`. Those predecessor images remain available. Retain schema/history/state/receipts, the original disabled-worker overlay and the source-aware collector. Do not restore over live PostgreSQL, downgrade schema, remove volumes, start the legacy worker or force desktop downgrades. A later roll-forward can reuse the preserved policy/state. No rollback was needed.

## Observed upstream collection warning

The unchanged collector completed its normal 04:20 UTC check after promotion. Its subsequent 04:25/04:30 checks were partial: auctions returned HTTP 200 but failed the existing transport/identity/payload guard; commodities subsequently returned **upstream HTTP 500**. The last complete market observation remains retained, and no false zero-supply snapshot is published. These observations are recorded rather than claiming zero failures throughout acceptance. Collector image, container identity, environment and schedule are unchanged; no unrelated provider retry/campaign or collector-code repair was performed. This does not change the verified backup-management behavior or the original-history preservation proof. See the exact feed statuses in [final-state.json](evidence/backup-release/final-state.json).
