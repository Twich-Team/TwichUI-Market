# L1 scoped Market bridge foundation: review and execution plan

**Offline contract/prototype candidate; no production integration or activation.** Normative proposal and reproduction: [scoped-l1 README](../contracts/bridge/scoped-l1/README.md).

## Executive outcome

Keep complete retained market evidence server/desktop-side; project only explicit exact variants and all eligible daily closes in the requested supported window to WoW. Use **contract 1 / schema 3 / transport 1**, required feature `scoped_selection`. Scope-complete does not mean whole-market-complete. Refuse the entire candidate on identity, authorization, unsupported basis, history support, integrity or capacity failures; preserve completed data.

The isolated reference producer, schema validators, independent expectations and test-only Lua consumer prove this distinction without changing any runtime route, cache, publisher, addon loader or UI. They do not implement the full-history archive, authenticated transport or transactional filesystem/SQLite recovery. Those remain L2/L3.

## Frozen sources and research dependency

| Input | Exact commit / status |
|---|---|
| Market integrated base | `73617a9e2ce6b32f539700c72caab4592a443a2f` |
| TwichUI integrated base | `732ccf87b825c7f93d7dbb73cae9fa9bfb001fd8` |
| Research #12 | Open draft, unmerged at inspection; pinned `49cfa2bc5701657c054d01ee44817ad4a3662aa3` |
| Concurrent changes | Market #10 and #11 already merged; no Explorer/Data Sources/provider files edited |

No PR #12 merge/cherry-pick or branch modification was needed. Its report was read from the pinned research worktree. M0 original chat is not present; its recorded conclusions in M0.5 were reviewed along with M1a, M1b, amendment, M1.5 and actual source paths.

Research suggested a new major contract; existing unknown-schema refusal makes schema 3 sufficient. Research's canonical complete-close semantics are retained, but today's exporter selects from accepted complete observations and emits `scope_complete=true`, rather than storing/querying partial source completeness. The prototype uses supported synthetic partial fixtures to define future behavior without claiming production has partial data.

## What L1 specifies and proves

The normalized request includes complete issuer/market identity, sorted exact `(item_id, variant SHA)` pairs, inclusive dates, algorithm/basis, expected schema and field profile. Duplicate pairs refuse. Different request order normalizes to the same bytes; different dates preserve stable selection ID but change request and generation IDs. Names/tracked-set origins remain local metadata resolving into explicit selections, not new implemented scope types.

The source-sealed generation contains the exact request/digest, included identity list/count, per-record hashes, calendar coverage, watermark, existing observation metadata and whole-generation integrity. `excluded=[]` proves no requested identity was dropped; it does not enumerate the entire unrequested market. All valid unrequested identities resolve to `outside_scope`, no record or zero. `scope_complete=true` coexists with both whole-market flags false. Missing/partial source dates remain gaps/unknown, while complete market observations can prove selected-item absence. Independent completion receipts stay outside source identity and contain no account/credentials.

The `daily_research_v1` profile excludes distributions by declaration, not by emergency compaction; metrics and all daily closes are retained. Full reference support and provenance are not recalculated from a shortened chart. Historical-only and bid-only records remain meaningful. Canonical/provisional algorithms, local aggregates, source identity and quality/trading policies remain distinct.

## Targeted capacity evidence

All sizes below are **new measured synthetic bytes**, including receipt and source escaping for Lua. No Forever or real production history was used. Selection-hash CPU is mean of 20 hashes in one Python process; it is not client validation time. Sparse means four observed dates across 60 days. Dense means 60 eligible closes. All counts are exact variants.

| Variants / shape | Canonical bytes | Lua source bytes | Manifest bytes | Scope bytes | Hash CPU µs | Result |
|---|---:|---:|---:|---:|---:|---|
| 10 / sixty | 159303 | 222391 | 35410 | 7615 | 103.403 | eligible_policy |
| 100 / sixty | 1298121 | 1841929 | 59263 | 31466 | 644.22 | eligible_policy |
| 500 / sixty | 6359505 | 9039793 | 165263 | 137466 | 3147.824 | refused_policy |
| 1000 / sixty | 12686247 | 18037165 | 297766 | 269967 | 7107.321 | refused_hard_bound |
| 10 / sparse-sixty | 25765 | 35429 | 11052 | 7733 | 107.846 | eligible_policy |
| 100 / sparse-sixty | 181963 | 248987 | 34905 | 31584 | 662.894 | eligible_policy |
| 500 / sparse-sixty | 876147 | 1198051 | 140905 | 137584 | 3155.893 | eligible_policy |
| 1000 / sparse-sixty | 1743889 | 2384423 | 273408 | 270085 | 6920.958 | refused_hard_bound |

At 100 dense variants, ~1.30 MB canonical/~1.84 MB Lua fits proposed byte policy; this does not prove acceptable frame time. At 500, dense fails both 2 MiB canonical and 3 MiB Lua policy, sparse fits. At 1,000, explicit membership duplication and record hashes exceed proposed 256 KiB manifest hard bound in both shapes. That refusal is intentional evidence, not a hidden test failure or reason to enlarge a limit. Scope overhead is ~31 KiB at 100 and ~270 KiB at 1,000; shared observation references add 26,221 bytes dense / 1,749 bytes sparse. No per-record market metadata or copies of observation objects are introduced.

Six contract-feasible cases cross-check predicted canonical and escaped-source lengths against actual serializers, with no difference. Two 1,000 cases are refused by exact manifest preflight before publication; their predicted source lengths are reported without materializing an addon. Boundary tests also prove exact-budget acceptance and one-unit-over refusal separately for canonical bytes, Lua bytes and count. No scope/date pruning occurs. Preflight in this small reference precedes activation but still builds a bounded candidate; L2 must use streaming sizing/materialization to eliminate large intermediate graphs.

Policy layering:

- Contract hard bounds: proposed schema-3 selected count 1,000; request 128 KiB; manifest 256 KiB; inherited generation 32 MiB, record 64 KiB, daily/reference/precision bounds and separate expanded Lua 130 MiB. Deployed v1 limits are untouched.
- Administrator budgets can tighten these bounds and expose structured actual/limit diagnostics. They cannot relax correctness or hard limits.
- Desktop initial delivery proposal: 100 default selected variants, all of ≤2 MiB canonical/≤3 MiB Lua/≤1,000 count. No automatic activation during L1.
- Real-client gates: nominal ~2 ms work, p99 ≤3 ms/max ≤10 ms, synchronous compile/load ≤10 ms, steady payload heap ≤5 MiB and old+new transient ≤16 MiB; ≤5 s readiness is an owner-review target. These are **not demonstrated** here.

M1.5's existing synthetic evidence remains decisive: 1,000 dense-sixty records required ~27.24 s validation CPU, ~12.64 MiB retained heap and ~112.14 ms median offline compilation; two-date 1,000 was ~3.16 s CPU with 8.60 ms worst slice. Full 25,000 one-date was ~71 s CPU/~258 ms median compile. This proof measures schema selection/size semantics, not a new timing comparison or faster Lua implementation. It does not repeat the five-pair matrix. Global GC, compilation and timer cadence still require Forever measurements.

## Verification and evidence boundaries

**Unit-tested:** 16 focused Python conformance methods, including all 18 negative mutations; 4 addon Python-driven tests executing the actual Lua parser/shared validators plus isolated schema-3 proof; 6 existing bridge reader methods pass unchanged. Eleven deterministic example documents reproduce byte-for-byte. Independent canonical JSON/SHA verifies selection, manifest, record-array, individual-record and source-body hashes; authored constant-price expectations are not derived by the implementation under test.

Shared payload: **15 files** (2 schemas + 13 fixture documents), plus identical `SHA256SUMS.json`. Hash manifest SHA-256: `c5a465e323005735444f3e5fe2ec48241f50942ebdfb7e7078049849206ec2a7`. TwichUI mirror pins the authoritative Market fixture commit in `UPSTREAM.json`; the final source pin is recorded there, not a mutable branch-only reference. Existing v1 fixture bytes/schema/amendment are unchanged.

The fixture corpus covers all 20 requested cases (mapping in normative README), plus current unknown/incomplete states, same-item different upstream variants, account/device/origin mismatch, receipt separation, unchanged-generation recovery-slot preservation and zero-insertion refusal. Semantic negative fixtures are independently resealed so missing closes/precision errors cannot fail only because outer hashes are stale. A per-record-hash mutation is outer-resealed without repairing that record hash.

One initial Lua harness run failed because it sent the deeply nested **schema plan** through the bounded **data parser**. Corrected the trusted test harness to construct its schema plan as test code; data still uses the unchanged strict parser, and parser depth limits were not widened. Final focused runs pass. This is not a runtime format exception.

No runtime reader code changed; comprehensive simulator/full-game suite was deliberately not run for isolated contract fixtures. No simulator-tested, screenshot-reviewed, Windows-installed, real-client-tested or genuine-history acceptance is claimed. No production access or credential use was needed. Python allocation/CPU and game-frame responsiveness are not equated.

Reproduction:

```sh
# Market
python3 -m unittest discover -s contracts/bridge/scoped-l1 -v
python3 contracts/bridge/scoped-l1/capacity.py > /tmp/scoped-l1-capacity.json
# TwichUI, with existing Lua 5.1 + bit test toolchain on PATH
python3 -m unittest discover -s tests -p test_workshop_scoped_bridge_l1.py -v
python3 -m unittest discover -s tests -p test_workshop_bridge.py -v
luac5.1 -p tests/prototypes/scoped_bridge_l1.lua
# Both repositories
git diff --check
```

Capacity hash timings naturally vary; exact size/status fields are the reproducible comparison. No network/DB/addon installation is part of these commands. The minimal prototype uses existing v1 arithmetic/time/record validators; it is not the production producer, cache, publisher or cooperative reader.

## L2 execution order: Market producer and desktop delivery

Separately authorize L2; keep current routes/defaults unchanged until explicit acceptance.

1. **Define the complete-history checkpoint API and retention ledger first.** It must describe retained source/derived coverage independently from WoW projection limits. Use an immutable checkpoint root binding issuer/market/algorithm, observation watermark/as-of, retained date bounds, evidence revision, ordered stream/part hashes and source completeness. Page bounded records/observations by stable identity/time; include late imports/daily-close corrections. Server can retain raw intraday evidence without requiring every raw listing in desktop's research cache. Document exactly which retained layer desktop mirrors. Do not promise canonical backfill without originals. Require account/device auth and selection/checkpoint-bound cursors; no giant full-generation intermediate. Tests: disposable PostgreSQL plans/counts, current/history-only union, incomplete/missing dates, source mutation mid-download, expired/revoked/cross-context cursor.
2. **Implement normalized transactional archive caching.** New namespaced SQLite store for source observations, exact variants, algorithm-qualified daily evidence and immutable completed checkpoints. Preserve legacy scalar and bridge-v1 stores. Persist requested named sets/private source binding separately; never encode mutable UI labels into source hashes. Stage/download/validate complete checkpoint before promotion, retain prior checkpoint, append unchanged evidence without duplicating whole histories. Budget disk/page/WAL growth and crash recovery. Do not delete full desktop history when a WoW set changes. Tests: restart/resume, late corrections, auth changes, disk full, corruption, migration/newer-schema refusal and independent checkpoint hashing.
3. **Selection resolution and streaming preflight.** Proposed distinct endpoint `POST /api/v1/bridge/scoped/selections` (not activated in L1) accepts the explicit selection schema and negotiated target. Validate authorization/mapping, resolve every exact variant, refuse unavailable/unsupported history before generating absent rows. Compute exact canonical/manifest/source sizes using the selected profile, immutable watermark and retained metric support. Produce structured refusal with limits/actual sizes and no secret data. Never invoke current exporter compaction to silently shorten a scoped request. Cache/reuse sealed projections by checkpoint+request digest/schema/profile.
4. **Safe manual scoped publisher first.** Read a completed archive/projection only, validate source+receipt+budgets and configured compatible target. Reuse owner/path/ACL/reparse checks, fixed literal grammar, flush/sync, atomic replace, independent readback and previous distinct artifact. Define versioned namespace/staging layout explicitly; old targets get legacy or refusal. No game discovery/installation or background auto-publishing until later authorization. Tests: partial candidate, mixed schema/generation, wrong account/market/profile, unknown feature, AV/file locks, power interruption and rollback on disposable Windows staging.
5. **Genuine observation acceptance, separately authorized.** Read-only safe aggregates and selected exact variant history compared against pinned retained evidence; prove source-count/date/integrity completeness and exact copper. Do not use synthetic fixtures as production-history evidence or re-run enormous failed exports. Confirm 100 dense/sparse budgets with actual distributions; production data must not be copied into repository fixtures.

L2 production impact: additive APIs/storage only after explicit deployment approval, backup/restore rehearsal and tests. Rollback disables new delivery, restores matching prior supported artifact/app/checkpoint, retains original observations and old stores. No collector/provider/Explorer/Data Sources changes are required.

## L3: Workshop scoped consumer

Add explicit schema dispatch/capabilities and a schema-3 scope validator, either shared factored evidence checks or strictly private adapter. Keep schemas 1/2 support and pinned mirrors. Enforce exact requested identity set, record hashes, calendar completeness and receipt, use immutable candidate state and last-good activation. Preserve existing local Prices/History2/distributions/market/profile namespaces byte-for-byte.

The external adapter returns typed `outside_scope`, source gaps, unknown, observed absent, unsupported arithmetic, loading/invalid and pending-request states. It must not reuse `not_observed` for unselected records. External catalogue enumerates only delivered identities; describe it as selected history, never whole market. Do not add local-source fallbacks or unlock Advisor/Sell/Shopping/CraftPlanner confidence. Exact variants remain explicit. Future request action is separate from price-source choice.

Keep strings retained, lazy per-record decode and the existing bounded cache concept (24 decoded records initially), with bounded selection/calendar indexes. Cooperatively validate scope, records and hashes; do not assume schema-3 larger manifest parsing is slice-safe because small-fixture proof passes. Register diagnostics for scope/hash validation, load/compile attribution, retained header/selection/index/cache and old+candidate heaps. No forced global GC. Tests: every shared fixture, adversarial nested/oversize/mixed data, strict schema/version refusal, source-aware UI handlers, local-history fingerprint, no eager startup load/no AH action. Run focused affected tests during development; one appropriate comprehensive run at frozen shared-runtime milestone, not at each research checkpoint.

Rollback: select prior supported consumer+artifact pair; new consumer must still read legacy full data and preserve local schemas. No default source switching or installation is implied.

## L4: actual Windows and Forever acceptance

Use separately authorized disposable profile/staging; preserve real player data. Measure native publisher ACL/reparse/AV/replace/restart/power-loss behavior and actual addon discovery/load ordering. Record synchronous compile+assignment, timer cadence, readiness, p99/max work and frame-time tails with representative other addons/global GC, steady and old+new memory. Test cold startup versus explicit first open, combat refusal, sparse/dense and maximum accepted byte sets, 100 selected variants with actual retained production shape, malformed/future/partial data and cross-session rollback. Verify exact price/supply/date/gap/provenance against pinned source and byte-identical local SavedVariables before/after. No offline test establishes these results. If gates fail, reduce delivery budget or investigate compact representation; do not increase limits automatically.

## M2: automatic delivery and freshness

Only after L4: opt-in configured game destination/account/market/working set, independently scheduled full-history sync and conservative projection publication, coalesced generation updates and recoverable previous data. Desktop-first selection is the least ambiguous request workflow; a later bounded player-mediated request string or explicit read-only SavedVariables request queue requires its own security/parser/profile/flush specification. The addon cannot call Market directly, read arbitrary disk files or force live SavedVariables flush; companion must never edit live SavedVariables.

Show actual source observation/upstream age separately from desktop completion/pending publication. Keep an already loaded generation immutable; queued updates apply at a player-confirmed safe refresh boundary. Do not assume newly written files or already loaded addons reread dynamically. No surprise reloads; target at most one optional coalesced session refresh, with extra user-requested history applied when chosen or next login. New addon discovery/restart details must be tested in L4. Automatic delivery, freshness UI/chips, reload integration and pricing/trading policy require separate authorization.

## Owner decisions for the next milestone

No owner intervention was required to complete L1. Before separately authorizing L2, confirm:

1. Accept schema-3/profile semantics and conservative 100/default byte policy; 1,000 is only a hard count ceiling and may fail metadata budget.
2. Define the exact desktop mirrored retention layer (all retained daily/provenance evidence at minimum; whether raw intraday listings belong desktop-side) and disk budget/retention. No evidence deletion or stronger history claims may be implicit.
3. Choose compatible target/namespace configuration and desktop-first selection as initial workflow. Named/tracked seeds are future selection inputs, not weaker identity rules.
4. Assign authorized Windows/Forever acceptance hardware/profile and agree readiness/frame/heap gates. Architecture/contract approval is not deployment or M2 permission.

Stop at L1. No server route activation, desktop schema migration/sync change, Workshop runtime integration, game installation, SavedVariables modification, production access/deployment, forced reload, freshness indicator, default pricing activation or live AH transaction occurred.
