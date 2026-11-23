# Final packaging refinement and conditional release

**Latest release state:** the approved25-addon selection is unchanged. Simulator environment is repaired and complete full45187769049 exits1 due Workshop/Reminders assertions. Production collection is healthy; no coordinated merge/deploy/beta12 publication. [Final report](market-simulator-final-results.md). Performance evidence below is retained unchanged.

The owner authorizes choosing only A (13), B (17) or C (25), adapting the existing
prepared containers, verifying both repositories, merging in dependency order and
deploying the backend/private Companion through the existing signing/distribution
process, provided all gates pass. No public addon release or temporary codec probe
merge is authorized. Offline observations are never real Forever results.

## Current result — 2026-11-23 08:17 UTC

**25 addons selected and implemented.** At the larger frozen fixture, current
physical-load p95 / maximum is4.326 /5.499ms, versus19.567 /20.889ms for13 and
9.137 /12.120ms for17. The repeatable13-addon loading hitch is reproduced
and avoided by the selected layout in this offline host. Native Forever remains
unavailable; this is not real-client frame acceptance.

Final source pair: Market **85f7dbd0a203553d5120ae601ef4d279c1561143** and
addon **daa674f58b33dc1640cf17f0ef9af8a8778fe702**, including prepared reader
**ee4120880e55b88d588392769fdd6682820d300d** and independently approved addon
main **364c4c28889d621335bc4b3a7b61d234c0b04ce0**. All nine final Market checks pass: backend, website, native Windows install,
picker, signed updater, publication, both consumers and repeated Windows
comparison. Addon's328
modules and fast Market check pass. **The required full simulator remains
blocked** by the actual isolated-network sandbox failure on both permitted
local and standard CI environments. No failed check or security gate is waived.

Only the independent collector repair has merged/deployed: Market main
**3f0421a2221e424df751b963f5b66b445e319018**, PR51. The worker-only replacement
is running with original limits/settings. Natural house114 collection recovered
at08:10:33 UTC:171,605 valid auctions and293,167 complete stored snapshot rows;
both feeds and market have zero failures, previous data is retained and actual
worker peak is296MiB under the unchanged384MiB limit. API/frontend and private
Companion2.0.0-beta.11 distribution are unchanged. No coordinated PR has merged,
no prepared backend was deployed, and no new Companion or public addon release
was published. The exact earlier checkpoints below remain chronological evidence.

## Initial source and dependency inventory (historical checkpoint)

Market main is `e2882dd822b356ffa081efebbff167827f9bf364`. Draft chain:
46 (`fce5c057`) → 47 (`2fcd450a`) → 48 (`1e61ff41`) → 49 (`1e105b16`)
→ 50 (`50246f1d`). Preserve ordinary merge ancestry and all Windows repairs.
TwichUI 131 (`ecc369d5`) must precede 136 (`5b25af4e`). Current addon main is
`2835d71`; it advanced independently and 131 requires conflict reconciliation.
Chart 117 and temporary probe 135 are excluded.

The addon Protect main ruleset requires a PR and passing `verify`, zero mandatory
approvals, no bypass actors and no force pushes. The connected app cannot read
legacy branch-protection endpoints (403); that is not evidence of absent rules.
Market has no visible repository rulesets; its legacy branch protection also
cannot be inspected through the app. Actual merges must still respect GitHub's
enforcement and required checks.

## Bounded performance experiment

`scripts/compare-current-containers.py` reuses the existing native publisher,
production Lua benchmark and complete economic oracle. It builds one frozen
16,384-record/60-day source. Experimental B/C publications regroup the verified
native A publisher's exact assignment lines, without re-encoding. An independent
non-executing parser requires every decompressed current/proof/history stream to
match A. Only the current physical lookup divisor changes in disposable reader
snapshots. This experiment does not establish native B/C migration acceptance;
the selected layout still needs implementation and full native/Windows checks.

Thirty fresh Lua processes per 120/1,000/5,000 workload and layout follow one
discarded warmup. Fixed-seed interleaving reduces timing-order bias. Reader and
pricing caches are cold; the OS filesystem cache is warm. All load samples,
read/compile/execute CPU phases, before/after heaps, callback tails, codec costs,
warm reuse, historical probes, retained/sample-peak Lua heaps and economic hashes
are retained. GC heap drops indicate correlation, not exact GC pause attribution.
CPU and process elapsed times are actual execution; scheduler seconds are modeled.

The first attempt failed while serializing the newly added trace, before accepting
any measurements. The strict production JSON codec rejects untagged tables and
fractional JSON numbers. The harness now emits typed arrays/objects and decimal
strings for fractional trace observations. The production codec and assertions
are unchanged. The failed receipt remains in local evidence.

## Read-only production preflight

At approximately 04:33 UTC on November 23, both APIs and PostgreSQL report healthy;
the actual `/api/v1/health` endpoint returns 200. A mistaken `/health` probe returned
403 and is not counted as service failure or endpoint success.

Actual API/local API image is
`sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c`;
the existing Workshop-current overlay remains last. Proxy remains `f48f8f1a7e5a`;
collector remains `aab0d6585115`. Private current pointer is `2.0.0-beta.11`.
Schema is `retention_20261118`. These are live read-only observations.

**Pre-existing collection gate failure:** house 114/market 2 alone remains enabled
at 300 seconds. Last complete market/auction success is
`2026-11-22T21:24:35.749844Z`; market failure count is 84. Commodities continue
successfully, most recently `2026-11-23T04:28:23.079860Z`. Auction failures return
HTTP 200 followed by `Feed transport, identity or payload validation failed`.
The latest recorded failure is `2026-11-23T02:47:31.827206Z`; seven auction
failures have scheduled persisted backoff until `2026-11-23T08:07:31.827206Z`.
The exact rejected payload condition is not retained by the generic diagnostic
and has not been inferred. The collector correctly retains the last complete
observation. No provider requests, retry overrides, settings or data changes were
made by this task. A healthy collection gate cannot currently be certified.

Performance work and independent safe verification continue. No merge, deployment,
signing, distribution-pointer change or installed-PC update has occurred.


## Selected implementation checkpoint

Current mapping is eight physical current containers per bank (four logical
partitions each), four history containers per bank unchanged, plus the root:
**25 Market addons**. Names extend current A/B slots through 07. Installed
`current_containers: 8` is strictly required by the producer; different declared
physical layouts fail before root activation. No API, pricing, compression,
authentication or scheduler change accompanies this refinement.

At the selected source checkpoint, all 85 native core tests pass (two explicit
integration drivers remain ignored in ordinary discovery). The 42-module focused
addon Market run passes; its local container could not read the external git
metadata, so it is preliminary functional evidence, not immutable-source
certification. Exact paired-addon CI remains mandatory. Native end-to-end
publication initially failed for missing read-only worktree metadata, then for a
retained partial output directory and an outdated exact-addon pin. Those receipts
remain in ignored local evidence. None is claimed as passing acceptance.

The complete simulator catalog is blocked before execution on both the local
rootless host and standard Ubuntu 24.04 GitHub runner: `unshare -Ur true` fails
writing `/proc/self/uid_map` with `Operation not permitted`. Hosted run
[45119849609](https://github.com/Twich-Team/TwichUI/actions/runs/45119849609),
job 137510875627, retains the failure; no suite was skipped into a passing verdict.
The existing Bubblewrap sandbox and host security were not relaxed. This blocks
the coordinated release even after production collection recovers. Independent
collector repair and native/Windows/data verification continue.


## Completed layout comparison

Two frozen synthetic 60-day sources were used: 16,384 exact records (30 cold
processes per workload/layout) and35,116 (20 per workload/layout, matching the
production generation's observed count, not its actual prices/history). Workloads
are120,1,000 and5,000 recipes. There are600 accepted cold process samples in
total, plus discarded warmups. All economic hashes and all logical current,
proof and history bytes agree. The larger campaign's harness hashes match exact
commit `f41e78052590433affb7e4a12f484f5c0d240428`; all frozen sources are unchanged.
The failed serialization receipt remains separate.

| Layout | Cold processes, large fixture | Current loads | p95 CPU ms | p99 CPU ms | Worst CPU ms | Loads above16ms |
|---|---:|---:|---:|---:|---:|---:|
|193 prepared|60|1,920|2.296|2.479|3.374|0|
|13 compressed|60|120|19.567|20.777|20.889|114|
|17 compressed|60|240|9.137|9.834|12.120|0|
|25 compressed|60|480|4.326|4.529|5.499|0|

These are pooled physical **current** loads, not all-game frames or per-session
percentiles. Historical physical p95/max for25 is4.770/4.875ms. Worst pricing
callback is13.218ms for25,15.816ms for17,20.942ms for13 and13.525ms for193.
The source-file read and Lua compilation explain the repeatable13-layout load
cost: maxima11.216/11.321ms, versus2.502/3.486ms for25. No13 current load has a
post-load heap drop. GC attribution cannot be inferred solely from heap samples,
but the repeated large-container hitch is not dismissed as host-only GC. The
previous29.206ms result came from another host; it remains valid evidence and
was not replaced by a claim of native acceptance on this host.

**Choose25:** it is the smallest tested layout convincingly below the preferred
8ms p95 at the current data scale, with substantial margin below16ms.17 avoids
16ms physical spikes but exceeds8ms p95 and approaches16ms callback tails.
The smaller16,384-record fixture alone would have favored17 (p95/max4.071/5.963ms);
its reduced data size is insufficient evidence for the current production scale.
25's corresponding smaller-fixture p95/max is1.963/2.641ms.

| Workload, large fixture |193 CPU ms|25 CPU ms|193 modeled settlement s|25 modeled settlement s|
|---|---:|---:|---:|---:|
|120|724.105|838.932|5.200|5.883|
|1,000|5,099.998|4,601.684|32.625|33.408|
|5,000|9,532.031|9,654.498|64.467|65.258|

120 CPU is15.9% above baseline and modeled settlement13.1% above. At16,384
records,120 CPU is10.9% above and modeled settlement18.2% above (5.183/4.383s).
These approximate-guideline edges are disclosed; no scheduler or pricing change
was made to improve the benchmark. Actual process elapsed times remain in each
receipt; they include oracle/probes, host scheduling and container throttling and
are not presented as gameplay settlement.

There is a cold first-row tradeoff. At35,116 records,193→25 median first usable
price CPU is83.897→121.989ms (modeled0.383→0.567s); initial20-row settlement
CPU204.056→290.142ms (modeled1.133→1.708s). Warm reuse remains zero recrafts,
zero reader calls and the same estimator:120 median0.058→0.063ms. A separate
1,000 warm-price probe is10.586→11.761ms. Container Base64/inflate totals across
cold current decoding are3.370/29.750ms for25 at120,3.956/31.232ms at5,000.
These native adapters use system zlib/OpenSSL offline, not Forever codecs.

At120, retained Lua growth is14.59→20.34MiB (+5.75MiB); sampled peak is
29.91→34.86MiB (+4.95MiB). At5,000 retained growth67.68→73.38MiB (+5.70MiB),
sampled peak129.08→124.92MiB (lower).25 and13 retained bytes are effectively
equal: partition splitting adds no material retained source payload. This is a
bounded absolute memory tradeoff against193, not a claim of zero regression.
Samples omit transient native allocations and actual WoW addon-registry cost.

The benchmark's explicit full-GC diagnostics reach149.029ms for193 and138.815ms
for25 in the dense workload. They execute outside measured pricing callbacks;
they are disclosed instrumentation costs, not inferred gameplay pauses. The
largest naturally sampled heap-drop pricing callback is13.218ms for25; heap
drops correlate with collection but do not measure exact GC pauses.

A requested60-day chart decodes one logical history partition, keeping all64
logical histories available and only the existing one-partition decoded cache.
At120, cold chart CPU1,655.825→1,682.267ms, warm0.348→0.388ms; the work is
incremental.25's maximum chart scheduler callback across all workloads is6.270ms.
Its requested721,067-byte history stream uses two bounded inflates. The prepared
baseline has a61.949ms dense history callback outlier, retained in the receipt;
we do not attribute that outlier without evidence or change the history design.

Full lossless receipts and readable summaries: [16,384](evidence/market-packaging-final/summary-16384.json),
[35,116](evidence/market-packaging-final/summary-35116.json). All observations
above are offline host execution or explicitly modeled scheduler values.


## Actual selected native publication and UI/reopen replay

The actual selected native publisher (not experimental regrouping) passes the
existing authenticated API→native installation→production Lua acceptance for129
variants and all60 daily observations. Exact prices/variants, authenticated
absence, both preparation sizes, full historical contents, atomic root and
unrelated-file/SavedVariables preservation remain checked.
[Exact synthetic API receipt](evidence/market-packaging-final/native-api-25.json).
Native core:85 passed,2 explicit integration drivers ignored during unit discovery;
the ignored pipeline driver was separately invoked for actual publication.

Five cold UI processes per120/1,000/5,000 workload and layout, plus discarded
warmups, now use the actual25 publisher versus actual193 publication of one
shared16,384-record/60-day source. The real Opportunities construction and
reopen scenario retain identical economic outputs and every cache-reuse check.
[Complete summary](evidence/market-packaging-final/ui-reopen-native-25-summary.json).

| Recipes |193 complete CPU ms|25 complete CPU ms|193 modeled initial settlement s|25 modeled initial settlement s|
|---|---:|---:|---:|---:|
|120|2,250.521|2,323.122|4.400|5.150|
|1,000|5,150.529|5,225.253|25.850|26.750|
|5,000|7,404.040|7,519.717|32.667|34.300|

The CPU column here includes the actual UI/reopen scenario, unlike the preceding
session-only comparison.120 modeled settlement is17.0% above baseline, a
disclosed approximate-guideline edge; complete CPU is3.2% above. Initial20-row
120 settlement is410.993→453.454ms CPU (modeled2.383→2.933s). Warm120 reuse
is0.154→0.581ms, with no recrafts or reader calls; at5,000 it is0.063→0.066ms.
No model value is described as actual frame or elapsed gameplay time.

These runtime tests use addon `fb64eeeb...` and Market `f2211d9...`; the subsequent
addon `5a30881052c5fe2118b00def6c5339115451c2e2` changes only the CI job condition
so the full simulator attempt is limited to this owner-authorized checkpoint
and future manual certifications, rather than ordinary Workshop PRs. All runtime
bytes are identical. Final paired Windows publication pins5a308810 explicitly.
The full sandbox attempt remains failed, with no security relaxation; final
coordinated merge, backend deployment and Companion publication remain blocked.


## Preserved Windows confirmation failure and measurement correction

Source163e765's native Windows install workflow fails its strict one-price-run
assertion after successfully installing/publishing the fixture. The counter
delta is2, expected1; the original assertion and90-second publication deadline
are retained. [Failed run and exact artifact](evidence/market-packaging-final/windows-confirmation-failure.json).
The receipt did not retain the extra request's status/timestamp, so it cannot
prove duplicate successful preparation work or assign a sole historical cause.

Two actual harness defects made that measurement ambiguous: it sampled its
start counter without fencing the earlier Resume action; and its60-second
access lifetime was shorter than the90-second prepared operation it permits.
The unchanged native authorization owner legitimately retries a resumable
operation once after an access rejection. The counter counts every activity
attempt, including401. The corrected fixture stays at120seconds, within the
existing native120-second proactive-renewal window (still forcing actual
renewal), while allowing the bounded prepared operation to complete. It also
requires the resumed run to finish and have a future schedule before capturing
the confirmation baseline. No production token lifetime, authentication,
scheduler or synchronization code changes. The exact `price_runs == 1`
assertion stays; actual duplicate runs still fail. Bounded HTTP path/status/time
events and before/after counters now survive both passing and failing cases.
Only an exact-source Windows rerun can accept this harness correction.

The actual required Bubblewrap command was separately tested, not inferred from
`unshare`: both the local host and standard CI runner fail with
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`. Hosted diagnostic
[45121804607](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45121804607),
job137517036003, retains the actual-command failure. No network-isolation flag,
host policy or assertion was removed. The diagnostic-only branch is not part
of the release. Full simulator execution therefore remains blocked.


## Current addon ancestry pin

All nine Market checks pass at dc54726 (PostgreSQL, website, Windows install,
picker, signed updater, both native publication/consumers and repeated Windows
comparison). Addon main independently advanced through approved Execute Range
PR137 to364c4c2. Reader131 now preserves that main at ee412088; containers136
preserves that reader at **cfc41d8b47d51c1be329aa3c46b994b70a742cf1**. The
container tree equals already verified preview121434c3; no Workshop runtime or
benchmark input changed. The exact native publisher/consumer pin is updated
to cfc41d8; final checks run again against that immutable source pair. Full
simulator execution remains blocked by the actual sandbox error, and the
production-health gate still waits for the unchanged natural auction retry.


## Final verification checkpoint and retained inputs

Both exact frozen upstream fixture files were reconstructed independently and
match their original campaign SHA256 values byte-for-byte (27,588,556 and
59,126,554bytes). They remain under ignored local `preserved-fixtures`, bounded
to83MiB; no provider or production data was used. [Input identities](evidence/market-packaging-final/preserved-fixture-identities.json).

The corrected installed Windows workflow passes the unchanged strict assertion.
[Its exact counter/event receipt](evidence/market-packaging-final/windows-confirmation-passed.json)
shows one confirmation price run (3→4), one actual token renewal (4→5), one
price page (4→5), and summary202→200 without restarting scalar pricing. The
measurement starts with the earlier Resume complete and its next scheduled
check in the future. Original failed evidence remains separate; its missing
request statuses do not permit a sole historical-cause assertion.

[Actual Windows lifecycle receipt](evidence/market-packaging-final/windows-lifecycle-25.json)
confirms native validation, private isolation,401/200/304 endpoint compatibility,
unchanged publication, running-game migration refusal, legacy restoration and
re-migration. These are disposable Windows fixtures, not a real WoW client.

The final installed workflow tests immutable Market preview1100a089, whose
tree exactly equals candidate dc54726. Current addon main independently advanced
to364c4c2 (approved Execute Range PR137). Prepared-reader131 now retains it
through ee412088; container136 retains that reader through cfc41d8. Its tree
exactly matches already verified preview121434c3. Market runtime and benchmark
inputs are unchanged. New head checks still run; required gates are not waived
on the basis of tree equality. [Precise identities](evidence/market-packaging-final/verification-checkpoint.json).


A bounded read-only check of the existing35,116-record production manifest
also verifies that the fixture's scale is relevant: its largest logical current
partition has1,290 records (below the same2,048-leaf proof-tree boundary as the
larger synthetic campaign), and the largest four-bucket physical group has4,817
records,9.7% above the balanced mean. No new provider request or source generation
was made. [Actual distribution](evidence/market-packaging-final/production-distribution.json).
This is an observed distribution check, not a latency measurement on genuine
production prices, and it does not establish real-client loading performance.


The existing three-repeat native Windows regression comparison also passes
with identical semantic values across baseline/candidate runs. Automatic
publication is164.529→57.617seconds median; the separate full archive is
34.758→33.561seconds. Those are actual native elapsed times including prescribed
retry waits against a retained older algorithm baseline. They preserve earlier
pipeline gains and **are not attributed to the25-addon physical layout**, since
this compatibility fixture uses its pinned older addon.
[Full Windows comparison evidence](evidence/market-packaging-final/windows-native-comparison-summary.json).


## Supplemental root-admission measurement

The complete20-process root-phase diagnostic (10 cold measurements per193/25
layout plus discarded warmups) records actual CPU inside each root admission
step. It uses a copy of the existing benchmark hook with only maximum-step
instrumentation; the original hook, product code, scheduler, frozen35,116-record
source and all economic results remain unchanged.
[Root callback distributions and exact hook identities](evidence/market-packaging-final/root-admission-summary.json).
Root admission does not depend on the current physical grouping: the13/17/25
experiment uses identical root files. The supplemental25 measurement represents
that same compressed-root path.

Root source loading is about0.22ms; root validation is about55ms total across
30 incremental steps (0.5seconds in the scheduler model). This phase was
reported separately from every pricing comparison above. For completeness,
per-sample sums of those already recorded phases give large-fixture120 medians
193→25: **779.355→894.527ms CPU** (+14.8%), **5.700→6.392s modeled settlement**
(+12.1%), and **139.512→178.365ms first-price CPU** (modeled0.875→1.083s).
These are explicitly derived phase sums, not measured WoW elapsed times. The
original after-admission metrics and their approximate-guideline edges remain
visible; neither definition replaces or hides the other.
[Root-inclusive calculations](evidence/market-packaging-final/root-inclusive-derived.json).

The85 native core checks were also certified against clean immutable source
0d510c5, with unchanged source hashes; the two ignored drivers are separately
executed by the publication acceptance. Later pin/diagnostics updates change
none of those Rust files. [Exact native unit receipt](evidence/market-packaging-final/final-native-core.json).


## Diagnostics enumeration correction

Final review found the existing in-game diagnostics aggregate still enumerated
two current containers per bank. It now includes all eight for memory totals
and addon/error attribution, with unchanged four history slots, sampler interval
and per-call CPU scopes. Boundary tests include current07 in both banks and
exclude current08/history04; the new test fails on the original domain and
passes on the correction. All four focused diagnostics modules and Lua syntax
pass. Offline benchmark heap measurements already included all allocations
and do not change. No pricing, codec, loader, scheduler or publication logic
changes. The final exact addon pin is now
**daa674f58b33dc1640cf17f0ef9af8a8778fe702**; immutable paired CI runs again.


## Final immutable verification — 07:43 UTC

All nine checks pass at Market **85f7dbd0a203553d5120ae601ef4d279c1561143**.
The installed/native source checkout is immutable preview
**06626a43b518d714094986c54de53f081b6bb457** with the identical full tree
**26f0b7a857ac62bed75215cd53261b10d9a7e114**. The exact pinned addon is
**daa674f58b33dc1640cf17f0ef9af8a8778fe702**; its328-module verification
and fast Market checks pass, including diagnostics domain regression. Its
preview8cb8550 has the identical38359dad tree. [Exact check IDs and outcomes](evidence/market-packaging-final/final-ci.json).
The earlier nine-green0d510c5 checkpoint is retained separately.

The required full simulator check still fails because its sandbox cannot create
isolated networking in the available environments. That explicit failed gate
prevents coordinated merging/deployment even after production collection recovers.
No additional product change, test waiver or security relaxation is proposed.

[Final-source Windows receipts](evidence/market-packaging-final/final-windows-receipts.json) also retain the exact artifact hashes, one-run confirmation counters, legacy installer retention, selected native publication and193→25 restore/remigration acceptance. The broader installed-UI fixture deliberately exercises its older compatible addon; the prepared publisher/consumer independently pins the final addon source. All fixtures remain explicitly synthetic and are not gameplay observations.


## Production health gate satisfied — 08:12 UTC

Independent collector repair PR51 / main3f0421a recovered on its original natural
retry, without a reset or forced request. HTTP200 capture212 contains171,605
valid auctions; HTTP304 validates121,562 commodity rows. Non-synthetic
observation2074 / snapshot181 contains exactly293,167 actual stored rows.
All feed/market failures are zero. Previous observation2073, snapshot180 and
capture199 remain; all other service IDs, credentials, polling, worker limits,
API/frontend and private beta.11 distribution are preserved. Peak worker memory
is310,743,040bytes (296.35MiB), with zero OOM/limit events/restarts. Public health
is HTTP200; original image and documented worker-only rollback remain available.
[Production acceptance and rollback](house114-collection-repair.md) /
[exact read-only verification](evidence/house114-collection/post-recovery-verification.json).
Acceptance evidence is also pushed independently at collector-report commit174bc9b.

**The coordinated release still cannot proceed:** the existing full simulator
gate is required by addon testing policy for release certification/high-risk
migration and cannot execute its sandbox in either available environment.
All nine Market checks and addon328-module/fast checks pass at the final pair,
but they do not replace that gate. No coordinated PR was merged, no prepared
backend deployed, no new signed Companion distributed and no public addon
release made. Next prerequisite is an approved environment where the existing
unchanged full simulator sandbox works; do not remove isolation or weaken tests.
Native Forever results remain unavailable and are a separate explicit uncertainty.


The following normal cycle succeeds at **08:15:47 UTC**, HTTP304 on both feeds,
fresh observation2075 and unchanged complete snapshot181. All failure counts
remain zero; no restart/OOM or forced request. Production health is confirmed
across both scheduled cycles. [Follow-up evidence](evidence/house114-collection/normal-followup-collection.json).

Final verified source pair remains Market85f7dbd / addon daa674f, with reader
ee412088 included. Final main tips are Market3f0421a and addon364c4c2. Only
repair PR51 is merged/deployed. To resume the coordinated sequence, first run
the existing unchanged full simulator gate in a permitted environment whose
sandbox works, preserving its reports and actual exit status. The supported
cloud command is `bash tests/run.sh full --profile cloud --jobs 2 --sim-jobs 1 --measure`;
cloud evidence must retain its stated coverage limits and must not assert a
local/native release flag. Then recheck actual main ancestry, protections and
immutable paired CI before merging/releasing. Existing signing/distribution,
versioning and compatibility gates remain required and have not been executed
for a new release. No new installer is offered to existing users and no owner
PC or WoW installation has been changed.
