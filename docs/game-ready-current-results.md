# Game-ready current data: implementation and verification

Status: coordinated **drafts**, no merge, deployment, signing or publication.

## Delivery and source identity

| Stage | Draft | Verified source |
| --- | --- | --- |
| A: authoritative server metadata | [Market #46](https://github.com/Twich-Team/TwichUI-Market/pull/46) | `fce5c0574a0457ad3326709d16a6b5bfb7495cb6` |
| B: native preparation/publication | [Market #47](https://github.com/Twich-Team/TwichUI-Market/pull/47) | `2fcd450a9982a1a1fa32286928f21d179c291e58` |
| C: cooperative addon reader | [TwichUI #131](https://github.com/Twich-Team/TwichUI/pull/131) | `db5bd544759c725a7f3dfe12d62743253f9e8551` |
| D: complete pipeline/benchmarks | [Market #48](https://github.com/Twich-Team/TwichUI-Market/pull/48) | `f7c937a23c350a3ebc82d6cd7c020ac818c70b2f` (measured runtime/tooling; later pin/diagnostic evidence noted below) |

Inspected main baselines were addon `b541c5b39f324c9d356cb3783cff67db1362787b` and
Market `e2882dd822b356ffa081efebbff167827f9bf364`. Addon #131 stacks on audit #127
(`b1d8da1d4668e7b10d7dd9ca4fa4161a25842a40`, reconciled with inspected main);
Market #48 stacks on #47, which stacks on #46. No protected branch was changed.
Chart-loading draft #117 stays separate: Pricing.Chart, MarketFacts, ViewOpportunities
and AdvancedChart behavior were not changed. Unrelated worktrees and development are preserved.

Final addon `db5bd544...` adds only passive diagnostic selection/proxies and its regression test
above measured reader revision `a59bbcec...`. Every measured addon source hash is unchanged
([source proof](evidence/game-ready-current/final-diagnostics-source.json)); the 14-test group
passes again in 10.456 s. The Workshop preset now selects all 24 bounded gauges before the
lazy addon loads, including nine prepared counters. No pricing/scheduling budget changed.

## What changed

The server exposes an explicitly requested prepared-v1 attestation for the original
Contract 3 generation. It binds exact item/variant tuples, both 16/32 layouts, counts,
canonical-current digests and positional Merkle roots, including empty buckets. The
original current/history endpoints and economic formulas remain unchanged.

The Companion independently validates the original authoritative source, rebuilds the
attestation roots, and emits fixed-width, data-only Lua current files. Readback uses a
closed parser, never Lua execution, and rebinds the installed tuples to **all original
64 current digests**. Existing historical bytes stay in the original 64-bucket layout.
The installed capability requires actual Prepared.lua and its TOC entry. Publication
is A/B, owned-file checked, byte checked and root-last, with last-good preservation.
Sidecar metadata does not alter the older private source-cache grammar.

The addon loads a physical prepared file, captures immutable strings, searches fixed
positions and authenticates requested tuples before use. Missing responses require
both authenticated adjacent positions and strict bounds. Binary-search pivots are
navigation hints, never displayed data. No full current JSON parsing or generic
canonical encoding occurs in the ordinary sparse lookup path. Dense demand can use a
cooperative streaming canonical-current digest; visible requests can interrupt it.
Every independently verified item releases its own existing Pricing reservation and
notifies only affected recipes. The existing 8,192-price cache and PR3 estimator/engine
remain the economic authorities; no second price table or full item-table index was added.

Summary current/history work shares the existing approximately 2 ms cooperative slice.
The existing engine retains its own 2 ms budget. These are not a global hard frame limit:
addon compilation, garbage collection and indivisible calls can exceed a slice. No budget
was raised and no continuous polling was added. Cancellation now replaces the calculation
context even when the immutable source generation stays unchanged; partial completions do not.

The attestation is **not a digital signature**. HTTPS/authenticated source, the verified
Companion and trusted installation remain the trust boundary, as for the existing unkeyed
manifest hash. It does not protect against malicious local code replacing root/code/data.
See the versioned contract and [reader design](https://github.com/Twich-Team/TwichUI/blob/feature/market-prepared-reader/docs/performance/game-ready-current-reader.md).

## Comparable performance evidence

| Recipes | Current layout | CPU (s) | First visible (modeled s) | Initial 12 settled (modeled s) | All settled (modeled s) |
| --- | --- | ---: | ---: | ---: | ---: |
| 120 | Legacy 64 | 3.299 | 1.717 | 17.067 | 31.633 |
| 120 | Prepared 16 | 0.708 | 0.367 | 1.083 | 4.883 |
| 120 | Prepared 32 | 0.611 | 0.350 | 1.017 | 4.550 |
| 500 | Legacy 64 | 3.419 | 1.750 | 16.867 | 31.683 |
| 500 | Prepared 16 | 2.250 | 0.583 | 1.183 | 16.517 |
| 500 | Prepared 32 | 2.079 | 0.600 | 1.100 | 15.117 |
| 1000 | Legacy 64 | 3.588 | 1.817 | 17.417 | 32.667 |
| 1000 | Prepared 16 | 3.778 | 0.783 | 1.183 | 27.983 |
| 1000 | Prepared 32 | 3.623 | 0.733 | 1.100 | 27.083 |
| 5000 | Legacy 64 | 5.205 | 2.267 | 19.950 | 38.633 |
| 5000 | Prepared 16 | 5.744 | 0.700 | 3.983 | 36.183 |
| 5000 | Prepared 32 | 5.755 | 0.767 | 3.950 | 33.867 |

Final dense CPU increases are **10.37% / 10.57%**, below the unchanged 15% maximum. The 120-recipe 16 case uses **21.5%** of control CPU. All 36 measured samples pass their full-field economic oracle and warm-reuse assertions.

[Raw final campaign](evidence/game-ready-current/benchmark.json) uses Market `f7c937a23c350a3ebc82d6cd7c020ac818c70b2f` and addon `a59bbcec042485e281a28fb54f14202d5b0abc8d`, both clean. The later evidence commit changes no measured runtime source.

| UI harness (120 recipes) | CPU including five reopens (s) | Cold list settlement (modeled s) |
| --- | ---: | ---: |
| 64 | 5.011 | 31.917 |
| 16 | 2.467 | 5.283 |
| 32 | 2.415 | 4.917 |

The [separate UI run](evidence/game-ready-current/ui-reopen-history.json) is one measured run after warm-up, not the three-repeat Session campaign. Every layout has zero reopen price-reader calls and crafts, and a valid 60-day historical series. Two historical addons load while the UI selects details. History work continues after prices settle; full timer drain is about 21.5 modeled seconds for prepared versus 48.3 for control. The explicit later historical probe loads no extra addon but can re-decode already-loaded raw history after the one-partition decoder cache changes. Its second valid hit does not decode again. UI CPU/heap includes recording fake frames and history, not the real client renderer.

Conditions: fabricated mixed 16,384-record / 14,745-item source, 60 daily observations,
exact variants and observed-missing prices, production server sealer and native publisher.
The 120-recipe cohort asks 158 distinct identities across 58 original buckets. Recipe
counts are 120/500/1000/5000, with shared materials and differing quantities. Each case has
one discarded warm-up plus three measured fresh Lua processes, on AMD EPYC 9V74 / Linux
6.18.57 x86_64 / Lua 5.1. Filesystem caches are warm. Fixtures, recipe digests and full
final economic snapshots match across formats. Every sample checks a fresh full estimator
recomputation, final sort/filter order and summary, plus zero warm reader calls/crafts and
estimator reuse. The raw JSON names exact clean commits, source/binary hashes, all samples,
CPU, process elapsed, callback percentiles, memory and operation counts.

The model uses a minimum one 60-Hz frame per After. It does **not** reproduce Forever's
scheduler, rendering, storage/Defender costs or game load. Root file load/admission is
reported separately and excluded identically from the opening workload. Add its modeled
admission for a sequential first-ever setup; opening after admission need not pay it.
CPU includes in-workload GC; explicit retained-heap collection and correctness oracle
are outside workload timing. Memory is sampled Lua heap, not allocator high-water or RSS.

The first implementation failed the unchanged dense limit: +23.33% (16) and +20.70% (32)
at 5,000 recipes. [The failed campaign](evidence/game-ready-current/initial-dense-regression.json)
is retained. Fixes remove redundant proof coroutines/searches after full authentication,
build canonical atoms directly for dense hashing, and reuse immediately returned prices.
The cancellation follow-up was then remeasured on its exact delivered code. No threshold
was weakened. Dense CPU can still exceed the control within the 15% allowance; sparse
speedup must not be generalized to 5,000 recipes.

## Layout, memory and folder recommendation

Keep **16 as the experimental test default**, with 32 supported by the same reader and
controlled package capability. Both remove most sparse decoding cost. 32 gives smaller
synchronous loads and lower sampled sparse memory in these fixtures, at 32 extra folders
across both banks. Make the permanent choice after matched Forever captures.

| Recipes / layout | Retained delta (MiB) | Sampled peak delta (MiB) | Median worst callback (ms) | Maximum callback across 3 samples (ms) |
| --- | ---: | ---: | ---: | ---: |
| 120 / 64 | 3.78 | 12.95 | 3.69 | 4.06 |
| 120 / 16 | 6.97 | 19.50 | 4.55 | 7.09 |
| 120 / 32 | 6.53 | 17.23 | 3.10 | 8.62 |
| 5000 / 64 | 56.19 | 103.75 | 7.24 | 26.94 |
| 5000 / 16 | 59.89 | 113.05 | 7.10 | 24.58 |
| 5000 / 32 | 59.53 | 113.03 | 8.35 | 9.04 |

The largest 16 callback is 24.583 ms at 5,000 recipes, in Summary; that sample includes a 21.413 ms synchronous current load. Control reaches 26.940 ms (engine notification), and 32 reaches 9.041 ms (engine callback). These are reported tails, not a hard frame-time guarantee or a load-p95 result. Current compilation/execution is measured separately in the JSON; root validation is approximately 42 ms control / 49 ms (16) / 54 ms (32), or 0.40/0.45/0.50 modeled seconds, outside opening timing. Compatible warm Session reads are sub-millisecond here with zero new current lookups/crafts.

Whole UI-harness retained/sample-peak deltas are about 33/76 MiB control, 36/83 MiB (16) and 36/81 MiB (32); recording fake frames and two historical selections dominate the additional heap. These are not native UI memory measurements. Native debug validation/publication of the 16k/60-day source takes about 28.2 s control versus 32.7/32.4 s prepared. This is deliberate native validation/preparation overhead in a debug test binary, not a measured Windows release-build synchronization result. Warm prepared HTTP reuse is verified separately; no unnecessary network/history-format change is claimed.

The provisional 16 MiB sampled incremental-heap goal from the investigation is **not met**
by the sparse offline candidate peaks. Retained memory is much smaller than sampled peak,
but both matter. No forced runtime GC or global GC tuning hides this result. Native memory,
GC and load tails must be reviewed before promotion; 32 remains a real alternative.
At 5,000 recipes, the existing estimator/catalog dominates total retained and transient heap.

For fully populated source layouts, a fresh single bank has 81 Market data folders with
16 current / 64 history, or 97 with 32. Two populated banks plus the root total **161 or
193**, compared with the Contract 3 64/64 maximum of 257. These counts exclude the ordinary
TwichUI addon folders. Upgrades retain old owned layouts for rollback, so installed folder
counts can be higher; no automatic deletion of existing folders was introduced.

## Compatibility, integrity and recovery

| Combination / boundary | Evidence and expected behavior |
| --- | --- |
| New server + existing clients | Original v1/v2/v3 fixtures/routes unchanged; existing Windows legacy/current consumers pass. Prepared metadata is an explicit request only. |
| New Companion + old addon | Existing native Contract 1/2/3 negotiation and original Windows installed/legacy consumers retained; no prepared format without capability. |
| Frozen old Companion + new addon | Windows builds exact `e2882dd...`, verifies its source/binary identity, publishes legacy Contract 3 with the pinned new addon, and checks actual Lua prices/history/Opportunities. No prepared request or file, no performance benefit claimed. |
| New/new prepared 16 and 32 | Actual authenticated API -> download/validation -> native A/B publication -> exact file artifacts -> production Lua -> incremental Opportunities, 129 fabricated variants and 60 days. Both current and history integrity checked; warm304 is one request, zero bytes and unchanged root hash/mtime. |
| Unavailable prepared server | Native HTTP404 fallback test publishes a complete validated legacy bundle; 409 uses the same explicit fallback. Other auth/network/integrity/410 errors do not pretend success. |
| Interrupted or corrupt publication | Native production publisher cancellation points preserve the active root and verify last good; corrupt bytes, rehashed wrong roots/counts, foreign account ownership, unknown files and mid-publication capability changes refuse activation. |
| Upgrade / downgrade / rollback | Native tests cover prepared publication, same-source legacy conversion, layout switching and compatible previous-bank rollback. Old-capability addons cannot restore prepared roots. |
| Reader lifecycle | Exact/absent variants, missing bounds, empty buckets, corrupt/truncated tuples/proofs, numeric bounds, per-item readiness, shared leases, combat, same/changed-generation cancellation and history preemption covered deterministically. |

Downgrading an old Companion **directly over an active root-v2 prepared generation is not
transparent**: old code cannot parse a new grammar and must refuse safely. First use the
new compatible publisher with a legacy-capable package to install/verify a complete root-v1
legacy bank, then downgrade. Preserve the prepared previous bank; never manually point an
old reader at it or activate partial files. No live downgrade was performed.

## Automated verification and existing failures

- Final addon exact-source unit selections: Market 65 + Crafting 37, **76 unique tests passed**, zero failed; clean `a59bbcec...`. Fast Market regression workflow44 also passes; focused development group is 14 tests (~10–12s).
- Broader checkpoint:76 offline checks and syntax pass; Auction/Chart simulator 21 scenes pass. Workshop simulator7 selected poses fail 41 existing checks (negative control 42); original-main and final-addon focused craft/opps/wrong reproduce the identical 41 ordinary failure lines. Overall integration command remains **FAIL** (664.5s); no release gate is claimed.
- Native core:76 passed, zero failed; existing opt-in profiler and explicit Unix integration driver ignored normally. Production-code API/publisher/consumer checks pass with 129 fabricated variants / 60 days in 16/32; all original legacy checks remain.
- Hosted runtime checkpoint Market `f7c937a...`: [Backend 319](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45069273246), [website 307](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45069273225), [Windows 311](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45069273222) **pass** (747 PostgreSQL tests), including installed UI, picker, legacy/current consumers, prepared16/32, frozen old native with new addon, and verification of the existing signed-updater chain. No new signing/publication occurs.
- Existing dedicated sync-performance 23 [fails](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45064754409) in baseline repeat 1 auto mode with Error:Network (one 202 response, server thread alive; no in-flight request at failure). Later source-equivalent campaign status is in ci.json; it is not silently excluded. The final documentation commit may have new CI runs; runtime evidence is pinned explicitly rather than relabelled. 

The Workshop simulator failure is not called a pass. The 41 exact failed lines in the
candidate Opportunities scene match the original `b541c5b...` baseline and the final addon.
They concern existing Worth/Disenchant/tooltips and planner assertions; classified simulator
UTF-8/voice limitations remain in the full logs. The broader Auction/Chart selection passed.
No assertions, catalogs or failure classification were suppressed. This is not full/release
certification, and the existing failure needs its own fix before a clean overall gate.

Hosted historical failures are retained: Stage A's first PostgreSQL run missed an autouse
fixture import (corrected without weakening runtime contract discovery); Windows307's UI
confirmation failed, while later identical-runtime installed campaigns pass without a UI
test change. The existing sync-performance automatic-delivery campaign fails in the **frozen
baseline** with Error:Network before candidate comparison. Initial/no-op/incremental and
archive comparison steps pass. The failed campaign is not treated as a new-format speedup
or a passing release gate; see the bounded CI evidence. No timeout or retry assertion was
changed to obtain green results.

## Reproduce

Use existing repository dependencies (Market backend requirements, Rust toolchain, addon
Lua 5.1/bitop). These commands write only disposable fixture data and evidence directories.
They do not discover a real installation or contact production.

```sh
# Addon checkout: fast normal-development group, then broader affected units.
python tools/test_runner.py feature market-performance --jobs 2
python tools/test_runner.py unit market --profile cloud --jobs 2
python tools/test_runner.py unit crafting --profile cloud --jobs 2

# Market checkout: source/codec/publisher tests.
(cd backend && DATABASE_URL=sqlite:// python -m pytest -q tests/test_workshop_prepared.py tests/test_workshop_summary.py)
cargo test --locked --manifest-path desktop/core/Cargo.toml --lib

# Build the opt-in Unix test driver; it is absent from release builds.
cargo test --locked --manifest-path desktop/core/Cargo.toml --lib --no-run --message-format=json > /tmp/prepared-driver.jsonl
driver=$(python -c 'import json; rows=[json.loads(x) for x in open("/tmp/prepared-driver.jsonl")]; print(next(x["executable"] for x in rows if x.get("reason")=="compiler-artifact" and x.get("executable") and x.get("profile",{}).get("test")))')

# Set this to the exact pinned, clean addon checkout.
addon=/path/to/pinned/TwichUI
python scripts/verify-workshop-e2e.py --rust-client "$driver" --addon-root "$addon" --current --prepared 16 --test-driver --variants 129 --days 60 --out /tmp/prepared-e2e-16
python scripts/verify-workshop-e2e.py --rust-client "$driver" --addon-root "$addon" --current --prepared 32 --test-driver --variants 129 --days 60 --out /tmp/prepared-e2e-32
python scripts/verify-workshop-e2e.py --rust-client "$driver" --addon-root "$addon" --current --ordinary-admission --test-driver --variants 129 --days 60 --out /tmp/prepared-e2e-legacy

# Opt-in campaign generates its source using the existing PR127 fixture builder.
python scripts/measure-workshop-prepared.py --addon-root "$addon" --rust-test-driver "$driver" --reps 3 --out /tmp/prepared-performance
# Separate actual UI harness, reopen and lazy-history exercise.
python scripts/measure-workshop-prepared.py --addon-root "$addon" --rust-test-driver "$driver" --recipes 120 --reps 1 --view ui --scenario reopen --history-probe --out /tmp/prepared-ui
```

Use the documented backend environment; CI supplies the existing contract-bundle fixture. All output directories above must be new/empty.
An existing audit `upstream.json` can be reused via `--source`; its SHA must match the
curated report. Do not regenerate on live records to reproduce these synthetic numbers.
The Unix publisher uses the existing **cfg(test)** synthetic executable identity; its
ownership, HTTP, codec and publication routines are production. Windows CI separately
uses the real versioned-PE disposable installation and exact old/new native clients.

Performance-specific ordinary development remains the existing market-performance group,
about 10–12 seconds here. The large campaign is never included in normal groups. Keep
operation-count invariants in the fast tier, native format/publication integration separate,
and larger stress/release runs opt-in, following PR127's four-tier plan. Store baselines in
`docs/evidence/game-ready-current`, compare identical source/fixture/recipe/oracle identities,
and review intentional baseline changes in a PR explaining hardware, source or fixture changes.
Report the failing case and raw samples; never update a threshold merely to make CI green.

## Exact owner-directed Forever procedure

After review and separate approval to install a test build, use a disposable/test installation
through the existing Companion workflow, not live fabricated data. Do not change native
admission flags. The current session has changed no real game installation.

1. Record addon/native source, source generation, prepared attestation id, layout and bank.
   For a legacy control install a compatible complete legacy generation. Test the same
   genuine generation, recipe set, scale, hardware and fixed initial viewport. Run three
   cold trials per layout, each starting with a safe `/reload`/fresh Lua session.
2. Run `/tui perf start workshop 3`, then `/tui perf mark opportunities-open`. Open Workshop
   -> Opportunities and keep the initial viewport fixed until all calculations settle.
   Run `/tui perf stop`; export Quick summary and JSON from Diagnostics after combat.
3. Record first/first-ten useful prices, actual initial visible completion, all-list completion,
   prepared loads/hashes/authenticated leaves/full partitions, price hits/pending, catalog/
   craft counts, total/worst prepared-load/verification/engine callbacks and sampled memory.
   Price settlement waits include queue/work; native LoadAddOn does not separate compilation
   and execution like the offline harness. A sampled heap figure is not a true peak.
4. Close/reopen without reload: expect cached rows promptly, zero new current loads/hashes
   and no compatible crafting recalculation. Scroll, sort/filter and compare exact profits,
   costs, selling values and unknown/variant behavior against the legacy control.
5. Select history separately; verify original daily provenance, gaps, hover/zoom and lazy
   loading. Rapidly switch recipes and hide/reopen while loading. Chart #117 remains its
   separate change. Try ordinary combat entry/exit without protected actions; cancelled
   price work must resume on existing lifecycle events, without a timer loop.
6. In the test installation only, exercise generation replacement (including unchanged-source
   publication), interrupted sync and compatible rollback. Never activate an incompatible
   root or incomplete bank. Judge GC/frame tails before choosing 16 versus 32 permanently.

The investigation's native goals remain goals: roughly <=2 s current preparation CPU,
<=3 s initial-visible settlement and <=10 s total for the 120-recipe scenario; <=10 ms
compatible warm settlement, current-load p95 below 8 ms, and review the provisional 16 MiB
sampled incremental-memory budget. This report does not claim them achieved in Forever.

Curated receipt hashes are in [SHA256SUMS.json](evidence/game-ready-current/SHA256SUMS.json).

## Handoff limits

No production service, collector configuration, database/history, real AddOns/SavedVariables,
release version/tag, signing identity or updater publication was changed. All four PRs stay
draft. Remaining work is review, the recorded baseline test failures and owner-directed
Forever acceptance/memory/layout choice. No subsequent optimization stage is authorized
or started by this handoff.
