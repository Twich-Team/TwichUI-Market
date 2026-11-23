# House 114 collection capacity repair

**Production recovered — 2026-11-23 08:10:33 UTC.** The scheduled auction request
returned HTTP200 and validated171,605 auctions, still above the old150,000 cap.
Both feeds and the overall market now have zero failures; retry cleared normally.
A complete non-synthetic293,167-listing snapshot is published, with the previous
observation, snapshot and capture retained. The original300-second schedule,
credentials, worker limits and other production services are unchanged.
[Exact post-recovery acceptance](evidence/house114-collection/post-recovery-verification.json).
The independent collector repair is complete; the coordinated prepared/Companion
release remains held by the required unavailable full simulator sandbox.
Earlier pending statements below are chronological checkpoints.


The owner prioritizes this repair over packaging. The coordinated prepared-price /
Companion release must not merge or deploy until production has a successful
validated house-114 auction collection. A separately verified targeted collector
repair is authorized. Do not reset backoff, force live collection, change polling,
delete history or change infrastructure.

## Exact diagnosis

The **first retained house-114 collection failure** is **2026-11-15
03:38:22.711308 UTC**, followed by another legacy failure November17 at
05:55:30.241046. Both retain only `Transport or payload validation failed`,
without precise exception/body, so their causes remain unknown. The first
per-feed auction failure is November18 at04:25:25.955434. These are distinct
from the current uninterrupted streak below. [Exact retained timeline](evidence/house114-collection/failure-timeline.json).

The current uninterrupted auction failure streak starts at
**2026-11-22 21:29:38.285896 UTC**. The last successful conditional check was
21:24:35.749844. The last captured HTTP-200 source was 20:28:51.398853,
14,639,222 bytes / **147,892 listings**. Sixty-five successful auction checks
occurred after the November 22 API deployment before the current streak.

One diagnostic auction fetch at **2026-11-23 04:37:58 UTC**, in a separate bounded
read-only container, returned HTTP 200, `application/json;charset=UTF-8`,
`dynamic-forever-us`, **17,907,298 bytes / 178,402 listings**. Namespace, exact self
host/path/query and house 114 all match. Top-level keys and all three auction
field combinations match the previous successful response. Every row validates
under the original field rules when inspected offline in bounded chunks; all
auction IDs are unique. The exact runtime rejection is **`Too many listings`**.
This is valid auction data, not an error body, identity failure or changed format.
[Sanitized response evidence](evidence/house114-collection/diagnostic.json).
Full responses remain private, ignored local evidence; no credentials or arbitrary
upstream error text are committed.

The 150,000 limit was set in `ingest.normalize` by commit
`417e20422a2bf367d43ba1b934e00d05eb38f6c5` on **November 14 at 02:59:55 UTC**.
It is unrelated to the unmerged prepared/container changes. The collector image
remains `aab0d6585115...`, created November 18 and last restarted November 22 at
14:25:14; API image `a3f8226431fb...` started at 14:43:06 and changed only security,
Workshop source delivery and contracts. Neither changed the listing guard.
The current incident is an existing capacity assumption exceeded by feed growth,
not a new release-induced format regression.

Earlier generic auction failures are recorded as far back as November 18 at
04:25:25.955434. Their rejected payloads and exact exception reasons were not
retained, so their causes cannot be asserted. Successful daily captures approached
the cap (daily maxima 147,814 / 149,591 / 149,276 / 148,633 / 147,892). This is
consistent with repeated capacity pressure but does not prove each older failure.

Only market 2 / house 114 is enabled. House 110 has been disabled since November
14 and has no current collector failure evidence. Commodities continue collecting.
There is no evidence that other current houses are unaffected: they are not being
polled. The shared guard would reject any feed above its cap; no broader live
market campaign was performed.

## Minimal bounded correction

Raise the **raw listing** cap to **200,000**, retaining the 32 MiB payload cap,
150,000 summary-variant bound and every identity, type, duplicate, quantity, money,
variant and complete-publication check. No truncation or partial market is admitted.

Hash the identical canonical normalized-row list incrementally, avoiding two
complete serialized copies. Free the parsed source envelope after normalization.
The exact old/new content digest for the captured response is
`b98df7f2c65311328d3ef3dccc8a7e1ec1142a28bad23e2a7da3fedf9dfc7c28`.
Snapshot identity, idempotency, observations, prices and pricing formulas remain.
Future capacity failures now report a bounded, fixed diagnostic rather than
mislabeling them as generic transport/identity failures.

A capacity-only 250,000 experiment was not accepted: the captured response's
normalization/canonical-copy probe reached about 400 MiB RSS without adequate
headroom. The corrected captured and synthetic 200,000-boundary probes pass at
the original **0.5 CPU / 384 MiB**, with swap disabled: cgroup peaks
295,473,152 and 314,789,888 bytes. [Memory and digest evidence](evidence/house114-collection/normalization-memory.json).
These are isolated normalization results, not complete production collection.

Fifty focused PostgreSQL tests pass: capacity acceptance/rejection, unchanged
digest, invalid last-row rejection, legacy ingestion/pricing, full unified feeds,
last-good retention, restart/backoff and scheduling. Failed receipts remain:
initial fixture lacked `pg_trgm`; a new test incorrectly expected a not-yet-due
poll to execute and was corrected to assert no fetch followed by actual persisted
backoff. A first full replay lost its disposable PostgreSQL connection after its
undersized RAM-backed database exited; Docker records exit 1, no OOM event.
That replay is not a passing result. A bounded disk-backed isolated `market_test`
replay now passes both captured-response and synthetic 200,000-auction cases.
It publishes all 310,842 / 332,440 combined auction/commodity listings, retaining
the previous 280,332-listing snapshot and observation. The corrected cycles take
33.72 / 37.06 seconds at 0.5 CPU, with cgroup peaks 323,379,200 / 348,762,112 bytes,
below the unchanged 384 MiB limit without swap. [Full replay evidence](evidence/house114-collection/full-replay.json).
This is isolated replay, not live production recovery. No production limits changed.

Initial hosted source `153e171` passes **741 PostgreSQL tests**, website, actual
Windows install/picker/consumer and signed updater. Its operational gate correctly
fails one stale ingestion-source fingerprint in the existing identity corpus.
That provenance entry now pins the exact changed source at `153e171`, preserving
its foundation and previous candidate hashes, every expected identity vector and
the strict assertions. All 32 identity tests pass afterward. No Advisor code,
trusted equivalence, activation or identity semantics change. [Original failed CI](evidence/house114-collection/ci-attempts.json).
Final exact-source CI remains required; prior passing jobs do not waive this failure.

## Deployment and recovery gates

Pending: exact final-source canonical CI and production preservation/deployment.
The original two-module candidate preserves every base layer and differs only in
`ingest.py` and `feed_collection.py`, in both active and installed package paths.
Its real immutable-image imports and exact digest pass. Existing Compose resolution
matches the actual worker environment, command, mounts, CPU/memory and log limits.
Other production containers are inventoried and unchanged. The protected November
22 release archive still matches its exact 1,662,789,332-byte SHA-256
`5bc9f1b3047b1911a7525e1f6cfa7a29c1f8ad5239ea5975373710106798dbee`;
its recorded isolated restore verified original historical rows and credential
continuity. No backup policy, storage budget, retention policy or archive changed.

Use [the two-module Dockerfile](../deploy/house114-collector.Dockerfile) over the exact original collector image
`sha256:aab0d6585115da68811f6c3ecebde4233d8e1a73306b2fc8f2d5ba6b1daad50b`.
Replace only the worker through its existing 21-file Compose chain plus an image
override ([release](../compose.house114-collector-release.yaml),
[rollback](../compose.house114-collector-rollback.yaml)). Before building, independently
verify the local base alias resolves to the complete original image ID above.
Copy only the two committed source files into a private bounded build context and
pass the exact source commit as `REPAIR_SOURCE`. Set `HOUSE114_COLLECTOR_IMAGE` to
the independently inspected immutable result. Recheck every module against the
base and committed source before promotion. Verify environment, command, mounts, networks, resource limits, original
data and other container identities. There is no schema migration or database
downgrade. Rollback is the identical worker procedure with the retained original
image; retain new valid observations and all historical data.

Preserve the existing auction `retry_after` **2026-11-23 08:07:31.827206 UTC**.
Do not advance or manually invoke collection. After deployment, wait for the
normal loop to reach its existing retry window and verify actual successful
auction validation/publication, unchanged 300-second schedule and zero new errors.
Only that genuine production result can clear the coordinated release gate.
As of this checkpoint, **no production deployment or recovery is claimed**.


## Targeted production deployment — 2026-11-23 05:49 UTC

Repair PR [51](https://github.com/Twich-Team/TwichUI-Market/pull/51) is merged
at **3f0421a2221e424df751b963f5b66b445e319018**. Its exact resulting main passes
PostgreSQL, website, native Windows, folder picker, actual signed updater and
paired addon-consumer checks. [Final CI and preserved failed browser attempt](evidence/house114-collection/final-ci.json).
The original post-merge website attempt exposed an unchanged, pre-existing
Explorer navigation race; a trace-based rerun passes without altering its source,
timeouts or assertions. A separate focused correction is draft PR52. No frontend
source from that correction is deployed with this worker repair.

Only **twichui-market-worker-1** was replaced at **05:49:35.318458 UTC**, with
immutable image
`sha256:ec94420d36baf501d312f3cbc85e38b77222e5b5bff92b76aae82dd8df95575d`,
labeled with merged source `3f0421a`. The actual image imports, exact content
digest and complete module inventory pass: only `ingest.py` and
`feed_collection.py` differ from original collector `aab0d6585115...`, in both
module paths. All other production service IDs remain identical. Environment
values, command, mounts, networks, restart policy, read-only root, security,
logging, 0.5 CPU and 384 MiB remain identical. A postcheck initially compared
environment lists by order and failed; dictionaries prove every key/value is
identical. Only Compose's ordering changed; no second deployment was performed.
[Deployment receipt](evidence/house114-collection/deployment.json).

Both API health checks and PostgreSQL remain healthy; `/api/v1/health` returns
HTTP200. House114 alone remains enabled at300seconds. Persisted auction retry
is still **08:07:31.827206 UTC**; last successful auction remains November22
21:24:35, auction failures7, last-good capture199 retained. Commodity collection
was healthy immediately before replacement. **Production auction recovery is
not yet established**: wait for the normal loop's existing retry window, with
no forced request or scheduling change. The coordinated release remains held.

The retained original collector image and verified original backup/restore path
remain available. For worker-only rollback, take the retained resolved Compose
command, replace its final release overlay with the versioned rollback overlay,
and run the same `up -d --no-deps --no-build --pull never worker`. Verify only
the worker image changes; retain all valid new observations and database schema.
No database downgrade or destructive recovery is needed.


At06:13 UTC the actual deployed private release loader validates the unchanged
**2.0.0-beta.11** store, source`b39a35c01676b50dbc159f4793e0ad547676acfc`,
installer4,885,541bytes/SHA256
`84dacad168dc212d8dda7d06f15ddc5a918f170ba1af0e9ece4e6373cd883129`.
This is private-store/evidence validation, not a new HTTPS authenticated
distribution campaign. No grant, signature, installer, update pointer or installed
client was changed. Older versions remain. No new Companion update is available.
[Unchanged distribution receipt](evidence/house114-collection/unchanged-companion-distribution.json).


## Natural production recovery and final acceptance — 08:12 UTC

The original persisted auction retry08:07:31.827206 was never reset. The normal
300-second loop began its next check at **08:10:33.907615 UTC** and successfully
collected HTTP200 auction capture212: **171,605** validated listings,
17,243,985 payload bytes, SHA256
`883214afc128e35c408508758d124eb0f2315fe5147b63f40339dcaf61692b10`.
Commodities conditionally validate HTTP304 against capture211's121,562 rows.
Observation2074 / snapshot181 is complete, non-synthetic and has **293,167**
actual stored listing rows, exactly equal to the two validated feed counts.
Its source manifest proves US/ruleset2/house114/dynamic-forever-us and both
feed checks/payload hashes. Auction, commodity and market failures are zero;
errors/retry are null. [Scheduled recovery receipt](evidence/house114-collection/production-recovery.json).

The08:12 bounded read-only verifier confirms old observation2073, snapshot180
(including raw data/statistics), and auction capture199 remain. It makes zero
provider requests. Public API health is HTTP200. All other production container
identities, worker environment/command/mounts/limits/security and private beta.11
manifest/installer are unchanged. No critical worker traceback/memory errors,
restart or OOM occurred. Actual cgroup peak **310,743,040bytes (296.35MiB)**
is below the original402,653,184-byte limit; cgroup max/high/OOM event counters remain
zero and CPU remains0.5. No production schema/data/settings/backoff/poll changes
or new Companion publication occurred.

Rollback preflight still resolves to the retained original collector image,
with the same environment/command/limits/logging and worker-only scope. No
rollback was needed. [Rollback readiness](evidence/house114-collection/rollback-preflight.json).
Keep this worktree: the live Compose label references its release overlay.

Final Market main remains **3f0421a2221e424df751b963f5b66b445e319018**.
The production-health gate is now satisfied. Coordinated PRs46–50/131/136 remain
unmerged and no prepared backend/private Companion update is deployed: required
full simulator verification remains blocked by the actual sandbox isolation
failure. That independent gate is not waived by production recovery.


The next ordinary scheduled cycle also succeeds at **08:15:47.245915 UTC**:
HTTP304 for both validated feeds, observation2075 reuses complete snapshot181,
all feed/market failure counts remain zero, retry/error remain null, and worker
still has no restart/OOM. The verifier makes no provider requests and does not
change the300-second loop. [Normal follow-up receipt](evidence/house114-collection/normal-followup-collection.json).
Production recovery is confirmed across two consecutive scheduled cycles.
