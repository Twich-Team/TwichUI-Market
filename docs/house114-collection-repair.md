# House 114 collection capacity repair

The owner prioritizes this repair over packaging. The coordinated prepared-price /
Companion release must not merge or deploy until production has a successful
validated house-114 auction collection. A separately verified targeted collector
repair is authorized. Do not reset backoff, force live collection, change polling,
delete history or change infrastructure.

## Exact diagnosis

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
replay is in progress. No production limits were changed for these tests.

## Deployment and recovery gates

Pending: full captured-response and maximum-boundary collection replay under the
unchanged worker limits; exact final-source canonical CI; inspected image and
configuration diff; preservation inventory and verified recovery reference.

Build a two-module layer over exact original collector image
`sha256:aab0d6585115da68811f6c3ecebde4233d8e1a73306b2fc8f2d5ba6b1daad50b`.
Replace only the worker through its existing 21-file Compose chain plus an image
override. Verify environment, command, mounts, networks, resource limits, original
data and other container identities. There is no schema migration or database
downgrade. Rollback is the identical worker procedure with the retained original
image; retain new valid observations and all historical data.

Preserve the existing auction `retry_after` **2026-11-23 08:07:31.827206 UTC**.
Do not advance or manually invoke collection. After deployment, wait for the
normal loop to reach its existing retry window and verify actual successful
auction validation/publication, unchanged 300-second schedule and zero new errors.
Only that genuine production result can clear the coordinated release gate.
As of this checkpoint, **no production deployment or recovery is claimed**.
