# Retention activation proposal — configured, not authorized

**Do not activate destructive maintenance yet.** Production deletion remains unauthorized and no batches have run. This is the exact proposal for separate owner review, subject to the recovery and compatibility prerequisites below.

Preview captured **November 18, 2026 at 08:32:50 AM MST** / `2026-11-18T15:32:50.087649+00:00`. Live administrator preview is read-only. The owner concurrently saved unchanged windows at15:18UTC, advancing revision2 to3; this proposal preserves revision3. No policy values were reset.

## Exact persisted policy and execution identity

| Setting | Value |
|---|---:|
| Policy revision | 3 |
| Raw auction/commodity listings and historical feed payloads | 7 days |
| Detailed intraday observations/statistics | 90 days |
| Daily price history | 365 days |
| Additional daily source support | 60 days (425 total) |
| Collection/feed logs | 90 days |
| Security logs | 365 days, with retention audit records protected |

Policy SHA-256: `9be787ac64d47f47ae20fda925dc720cb353591cd3588d39f5502a425185aef7`.

Execution/authorization SHA-256: `3543c34bde2c8e3ed5b63c21ef645c6c6ccfbb19945b4ff7a685e37694e4d243`.

Scheduler source SHA-256: `1f38819646cb84561565a5037f6579e525617973670ee0c6272eff629ca8acd8`. Candidate/mutation source SHA-256: `e2f408b72f27589dcc9ff736c5da476454b8c60480a97c3cd7bef82e4ad91acb`. Authorized-scope filesystem reserve: **32 GiB**.

The execution identity binds the exact policy revision, allowed table stages, current-head/shared-reference protection,60-day support, engine and scheduler implementations, physical reserve and all limits. A policy save, changed execution scope, changed scheduler/engine or changed reserve/limits requires review again. Saving a policy and starting the service never authorize deletion.

## Exact current cutoffs (UTC)

| Cutoff | Value |
|---|---|
| raw before | `2026-11-11T15:32:50.087649+00:00` |
| intraday before | `2026-08-20T15:32:50.087649+00:00` |
| daily chart before | `2025-11-18` |
| daily support before | `2025-09-19` |
| operational before | `2026-08-20T15:32:50.087649+00:00` |
| security before | `2025-11-18T15:32:50.087649+00:00` |

Approval would cover these **rolling age windows**, not only today's zero-row preview. Cutoffs advance with time. Refresh the preview and recovery verification immediately before any future authorization; stale preview counts are not an approval for a different policy or broader scope.

## Current deletion preview

| Stage | Eligible rows | Estimated logical bytes | Oldest affected | Newest affected |
|---|---:|---:|---|---|
| daily_references | 0 | 0 | None | None |
| observations | 0 | 0 | None | None |
| raw_listings | 0 | 0 | None | None |
| raw_feed_payloads | 0 | 0 | None | None |
| intraday_statistics | 0 | 0 | None | None |
| collection_logs | 0 | 0 | None | None |
| feed_checks | 0 | 0 | None | None |
| security_logs | 0 | 0 | None | None |

Current total: **0 rows / 0 estimated logical bytes**. Current backlog requires zero destructive batches. The dry run does not mutate data. Full table/index proportional estimates are approximate; DELETE does not immediately reduce database allocation or promise filesystem shrink.

Protected: every market's latest head, current feed captures, shared snapshots used by protected observations, all configured intraday history, daily history plus60days of supporting observations/statistics, source hashes/namespaces, existing exact derivations, accounts/preferences/metadata and existing audit evidence. Missing old desktop observations/statistics/support retain the tested409/full-refresh behavior and completed offline caches.

**Workshop compatibility condition:** already materialized canonical derivations are preserved. Cold canonical exports cannot reconstruct originals that expire before derivation; the existing explicit409 and provisional-export option remain. Do not approve a requirement for complete cold canonical archive coverage on the assumption that legacy means can recreate it. Verify the required exact derivation/coverage preservation plan first if that coverage is required. No source facts are invented and no backfill campaign was run in production.

## Protected recovery evidence

Current required recovery point: `market-release-20261118T144809003060Z-df8c8cd2a368.dump`.

- Size: **723,098,027 bytes**.
- SHA-256: **`a8fda36e26ecb839427952bab75b14b3b2862d21e731153b1ca4328cb6c69d66`**.
- PostgreSQL17 custom archive fully decoded; full isolated restore and constraints pass.
- Exact original-column fingerprints across45data tables match before/after the candidate migration.
- Restore verified at `2026-11-18T14:57:52.594491+00:00`.
- Protected and pinned by `automatic-retention-owner-review, restore-recovery-gate`; origin release is excluded from automatic rotation.
- Earlier verified recovery point also remains protected; no production archive was removed.
- **Off-VM recovery copy and required recovery key material remain unverified.** The mounted NAS was not modified. Missing: an explicitly authorized destination, independently checksummed protected copy outside this VM's failure domain, and matching dated verification evidence.

[Current manifest](evidence/automatic-retention/protected-backup.json), [restore proof](evidence/automatic-retention/backup-restore.json), [45-table preservation](evidence/automatic-retention/restored-preservation.json).

The live gate requires matching protected local archive bytes, restore and off-VM verification within24hours. The existing backup schedule remains disabled. An approved way to refresh archive/restore/off-VM evidence is required for sustained operation; otherwise maintenance pauses after its verified window. Do not write a successful recovery receipt merely to satisfy the gate.

## Bounded automatic work and collector impact

| Limit/control | Exact proposal |
|---|---|
| Concurrent workers | 1 |
| Maintenance cadence | 300 seconds |
| Rows per batch | 5,000 |
| Compressed feed payloads per batch | 25 |
| Maximum batches per interval | 12 |
| Deletion-work budget | 20 seconds |
| Statement / transaction deadlines | 2000ms / 3000ms |
| Lock wait | 250ms |
| Collector priority margin | 30 seconds |
| Empty contention retry | 60seconds; only when no batch committed |
| WAL allowance | 2GiB |
| Controller resources | 192MiB /0.25CPU /64processes |
| Backup validation | Separate30-second internal HTTP deadline, outside collector locks |

Each transaction shares the collector/sync lock and rechecks authorization/enablement. A leader lock prevents overlapping cycles. Committed row counts and stage receipts survive restart; failed transactions roll back. Due/busy collectors, missing backup evidence, missing/low physical space, excess WAL and timeouts stop work. Saving a policy revokes authorization. Administrator Pause stops between bounded transactions; stopping the retention service also halts it safely.

At production controller limits, the restored-copy sample handled60,000raw rows in4.61seconds with about94.3MiB peak memory, zero measured temporary-file growth and approximately14.6MB WAL. The maximum cadence allowance is17.28million rows/day, above the provisional4–6million raw rows/day range; this is an isolated sample, not a production throughput guarantee. Current catch-up backlog is zero. Never extend work indefinitely or increase provider request frequency.

## Storage and capacity limits

Current database allocation approximately **4.35GiB**, configured cap **64GiB**, PostgreSQL filesystem total **248.4GiB**, available approximately **148.0GiB**, reserve **32GiB**. A conditional retained-history envelope of30–45GiB is a model, not proven total steady state. Commodity frequency, unpruned exact derivations/metadata and internal/index reuse remain uncertainties. Review measured growth after seven commodity-enabled days and after any future authorized retention. No automatic cap increase, VACUUM FULL, table rewrite or volume recreation is approved.

## Deliberate activation sequence — only after separate approval

1. Resolve off-VM recovery, fresh verification and the required Workshop canonical-coverage condition above. Retain protected recovery points and supporting key material.
2. Refresh the live preview. Verify saved revision/hash and execution hash still equal this proposal, check physical reserve, WAL and collector/feed health, and record the owner's explicit approval of the exact rolling scope and limits.
3. An operator invokes `authorize_automatic` with an active administrator, approval reference and the exact `expected_execution_hash` above in a committed transaction. This records approval but leaves enabled=false. There is no HTTP authorization endpoint.
4. Separately enable the authorized schedule through Administration. Monitor committed batches, rows/stages, collector cadence, WAL, free space, backlog trend and recovery freshness. Routine bounded batches do not require repeated manual confirmation.
5. Pause on unexpected behavior. Code rollback cannot restore deleted history. Verify the protected archive, restore a fresh isolated database, validate constraints/counts/prices/provenance and reconcile later observations before proposing any production recovery cutover. Never restore over live data as a rehearsal.

**Current decision: remain unauthorized and disabled.** No deletion is requested by deployment, by this proposal, or by the owner's policy Save action. Separate explicit owner approval and actual readiness evidence are required.
