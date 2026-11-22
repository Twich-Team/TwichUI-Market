# Game-ready current prices: coordinated implementation

Owner-authorized development only. No merge, production service/data change,
signing, release or installed game-file change is authorized.

Baseline: Market main `e2882dd822b356ffa081efebbff167827f9bf364`; addon main
`b541c5b39f324c9d356cb3783cff67db1362787b`. Investigation and benchmark source:
[addon draft #127](https://github.com/Twich-Team/TwichUI/pull/127). Chart draft
[#117](https://github.com/Twich-Team/TwichUI/pull/117) remains independent.

1. Server: versioned, explicitly requested source-bound integrity sidecar and
   shared vectors. No economic formula, historical observation, schema migration
   or default summary negotiation changes.
2. Companion: independent native encoder/validator; safe deterministic current
   files, 16/32 opt-in layout, original history, A/B readback and rollback.
3. Addon: authenticated exact lookups/misses, bounded shared scheduling, visible
   demand priority and individual completion; preserve existing caches/engine
   and history APIs.
4. Integration: actual producer/native files/production Lua and Opportunities;
   compatibility, interruption/corruption, memory and matched 60-day benchmarks.

Stage 1 focused SQLite verification: `DATABASE_URL=sqlite:// python -m pytest -q
 tests/test_workshop_prepared.py tests/test_workshop_summary.py` (from `backend/`)
passes **36 tests, one existing PostgreSQL-only test skipped**, in 2.82 seconds.
The source-bound shared vectors and schema are included. No database, deployment
configuration, price formula, history bytes or release identity changes. The
first test expected auth 403 for an absent POST handler; the framework correctly
returned 405. The test now asserts that precise denial and separately checks
scoped authorization on existing routes. No production assertion was weakened.
Existing PostgreSQL-specific query behavior remains a separate required check.

See the [versioned contract](../contracts/workshop-prepared/v1/README.md) for the
exact source/encoding/hash boundary and explicit 4/32 MiB prepared bounds.
Oversized prepared projections retain the complete legacy format without pruning.
Actual Forever latency remains an owner-directed acceptance requirement, not
an offline timing claim.

## First hosted verification and correction

At `074abfc`, the Backend run `45057534987` passed 740 tests and failed seven
new prepared tests because their module did not import the existing autouse
`contract_bundle` fixture. Installed-package CI correctly refuses to discover
contracts from an arbitrary working directory. The fix imports that existing
fixture; production contract discovery is unchanged. An explicit missing-root
local reproduction fails before the fix and passes afterward. Full failed logs
are retained in the task workspace; no failed receipt is called passing.

Windows build/picker/signed-update verification and existing consumer acceptance
passed. The separate performance run `45057534933` failed in **baseline repeat 1**
with native `Error: Network`, after actual 202 preparation responses; the candidate
automatic-publication comparison did not complete. Its credential-free failure
artifact is `14768591665`. This is not a prepared-format performance result or
a passing baseline. Preserve the failure and the separate release gate.


## Stage B: native preprocessing/publication

The core independently validates the authoritative sidecar against the complete
original Contract 3 bundle, encodes 135-character records, and regenerates the
packed SHA proof tree. Static literal templates accept only bounded numeric/hex
atoms. Installed prepared files are parsed as a fixed grammar, never executed,
and their decoded rows are independently rebound to every original modulo-64
current descriptor. History retains the exact original 64-bucket projection.

Prepared publication uses outer `summary_version=2`, distinct
`TwichUI_MarketCurrentPart{A|B}{00..31}` children, and the existing root/history
names. The original source manifest remains Contract 3. An explicit additive
consumer capability selects 16 or 32, requires the actual Prepared.lua TOC entry,
and is rechecked immediately before activation. Older capabilities retain their
existing 1/2/3 negotiation. A server without the optional sidecar or an oversized
prepared projection falls back to a fully validated legacy summary; malformed
integrity evidence never becomes a successful prepared publication.

The original two-slot source-cache files keep their frozen grammar. Two bounded
sidecar metadata files reuse verified attestations; warm synchronization makes
no extra sidecar request. Output is streamed per child instead of retaining all
escaped history source. Existing ownership/link/unexpected-file checks, exact
readback and file/directory durability remain. Root pointer publication is last;
mid-publication capability changes and cancellation preserve the prior root.

Legacy conversion regenerates a complete source-format bank through the existing
publisher. It must finish before downgrading a Companion that cannot read the new
outer root. An older addon is never allowed to restore an incompatible prepared
root. Both supported new layouts can restore a previous verified prepared layout.
No installed legacy folders are deleted: fresh maximum layouts are 161 (16/64)
or 193 (32/64); upgraded installations retain their prior owned folders until a
separately verified retirement can preserve compatible rollback. Folder reduction
is not claimed to happen immediately on an existing installation.

Linux verification: `cargo test --locked --offline --manifest-path
 desktop/core/Cargo.toml --lib -j 2`: **76 passed, zero failed, one existing opt-in
profiler ignored**. Shared Python/native vectors, valid-looking corruption,
source injection, rehashed metadata, source changes, atomic/no-op publication,
legacy downgrade, cancelled writes, layout-switch rollback, foreign accounts,
unknown files, capability replacement and actual HTTP/cache/fallback paths pass.
`cargo check --locked --offline --manifest-path desktop/core/Cargo.toml --examples
-j 2` also passes. These checks do not certify new-format Windows publication,
an installer, or real Forever frame time; paired acceptance follows in Stage D.
No release version/signing/updater configuration has changed.

## Stage D integration checkpoint

The Unix cfg(test) native publisher driver uses the existing synthetic executable identity;
all HTTP negotiation, validation, ownership, bank publication and readback are production
code. The driver is ignored by ordinary tests and absent from release builds.
Actual API -> native publisher -> exact addon 3596347 -> production Lua current/history ->
incremental Opportunities passes for both 16 and 32, with 129 fabricated variants and
60 dated observations. Warm 304 does one request, transfers zero bytes and preserves
the active root mtime/hash. No archive or player data is changed.
Core tests: 76 passed, zero failed; two opt-in tests ignored (the existing profiler and
this explicit fixture driver). New native Windows publication/paired Linux consumption
jobs are separate from the installed UI campaign, which remains required and unsuppressed.

Scripts reuse `verify-workshop-e2e.py` and addon PR127's Opportunities benchmark/oracle.
The dedicated campaign is `scripts/measure-workshop-prepared.py`; it is never selected by
ordinary feature commands. Full repeated 60-day 120/500/1000/5000 results follow in the
integration evidence report. No native Forever target achievement is claimed.

Hosted status reviewed: corrected Stage A fce5 passes Backend314, Windows306 and website302.
Its sync-performance21 campaign fails, as does the earlier20 campaign (baseline Error:Network).
Stage B 2fcd passes Backend315 and website303; Windows307's core/desktop tests, build, picker
and existing signed-updater verification pass, but installed WebView2 multi-installation
selection fails waiting for `#workshop-confirmation` (job137327529233), skipping subsequent
legacy/current publication steps. This failure is unresolved, not classified as passing or
proven unrelated. No checks are disabled.

Stage C follow-up is pinned at `d7150fc3fb5afe524a4a0001208a315f92a1d7bc` after the
first dense campaign failed its original 15% threshold (+23.33% / +20.70%). The
failed report is retained. Dense completion avoids redundant proof work and generic
JSON tuple construction; no frame budget increased. New fast checks also cover
large numeric boundaries, stale eligibility and cancellation of enumeration.
The benchmark separately reports root file compilation/execution and cooperative
root admission (excluded identically from the opening workload), plus first/default
12 visible results. It supports the actual UI harness separately from the full
120/500/1000/5000 Session campaign. Final evidence must name exact clean commits.

Windows308 (`45064754346`) passes new prepared-publisher and prepared-consumer jobs
for both layouts, plus the existing installed Windows workflow, native picker and
existing signed-updater verification. The earlier Windows307 UI failure remains
in the record; the later installed run passes without altering UI/runtime tests.
The original legacy/current consumer job and sync performance status are tracked
separately until complete; no new signed artifact is produced by these checks.

Compatibility acceptance now also builds the exact pre-prepared Market main
`e2882dd822b356ffa081efebbff167827f9bf364` in Windows, pairs it with the pinned new
addon, and requires root version 1, no prepared request/files, original 64/64
projections, correct prices/history/Opportunities and unchanged-data reuse. The
existing installed Windows legacy-addon checks remain intact. A local native
ordinary-admission legacy-file control passes with 129 fabricated variants/60
days; the old-binary Windows result is separately recorded when CI completes.
No runtime or protocol changes accompany this compatibility harness.

Final lifecycle correction is pinned at addon `a59bbcec042485e281a28fb54f14202d5b0abc8d`.
Replacing/cancelling pending work with the same immutable source generation reproduced
a stranded waiting row. Calculation context now includes the existing cancellation epoch;
partial item completion still does not invalidate the full catalog. Header activation
drops work queued against the previous context during admission. Fast44 passes; final
Market65 and Crafting37 unit selections pass locally. The earlier broader run passed all
76 offline checks and the 21-scene Auction/Chart simulator; Workshop failed41 checks.
The original main b541 reproduces the identical41 failure lines, without weakening tests.
Windows310 passes the exact old-native/new-addon compatibility addition as well as
prepared16/32 and original installed/native/legacy consumer checks.
