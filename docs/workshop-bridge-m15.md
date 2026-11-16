# M1.5 bridge performance and capacity acceptance

This is a source review candidate, not a deployment or client activation. M1.5 improves the existing bridge without changing pricing, identity, history, authentication or atomic-generation meanings. Both PRs remain draft: [Market #9](https://github.com/Twich-Team/TwichUI-Market/pull/9) and [TwichUI #23](https://github.com/Twich-Team/TwichUI/pull/23).

## Frozen sources and method

Baseline Market: 68c075138d5f50608c741b0e51b7013d9bf8769d, target integration/companion-v2-metadata-recovery. Baseline addon: c0c9de1ef3242d5ca50c2c514cd481e81dfaf13b, target feature/workshop. Upstream heads were fetched and matched before implementation.

Measured checkpoints: Market d012c32513b4205eee4167db85aac065cbfdc84f, addon a779e227d32d65c90871c00c347f5dd9ce91ce31. Addon febed289d7db429d00d02fcff73cdbf262d541c2 strengthens a foreign-item negative control; runtime files are identical to the measured checkpoint.

All scale observations are **synthetic**. Listed prices are a constant 100 copper, making expected supported means/medians independently known. Missing dates, complete/incomplete observations, explicit absence and unknown states are retained. Dense 14/60-date inputs test structure and cost, not production pricing over those horizons.

Five interleaved baseline/candidate pairs use identical generation bytes, fresh processes, default Lua GC, release Rust test binaries and the actual reader. Source IDs, binary hashes, runtime context and every sample are in [capacity.json](evidence/bridge-m15/capacity.json). Linux has a four-CPU quota and 16 GiB memory limit; each child has a 2 GiB address-space guard. CPU, child wall time, peak RSS, incremental Lua heap, compile/assignment cost and scheduling steps are distinct. Child wall time includes up to roughly 10 ms parent polling quantization.

The Rust baseline has the identical opt-in harness appended only inside its test module; production functions remain those of the frozen baseline. [prepare-bridge-baseline.py](../scripts/prepare-bridge-baseline.py) reproduces this overlay and prints hashes. No benchmark binary or generated data artifact is shipped.

Improvement claims follow the existing noise rule: median difference exceeds both 5% and three times the larger MAD, with consistent direction in all five pairs. Maxima are always reported, not replaced by averages. Unfavorable exploratory samples also remain in [exploratory-index-pairs.json](evidence/bridge-m15/exploratory-index-pairs.json) and [exploratory-checksum-pairs.json](evidence/bridge-m15/exploratory-checksum-pairs.json).

## Bottlenecks and implementation

An instrumented diagnostic baseline attributed approximately 69% of CPU to hashing, 22% to encoding, 6% to parsing and 3% to semantic checks. This is attribution with instrumentation overhead, not the paired timing benchmark. The original 1,000-record workload reproduced at 4.43–4.70 seconds CPU, about 7,994 steps and a 3.32 ms maximum in three exploratory runs. The older 27 ms spike did not recur in that reproduction; [all reproduction samples](evidence/bridge-m15/baseline-reproduction.json) remain available.

Changes:

- Hoisted escape maps, bounded ASCII runs and one canonical fragment buffer reduce temporary allocations.
- Reused SHA scratch storage, equivalent binary Ch/Maj formulas and yields within checksum work require no new game library, rotate helper or variadic bit API.
- Elapsed budgets reserve one millisecond of headroom, with a 512-unit ceiling and the original 32-unit fallback when no clock exists.
- Existing sorted identities support compact exact-variant ranges instead of two per-item tables. Missing keys cannot cross item boundaries.
- Idempotent access retains the validated manifest string rather than re-encoding it; a new unvalidated snapshot is never trusted.
- Safe printable ASCII remains inside fixed quoted Lua literals. Quotes, backslashes, controls and non-ASCII bytes use fixed-width decimal escapes. Narrow readback accepts both old all-decimal and compact representations. Export avoids cloning every record just to create its small manifest.

No complete hash, schema/semantic check, duplicate check, bound, exact-copper rule or observation reference was removed. Canonical/provisional meanings and local trading-confidence gates are unchanged. Server exporter/collector production code is unchanged.

## Results and limits

Larger matched workloads demonstrate roughly 30–35% lower validation CPU, with some rows approaching 36%, around 65% smaller Lua source, fewer callbacks and lower retained memory. Exact tables below take precedence over rounded summaries. The 1,000-record two-date case retains about 1.79 MB after collection versus 2.00 MB: incremental payload/index heap, not all Workshop or game memory.

**The 3 ms worst-slice target is unmet.** Final samples include **23.017 ms** at 10,000 records, **26.480 ms** at 1,000 records/14 dates and **26.170 ms** near the input ceiling. The primary 1,000-record case has an 8.595 ms maximum. Some maxima worsen despite lower median CPU. Every sample is preserved.

Lua deadlines are checked between resumable units; they cannot preempt interpreter GC, C string operations or the addon compiler. Diagnostic tails also occurred with GC stopped, so they cannot be attributed solely to collection. Explicit diagnostic collection grows into double-digit milliseconds at larger heaps. Source work is bounded, including 16-round checksum units and 128-byte string runs, but a hard elapsed ceiling is not established. Compilation is separately synchronous; assignment time alone conceals it. Production GC policy is untouched.

Unchanged frozen limits: **32 MiB canonical serialized input**, **64 KiB manifest/record strings**, **150,000 records**, **61 observation references**, **60 daily rows per variant**. The separate expanded-Lua bound remains **4 × 32 MiB + 2 MiB = 130 MiB**.

The fully priced 25,000-record/one-observed-day input is 33,026,981 canonical bytes, just below 32 MiB. It loads offline but needs about 71 seconds CPU and tens of thousands of steps. This is not client comfort. Fifty thousand historical-only variants project to 53,502,418 bytes and are refused by preflight: **zero exported records**, no sampling/history pruning. Preflight refusal is not an actual server HTTP result.

### Capacity and memory

| Variant records / profile | Canonical MiB | Candidate Lua MiB | Validation CPU s: before → after (median) | Worst step ms: before → after (observed max) | Candidate steps (median) |
|---|---:|---:|---:|---:|---:|
| 100 / two-gap | 0.14 | 0.20 | 0.46 → 0.32 | 3.93 → 3.54 | 159 |
| 1,000 / two-gap | 1.42 | 1.99 | 4.44 → 3.16 | 4.46 → 8.60 | 1,574 |
| 5,000 / two-gap | 7.10 | 9.92 | 22.96 → 16.10 | 8.72 → 9.00 | 7,991 |
| 10,000 / two-gap | 14.20 | 19.83 | 48.24 → 32.36 | 20.74 → 23.02 | 16,023 |
| 25,000 / one | 31.50 | 43.87 | 110.52 → 71.00 | 32.34 → 26.17 | 35,255 |
| 25,000 / historical-only | 25.51 | 34.88 | 93.08 → 59.61 | 32.13 → 20.66 | 29,576 |
| 50,000 / historical-only | 51.02 | refused | — | — | — |
| 1,000 / one | 1.26 | 1.76 | 3.97 → 2.83 | 4.90 → 3.86 | 1,409 |
| 1,000 / fourteen | 3.66 | 5.19 | 11.21 → 8.10 | 20.96 → 26.48 | 4,131 |
| 1,000 / sixty | 12.23 | 17.45 | 38.77 → 27.24 | 37.92 → 12.65 | 15,227 |
| 1,000 / sparse-sixty | 1.79 | 2.52 | 5.72 → 4.04 | 7.64 → 4.26 | 2,000 |
| 1,000 / mixed | 2.34 | 3.30 | 7.24 → 5.22 | 13.29 → 13.48 | 2,617 |
| 1,000 / mixed-provisional | 3.15 | 4.38 | 9.62 → 6.95 | 15.67 → 18.62 | 3,708 |

| Variant records / profile | Retained Lua MiB: before → after (median) | Candidate peak sampled Lua MiB | Desktop process peak RSS MiB: before → after (max) | Candidate Lua process peak RSS MiB |
|---|---:|---:|---:|---:|
| 100 / two-gap | 0.21 → 0.19 | 1.03 | 12.35 → 10.70 | 10.39 |
| 1,000 / two-gap | 1.90 → 1.70 | 4.03 | 77.06 → 56.69 | 15.79 |
| 5,000 / two-gap | 9.91 → 8.85 | 18.29 | 312.87 → 278.41 | 40.02 |
| 10,000 / two-gap | 19.82 → 17.69 | 35.88 | 617.74 → 550.05 | 54.58 |
| 25,000 / one | 42.45 → 37.91 | 75.68 | 1,394.27 → 1,154.53 | 93.36 |
| 25,000 / historical-only | 36.47 → 31.93 | 63.98 | 967.79 → 785.54 | 114.19 |
| 1,000 / one | 1.74 → 1.54 | 3.70 | 76.04 → 76.04 | 76.04 |
| 1,000 / fourteen | 4.16 → 3.96 | 8.64 | 155.23 → 129.49 | 76.91 |
| 1,000 / sixty | 12.83 → 12.64 | 26.28 | 480.54 → 427.09 | 86.36 |
| 1,000 / sparse-sixty | 2.28 → 2.08 | 4.80 | 87.03 → 78.89 | 78.89 |
| 1,000 / mixed | 2.84 → 2.64 | 5.91 | 98.13 → 79.32 | 78.89 |
| 1,000 / mixed-provisional | 3.65 → 3.45 | 7.59 | 137.02 → 110.48 | 78.89 |

## Compatibility and security

Contract/transport remain v1; schemas 1/2, AMENDMENT-001 and pricing/history/quality/generation meanings remain unchanged. All 14 authoritative files match the addon mirror pinned to 1f76f8468722f07430acb3a10d26d6ad2d20e9cd. No fixture/schema bytes changed. The v1 wrapper already permits bounded quoted strings with fixed-width escapes: compact source represents identical decoded bytes.

[Focused compatibility](evidence/bridge-m15/compatibility.json) uses actual publishers/readers and malicious literal text. Old Lua reads compact source; new Lua reads legacy source; publication over a legacy artifact validates readback and keeps recoverable artifacts. Appended code and invalid literal bytes are rejected. An older desktop narrow inspector may refuse compact source on downgrade and fails closed; old native applications are not promised forward readback support.

[Authenticated HTTP end-to-end proof](evidence/bridge-m15/e2e.json) uses independent shared fixtures through actual FastAPI, Rust cache/promotion/export and Lua. Generation stays 4e6cea38071018d519682ba4690b79566303f8ce67039ef6e99472f107ee453f: four pages, 7,702 canonical / 10,671 compact Lua bytes; Nov 13/15 dates and missing Nov 14. Corruption retains the preceding valid snapshot, and local data stays unchanged. This is synthetic, not genuine production acceptance.

[Server probe](evidence/bridge-m15/server.json): authenticated ASGI requests, disposable synthetic SQLite, 1,000 records/two dates, 20 pages/four SQL statements per page. Cold materialization was 1.571 seconds/60 SQL statements; warm manifests were 3.820–8.203 ms/9 statements, and all pages took 174.103–193.002 ms/80 statements. Peak process RSS was 105,418,752 bytes. Imports are separate. This is not production PostgreSQL/network capacity acceptance.

Negative controls cover hashes/lengths, duplicate keys/identities, markets, future versions/algorithms, dates/references, large exact copper, truncation/oversize, partial downloads, interrupted/failed replacement, historical-only variants, absent/invalid addons, last-good retention and unchanged local state. Independent Python JSON/SHA vectors and deterministic work/range tests cover optimized paths. Injection text stays data: an encoding-specific text-absence assertion is replaced by exact readback and actual Lua execution sentinels.

## Verification

[Machine-readable verification](evidence/bridge-m15/verification.json) records exact sources, fixture hashes and completed checks. The [addon acceptance report](https://github.com/Twich-Team/TwichUI/blob/feature/bridge-performance-m15/docs/workshop/market-bridge-m15.md) owns the source-pinned comprehensive Cloud result and preserved simulator/negative-control reports.

| Check | Result |
|---|---|
| Locked Rust workspace | 80 passed, 0 failed; 1 newly added opt-in profiling test excluded from normal regression and exercised by the benchmark harness |
| Deterministic workload shapes, incomplete/missing history and refusal | 3 passed |
| Independent Python JSON/SHA and actual Lua bridge reader | 6 methods passed |
| Addon fast / affected feature | 18 / 42 modules passed; affected Workshop simulator catalog passed |
| New bridge-focused negative controls | 16/16 detected; no survivor, invalid, timeout or infrastructure failure |
| Full Market mutation campaign | 234/234 detected; 226 assertion failures, 8 runtime failures, no survivor/invalid/timeout/infrastructure failure |
| Mutation catalog validation | 351 valid patterns (234 Market, 117 Craft); Craft campaign not repeated because Craft implementation is unchanged |
| Old/new source representation and injection | PASS; actual Rust publishers and actual Lua readers |
| Authenticated cross-component golden fixture | PASS; actual HTTP, Rust and Lua with independently committed expectations |
| Market checkpoint CI | Backend, Windows companion and private website workflows passed at d012c325; backend 503 PostgreSQL tests and 37 script tests passed |

The final addon full run is performed once at the frozen code/test commit because shared parsing/loading changed. Consult its linked report for actual counts, deterministic PNG/replay/negative-control outcomes and timing; no repeated full run or benchmark matrix is required for documentation changes. Cloud runs retain the existing no-assets limitations and never set the local milestone gate. CI uses disposable databases and isolated Windows workers; it does not establish owner staging/Forever behavior or live migration acceptance.

## Conservative proposal and M2 prerequisites

These are review proposals, **not enforced limits or client-qualified capacity**:

- Start with all of: at most **2 MiB canonical**, **1,000 exact-variant records**, **3 MiB Lua source**. Record count alone cannot bound long history.
- Review nominal 2 ms validation work, p99 at most 3 ms, maximum at most 10 ms, and compile/load at most 10 ms on actual hardware. Offline tests do not establish these targets for the game.
- Review incremental steady heap at most 5 MiB and two-generation transient heap at most 16 MiB. Measure changed-generation behavior and global game GC.
- Measure callback cadence and elapsed readiness. One callback/frame is only a model; CPU time is not client elapsed time.
- Near budget, require explicit size/history/coverage review. Hold/refuse over-budget delivery and preserve the previous good snapshot; never sample variants, discard required observations or label incomplete data complete. No delivery/UI policy is activated here.

Before M2 activation, owner review must settle budgets and separately authorized Forever testing must establish compile cost, frame tails, timer cadence and readiness under real global heap pressure. Windows ACL/junction/reparse, interruption, replacement, antivirus/power-loss acceptance remain open. Genuine production history was not accessed.

If full-market volumes cannot meet these budgets, a separately reviewed versioned representation/transport change may be needed. That redesign is a follow-up, not a reason to extend M1.5 indefinitely. No M2 delivery, freshness chips, installation, reload, production deployment/migration/pricing activation, transactions or takeover began. No real game directory, credentials or player SavedVariables were modified.

## Reproduction and review

Use Lua 5.1/luabitop and the locked Rust toolchain. Build the release library test executable with:

    cargo test --manifest-path desktop/Cargo.toml -p twichui-market-core --lib --release --locked --no-run --message-format=json

The opt-in bridge::export::tests::profile_workload is not a timing assertion in normal regression tests. scripts/bridge_capacity.py drives identical synthetic fixtures through executables and readers. scripts/bridge_profile.lua is diagnostic; its no-gc mode is offline only. scripts/benchmark-bridge-server.py uses market_test.sqlite only. scripts/verify-bridge-compatibility.py checks both source representations; scripts/verify-bridge-e2e.py is the independent HTTP proof.

The completed matrix is sufficient. Do not expand/repeat it during this review, discard unfavorable samples or add fragile timing assertions. Use deterministic tests for remaining sparse/incomplete correctness questions. Keep replay/negative controls and one justified full run on frozen shared loader/parser changes.
