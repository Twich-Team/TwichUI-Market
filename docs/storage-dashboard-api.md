# Storage dashboard read models

These additions preserve existing endpoints and response fields. They do not alter backup execution, destinations, retention policy, authorization, recovery evidence, migration workers or deletion safeguards. No migration, new dependency, sampler, background worker or telemetry table is introduced.

## Database history

`GET /api/v1/admin/storage` retains its current response. Each `growth.samples` entry additionally exposes the already persisted `filesystem_available_bytes`, `retention_eligible_rows` and `retention_processed_rows`. Missing measurements remain `null`. These are measurements of PostgreSQL's configured underlying filesystem, never of the NAS. Existing hourly sampling and 90-day retention remain unchanged.

## Maintenance health

`GET /api/v1/admin/retention/health` adds:

- `composition`: `status`, `total_bytes`, `categories` (`key`, `label`, `bytes`, `percent`) and an accounting `notice`. PostgreSQL relation metadata measures table and TOAST allocation separately from table indexes. The difference between these relations and total database allocation is Other. Shared derived history caches remain Other; they are not assigned to a fictitious exclusive daily tier. No listing/table population scans are used for this chart. Unsupported databases or an inconsistent concurrent allocation measurement return empty categories with a non-measured status.
- `activity`: `since`, `measured_at`, `unit: "records"`, `days` and a `notice`. Up to 31 UTC dates, beginning at midnight 30 days ago, are summarized from retained `Snapshot.listing_count` metadata and actual committed `RetentionBatch` receipts. Each observed date has optional `raw_added`, `raw_removed` and `removed_by_category`. An absent field/day is unknown, not a recorded zero. The query does not scan raw listings. Counts describe recorded content generations and deletions; they do not measure aggregation output, reusable pages or reclaimed filesystem bytes.

The existing administrator dependency and three-second PostgreSQL statement bound remain in effect. Composition adds one bounded relation metadata query; activity adds two date-filtered metadata aggregates. The existing largest-table diagnostics and 20 recent execution receipts remain available.

## Backup inventory

`GET /api/v1/admin/backups` accepts existing `offset` and `limit` plus optional:

| Parameter | Values |
|---|---|
| `search` | Case-insensitive text, maximum 190 characters |
| `storage_id` | `local` or an existing-format 32-character destination identifier |
| `protection` | `all`, `protected`, `unprotected` |
| `verification` | `all`, `restored`, `integrity`, `unknown` |
| `backup_type` | `all`, `scheduled`, `manual`, `release`, `restore-verification`, `legacy`, `unknown` |
| `sort` | `created_desc` (default), `created_asc`, `bytes_desc`, `bytes_asc` |

Filtering/sorting occurs before pagination over the manager's existing measured inventory. `total` and `total_bytes` retain their original meaning: recovery points deduplicated across active and previous migration locations. New `matched_total` counts the matching recovery points. Query values are validated on both sides of the private service boundary and encoded as URL parameters, never used as SQL or filesystem paths. Last-known inventory caches include a digest of normalized filters so a stale response cannot return a different query's results. The existing maximum 20 cached pages remains.

`inventory_by_storage` maps actually inventoried storage IDs to physical archive `count` and `bytes`, before duplicate migration originals are removed from the recovery inventory. A missing location was not measured. `bytes` is `null` when any archive size there could not be measured. These values are Market archive consumption, not total filesystem utilization; duplicate originals consume space without increasing recovery point count. Existing `inventory_stale` applies to the entire cached response.

`reliability` summarizes existing immutable `backup.published` and `backup.failed` receipts over 42 UTC dates. It provides `since`, `days` (`day`, `succeeded`, `failed`), up to 200 recent `attempts` (`at`, `status`, `origin`, optional `backup_id` and `bytes`), `truncated`, `schedule_history_available: false` and a notice. At most 1,000 receipt outcomes are read, using the existing action/time index. A 1,001st row marks the result truncated. Unknown days and missed schedules are not inferred from today's policy. This creates no new event storage and does not reconstruct historical schedules.

All mutations retain their existing routes, CSRF checks, manager authorization, explicit protected/reserved/recovery-loss confirmations, dependency checks, audit receipts, shared locks and revalidation. The previously active live migration completed independently; deployment still requires separate owner authorization and a fresh check that no manager operation is active.
