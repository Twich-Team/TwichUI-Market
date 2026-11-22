# Approved overlay restoration and collector investigation — 2026-11-22

The seven-file restoration approved against commit
`7b342109eaa7287a86b7233ee4af09139361b394` is complete. All eight recorded
Compose chains now render successfully. The full 25-file API chain matches the
checked effective settings of all nine running services. Two stopped historical
containers differ from their own old chains; no discrepancy was corrected.
**Stop here as requested. No deployment or release was attempted.**

## Exact restoration

The approved repair manifest SHA256 remains
`34e1df21dbd91553eab1230005bf437e6b9801b26c76311b168e94934a70172a`.
Each file was read from the approved commit, checked against its recorded SHA256
and Git blob, and checked again after writing and at final preservation verification.
All seven destinations were absent. Every existing ancestor was checked for
symlinks, directory type and expected ownership before mutation. Directory-FD
traversal used `O_NOFOLLOW`; file creation used `O_CREAT|O_EXCL|O_NOFOLLOW`.

Only two missing parent directories were created, both owned by UID 1002/mode 0700:

- `/home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market`
- `/home/marketdev/.codex/worktrees/backup-management-retention/TwichUI-Market`

Restored files are UID 1002/mode 0644. Existing parent permissions were preserved.
No existing file was overwritten, no Git metadata was created and no worktree was
registered or recreated. Writes and parent directories were fsynced.
[Exact paths, hashes, sizes and permission receipt](evidence/opportunities-overlay-repair-20261122/restoration.json).

## Actual Compose validation

The current service labels supplied each ordered chain, original project directory,
project name and environment-file paths. No overlay was removed or reordered.
The two nonsecret backup interpolation paths were derived from the actual
backup-manager mounts, preserving the existing archive and token locations.
Private environment inputs were never printed or committed. All profiles were
enabled only for configuration rendering; this starts nothing.

| Services carrying the recorded chain | File count | `config --quiet` |
| --- | ---: | --- |
| API / local API | 25 | Pass |
| Retention / monitor | 22 | Pass |
| Proxy / collector | 21 | Pass |
| Backup manager | 18 | Pass |
| Enrichment | 12 | Pass |
| Stopped legacy backup | 5 | Pass |
| Stopped historical migrate | 2 | Pass |
| PostgreSQL | 1 | Pass |

[Ordered chains and return codes](evidence/opportunities-overlay-repair-20261122/chain-validation.json).
Both the service-specific chains and the full API chain were compared against
the nine running services. Checked fields match: resolved immutable image,
effective environment, mount type/source/target/read-only state, network membership,
published ports, memory/CPU/PID limits, restart/logging, read-only root, security
options, dropped capabilities, tmpfs, command and entrypoint.
[Full-chain running-service comparison](evidence/opportunities-overlay-repair-20261122/api-full-chain-running-comparison.json).

Comparison accounts for Compose/Engine representation differences: string byte
counts versus integers, logging field names, null command/entrypoint inheriting
image defaults, absolute secret targets and image-declared anonymous volumes.
Anonymous volume identities were independently preserved by the before/after
container inspection; no recreation behavior is inferred from this check.

Two **stopped** historical service discrepancies remain:

- `backup`: its original five-file chain says `restart: unless-stopped`; the actual
  stopped container has restart `no`, consistent with the owner's disabled-worker
  policy. The original chain omits the later owner-policy overlay. Do not execute
  it to recreate or start that service.
- `migrate`: the historical mutable `twichui-market-backend:dev` reference now
  resolves to `sha256:9fe1f98e78e86eae9821d2c5e02a6e0f48cc9899cb259c63a4a05416118413a0`,
  whereas the stopped container references
  `sha256:4255007bdcf12a9b29e93a6be0e4be4a66480ce8139725ef3ba5e9fadae81550`.
  The historical image was already absent at preflight. Current tag/image defaults
  also differ for `RAW_LISTING_DAYS` and `DETAILED_STATISTICS_DAYS`; private values
  are withheld. This chain cannot reproduce that stopped container's identity.

[Per-service comparisons](evidence/opportunities-overlay-repair-20261122/effective-comparison.json),
[historical restart detail](evidence/opportunities-overlay-repair-20261122/historical-discrepancy-detail.json).
These findings do not authorize correcting old chains, retagging images, changing
retention or enabling backup scheduling. They remain reported operational debt.

## Collector findings from existing records only

At the read-only database snapshot `2026-11-22 13:12:36 UTC`, market 2 / house 114
was still the sole previously observed enabled market, with unified coverage and
its 300-second interval unchanged. Both feeds and the market had **zero current
failures**, with last success `13:08:50.880912 UTC`. Genuine observation 1962 /
snapshot 173 was retained. Recovery occurred **before** restoration began at
`13:10:39 UTC`; it was not caused by this repair.

Persisted feed checks explain the earlier degraded period:

- Auctions received an actual upstream **HTTP 500 at 00:21:27 UTC**.
- Six later auction responses recorded **HTTP 200** but failed the existing
  transport/identity/payload validation path, from **00:26:29 to 05:39:19 UTC**.
- **120 deferred auction checks** from **00:31:36 to 10:57:02 UTC** were waiting
  for the persisted retry window. The existing code increases per-feed backoff
  after failures, while checking the logical market at its unchanged interval.
- The commodity feed continued successful 200/304 checks. A missing successful
  auction peer prevents a complete observation: the existing code retains the
  last complete market observation and records partial runs rather than publishing
  a mixed-age market or false zero supply.
- Auction collection resumed with HTTP 200 at **11:02:05 UTC**. Through the snapshot,
  it recorded three collected auction responses since midnight; both feeds had
  subsequently succeeded at 13:08 UTC, including unchanged responses.

[Actual market/feed/run records and aggregates](evidence/opportunities-overlay-repair-20261122/collector.json).
The running collector's `worker.py`, `feed_collection.py`, `probe.py` and `ingest.py`
hashes match the frozen reviewed Market source. No new provider request was made.
The bounded existing-container log query returned no lines, so logs add no further
failure detail. [Source/log receipt](evidence/opportunities-overlay-repair-20261122/collector-log-source.json).

The six HTTP-200 failures intentionally persist a generic sanitized error. The
records do **not** identify which particular validation predicate failed, and
failed response bodies were not retained by that path. This read-only investigation
cannot distinguish namespace/source-identity, payload structure/bounds or another
caught validation failure. No claim of an exact upstream defect or permanent fix
is made. No probe, collection trigger, retry reset, restart or threshold change
was performed.

## Preservation and stopping point

All **11** production container IDs, immutable images, start times, status and
restart counts match the session's before-state. Full container configuration,
host configuration, mounts and network settings are unchanged. This includes
nine running services and the two stopped historical containers. Both APIs and
PostgreSQL retain their healthy status.
[Final preservation receipt](evidence/opportunities-overlay-repair-20261122/preservation.json).

No service replacement/restart, build, migration, signing, publication, Contract-3
activation, collector/backup/retention setting change or deployment step occurred.
No grants were created. The two task-created raw private inspection/render
snapshots were removed after sanitized receipts and preservation comparisons;
no original private file was removed. Existing signed releases, recovery points,
updater keys, observations and client/game files remain untouched.

The owner explicitly requested stopping after restoration, configuration validation
and collector findings. The earlier deployment program has not resumed.
