# Automatic historical retention — release and activation record

**Verified release candidate. Production history deletion remains unauthorized.** Application source `4a0a44a037d1c870e3c21b1a24e0970c4bca506c` has all exact-source CI green. Final production acceptance follows scoped promotion.

## Problem and immediate stabilization

The collector guarded `pg_database_size` with a 5 GiB default despite expanded storage, and historical retention was a saved proposal/manual engine without a scheduler. Database allocation is not physical filesystem consumption. At entry PostgreSQL 17.12 / coverage_20261117 allocated 4,560,287,411 bytes (4.247 GiB). Collection was already healthy, not currently cap-paused. Both unified feeds succeeded and house 114 / market 2 alone remained enabled every 300 seconds.

Server-side filesystem inspection and Docker volume mapping independently confirm PGDATA uses the expanded ext4 filesystem: total 266,736,099,328 bytes (248.417 GiB), initially approximately 160,302,305,280 bytes (149.293 GiB) available. Rootless volume `twichui-market_market-data` maps to `/home/marketdev/.local/share/docker/volumes/twichui-market_market-data/_data`. A read-only probe through that same volume returned identical total capacity, rather than measuring the API container overlay. Initial WAL allocation was 285,224,960 bytes.

Immediate configuration-only stabilization raised the original compatible collector image's cap from **5,368,709,120 to 68,719,476,736 bytes (64 GiB)**. Every other environment value, command, market and resource limit was verified unchanged. The worker was replaced once, without overlapping collectors. [Receipt](evidence/automatic-retention/cap-stabilization.json), [retained cap overlay](../compose.retention-cap.yaml), [original-cap rollback](../compose.retention-cap-rollback.yaml). Regular successful five-minute checks continued.

The full safeguard release additionally enforces **34,359,738,368 bytes (32 GiB) available space**, measured on the PostgreSQL data volume. Missing measurements fail closed. Allocation and physical-reserve pauses have different reasons. Growth from the entry allocation to the 64 GiB cap would initially leave roughly 89 GiB free before other workloads grow; the cap does not consume all expanded capacity. No automatic cap increase exists.

## Automatic engine and authorization

Configured policy, owner authorization, and scheduler enablement are separate states. The worker uses the existing candidate predicates and transactional mutation; it retains shared/current snapshots, source capture provenance, daily history plus 60 supporting days, exact prices, partial rehydration and desktop 409/full-refresh semantics. It does not change provider calls, feed cadence, bridge formulas or desktop releases.

Authorization records the exact policy revision/hash, candidate/mutation and scheduler source digests, physical reserve, allowed stages and reviewed limits. Policy edits clear both authorizations and disable automation. Source/scope/reserve/limit changes invalidate authorization. There is no HTTP authorization endpoint. Owner/operator authorization is followed by a separate administrator enable action; deployment creates neither approval nor enablement.

Default production proposal: one worker, 300-second interval, at most 12 batches and 20 seconds of deletion work per interval, 5,000 rows or 25 feed payloads per batch, 2-second statements, 3-second transactions, 250-ms lock waits, 30-second collector margin, 2 GiB WAL threshold. Empty collector/contention attempts retry after 60 seconds to avoid phase starvation; any attempt committing rows retains its full interval. Backup validation has a separate 30-second HTTP deadline outside collector locks and the deletion work budget.

Authorization also binds the complete scheduler source digest and configured physical reserve; a later code or reserve change requires review again. The session leader lock prevents overlapping cycles; each batch uses the existing collector/sync transaction lock. Due collectors get priority. Committed batches and stage counts survive crashes; failed transactions roll back, and restart records interrupted receipts even if the owner paused meanwhile. Backup, storage, WAL, lock and timeout failures pause or fail with durable reasons. The service has no published port, 192 MiB / 0.25 CPU / 64-process limits and bounded logs.

## Dependency audit and compatibility limits

| Component | Verified behavior / current use |
|---|---|
| `retention.py` | Shared dry-run predicates, signed manual batches and bounded mutation; policy edits invalidate approval. Production has no authorization or completed batches. |
| `maintenance.py` | Existing bounded operational housekeeping remains; legacy historical compaction is disabled and production-rejected. |
| `ingest.py` / daily/statistic models | Exact prices and provenance, shared snapshots, independent retained flags, partial raw rehydration, daily history plus 60 support days remain covered by PostgreSQL regressions. |
| `feed_collection.py` / feed models | Both feeds publish one complete market view; current captures are protected, historical payload clearing keeps capture identity/hashes and observations. |
| `worker.py` | One verified market, 300-second cadence, unchanged provider request logic; independent allocation and physical guards. |
| `storage.py` | Hourly allocation/backlog/processed-row sampling is independent of collection. Throughput remains unknown until two suitable new measurements exist. |
| Desktop / Workshop | Existing 409/full-refresh and cache preservation, exact monetary contracts, and already materialized canonical derivations are retained. No pricing/default or genuine-history delivery hold is changed. |
| Backup Management | Owner-disabled schedule remains disabled; one actual protected restored release archive is present. External recovery evidence is absent. |

Canonical export has an existing availability constraint: if raw originals were never canonically derived before expiry, canonical history cannot be recreated from legacy means. The existing tested response is an explicit 409 directing the caller to request `asking-v1-provisional`; the engine never invents canonical facts or silently changes algorithms. Existing canonical derivations are outside deletion scope and remain available, as do supported provisional exports and website/daily calculations. **Do not interpret the raw-seven-day proposal as proof that every future cold canonical historical export will remain possible.** Before approving destructive activation, review required Workshop/archive coverage and exact derivation availability; if full cold canonical coverage is required, complete its preservation plan first. No canonical reconstruction/backfill campaign or change to the existing genuine-history delivery hold was performed here.

## Recovery evidence and current activation blockers

A current custom-format archive was created using Backup Management without enabling its schedule or rotating/removing archives:

- Filename: `market-release-20261118T133835118331Z-a0d03457794e.dump`.
- Size: **713,963,067 bytes**.
- SHA-256: **55ac4af5da2731c61b4bbc5fb3902147528990882132311412de3b9f9ddaa802**.
- Custom archive fully decoded and restored with constraints into a separate no-port PostgreSQL `market_restore` instance.
- An additive migration round trip preserved every original column in all **45 data tables**; [fingerprints](evidence/automatic-retention/restored-preservation.json).
- Archive is protected and required by `automatic-retention-owner-review` and `restore-recovery-gate`; [manifest](evidence/automatic-retention/protected-backup.json).

**Off-VM recovery is unverified.** A mounted NAS is not proof of a copy and is not authorization to modify external storage. No external storage was changed. Missing items are an owner-authorized destination, a copied archive with independently matching checksum, required protected encryption/provider key material where applicable, and a dated off-VM verification receipt bound to this archive. No such receipt is manufactured by deployment.

Both manual and automatic pruning now rehash a present protected local archive through the backup lock and require a matching restored archive plus recent off-VM evidence. Recovery checks expire after 24 hours. Recurring backups remain owner-disabled. Sustained activation therefore also requires an approved way to keep fresh archive/restore/off-VM evidence current; otherwise maintenance correctly pauses after its verified window. This release does not silently enable backup scheduling.

Recovery after any future approved deletion starts by verifying this protected archive, restoring a new isolated database, checking schema/counts/constraints/prices/provenance/identities, and reconciling observations collected after the recovery point. Production cutover and restoration over live data require a separate deliberate approval. Application rollback cannot recreate deleted rows.

## Capacity and maintenance evidence

An explicitly isolated, simulated eight-day backlog rehearsal processed **60,000 raw listing rows in 12 batches / 2.180 seconds**, generating approximately **14.61 MB WAL** including background activity. Current head retained 179,200 listings, and six sampled variants' exact prices and 365-day charts were identical. This nominal cadence supports 17.28 million rows/day if continuously available; it is one restored-copy sample, not a production throughput guarantee. [Detailed performance](evidence/automatic-retention/restored-performance.json).

Prior three full days contained about 2.84 million ordinary listing rows/day and 0.60 million statistic rows/day. The short commodity window suggests a provisional 1.3–2.5 million commodity rows/day, with material uncertainty. Catalogue allocation estimates are about 256 bytes/listing and 318 bytes/statistic, including relation/index allocation. Seven-day raw data models to 6.9–8.9 GiB, 90-day statistics about 16 GiB, and additional daily support about 2.5 GiB. A **conditional 30–45 GiB retained-history envelope** includes other retained history and internal slack. It does not prove a finite total database steady state: bridge derived records, metadata growth, future commodity changes and fragmentation remain uncertain/outside this deletion scope. Review after seven commodity-enabled days and after actual authorized maintenance. [Measured inputs/model](evidence/automatic-retention/capacity-model.json).

The final exact-source rehearsal at production controller limits (192 MiB / 0.25 CPU) repeated 60,000 rows in **4.61 seconds**, peaked at **94.3 MiB**, and generated **zero measured temporary-file bytes**. Current listings and all six price/chart samples again remained unchanged. [Exact-source resource receipt](evidence/automatic-retention/restored-performance-final.json).

Ordinary production autovacuum is enabled (1 GiB max WAL size, five-minute checkpoint timeout); largest historical tables showed zero estimated dead tuples at entry and actual automatic vacuum/analyze activity. Read-only catalogues expose dead/live tuple estimates and checkpoint/WAL facts. Isolated ordinary vacuum plus `pgstattuple` measured zero dead tuples and 32,211,912 bytes internally free in the listing heap. [Isolated reuse proof](evidence/automatic-retention/isolated-vacuum-reuse.txt). No production extension, VACUUM FULL, rewrite, recreation or index rebuild was run. DELETE does not promise smaller database files or immediate host free space.

## Deployment procedure and rollback

Preserve the complete current rootless production Compose chain and both original environment files. Two old backup overlay paths in container labels referred to an already absent worktree; the release uses the identical tracked copies in this worktree and verifies actual environment/mount/resource preservation. Append `compose.retention-cap.yaml` and `compose.retention-release.yaml`. Keep this worktree attached while production labels reference its files. [Sanitized preflight](evidence/automatic-retention/release-preflight.json).

After final CI, image/source verification and fresh health checks, run only the additive migrate one-shot, then replace **api, local-api, worker, monitor, proxy** and explicitly install **retention**. Keep database, enrichment, backup-manager and unrelated services untouched. The scheduler remains unauthorized/disabled; no live pruning test is permitted. Record exact commands privately with original configuration and immutable rollback pins; never publish environment secrets.

Preferred rollback stops only `retention`, appends `compose.retention-rollback.yaml`, and restores `api local-api proxy` while keeping the verified collector safeguard. The pins also retain original worker/monitor images if a specific regression requires them; before restoring an older collector, recheck actual filesystem reserve because that original image has no physical guard. Stop collection if that check is unsafe. Never blindly replace unrelated services. Preserve the additive schema, all data, backup archive/protection/receipts, original market mappings and the immediately stabilized 64 GiB collector limit. Do not restore over production, downgrade populated receipt tables, delete volumes or enable backups as part of rollback.

## Final verification and exact activation proposal

Local final-source verification: 696 PostgreSQL tests, 132 frontend tests, 65 operational checks, shared-filesystem Chromium/WebKit commodity flows, and four backup browser cases including actual create/protect/download/delete on disposable fixtures pass. The first hosted browser run correctly refused the old fixture without a measurable PostgreSQL filesystem; the repaired browser and backup overlays share their own disposable data volume and retain the full guard. All final hosted CI workflows pass at `4a0a44a`; [exact runs](evidence/automatic-retention/ci.json). Production promotion, authenticated production screenshots and final acceptance are pending. Production historical deletion is not authorized by any section of this report.
