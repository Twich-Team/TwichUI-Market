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
