# Provider rate management progress

## Isolation and baseline

- Separate Cloud worktree and feature branch created from pushed integration SHA `68c075138d5f50608c741b0e51b7013d9bf8769d`. No other branch/worktree is modified; production and addon repository are untouched.
- Read AGENTS.md, implementation/progress and item modernization plans/progress plus existing metadata provider decisions. The integration head already includes bridge migration `bridge_20261115`; the additive provider migration must descend from it.
- Initial Cloud resources: 18,007 MiB RAM, ~17 GiB available, 60 GiB free disk. Proposed ports 19432/19480/19481 unused. Docker reports rootless; no production services, volumes, networks or secrets are present/used.
- Git HTTPS reads work. GitHub CLI's inherited token is invalid; connected GitHub tools work. Push access and PR creation will be verified separately.

## Audit

Existing `metadata_recovery.reserve_budget` charges persistent anchored hourly/daily counters and spaces calls; a session advisory lock serializes recovery workers. Task leases commit before I/O and preserve charged usage on crashes. Credential tests share this reservation. Enrichment artwork uses the same counters but currently holds its transaction during I/O. Legacy optional resolver paths and operator diagnostic scripts need to share the same reservation as well.

Current ceilings are application choices, not key entitlements: ForeverDB 60/hour, 500/day; Everloot keyless 20/hour, 100/day or validated 240/hour, 2,000/day; TheWoWDB 60/hour, 500/day; Blizzard metadata 240/hour, 2,000/day. No minute window or token bucket exists. Editing settings does not reset counters. 429 supports Retry-After dates but lacks bounded adaptive pacing and response quota observations. A queued 429 retry can be skipped by source caching or an exhausted job budget. Validation selects one provider before checking cooldown, potentially delaying others. Existing UI shows raw cumulative counters even after a window expires.

## Next

Implement scheduler/schema and independent limits API; research findings and test evidence follow in dedicated review documents. No live-provider verification is authorized or performed.

## Implementation checkpoint

The existing reservation entry point now uses row-locked, committed rolling buckets plus preserved legacy guards. Per-provider configuration, TheWoWDB refill/burst state, concurrency leases, numeric quota observations and 429 adaptive cooldown are persisted separately from secrets. Validation, automatic/manual/bulk/stale recovery, legacy name/media/community calls and operator diagnostics share accounting. Public Blizzard artwork CDN is independent of the authenticated API; TheWoWDB-hosted artwork shares that provider's pool. No collector code, pricing, desktop/addon contracts or deployment configuration changes.

Rate editing is independent from connection settings and credential replacement. The UI distinguishes documented limits, configured maxima, observed quota and estimates; expired windows display zero current usage. Jobs retain queued work across cooldown and do not count it as permanently failed. An exhausted finite campaign pauses for explicit retry allowance rather than silently overspending or discarding a 429 item. The metadata worker wakes for configured pace, capped at four ticks/second and sleeping normally when idle; existing resource limits remain unchanged.

Verified locally: full baseline-plus-feature PostgreSQL suite **543 passed** (238.85s); subsequent scheduler refinement suite **106 passed**; artwork/community and quota follow-up **57 passed**; API/accounting follow-up **50 passed**. Frontend **119 unit tests**, TypeScript/Vite build and **34 operational checks** pass. Provider, legacy metadata and Companion migration preservation/downgrade/re-upgrade rehearsals pass at `rates_20261115` descending from `bridge_20261115`. Additional cross-process/wakeup/hot-reload checks and actual browser verification are in progress.

Synthetic full-day bucket benchmark improved from 56.265 ms median / 9 SQL statements to **18.000 ms / 6 statements** after using scalar rows and a bounded atomic bucket upsert. Status view: 10.208 ms / 1 statement; quota relation 237,568 bytes for 1,441 minute buckets. These are local warm handler measurements, not production p95 or real provider throughput.

The browser review uses a separately named rootless `provider-rate-review` Compose project, uniquely tagged images, temporary `market_test`, localhost port 19482, bounded memory/CPU/logs, and only db/migrate/api/proxy. No collector, enrichment worker, live credentials, production networks or volumes are used. Synthetic quota fixtures are applied after ordinary browser workflows to keep those tests independent.
