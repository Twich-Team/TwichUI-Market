# Backup management operations and owner review gate

This candidate is **not deployed**. Installing the feature does not authorize a production backup, deletion, schedule activation or historical-data retention. The owner currently requires recurring backups off and no retained production dumps. The read-only audit found **zero recoverable database archives**, not the old budget-full inventory. The active production overlay `compose.owner-backup-policy.yaml` must remain in place. No populated PostgreSQL migration is introduced; management state uses its own durable SQLite ledger and archive manifests.

## Ownership and scope

`backup-manager` alone mounts the single, explicitly reviewed host archive root at `/backups` (mode 0700, service-owned). The API mounts only a private service token, not archives, host storage, PostgreSQL data or Docker sockets. Token-authenticated internal HTTP exposes fixed inventory/policy/create/protect/delete/download/manifest operations. Administrator browser sessions, existing CSRF/origin checks and API security receipts precede requests; native device/member sessions cannot use this boundary. No host ports are added. Do not publish port 8091 or attach unrelated workloads to its private network. The manager additionally needs the existing database network for pg_dump; its filesystem capability remains confined to the reviewed bind and dedicated state volume.

A pinned directory descriptor, openat/O_NOFOLLOW, regular-file/single-link/owner checks and opaque hashed identifiers prevent client path selection. Symlinks and unknown ownership fail closed. All writers, downloads, deletions, operator restores and policy edits share `.backup.lock`. Existing helper rotation is removed: filename patterns cannot establish recovery ownership. Never bypass the lock with ad-hoc release/restore shell commands against this root.

The original worker is left disabled in production and is not replaced/started by this overlay. Its source no longer does filename-only rotation. `scripts/backups.py --keep` remains accepted for compatibility but no longer authorizes deleting archives. Its v1 archives are conservative legacy entries. Existing release archives in worktree artifact directories are **outside** the manager's scope; they are neither adopted nor deleted. Docker images, private Companion installers, keyrings, AMP and host backups are excluded.

## Policy and rotation

First initialization creates an audited **disabled** policy proposal: daily 2, weekly/monthly off, minimum recovery points 1, no total-byte budget, 3 GiB warning and a fixed 2 GiB reserve. These values do not infer activation of old environment settings. No existing archive is migrated or removed. The explicit owner-disabled production schedule remains disabled.

On an explicitly approved later save, the schedule waits a full configured interval. Restart preserves policy and next due time; it does not dump at startup. Missed runs are bounded to one replacement, with no catch-up burst. Weekly/monthly retention keeps the newest scheduled archive in each distinct UTC week/month; daily retains UTC day representatives. The union of tiers is retained, so one archive may satisfy several tiers. An hourly cadence may retain only the newest archive within a day. Only manager-v2 **scheduled** archives can rotate; manual, release, restore-verification, legacy, required and protected files do not rotate. Manual archives start protected. Saving previews a policy but never executes cleanup.

A new archive is written to a mode-0600 partial, with actual-output budget and free-space checks plus a two-hour deadline. pg_dump and PostgreSQL server major versions must match. pg_restore decodes the **entire** custom archive to `/dev/null`, then SHA-256/size/version/identity metadata is written and fsynced before the archive is atomically published. A crash between pair publication leaves an identifiable incomplete/orphan artifact, not an eligible point. Only successful scheduled publication permits retention. A failed dump, decode, hash, fsync or publication cannot cause rotation.

Archive integrity is **not** restore verification. Only a separately completed isolated pg_restore rehearsal with its actual evidence may set `restoration_verified_at` and `restored`. The existing operator `scripts/backups.py verify-restore` accepts v1/v2 metadata, preserves the shared lock, and pins v2 rehearsed archives using `required_by=['restore-recovery-gate']`. This also protects backups used by the historical-retention authorization gate, which is otherwise unchanged. Release backups must start protected and declare `required_by` before active recovery/retention/release operations. The web UI cannot clear operation references. An operator may release a completed operation reference only under its separate recovery authorization and shared lock, retaining a receipt; this candidate exposes no HTTP bypass. Legacy points cannot be unprotected or deleted through the manager.

The newest configured minimum number of integrity points and restored points is guarded. Deletion rehashes the selected archive **and surviving recovery points**, refuses insufficient intact survivors, and never removes the final intact restored point. Protect/unprotect changes have durable intent and result receipts. Selected manual/release points may be explicitly unprotected only when no active reference exists; they remain excluded from automatic rotation.

## Low storage and deletion

The replacement estimate is 1.5 times the largest of the last five measured valid archives plus 64 MiB; the first attempt uses a disclosed 1 GiB allowance. Database allocation is not a compression estimate. Before starting, existing archives plus the allowance must fit the optional budget, and the actual backup filesystem must have allowance plus the 2 GiB reserve. Actual streaming output also checks budget and free-space reserve; other processes' growth can still cause a safe abort. The reserve is a minimum guard, not a filesystem quota or guarantee against unrelated writers. Owner sizing must account for PostgreSQL/WAL growth and a full replacement. No pre-deletion occurs.

A full budget can still require an explicit operator decision: preserving recovery points takes precedence over making a new full dump fit. The UI shows filesystem available bytes (excluding privileged reserved blocks), capacity, archive bytes, warnings and a dry-run retention preview. Storage pressure pauses creation. Emergency cleanup is **individual explicit deletion** from the preview/inventory, with exact-name confirmation; all normal recovery safeguards remain in force. Increasing storage or making an authorized off-host copy may be necessary. No API procedure removes the sole recoverable point.

Deletion commits a durable intent with original metadata before unlinking. It removes archive then manifest under the shared lock, fsyncs, and records actual results. The returned `unlinked_bytes` is logical archive size, not a claim about instantly reclaimed physical blocks. Partial removal reports both outcomes. On restart, the service only reconciles a leftover manifest if a durable intent exists, the archive is absent and its metadata still matches exactly. A surviving archive is never automatically retried/deleted on restart. Audit receipts outlive archives. Downloads rehash, hold the lock while streaming, and are no-store; the corresponding manifest is separately authorized and downloadable through details.

## Exact deployment sequence after owner review

1. Reconfirm current integration/production versions, active overlays, rootless context, available disk and collector state. Re-run the read-only inventory. The review evidence must match the commit being promoted. Keep original compatible source-aware APIs/collector and all signed releases.
2. Obtain owner approval for **this release only**, including whether any new retained backup/rehearsal is now authorized under the current no-retained-dumps policy. If an archive is authorized, use the existing consistent release backup/isolated restore procedure and preservation fingerprints; never restore over live PostgreSQL. This implementation task creates no production archive. A schedule enablement is a separate explicit policy decision.
   Capacity gate: the source currently allocates about 3.8 GiB, with about 5.4 GiB filesystem availability at the recorded check. A full restored copy, a fresh compressed archive, restore/WAL overhead and the 2 GiB production reserve may not fit together. Before a production rehearsal, obtain reviewed additional headroom or use an isolated off-host restore target; never reuse the 512 MiB synthetic-fixture tmpfs for this live dataset. The older one-off helper still uses conservative database-allocation/budget preflight; do not override it by deleting recovery points. The reviewed manager can create a separately authorized protected manual/release point with measured-size safeguards, but starting that operation and arranging adequate restore capacity remain owner release decisions.
3. Build reviewed immutable backend/frontend/manager images from the approved commit. Pin their digests in a release overlay. No database migration is needed. Prepare the existing absolute host backup directory at mode 0700 and a private random token file under the owner's project-managed secrets location. Token: at least 32 random bytes; API uid 10001 must be able to read the mounted secret without exposing the host directory. Docker Compose file secrets do not implement uid/mode remapping: validate read access in the candidate API with no token output; use a dedicated read-only file accessible only through the intended mounts. Do not print rendered Compose environment/secrets.
4. Preserve the **complete current production chain**, including metadata release → chart → API overlays, the current usability/mobile overlays, `compose.owner-backup-policy.yaml` and `compose.unified-coverage-release.yaml`. Append `compose.backup-management.yaml`, then the new immutable-image overlay. Set `MARKET_MANAGED_BACKUP_ROOT=/home/marketdev/projects/TwichUI-Market/backups` and `MARKET_BACKUP_TOKEN_FILE` to the reviewed private token file. Do not change the Compose project or database volume. Preflight `config --quiet` and inspect sanitized service/mount/resource differences. Confirm backup-manager has no published ports, API has no archive/socket mount, and the old `backup` remains stopped/restart no.
5. Explicitly start **only** `backup-manager` using `--profile backup-management up -d --no-deps --no-build --pull never backup-manager`, then replace **only** `api local-api proxy` from the exact prepared images with `--no-deps --no-build --pull never`. No collector, database, monitor, enrichment, provider, bridge or desktop restart/configuration belongs to this feature. The manager starts with its schedule disabled. Do not invoke bare `compose up` or the old operations profile.
6. Verify authenticated desktop/mobile inventory, filesystem device/size against host statvfs, zero unexpected archive creation, default disabled schedule, unauthorized 401/403 and CSRF refusal, API audit receipts, existing data/credential fingerprints, collector cadence and live health. Inspect private state-volume persistence across a manager-only restart. Do not exercise production deletion/creation/protection/schedule changes without their separate exact authorization. Record owner visual acceptance and any authorized later policy revision.

Rollback: stop only backup-manager, restore the pre-feature pinned API/local-API/frontend images, retain the original disabled-worker overlay and full compatible unified-coverage chain. Do not start the legacy scheduled worker, downgrade PostgreSQL/schema, delete state/manifests, remove volumes, restore over live data or roll back the source-aware collector. Keep `backup-management-state`, private token, archives and all receipts for diagnosis/roll-forward. A rollback of application code cannot recreate a deleted archive. No production deletion is part of this candidate.

## Proposed production cleanup

Actual discovery: zero managed archives and zero reclaimable archive bytes. Preserve the 29 orphan manifests, stale status and empty lock (16,809 bytes total). These are historical receipts with negligible space impact; deleting them needs explicit file selection/confirmation and is outside the automated v2 policy. No other Market dump was found in repository/worktree artifact roots. No unrelated volume/host cleanup is proposed. Off-host backup/keyring durability remains unverified.

## Prepared commands (not executed on production)

The current production environment files and full overlay list were read from the live container's Compose labels. [Prepared immutable candidate pins](../compose.backup-review-images.yaml), [prior-image rollback pins](../compose.backup-review-rollback.yaml) and [image/source receipts](evidence/backup-management/images.json) are review artifacts. Candidate images are local to this rootless host; no registry publication is implied. Reconfirm all paths and image IDs after owner approval, especially if another release has intervened.

```bash
MARKET_PROD_ROOT=/home/marketdev/projects/TwichUI-Market
MARKET_REVIEW_ROOT=/home/marketdev/.codex/worktrees/backup-management-retention/TwichUI-Market
# Set MARKET_BACKUP_TOKEN_FILE privately after approval; do not echo the token.
export MARKET_MANAGED_BACKUP_ROOT="$MARKET_PROD_ROOT/backups"
export MARKET_BACKUP_TOKEN_FILE
MARKET_BACKUP_DC=(docker --context rootless compose -p twichui-market
  --project-directory "$MARKET_PROD_ROOT"
  --env-file "$MARKET_PROD_ROOT/.env"
  --env-file "$MARKET_PROD_ROOT/.env.combined-release"
  -f "$MARKET_PROD_ROOT/compose.yaml"
  -f "$MARKET_PROD_ROOT/compose.tls.yaml"
  -f "$MARKET_PROD_ROOT/compose.traefik.yaml"
  -f "$MARKET_PROD_ROOT/compose.companion-private-beta.yaml"
  -f "$MARKET_PROD_ROOT/compose.combined-release.yaml"
  -f "$MARKET_PROD_ROOT/compose.admin-release.yaml"
  -f "$MARKET_PROD_ROOT/compose.explorer-release.yaml"
  -f "$MARKET_PROD_ROOT/compose.polish-release.yaml"
  -f "$MARKET_PROD_ROOT/compose.foreverdb-release.yaml"
  -f "$MARKET_PROD_ROOT/.worktrees/usability-release/compose.usability-release.yaml"
  -f "$MARKET_PROD_ROOT/.worktrees/mobile-release/compose.mobile-release.yaml"
  -f "$MARKET_PROD_ROOT/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-release.yaml"
  -f "$MARKET_PROD_ROOT/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-chart.yaml"
  -f "$MARKET_PROD_ROOT/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-api.yaml"
  -f "$MARKET_PROD_ROOT/compose.owner-backup-policy.yaml"
  -f "$MARKET_PROD_ROOT/compose.unified-coverage-release.yaml"
  -f "$MARKET_REVIEW_ROOT/compose.backup-management.yaml"
  -f "$MARKET_REVIEW_ROOT/compose.backup-review-images.yaml")
"${MARKET_BACKUP_DC[@]}" --profile backup-management config --quiet
# OWNER-APPROVED RELEASE ONLY; the commands below are not executed by this task.
"${MARKET_BACKUP_DC[@]}" --profile backup-management up -d --no-deps --no-build --pull never backup-manager
"${MARKET_BACKUP_DC[@]}" up -d --no-deps --no-build --pull never api local-api proxy
# Compatible code rollback, only if needed after that approved release:
"${MARKET_BACKUP_DC[@]}" --profile backup-management stop backup-manager
"${MARKET_BACKUP_DC[@]}" -f "$MARKET_REVIEW_ROOT/compose.backup-review-rollback.yaml" up -d --no-deps --no-build --pull never api local-api proxy
```

Keep the token mount and state volume during rollback; the prior API ignores the feature. No command removes a volume, runs migrations, starts the old backup worker, enables the manager schedule or removes an archive. Retain the explicit owner-disabled policy. A later management-service restart is safe only while its persisted schedule remains in the owner-approved state.
