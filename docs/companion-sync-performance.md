**Owner-approved release is live:** [Market deployment and signed Companion beta.9 acceptance/rollback](companion-sync-performance-release.md). The review-only state below is historical for this completed release. The owner-provided short capture was exactly the requested diagnostic; no full ten-minute export was required.

# Companion synchronization performance investigation

Owner requested measurement before optimization, comparable repeated runs, exact cache equality, correctness/durability preservation, separate standard/archive/Workshop stages, real progress, Windows verification and a draft review PR. No automatic performance deployment, signing or publication. Resume authorized after the separate Workshop server repair; that deployed image and all production policies remain preserved.

Base: integrated beta.8 plus the owner's Windows validator repairs. The deployed Workshop repair is included unchanged. [Draft PR #40](https://github.com/Twich-Team/TwichUI-Market/pull/40) stacks on fix/workshop-validator-dev-build, preserving its history. Earlier Workshop route404s are a now-repaired availability failure, not standard synchronization throughput.

## Stages and baseline

Native price synchronization executes bootstrap, paired-device activity, sequential signed-cursor price pages, durable SQLite staging/activation, then source provenance. Successful automatic runs then invoke Workshop delivery synchronously on the same worker: the application remains busy through that separate operation. Version2 broad Workshop summaries require no archive; optional manual archives and legacy version1 selected delivery have distinct paths.

Bounded read-only production inspection captured exact daily winners and complete variant sets from six snapshots (153,393 aggregate statistics), plus recent changed/repeated observations. This summary-only slice contains genuine commodities and no accounts, credentials or raw listings. Current set is complete; history is explicitly bounded and cannot be presented as a complete retained-history archive or as canonical raw-listing pricing. Repeated native HTTP/SQLite runs use only isolated market_test. Fixture SHA/source scope and three-run aggregate evidence: [baseline](evidence/sync-performance/baseline.json).

Linux native release baseline, loopback (no WAN delay injected), API1CPU/768MiB, PostgreSQL1CPU/1GiB, client2CPU/1GiB; WAL/FULL durability. Full24,584 variants: median10.205s at50 versus6.694s at100. Genuine incremental: median22.763s versus13.848s, 11,623 transferred changes, resulting25,426 variants. HTTP requests495→249/full and554→279/incremental. Unchanged checks already avoid record transfer and full cache copying: about0.05s/four requests. All final value hashes match across page sizes. These are Linux fixture-copy observations, not production or Windows speedup claims.

Measured ranking: per-page server/round-trip overhead dominates; incremental database SQL is12.715s at50 and7.077s at100. SQLite transactions total2.017s and1.167s; final activation is a small share. Historical signatures are repeatedly calculated but measured below key-generation/pricing costs. Do not rewrite staging, weaken synchronous durability or introduce cross-account caches without stronger evidence. Bounded per-snapshot key discovery now uses the existing primary key instead of repeatedly sorting the whole incremental union. Three comparable runs at100 yield full6.35–6.49s and incremental9.51–9.62s, with byte-exact cached values across both algorithms and both page sizes. SQLite durability and staging semantics remain unchanged.

## Candidate status and owner timing

The candidate is complete at draft review: repeated Linux/genuine-summary and hosted Windows comparisons, installed-app/browser/consumer acceptance and recovery checks pass. Production remains unchanged. Instrumentation is opt-in/thread-scoped, records bounded fixed stage/counter maps without payloads, tokens, URLs or cursors. Benchmark-only server wrapper captures bounded timing/SQL counts without SQL text or parameters and is guarded by explicit market_test identity. Product diagnostics/progress and archive/Workshop instrumentation are implemented. DEV-b0fe5f0 has passed installed Windows timing-toggle/export acceptance and is available for owner timing capture during an unfinished run. The detailed results below close source verification; a real owner-PC partial capture below now narrows its active delay to response waiting; complete pre/post-deployment PC timing remains unconfirmed.

Owner reports ten-minute waits with “x safely saved.” Bounded live logs contain105 continuation responses in ten minutes with median5.26s gaps, while one final-page read-only query probe completes0.631ms (candidate0.315ms). That end-of-keyspace sample does not establish the cause of the multi-second gaps. No Workshop requests appear in the last30-minute owner activity window. The later native partial capture below separates response waiting from Windows cache writes; the production query probe independently identifies server work. It cannot split network latency from server execution without server timing headers; do not misrepresent loopback speedups as resolution of this observed delay. [Bounded production probe](evidence/sync-performance/production-key-probe.json).

## Further measured bottlenecks and bounded candidate

A representative middle-of-keyspace read-only production probe cancels the legacy incremental key query at its750ms safety deadline; the candidate returns51 keys in6.35ms. This establishes a live server bottleneck; it is not a completed-result equality proof because the legacy query was cancelled. Exact-key and final-cache equality are verified on isolated data. [Probe receipt](evidence/sync-performance/production-middle-probe.json).

A separate synthetic26,342-variant unified auction/commodity fixture exercises actual native price synchronization, server preparation, strict summary validation and warm zero-byte reuse. One Linux baseline/candidate cold automatic-delivery pair takes188.77s/70.11s with identical semantic parts hashes. [Preliminary receipt](evidence/sync-performance/linux-automatic-preliminary.json). The baseline spends140s in real retry sleeps; candidate uses the existing5s delay for cold derivation and1s only when the next bounded projection batch is ready. Batch size, export lock, memory bounds and source/pricing protocol are unchanged. Linux writes only private staging; actual Windows publication is separately tested, never a real game installation. This single pair is preliminary, not the required repeated Windows result or owner-PC acceptance.

Three subsequent comparable full synthetic archive runs take median51.338s baseline (50.350–51.657s) and51.212s candidate (51.146–51.456s), with identical exact history hashes,531 requests and52,684 archive records. [Archive comparison](evidence/sync-performance/linux-archive-comparison.json). No material archive speedup is claimed. Fixed timestamps and cold disposable export-cache resets make repeated comparisons comparable. All synthetic observations are explicitly marked synthetic; no full production archive was requested.

The new Windows comparison workflow freezes legacy algorithms atfe854b0, shares measurement-only modules/examples, builds baseline/candidate into separate target directories and records source/binary hashes. It runs three repeats of full/no-op/incremental/unchanged price sync, a separately labelled simulated20ms latency variant, archive download and automatic Workshop publication. Automatic delivery measurement includes the same upfront scope bootstrap and final exact-output/warm-reuse verification in both binaries; those checks add overhead beyond one UI worker attempt. The baseline retry header is reproduced as5s in the fixture; candidate5s/1s comes from the real route. Both use identical server data/pricing/limits and native protocol paths. Native process-lifetime peak memory is explicitly labelled; inclusive stages must not be summed as disjoint elapsed time.

New native disk-full, lock-contention and process-kill tests preserve completed prices and resumable cursor state. A stale installed-UI assertion now expects the earlier validator repair’s specific missing-Summary.lua check and verifies its exported diagnostic; product validation is unchanged. Relevant PostgreSQL suites pass44 checks, with full Linux/Windows verification tracked separately.

## Standard price comparison and interpretation

[Three-run detailed comparison](evidence/sync-performance/genuine-comparison.json) records min/median/max, HTTP/body bytes, SQL time/query count, native transaction/commit/activation and exact semantic hashes. The earlier comparable pair remains the headline; a fresh final-source repeat is recorded separately to avoid silently substituting a faster later host run.

| Genuine summary-copy scenario | Baseline page50 median | Candidate page100 median | HTTP requests before/after |
| --- | ---: | ---: | ---: |
| Initial24,584 variants |10.205s|6.407s|495 /249|
| Unchanged |0.054s|0.055s|4 /4|
| Incremental to25,426 variants |22.763s|9.595s|554 /279|
| Unchanged snapshot, newer observation |0.049s|0.057s|4 /4|

Incremental SQL time falls12.715→2.961s and queries9,943→4,993; initial SQL2.764→1.651s and queries6,421→3,223. Initial native cache transaction time1.711→1.071s; incremental2.017→1.218s. Final activation remains about0.16–0.19s. Body bytes fall8,392,151→8,279,596/full and3,703,232→3,576,311/incremental, mainly fewer page envelopes; record payloads are unchanged.

Pricing time excluding its SQL component changes only1.082→0.970s/full and2.352→2.174s/incremental; repeated pricing arithmetic is a smaller remaining cost than the repaired query. The controlled incremental matrix separates the effects: legacy query/page50=22.763s, legacy query/page100=13.848s, bounded query/page50=13.817s and bounded query/page100=9.595s. Both changes contribute; a larger page alone does not remove the expensive query.

The complete candidate-source repeat returns the same hashes: initial5.607–5.685s, incremental8.801–8.949s and unchanged0.049–0.053s. This repeat has detailed CPU/RSS and disk-size receipts, but no new contemporary legacy control; it does not replace the matched comparison. Inclusive SQL/cache/HTTP stages overlap and are not additive.

Incremental scanning visits27,504 exact keys and transfers11,623 actual changed records (42.3%); unchanged effective values already stay on the server. Increasing page size does not change this set or full-sync values. The existing generation-signature shortcut skips all record work for no-op checks. Compression, signature caching and cache-layout changes are deferred: measured key discovery/request overhead offers higher value without another encoding, cache invalidation policy or durability/migration change. Historical signatures, source identity, null/absent meanings, changed-observation selection and copper formulas remain byte-identical in behavior.

## Verification scope

- Linux native workspace:60 library plus69 integration tests pass; one explicitly manual profile test remains ignored. Recovery checks include interrupted pages, process kill/restart, disk full, busy transaction, rollback, empty-final-page activation, old schema migration and corrupt/future caches.
- Authentication and isolation: scoped device grants, expired/rotating credentials with durable rotation intent, cross-origin refusal, account/market switching, stale worker cancellation, signed cursors and retention-induced409/full rebuild use existing native/backend suites. Failed or incomplete feed data never becomes a synthetic deletion.
- Compatibility: API default50/max100 and signed cursor format remain unchanged; an older client can use the optimized server, and the new client’s100 limit already works on the deployed server. Legacy strict settings remain readable because the opt-in preference is a separate versioned file. The native HTTP body ceiling remains2MiB. Canonical archive and provisional paths retain their protocols and integrity checks.
- Windows CI separately verifies the native core, installed app/frontend/diagnostic toggle, source-only addon publication and existing installer upgrade. The Windows performance server uses portable SQLite, so its price comparison isolates page-size/client effects; PostgreSQL query optimization is independently measured against the genuine summary copy and read-only production probe. The storage receipt records the runner’s SystemDrive volume and disk metadata; it does not establish the temporary fixture volume’s filesystem or a physical SSD. The new performance workflow records that Windows context; this is a hosted Windows fixture, not evidence of the owner’s disk or game.
- Update trust: updater/signing authority modules, embedded public key, release manifests, installer configuration and immutable signed distributions are unchanged. Native signature/authority tests pass. The workflow’s signed-SDK selector does not constitute a fresh SDK acceptance when its optional candidate is absent; retain the existing beta.8 signed acceptance record and require new exact-source SDK verification before any future signed publication.

## Review and eventual rollout order

No performance deployment/publication is authorized. Review [draft PR40](https://github.com/Twich-Team/TwichUI-Market/pull/40) on the integrated repair branch. A future approved API release must start from the exact current production image/overlay chain, preserve the completed Workshop repair and retention recovery/authorization modules, and replace only reviewed performance modules after exact integrated CI/preservation acceptance. Do not deploy an old standalone baseline or blindly replace the full production tree.

API query/retry optimizations can precede a client release and benefit old clients. Server timing headers stay disabled unless the operator explicitly opts in; no schema migration or new index is required. The100-record client is compatible with the already deployed API. Any signed client release is a separate owner decision with exact-source Windows/SDK tests and the existing private updater trust key; keep beta.8 and every previous immutable release. API/client rollback remains protocol-compatible, and the unchanged cache/settings formats require no destructive rollback migration.

The owner’s observation (“x safely saved”) identifies standard price pages, before automatic Workshop. The production middle-page timeout confirms one actual server bottleneck but cannot account for every Windows/network/disk delay. For complete pre/post-deployment PC timing, use [DEV-b0fe5f0 timing receipt](evidence/sync-performance/owner-timing-build.json): enable Include sync timings in diagnostics, start a new attempt and export redacted diagnostics after several pages, even while busy. CPU, completed-request waits and SQLite components from that run can distinguish the remaining delay. No ten-minute owner-PC resolution, physical Forever acceptance or game-loaded generation is claimed.


The task-owned PostgreSQL/API/test containers and isolated network are retired after their measurements. Genuine bounded source capture, local raw benchmark receipts and frozen baseline worktree remain ignored locally for reproducibility; no production or unrelated container was replaced.

## Hosted acceptance checkpoint

Application and harness source34363c3 is verified as combined PR previewa72de05 (base d7fac057), not a release approval. [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44413175893) passes734 PostgreSQL tests,122 operational tests,16 contract tests, migrations/preservation and isolated backup/restore. [Website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44413176295) passes132 unit tests,49 main browser workflows and the separate mobile, Workshop intent, archive, commodity and administration suites.

[Windows](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44413175645) native core/installed-app job passes134 core checks plus native HTTP/authorization, canonical/provisional archive, legacy installer upgrade, installed frontend/diagnostics/Workshop commands and actual45125-variant synthetic game-folder publication. Folder-picker/inherited NTFS checks also pass. The separate addon Lua consumer job also passes. The repeated-performance workflow also passes; the signed SDK’s optional new-candidate stages were skipped, never fresh acceptance. [Structured CI receipt](evidence/sync-performance/ci-verification.json).

## Repeated hosted Windows results

[Exact-source performance run](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44413175633) passes all cases, with three baseline and three candidate runs each on26,342 synthetic unified variants, including1,318 commodities. Frozen algorithm hashes, distinct baseline/candidate binary hashes, raw-JSON digests, min/median/max, CPU, peak memory, network, SQLite and server per-operation measurements are retained in [the detailed comparison](evidence/sync-performance/windows-comparison.json). The downloaded artifact ZIP digest matches GitHub’s metadata. All equivalent price caches, complete archive values and Workshop semantic part hashes match exactly.

| Windows fixture operation | Baseline median | Candidate median | Candidate min–max |
| --- | ---: | ---: | ---: |
| Initial price sync |4.709s|3.025s|2.933–3.090s|
| Incremental price sync |9.605s|6.054s|5.895–6.056s|
| Unchanged check |0.0266s|0.0265s|0.0264–0.0268s|
| Initial, simulated20ms/request |17.738s|9.916s|9.069–9.972s|
| Incremental, simulated20ms/request |24.388s|12.697s|12.523–13.215s|
| Complete historical archive |21.606s|22.093s|22.081–22.979s|
| Price sync plus cold automatic Workshop and warm verification |154.591s|50.914s|49.965–51.304s|

The Windows price comparison uses identical portable SQLite server logic: it measures the existing50→100 page limit, independently of the PostgreSQL-specific query repair. Initial requests fall530→267, incremental531→267. Native price-cache transactions fall0.560→0.487s/full and0.616→0.540s/incremental. Durable commits remain enabled. Added latency is an explicit per-request fixture delay, not a real Internet/disconnect measurement.

Automatic delivery uses actual Windows validation and bank publication inside disposable synthetic Forever folders. Both versions make29 preparation attempts; real sleeps fall140→36s because productive projection retries become1s while cold derivation stays5s. Total elapsed falls103.677s (67.1%); time excluding those waits is about14.6s/14.9s, so the measured automatic gain is predominantly removed idle waiting. Independent HTTP counts fall738→475 and SQL queries9,477→6,321. Warm delivery makes one request, transfers zero data and performs no new installation. This is genuine native publication of synthetic data, not owner-PC or game-loaded acceptance.

Automatic native CPU medians1.641→1.578s and process-lifetime peak working set20.37→20.41MB show no material memory growth. Initial price CPU0.547→0.422s; incremental0.453→0.438s. Full archive timing is0.487s (2.3%) slower with detailed capture enabled; native archive CPU2.484→2.609s and peak working set19.03→18.89MB. Archive protocol/algorithms were not optimized and no archive improvement is claimed. Default product detailed capture stays off; do not infer an unmeasured zero-overhead default from these opt-in runs.

The first Windows benchmark run completed exact price comparisons but failed fixture cleanup because pooled SQLite handles stayed open. Closing the test engine after the server stops fixes cleanup; the full rerun above passes. This correction touches only test harnesses.

The candidate is pushed for owner review, with quantitative improvements independently reproduced on hosted Windows and genuine-summary PostgreSQL data. A closing evidence-only commit changes no tested application source. The owner has supplied a partial PC capture; complete before/after PC timing remains outstanding; no performance API deployment, merge, signed client/addon publication, production archive bootstrap, live game-file change or native game-loaded claim occurred.

## Actual owner-PC capture received

The owner supplied DEV-b0fe5f0 opt-in diagnostics during an active price sync. [Sanitized numeric receipt](evidence/sync-performance/owner-pc-partial-capture.json):27 received pages,1,743 changed records and549,374 bytes over a14.399s partial interval. Waiting for response headers consumes13.770s (95.6%); body transfer0.186s, SQLite transactions0.090s (including0.081s commits),55 cache opens0.144s and process CPU0.375s. JSON parsing/validation are below0.003s. Stages overlap and must not be summed. Previous completed26,342-record genuine cache remains available; current sync reports no error.

This confirms response waiting dominates the observed PC interval, rather than local SQLite writes. The build already requests100 records/page, so another page-size update alone will not remove this wait. Network-header timing includes server execution and network latency; deployed server timing headers are unavailable, so this export cannot divide them. The independently observed production key-query timeout identifies a relevant server bottleneck and supports prioritizing the reviewed API query repair.

No Workshop span appears in the active sample. Its persisted “preparing” status is from a prior attempt and does not establish that Workshop is currently running. The export is14.4 seconds of an unfinished run, not a complete ten-minute observation or a before/after PC acceptance. No additional source change, production deployment or release follows automatically from this evidence.
