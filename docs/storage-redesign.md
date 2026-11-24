# Storage & Backups dashboard

Review candidate only. Production services, destinations, migration, archives and maintenance must not be changed by this task.

Baseline: main c6946cd. Separate feature/storage-backups-dashboard worktree preserves the original dirty release checkout.

## Feature parity inventory

| Existing feature / operation | New location |
|---|---|
| Manual creation, running backup and latest outcome | Header / Overview; Backups |
| Scheduled policy, interval, daily/weekly/monthly tiers, minimum points, byte budget, warning reserve, confirmation | Backups → Backup Policy |
| Recovery inventory, paging, selection, protected and ordinary explicit deletion; completed reservations and active-use blockers | Backups → inventory / details / existing confirmation dialogs |
| Archive download, manifest, SHA256, archive integrity, isolated restore, protection reason and management | Backups → details drawer |
| Legacy artifacts, rotation dry run, immutable operation receipts | Backups → diagnostics disclosures |
| Local/mounted/native SMB, active destination, connectivity/capacity/permissions | Storage → location cards / diagnostics |
| Host, port, share, username/domain, masked saved password, encryption, directory, validation | Storage → Configure dialog |
| Browse, breadcrumbs, paging, create folder, choose directory | Storage → NAS folder dialog |
| Preview, copy/checksum/activate, interrupted/error state, explicit verified-original cleanup | Storage → migration workflow; active summary on Overview |
| Interrupted partial-file cleanup | Storage → diagnostics |
| Automatic isolated restore, exact recovery expiry/remediation | Overview health; Storage and Maintenance |
| Current allocation, actual hourly measurements/ranges/gaps | Overview → Database Growth; diagnostics |
| DB cap, actual DB filesystem reserve, WAL, live/dead tuple estimates/autovacuum | Maintenance → database diagnostics |
| Historical raw/intraday/daily plus operational/security periods, proposal save | Maintenance → Edit Retention Policy |
| Dry run, coverage, aggregate/recovery safety, explicit batch, automatic enable/pause, authorization identity | Maintenance → existing retention controls in dialog |
| Cleanup execution history, stage counters, aggregation/daily support status | Maintenance → history / health / activity |
| Original legacy backup-worker receipts | Maintenance → legacy diagnostics |

## Initial wireframes

- Overview: title / Create Backup; four metrics; conditional attention; wide growth chart + health list; storage capacity rows.
- Backups: policy summary; history + reliability; compact inventory; details drawer and focused policy dialog.
- Storage: per-location cards; focused migration; configuration/folder dialogs; forecast and diagnostics disclosures.
- Maintenance: health; configured lifecycle; composition + record activity; execution history; policy dialog and diagnostics.

## Measurement decisions

Reuse ECharts, TanStack Query and native dialog focus management. No chart framework or background worker. Shared private query keys; active jobs poll faster, ordinary health refreshes each minute. Database/backup capacity is shown independently where filesystem identity cannot prove colocation. NAS totals include other files. Duplicate archive copies consume real storage and are not claimed to be distinct recovery points. No guessed database/backup allocation segments.

Hourly PostgreSQL allocated bytes are recorded data with gaps. Logical deletion counters are records removed, never disk reclaimed. Forecasts require actual filesystem history and sufficient observations; database allocation growth alone is not a NAS capacity forecast. Unknown calendar days are not missed backups. No new unbounded event ledger or historical backfill.

## Operational observation

Read-only SQLite URI inspection at task start found migration 4dd02526379c4e0083f62f68fab4674c running, with copied=3 and bytes_copied=6321127985. No manager operation, service restart, storage mutation, backup deletion or actual cleanup was initiated. Recheck before any separately authorized future deployment.

## Validation

All four final hosted workflows pass: Backend, Private website, Native NAS storage and Windows companion. [CI record](evidence/storage-redesign/ci-results.json).

Application `1137602` and test assertion correction `8d12051` pass 776 PostgreSQL, 157 operational, 149 frontend and 17 dashboard browser checks locally, plus three existing backup-management fixture checks in each of Chromium and WebKit and an all-four-page 2560×1440 review. TypeScript/Vite build and axe checks pass. Existing integration selectors retain their assertions under the new navigation and dialogs. No package changes were introduced.

The visual review corrected capacity accounting, header/drawer sizing, chart axes and legends, phone unavailable metrics, and lazy-chart capture. The baseline capture honors its original requested inventory page size. [Review report](storage-redesign-review.md) and [before/after gallery](evidence/storage-redesign/review.html) retain the final evidence.

The live migration independently completed at 11:30:35 a.m. America/Denver on November 24; durable state records six archives and originals preserved. This task did not remove originals or change production services/settings. Deployment requires separate owner authorization and a fresh operational preflight.
