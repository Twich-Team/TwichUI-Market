**Released after owner approval:** PR #33 is merged/deployed at `e49de6a`. [Current production acceptance and rollback](backup-management-release-acceptance.md). The candidate-stage audit and stop boundary below describe the earlier review stage and are superseded only for this completed release.

# Backup Management — owner review candidate

Draft [Market #33](https://github.com/Twich-Team/TwichUI-Market/pull/33), branch `feature/backup-management-retention`, targets the current `integration/companion-v2-metadata-recovery` (`177ea99`). Reviewed runtime source: `2796e70e622ef0f5c3270e7aef4d4428eabeef70`; CI fixture-directory/readiness repair: `20b99f5a0bc792e81e84be329f7beeaa84002fce` (runtime trees unchanged). Production is unchanged. Stop at owner review; no merge, deployment, schedule enablement, production retention edit or production archive deletion is authorized.

[Desktop/mobile screenshot gallery](evidence/backup-management/review.html) · [deployment, security, exact commands and rollback](backup-management-operations.md) · [read-only production audit](evidence/backup-management/production-audit.json) · [final live-state check](evidence/backup-management/production-final.json).

## Actual discovery and root cause

Earlier backups accumulated across scheduled, manual and release/rehearsal locations, with generic `development` naming and no administrator inventory/deletion controls. Release archives outside the scheduled root had no shared lifecycle. The former worker checked `used + pg_database_size` against its budget **before** post-success rotation; database allocation also overstated compressed archive requirements. That ordering could prevent replacements indefinitely. Old filename-only rotation did not understand recovery pins.

The state has since changed through a **prior owner-authorized task**, not this implementation: 33 dump copies / 4.913 GiB and a temporary release archive were removed, and recurring backups were disabled. This task's initial and final read-only inventories both find:

| Measurement | Actual production observation |
|---|---|
| Managed PostgreSQL archives | **0 files / 0 bytes** |
| Remaining original-root files | 29 orphan manifests, one stale status and one empty lock; **31 files / 16,809 bytes** |
| Backup filesystem capacity | **105,089,261,568 bytes / 97.9 GiB** |
| Available space at final read-only check | **5,750,120,448 bytes / 5.4 GiB**; includes unrelated filesystem activity |
| PostgreSQL allocation at final check | **4,121,859,763 bytes / 3.8 GiB**; distinct from filesystem and archive bytes |
| Scheduled backup status | Container exited; restart `no`; `disabled_by_owner` |
| Former, inactive schedule | Every 86,400 seconds, keep 30, 3 GiB budget; **not active** |
| Other Market archives in repository/worktree artifact roots | None found |
| Public health / data collection | HTTPS health 200; Market 2 alone enabled at 300 seconds, zero failures; schema `coverage_20261117` |

There is currently no local recoverable database archive in these managed locations. Historical restore receipts do not imply that their archives still exist. Off-host archive/keyring durability is unverified. PostgreSQL data uses `twichui-market_market-data`; scheduled backups used a host bind, not that database volume. The backup image's unused anonymous PostgreSQL mount is not a backup archive. Docker release images and private Companion release assets are excluded.

Classification covers scheduled/manual/release/restore-verification v2 archives, protected/required points, conservative legacy archives, incomplete partials and orphan manifests. Actual remaining files are orphan receipts; historical manifests alone cannot distinguish scheduled from operator `development` origin. Previous release dumps were outside the managed root and are now absent. No AMP, other-user, arbitrary host or unrelated Docker backup store was inspected or adopted.

## New controls and safety

Administration → Storage & backups now includes Backup Management: compact service/storage cards, real backup-mount capacity meter, compressed archive totals, local timestamps, server pagination, verification/protection/eligibility, details, authorized archive/manifest downloads, protect/unprotect, exact-name deletion and protected manual creation. Advanced policy limits, retention preview, orphan details and audit receipts use disclosure panels. Legacy service receipts are clearly labeled separately. Mobile layout and confirmation dialogs are reviewed in Chromium and WebKit, including America/Denver timezone rendering and accessibility checks.

The website gets no archive, live database-file, host-directory or Docker-socket mount. A private authenticated manager owns one verified root and a separate durable SQLite policy/audit volume. The existing browser-admin/CSRF/origin controls apply; members and desktop credentials are denied. Opaque IDs, directory descriptors, no-follow opens, single-link regular-file/owner checks and shared locking constrain filesystem actions. Downloads are rehashed, no-store and coordinated with all other operations. State survives restarts; interrupted jobs are not silently retried.

The default migrated policy is **disabled**. It proposes daily 2, weekly/monthly off, one minimum recovery point and a 3 GiB warning; no existing archive is adopted or deleted. Admin review/confirmation precedes policy saves. Enabled cadence starts a full interval after saving. UTC daily/weekly/monthly representative tiers overlap; protected/manual/release/legacy archives remain excluded from automatic rotation. The optional budget must accommodate a full replacement, and the fixed 2 GiB reserve cannot be lowered.

Every new dump is completed in a partial, fully decoded with pg_restore, SHA-256 hashed and atomically published with v2 restore-compatible metadata. PostgreSQL client/server majors must match. Integrity and actual restored-rehearsal evidence remain distinct. Only successful scheduled publication permits rotation. Failed creation/decode/publication/cleanup cannot delete valid recovery points. Active operation references and explicit protection block unprotection/deletion; the latest minimum integrity/restored points are retained. Deletion also rehashes **surviving** points to catch silent corruption before removing an older valid archive.

Deletion commits an audit intent before filesystem changes, removes archive/manifest under the shared lock and records actual results. Partial failure reports each component; restart only reconciles an exactly matching leftover manifest from a durable intent, never an existing archive. Audit records survive deletion. The old helper/worker no longer perform filename-only rotation. Existing operator restore rehearsals accept v1/v2 metadata and pin v2 recovery-gate archives. Release points outside the root stay outside management.

Storage pressure produces warnings and pauses creation. Estimates use measured archives plus margin, with a disclosed first-backup allowance. There is no pre-deletion. Emergency cleanup is a dry-run candidate list followed by individually selected exact-name confirmations, still preserving intact recovery points. Capacity may require an owner-approved storage/off-host decision.

No historical-retention model, authorization, compaction setting, collector cadence, provider settings, workshop pricing/delivery or desktop distribution changes are included. Removing an archive cannot issue live history deletion SQL.

## Acceptance evidence

| Check | Result and evidence |
|---|---|
| Filesystem, concurrency, policy and safety | **21 passed**, [focused results](evidence/backup-management/filesystem-tests.txt). Inventory/pagination, disk mount, daily/weekly/monthly selection, protection/references, final restored point, exact confirmation, partial deletion/restart, changed/corrupt files, silent survivor corruption, symlinks/hardlinks/traversal, busy operations, policy persistence, interrupted jobs, storage/budget refusal, failed pg_dump/decode/cleanup and missing roots. |
| Admin API, CSRF, device/member denial and audit | **9 passed**, [API results](evidence/backup-management/api-tests.txt); includes streamed download close and unsafe filename refusal. |
| Actual PostgreSQL archive/restore/rotation | **Pass**, [receipt](evidence/backup-management/postgres-acceptance.json). Three real custom archives A/B/C; keep-two removes A only after C's full verification, leaving B/C. A survivor restores 200 fixture rows. Manual deletion removes an eligible archive and manifest; protected restored point remains; source fingerprint unchanged. Unique disposable restore database is removed afterward. |
| Backend regressions | **670 passed in exact-source CI**, including all nine new API tests. Local missing script/source mounts were corrected; both affected pricing-shadow tests pass unchanged. |
| Operational and scoped contracts | **65 operational** and **16 scoped contract** checks pass. |
| PostgreSQL migrations | Existing upgrade → schema check → downgrade → upgrade passes on a fresh isolated database; no new PostgreSQL migration. All eight existing populated migration-preservation checks pass in exact-source CI. |
| Frontend | TypeScript/Vite build and **132 unit tests** pass. |
| New browser flows | Four scenarios each in Chromium and WebKit: inventory/details/pagination, strong deletion/policy review, mobile pressure/disclosures, empty/unavailable state and actual service creation/protection/download/deletion. UI gallery fixtures are explicitly synthetic; the actual-service case uses only isolated market_test. |
| Existing browser regression | **74 browser scenarios pass in final CI**, including all ordinary and specialized Chromium/WebKit suites plus eight new backup scenarios. Local harness trace/keyring issues were corrected; CI fixture ownership and post-restart API readiness are explicit. No product assertion was waived. |
| CI | **All final checks are green** at `20b99f5`: [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44233063582), [Website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44233063756), [Windows](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44233063576). Exact run/job conclusions are recorded in [CI receipts](evidence/backup-management/ci.json). Backend includes all existing migration/operational checks and real backup rehearsal; website includes existing Chromium/WebKit and new real-service scenarios; Windows retains native/installed compatibility. No signing or publication is performed. |

No production backup/restore or destructive action was used for acceptance. All database mutation/restore fixtures use isolated `market_test` and uniquely named disposable restore databases. Prepared backend/manager images are checked against every corresponding runtime Python module; immutable candidate/rollback pins are additive review artifacts. Screenshots and receipts are not claims of production promotion.

## Cleanup, release and rollback proposal

**Proposed production archive cleanup: zero files / zero reclaimable archive bytes.** Preserve the 29 orphan manifests, stale receipt and lock unless the owner explicitly selects and confirms them; their 16.4 KiB total is negligible. Legacy cleanup remains a separate explicit operator procedure. Do not make the new retention proposal retroactively delete production files.

[Operations](backup-management-operations.md) contains the complete observed production Compose/environment chain, immutable candidate/prior-image pins, scoped start/replace commands, preflight and acceptance requirements. Owner review must first resolve whether a new retained pre-release backup/restore is authorized under the existing no-retained-dumps instruction. This candidate does not infer that approval. It does not enable scheduling during installation. A full production restore rehearsal also needs additional reviewed capacity or an isolated off-host target: current free space must accommodate a restored allocation, archive, WAL overhead and the fixed production reserve. The small disposable acceptance fixture is not a production sizing claim.

Rollback stops only the new manager and restores the prior compatible API/local-API/frontend images. Preserve the owner-disabled legacy-worker overlay, unified source-aware collector, schema, live history, archives, token/state and receipts. No volume removal, downgrade or production restore is part of rollback. Code rollback cannot recreate an explicitly deleted archive.
