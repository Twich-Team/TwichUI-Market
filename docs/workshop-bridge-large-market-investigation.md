# Large Market delivery investigation and implementation recommendation

Research snapshot: 2026-11-16. **Documentation and synthetic sizing only; no implementation or production acceptance.**

## Executive summary

Recommend **D: complete desktop history cache plus a bounded, explicitly scoped WoW working set**, using C's selection workflow. Keep the current validated string transport initially; investigate E's compact representation only if real-client measurements require it. Do not raise bridge-v1 limits or split the entire market into dozens of addons as the first solution.

The reported production HTTP 413 is explained by a specific exporter ordering: it assembles and retains every record, summing canonical record bytes against 64 MiB, **before** its 32 MiB generation compaction pass. The 64 MiB counter is neither heap nor HTTP size. Dense daily rows, including explicit absence for historical-only variants, multiply the full variant union. Earlier preflight and streaming materialization are needed, but neither makes a full-market addon responsive. Existing synthetic measurements already demonstrate unacceptable full-generation loading costs.

No current consumer requires all 45,125 exact server variants resident simultaneously. External Market/history is display-only and explicitly selected. Local pricing, Advisor, Shopping, CraftPlanner and Sell remain independent. Complete data can exist on server/desktop while WoW holds only selected complete histories. Start acceptance at **100 exact variants**, subject also to byte/day budgets; 1,000 is an experimental upper ceiling, not an established safe default. Preserve full requested daily history or refuse the candidate with an actionable budget explanation.

Owner decisions: approve the scope/coverage model and workflow, define desktop history retention, agree real-client responsiveness gates and nominate a Windows/Forever acceptance profile. No implementation, production changes, automatic delivery or merge is authorized by this report.

## 1. Sources, evidence classes and isolation

Fetched integrated bases before inspection:

| Repository | Requested base | Inspected HEAD |
|---|---|---|
| Market | integration/companion-v2-metadata-recovery | `afb411a2da7d40c6950cf7ca4b5b414094fdbd1f` |
| TwichUI | feature/workshop | `732ccf87b825c7f93d7dbb73cae9fa9bfb001fd8` |

Market HEAD already includes the concurrent task's merge of provider-management #10. This investigation did not perform it. Research uses its own worktree and branch; addon inspection uses a detached worktree. No shared development checkout, deployment, collector, provider configuration or database was changed.

Authoritative review trail:

- [Architecture](architecture.md), [M0.5 specification](unified-pricing-m05.md), [research](unified-pricing-m05-research.md), [migration](unified-pricing-m05-migration.md), [M1a implementation](unified-pricing-m1a.md) and [acceptance](unified-pricing-m1a-acceptance.md).
- M0's original architecture is referenced as originating-chat material by M0.5; that chat is not available here. Its recorded decisions (separate data addon/provenance, exact currency, complete atomic generations, explicit reload, no local-history overwrite) are recoverable there. This report does not claim to have read an unavailable standalone M0 document.
- [Bridge-v1 normative README](../contracts/bridge/v1/README.md), schema/semantic validator and AMENDMENT-001; [M1b acceptance](workshop-bridge-m1b.md); [M1.5 report](workshop-bridge-m15.md), [raw capacity evidence](evidence/bridge-m15/capacity.json), [server evidence](evidence/bridge-m15/server.json).
- Actual [server exporter](../backend/market/bridge_api.py): `selected_observations`, `prepare_snapshot`, `record_batch`, `assemble_record`, `build_generation`, manifest/records routes; [desktop bridge cache](../desktop/core/src/bridge/cache.rs), [publisher](../desktop/core/src/bridge/export.rs), validators and schema.
- At the pinned addon HEAD: `TwichUI_Workshop/{Bridge,BridgeCodec,BridgeValidate,ServerMarket,Market,MarketFacts,History2,AdvisorData,Shopping,CraftPlanner,Sell}.lua`, `auction/{MarketData,ViewMarket}.lua`; `docs/workshop/market-bridge-m1b.md`, `market-bridge-m15.md`, `AGENTS.md`, `CLAUDE.md`, `docs/dev-rules.md`, `docs/testing-performance.md`.
- Read-only Forever UI source: `Interface/AddOns/Blizzard_SharedXMLBase/AddOnUtil.lua` checks `C_AddOns.IsAddOnLoaded` before loading. This supports one-shot LoD assumptions; it is not proof of runtime filesystem discovery or rereading.

Evidence labels used below: **reported production** = facts supplied in the task, not independently reproduced; **source-reviewed** = verified implementation; **existing synthetic measurement** = committed M1.5 offline results; **new synthetic sizing** = streaming script in this PR; **projection/proposal** = not acceptance evidence. No genuine production credentials or approved aggregate database connection were available in this workspace. No production access, secret inspection, payload export or live SQL was attempted. Four older genuine listing excerpts do not establish the current production shape or history.

## 2. Exact failure mechanism and what remains unknown

### Execution path (source-reviewed)

1. Authenticated device GET manifest invokes `build_generation` under the existing collection/retention advisory transaction lock. PostgreSQL gets a 10-second **per-statement** timeout, not a total build timeout. Busy lock returns 409.
2. Select a watermark, latest eligible current observation and daily winners over the pricing support window. Canonical selection uses complete scopes; provisional retains its documented legacy basis. Requested `history_days=2..60` limits delivered daily rows, **not** all reference support, pricing formulas or the identity union.
3. Load snapshot metadata; derive missing retained originals in batches of at most four snapshots per call, returning 202 for further preparation. Original listing derivation streams 1,000 rows at a time but accumulates one variant's rows and summary output. It has its own listing bound. Missing originals are 409, not this 413.
4. Build the distinct sorted union of `(item_id, variant_key)` across supporting snapshots (limit 150,001 to detect >150,000). Batch 100 identities across all supporting snapshots, parse retained JSON into a values dictionary and assemble one current summary plus each delivered date per identity.
5. For each record compute `raw = contract().canonical(r)`; check 64 KiB per record; add `len(raw)` to `record_bytes`. If the sum exceeds **67,108,864**, raise **413: Bridge build exceeds bounded working set; request a narrower history window**. Otherwise append the Python object to `records`.
6. Only after this loop construct the generation and repeatedly serialize it to compare `len(canonical(g))+512` to **33,554,432**. Remove distributions first, then oldest whole delivered dates uniformly until it fits or cannot retain the newest two observed dates. Reconcile observation refs, seal, validate, check manifest ≤64 KiB, and insert immutable generation/record rows.
7. Only then can paginated GET records deliver ≤100 records and ≤1 MiB per page using signed generation/account/credential/market-bound cursors.

Thus the supplied production guard failure means the sum of **pre-compaction canonical record lengths** exceeded 64 MiB. It excludes the manifest, separators, Python object overhead, ORM state, raw database rows and HTTP envelopes. For a 45,125-record export union the threshold is about **1,487.18 bytes per variant averaged over the full union**. Failure occurs at the first crossing, possibly before all variants are serialized: exact final bytes and failing position were not recorded here. It does not mean one page, manifest, network proxy or Lua file exceeded that size.

### Dataset composition and causal classification

| Quantity | Evidence / conclusion |
|---|---|
| Complete retained-history variants | **45,125 variants, reported production**; not necessarily today's current count, a count of distinct base items, or independently verified cardinality of the failed request's selected support union |
| Export outcome | **HTTP 413 and 64 MiB build guard, reported production**; source path above explains that specific message |
| Raw observations/listings, distinct items, current-only/history-only/intersection | Unknown production aggregates; cannot derive from union cardinality |
| Observed dates/density and exact algorithm/window used by failed request | Unknown here; 60 is route default, not evidence that it was requested |
| Serialized record p50/p95/max, distribution contribution, manifest size | Unknown production values; synthetic counterpart measured below |
| Snapshot deduplication | Source: observations can reuse content snapshots. Support snapshot IDs are deduplicated for querying; daily dates remain separate valid observations even when content repeats |
| Historical-only shape | Source: current absence plus dated history is retained. Exporter emits an absent row even on a complete date with no variant listing; sparse **listing presence** does not necessarily mean sparse **serialized rows** |

Classification: **serialization redundancy and inefficient materialization/late preflight are established**. Per-date long keys, algorithm IDs and arithmetic status repeat; prices/counts/nulls and explicit absent dates repeat. Market/observation metadata is already shared at header level. The exporter does not duplicate every raw listing into the bridge; it exports derived summaries. Its union query is distinct and `record_batch` keys by snapshot/identity, so there is no evidence of accidental duplicate identities within a generation. Legitimate daily repetition must not simply be deleted without preserving absence/coverage semantics.

An oversized *pre-compaction* complete generation is established by the reported bound. A necessarily oversized *final compacted* generation is **not** established without production sizes: the early guard prevents finding out. Raising the guard could expose an otherwise fitting compacted result but would neither enforce a real heap bound nor resolve client loading. There is no evidence that the counter arithmetic is wrong; the design's naming/order and absence of early feasibility accounting are the problem.

Distinct generations duplicate derived record JSON in disposable server cache rows (up to two per market/algorithm, eight globally, one hour) and desktop active/previous/staging slots. That is intentional recovery storage, not evidence that one build counted prior generations. Compaction repeatedly canonicalizes the entire object graph, allocates large temporary bytes, and can do many whole-generation passes. Sealing/validation/persistence serialize again. Query batching bounds one lookup but retains all output dictionaries; the 64 MiB encoded-byte guard cannot constrain their real Python heap.

### Earliest reliable preflight

Identity-count refusal is possible immediately after the pinned union query; byte refusal is not reliably determined by count alone. Before cold derivation, safe aggregate lower bounds from available derivations can reject clearly impossible work; missing derivations must be reported as unknown, not guessed.

The earliest exact byte preflight is **a streaming sizing pass over pinned, derived records before retaining the output list**. Count exact record bytes, section contributions, per-date bytes, manifest/ref overhead and per-record maxima, under the intended explicit scope/history policy. Use indexed per-snapshot size metadata later only if versioned to the derivation and equivalent to that calculation. Preserve all pricing support even if delivery range differs. A future streaming materializer should hash/write bounded staging rows, seal only when complete, and publish atomically; no arbitrary full Python list or repeated full serialization. This is a follow-up design, not implemented here.

For production verification later: read-only repeatable snapshot, statement/resource limits, return aggregates only. Count observations versus distinct snapshots, raw retained rows versus retained statistics, distinct item/variant union and current/history overlap using the **same selected observation IDs**; group daily listed/absent states; sum `octet_length(record_json)` by algorithm/revision/snapshot and collect bounded histograms. Existing derived JSON is not the assembled bridge record, so its bytes cannot substitute for exact export size. An approved streaming assembler sink can count final record/section bytes without returning bodies. Obtain `EXPLAIN` first; use `EXPLAIN ANALYZE` only on a replica/approved bounded query. Record query plans, CPU/RSS, lock duration, rows and dates. Do not run a huge failed export merely to measure it.

## 3. Eight different capacity constraints

| Layer | Present representation and constraint | Implication |
|---|---|---|
| Database storage | Raw listings, observations, deduplicated snapshots, retained stats, versioned derivations, export cache plus indexes/TOAST/WAL | Production allocation unknown; no direct conversion from 45,125 variants |
| Canonical generation | Sorted strict JSON with exact copper strings; ≤32 MiB, ≤150k records, ≤64 KiB record/header | Whole-generation validation bound, independent of pagination |
| Server build | Sum of pre-compaction record JSON ≤64 MiB; Python graph, batch dictionary, temporary encodings coexist | Encoded guard is not a heap/RSS bound |
| HTTP | Manifest envelope; records objects on ≤1 MiB pages/≤100 records, default 50 | Pages bound responses, not total materialization; not JSON strings inside JSON strings |
| Desktop | SQLite per-record canonical text plus manifest, slot keys/indexes, active/previous/staging, WAL; reconstruction into `serde_json::Value` | Current completed generations still ≤32 MiB; current cache is not an unlimited archive |
| Generated Lua | Fixed trusted assignment wrapping escaped JSON strings, no SavedVariables; hard max **130 MiB** | Fourfold worst-case escape expansion plus 2 MiB; compact ASCII is typically much smaller |
| Lua validation memory | Raw strings, index, transient parsed record, canonical re-encoding/hash scratch, old active/new candidate, garbage pending collection | Default GC and synchronous compiler can stall outside cooperative yields |
| Lua retained memory | Encoded records, observation/context tables, flat variant keys/item ranges, up to 24 decoded records | No permanent decoded full-market tree, but raw whole-generation data still remains resident |

Desktop `max_page_count=65536` is an additional disk bound (typically 256 MiB at 4 KiB pages; verify actual page size). It is not enough to promise several dense full-market generations, especially with WAL. Existing bridge cache stores generations, not append-only all-time history. Full desktop history retention requires a new normalized store and protocol. The legacy scalar synchronization cache cannot reconstruct daily history.

## 4. Actual consumer requirements

All entries are **source-reviewed**. “Offline” describes current local/cache reads; these modules do not fetch Market directly. Future selection is separate from changing their pricing sources.

| Consumer | Required fields / identity | History / freshness | Simultaneous, offline and load timing | External read-only role |
|---|---|---|---|---|
| Workshop pricing / worth | Local Prices/Market/Valuation: min, recent, references, distribution, quality; local item aggregate with variant refusal/flags | Local reference windows and existing age gates | Relevant items; local saved data offline, no bridge prerequisite | Current server data does not replace these calculations |
| Workshop Price history | Local History/History2 typed points/buckets/gaps, item aggregate | Local retained ranges; preserve legacy/aggregate basis | Selected item, offline; page-driven | Server history opens explicit separate source |
| AH Market external | Bridge record: exact item ID + upstream SHA/descriptor, current metrics/supply/status; observation metadata, daily points/gaps | 1..60 requested days; UI defaults/ranges; actual upstream freshness displayed independently | Browse index plus selected variant/history, not every decoded record; LoD on explicit source/page | Implemented research view, trading shortcuts disabled |
| AH Market local | Local catalogue, items/history/distributions; local identity | Existing local chart ranges up to 120 days / recent observations | Bounded page jobs, offline local data | Separate from external source |
| Item Advisor | MarketFacts, local quality/competition/supply, bag/vendor/disenchant facts; tracked item IDs | Existing confidence and age tests | Tracked/bag candidates, not complete server history; offline local state | Tracked set is a possible future selection seed only |
| Shopping | Materials quantities, vendor data, local Prices quote / Market cost | Latest eligible local cost, no full server history requirement | Required items and recipe dependencies; offline estimates | Future history research may help display; no source-policy change |
| CraftPlanner | Recipe/material graph, owned counts, vendors, local Quote/Cost | Current local cost; no full-history input | Planned outputs/material closure, offline data; planner open | Legitimate future seed; exact server identity must be resolved |
| Sell preparation | MarketFacts, local distribution/competition, quality, complete/age/mixed checks | Existing good/fair gates and freshness | Selected items; local data available independently | External research cannot satisfy sell gates |
| Other research/compare/tooltip views | Local Market API or selected external adapter as explicitly wired | Basis/coverage depends on source | Per item/query; no demonstrated all-market external requirement | Do not infer new consumers from a shared item ID |

No current consumer needs all exact server variants simultaneously. An all-market external browse *catalogue* is a future product choice; keep full search on desktop/server initially rather than forcing all histories into WoW. If owner requires a whole-market in-game index, separately budget a compact metadata-only index; do not assume that requirement today. Local item IDs/links cannot prove exact upstream variant mapping. A base-item selection must visibly resolve/expand server variants before export and count every expanded variant against the budget.

## 5. Quantitative comparison and reproduction

[New streaming sizing script](evidence/large-market/measure.py) and [output](evidence/large-market/sizing.json) use the existing M1.5 generator. Six shapes are streamed once through 45,125 records; checkpoint sizes cover 100/1k/5k/10k/25k/full union. Only integer size samples are retained, never an enormous generation. Exact byte equations are cross-checked against the actual generator at 100 records for all shapes. Synthetic records use short descriptors, 100-copper prices and simple distributions; these are **not production size estimates with confidence intervals**. Real variants/descriptors/prices/distributions may be larger.

Dense 14/60 means every eligible date serialized. Sparse sixty uses four observations across 60 days, **not** sixty observations with most listings absent. Historical-only uses two dates and current absence. Positional nested arrays in the evidence remove field names only, preserving all scalar values; they are an illustrative size lower-complexity comparison, not an implemented or validated v2 contract, decoder or publisher.

### New synthetic canonical sizes (MiB, measured bytes)

| Variants | One date | Two-gap | Dense 14 | Dense 60 | Sparse 60 | Historical-only |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 0.128 | 0.144 | 0.372 | 1.247 | 0.182 | 0.104 |
| 1000 | 1.262 | 1.422 | 3.656 | 12.229 | 1.794 | 1.023 |
| 5000 | 6.301 | 7.101 | 18.250 | 61.041 | 8.957 | 5.104 |
| 10000 | 12.600 | 14.201 | 36.493 | 122.057 | 17.911 | 10.207 |
| 25000 | 31.497 | 35.498 | 91.222 | 305.103 | 44.774 | 25.513 |
| 45125 | 56.851 | 64.073 | 164.650 | 550.689 | 80.814 | 46.049 |

Synthetic serialized record byte distribution across 45,125 records:

| Profile | Min | Median | p95 | Max | Positional records MiB (full union) |
|---|---:|---:|---:|---:|---:|
| one | 1320 | 1320 | 1320 | 1320 | 18.376 |
| two-gap | 1069 | 1514 | 1514 | 1514 | 20.722 |
| fourteen | 3406 | 3851 | 3851 | 3851 | 53.127 |
| sixty | 12376 | 12821 | 12821 | 12821 | 177.841 |
| sparse-sixty | 1458 | 1903 | 1903 | 1903 | 26.102 |
| historical-only | 1069 | 1069 | 1069 | 1069 | 15.579 |

The full two-gap case's **record sum**, not only its canonical total, exceeds 64 MiB (see JSON). Its manifest is only a few KiB; dense-sixty manifest is tens of KiB. Manifest overhead cannot explain hundreds of MiB. In the full dense-sixty fixture, encoded daily arrays contribute 503.11 MiB, current objects 19.53 MiB and distributions 17.91 MiB (value sections including their nested keys; not additive whole-record totals). Two-gap daily/current/distribution contributions are 16.73/19.31/17.91 MiB. This isolates history-row density as the main dense-case cost, while optional distributions matter substantially at shallow history. One additional daily row costs roughly 194–195 bytes in these fixtures. Even 45,125 tiny one-day records exceed 32 MiB; two-date historical-only records also exceed it. This supports rejecting “just shorten history” as a general solution, without claiming production's exact compacted size. Full dense-sixty positional records still occupy 178 MiB **before** their header, schema dictionary and any Lua source expansion. Removing keys alone does not solve whole-market residency.

### Existing M1.5 offline measurements, reused rather than rerun

| Variants / profile | Canonical / Lua MiB | Validation CPU median s | Worst step max ms | Retained / sampled peak heap MiB | Compile median / max ms |
|---|---:|---:|---:|---:|---:|
| 100 / two-gap | .14 / .20 | .32 | 3.54 | .19 / 1.03 | .47 / .47 |
| 1,000 / two-gap | 1.42 / 1.99 | 3.16 | 8.60 | 1.70 / 4.03 | 5.35 / 6.64 |
| 5,000 / two-gap | 7.10 / 9.92 | 16.10 | 9.00 | 8.85 / 18.29 | 49.29 / 49.58 |
| 10,000 / two-gap | 14.20 / 19.83 | 32.36 | 23.02 | 17.69 / 35.88 | 168.04 / 171.54 |
| 25,000 / one | 31.50 / 43.87 | 71.00 | 26.17 | 37.91 / 75.68 | 258.29 / 288.35 |
| 25,000 / historical-only | 25.51 / 34.88 | 59.61 | 20.66 | 31.93 / 63.98 | 983.36 / 1,020.75 |
| 1,000 / dense 14 | 3.66 / 5.19 | 8.10 | 26.48 | 3.96 / 8.64 | 35.99 / 56.11 |
| 1,000 / dense 60 | 12.23 / 17.45 | 27.24 | 12.65 | 12.64 / 26.28 | 112.14 / 120.90 |
| 1,000 / sparse 60 | 1.79 / 2.52 | 4.04 | 4.26 | 2.08 / 4.80 | 6.89 / 6.91 |

Compile includes reading/compiling the generated assignment in the offline harness; assignment execution is separately tiny (first samples 1–305 microseconds), and must not stand in for compilation. Selected history lookups in first-pair samples range about 9–62 microseconds; first record decoding about 77–1,005 microseconds depending on daily density. These are illustrative existing samples, not full latency distributions or real rendering. Explicit diagnostic GC maxima include 15.68 ms at 10k/two-gap and 34.73 ms at 25k/one. Diagnostic collection is not a proposed runtime strategy. Global Lua GC includes unrelated addon heaps; coroutine deadlines cannot preempt it or the compiler. Some M1.5 long tails occurred with GC stopped as well.

### Projections and costs that remain unmeasured

For full 45,125/two-gap **linear extrapolation only**, 64.07 MiB canonical implies roughly 89.5 MiB compact Lua (using 10k ratio), 146 s validation CPU, ~80 MiB retained and ~162 MiB sampled transient heap. Full dense-sixty using 1k ratios implies ~786 MiB Lua, ~1,230 s CPU, ~570 MiB retained/~1,184 MiB transient heap. These cannot pass existing contract/source limits and were **not loaded**. Compiler behavior, GC and hash/index work are nonlinear; no frame maximum can be extrapolated. Dense 100-variant size is 1.247 MiB and approximately 2.7 s validation CPU by the 1k ratio, not a measured latency for that workload. This is why a count cap alone, even 100, is insufficient.

Server cold source work is proportional to retained input listings for missing derivations, then approximately identities × selected snapshot lookups/daily rows for assembly. With 45,125 keys, 452 batch calls query up to ~61 supporting snapshots each; actual row density, index plans and cold derivations dominate. Existing synthetic SQLite ASGI probe: 1k/two dates, cold 1.571 s / 60 SQL statements; warm manifest 3.820–8.203 ms / 9 statements; 20 pages 174–193 ms / 80 statements, 1,526,815 wire bytes, process peak RSS 100.54 MiB. This is neither PostgreSQL nor production network acceptance. Linear scaling of cold CPU/RSS would ignore cache hits, indexes and Python graph inflation; no reliable production estimate is available.

Network is approximately canonical record bytes plus page envelopes and one manifest, without transport compression assumed. At the default 50 records, 45,125 variants need at least 903 pages; dense-sixty records hit the 1 MiB page cap near ~81 records even at a requested limit of 100. Header/cursor/record-length details lower that capacity. Compression would reduce transfer bytes, not decoded Lua/validation CPU. Ordinary selected sets need a few to tens of pages; a 100-record two-date set can fit one requested-100 page. Exact page counts must be measured through the actual route.

Desktop storage lower bound is the encoded retained evidence; SQLite row/index/page/WAL overhead increases it. Three full dense-sixty textual generation copies would be ~1.65 GiB before indexes/WAL, beyond the present bridge DB cap. Proposed normalized `(source,algorithm,variant,day,observation)` evidence avoids repeating unchanged whole generations. Never deduplicate different dates solely by price equality. Budget normalized history and staging/WAL separately on desktop; actual file growth and Windows SSD/AV behavior await L2. Existing desktop process peaks reached ~550 MiB at 10k/two-gap and ~1,155 MiB at 25k/one; RSS includes harness/fork footprint and extra first-pair repeat work. It does not measure SQLite file size or WoW heap.

Current incremental bridge update is a complete changed generation download, revalidation and export, even when most identities are unchanged; unchanged source signatures can reuse server cache. Proposed desktop changes can retain unchanged daily rows, append new observations and replace daily winners transactionally, including late historical corrections. Whole working-set replacement initially keeps recovery simple. Incremental WoW patching is unnecessary for 100–1,000 records and complicates identity/rollback; do not add it initially.

## 6. Architectural alternatives

| Option | Completeness, responsiveness, memory | Cost and failure recovery | Assessment |
|---|---|---|---|
| A Efficient complete generation | Preserves whole scope; compact keys/dictionaries/variant references reduce bytes. All data still compiled, validated and retained if loaded together | Streaming avoids Python copies; dictionaries/indexed history require new schema, hash vectors and consumer. One artifact has simple rollback | Useful server/desktop efficiency; insufficient evidence for full-market WoW. Dense positional lower-complexity example still ~178 MiB |
| B Multiple bounded data addons | All parts on disk; selectively loaded parts can bound initial cost. Eventually loading every part restores full heap/GC burden | Shared root + per-part hashes + publication protocol, part discovery/version compatibility, cross-part queries and many files. Cannot generally unload a loaded addon or reread its modified file | Second-line choice if a proven large in-game catalogue requires it; not simplest current requirement |
| C Bounded working set | Complete **within explicit identities/date scope**, not whole market. Good responsiveness if all byte/day/load gates pass | Selection API, persistence, scope manifests and unavailable UI; one addon is easy to recover. Server remains required for unselected history | Good first proof, but desktop disconnected use is limited without D |
| D Full desktop cache + bounded WoW | Whole retained history accessible to desktop; selected histories offline in WoW. Bounds game allocation independently from market growth | New complete-history desktop sync/store and selection projection, but reuses auth, transactional staging, pinned generation and fixed data-only output patterns | **Recommended**, best match to actual consumers and M2 |
| E Safe compact representation | Fixed arrays/dictionaries can reduce parse/hash/compile volume; still requires strict semantic validation and no new algorithm. Data loaded as nested tables can inflate heap | New format, independent validators/oracles, parser bounds, migration. No assumed Forever binary/compression library | Targeted fallback/enhancement within D after proof; avoid format redesign without a measured need |

### B: what a correct partition design would require

Stable part identity should derive from exact market/algorithm plus fixed prefix/range scheme and partition version, not record position or arbitrary changing file sizes. Skew must trigger explicit repartition/version changes, never silently reassign loaded identities. A root manifest pins part IDs, record ranges, counts, byte lengths, hashes, observation table, scope and generation. Each part is independently bounded and verifies against that root; global ordered ranges prove disjointness and requested coverage. Keep all dates for a variant in the same part to avoid cross-part history joins; a single dense variant must still fit a part budget. Large dictionaries cannot be mandatory full-market payloads.

A TOC listing every chunk file causes them all to execute when that addon loads: many files inside one addon are not independent LoD. Truly selective loading needs separate installed/known addons plus a small coordinator, no eager dependency on every part. At a conservative 100 identities per part, 45,125 variants require **452 data addons plus coordinator**, at least TOC+data per part; 1k per part requires 46 plus coordinator but sixty-day parts already fail proposed budgets. Disk partitioning does not bound later session-wide loading, and there is no supported general addon unload in the inspected integration.

Atomic multi-file publishing is not the current single-file atomic rename: stage immutable complete part directories, validate root/all parts, then use a last activation marker/root with hashes. An interrupted publish must resolve to all-old or all-new; unknown/mixed/missing parts refuse candidate and keep last validated set. Filesystem root atomicity alone cannot prove the client opened all files from one generation, so root/part checks remain mandatory. Preinstalled fixed slot addons might avoid changing discovery, but slot reuse while old slots are loaded is hazardous. Newly created addons may require client restart/discovery, not merely `/reload`; verify Forever. Do not claim `LoadAddOn` rereads already loaded parts or new files written during a session. Part-loading order, global GC and combat require real-client testing.

### E: safe representation boundaries

If needed, compare fixed positional records (schema names shared once), short enum dictionaries and per-variant daily tuples referencing the shared observation index. Encode price values as validated decimal strings with exact conversions only in supported range; do not put signed-64 money into unchecked Lua doubles. A trusted local exporter may produce quoted data bytes under a fixed grammar; the server must never supply executable Lua. Do not use `load`, `loadstring`, metatables, arbitrary object constructors, native binary plugins or an assumed compression library. Packed binary or compression shifts CPU and allocation into decompression and needs bounded independently tested decoding; not selected initially.

Incremental validation can process bounded records/tuples and hash fragments, then atomically activate only a fully verified scope. It cannot make file compilation or global GC preemptible. Avoid whole-generation decoded tables and whole-dictionary copies. A dictionary changes checksum canonicalization/versioning; strings with numeric-looking keys, nulls, duplicates, ordering and malformed indices need independent vectors. Retain exact upstream descriptor hashes and source/provenance; representation compression must be lossless, not daily averaging or pruning disguised as complete history.

## 7. Recommended design and user workflow

### Data flow (proposed, not implemented)

1. Server retains original observations and versioned exact derivations. A new pinned **desktop history** protocol can stream complete requested retained history without constructing one bridge-v1-sized generation. Dataset availability/retention and export scope are explicit.
2. Desktop transactionally caches complete market history in normalized storage, independently from the small game projection. It must first complete/validate its advertised coverage before saying “complete”; partial/cold/unsupported canonical dates remain explicit. The existing bridge-v1 cache cannot already do this for oversized history.
3. Desktop selector: search market, choose base item then resolve exact variants, select dates, preview exact expanded identities/coverage and byte budgets. Persist selections per origin/account/verified market/algorithm with named user sets. No fuzzy automatic crosswalk from local item strings.
4. Build a **scope-complete** immutable WoW projection from that cache. Validate it with independent contract implementations and the same quality rules. Publish one data-only LoD addon conservatively. Keep complete history desktop-side when a working set is changed; replacing a game cache does not delete archive data.
5. Workshop explicitly loads external research source and lazily decodes only selected records. A missing requested item shows why and can offer a player-mediated request. It never falls back to interpreting a local item aggregate as the server variant or changing local pricing inputs.

Users can request additional items **without manually exporting files** in the proposed desktop selection UI, followed by a future M2 managed publisher. That capability is not present now: current export is manual staging only. In-game selection communication has two honest paths: (a) initial player-mediated bounded request text copied from addon into companion, containing only version, market identity, exact variants and dates; (b) later explicit opt-in SavedVariables request queue written by the game on orderly logout/reload, read-only by companion. Never edit or overwrite live SavedVariables, execute their Lua, or assume live flush/OS clipboard/HTTP access. A strict narrow parser with size/depth/count bounds and account/profile mapping would be required for (b). Reading arbitrary SavedVariables with an executable Lua interpreter is unacceptable. Desktop-native selection is the simplest L1/L2 path and avoids the extra communication reload.

Advisor tracking is currently bounded at 200 base item IDs (`AdvisorData.TRACK_MAX`); those can expand to more exact upstream variants and do not imply that every tracked item fits. Tracked IDs, recipe/shopping requirements and explicitly watched/recent items can seed selection later, with player opt-in and visible expansion/budget preview. Track provenance and pinning priority, not every item ever viewed indefinitely. Explicit favorites and tracked sets have stronger justification than broad categories; categories need current server classification and exact expansion. Recency is bounded and evictable only with a declared changed scope. Selection preferences survive logout independently of the exported artifact. Clear or namespace across account/market changes; do not leak previous-account catalogues.

### Scope, coverage and missing-data semantics

A v2 scope must include canonical sorted requested exact identities (or a bounded independently verifiable selection manifest), request hash/version, resolved identities, market/issuer, algorithm/history basis, requested date range, actual observed dates, unavailable dates and reasons, completeness **within** that range, and whole-market completeness **separately false**. Bind the projection to a desktop source checkpoint and generation digest, receipt and policy version. Price reference support may include 60 dates even for a shorter delivered chart; retain support coverage/provenance separately. No silent shortening of the requested range.

Each selected identity must resolve to data or explicit status: `included`, `not_in_retained_union`, `identity_unresolved`, `source_history_unavailable`, etc. Define these in L1; these names are recommendations, not existing enums. `not_in_retained_union` is a producer's claim about pinned retained evidence, not proof the item never existed. A non-selected identity returns **outside_scope**, never current `not_observed`/zero. A selected observed-absent date is proven only by the original complete source observation. Other states: no source observation, incomplete observation, unsupported arithmetic, loading, invalid candidate, stale cached source, request pending. Keep “not downloaded” distinct from “downloaded evidence says absent.” Do not drop missing selected identities from the requested list and then claim scope completeness.

Whole-market source completeness (used to prove daily absence) and delivery scope completeness (selected subset) are different fields. A scope-complete subset cannot change source `house_auctions` into a claim that all house variants were delivered. Unknown enums/version/features fail closed. UI captions should say “Selected history: 83/100 identities available; through [date]”, with per-item reason and cache generation; do not label it “complete market.” This is future unavailable-state design, not freshness-chip implementation.

### Proposed operating and performance budgets

Use the intersection of bounds, not a variant-count-only limit:

| Gate | Initial acceptance proposal |
|---|---|
| Working-set default | 100 exact variants maximum; no silent item sampling |
| Candidate experiment ceiling | 1,000 exact variants, only if every other gate passes; no production activation implied |
| Bytes | ≤2 MiB canonical and ≤3 MiB generated Lua; keep existing 32/130 MiB hard refusals unchanged |
| Daily coverage | Full requested supported range up to 60 days, ≤60 rows per variant; dense sets must reduce variant selection rather than silently prune dates |
| Validation | Nominal ~2 ms slice, p99 ≤3 ms, max ≤10 ms under representative global GC/load; not a demonstrated safe bound |
| Load | Synchronous compile+assignment ≤10 ms on acceptance hardware; not established by Cloud |
| Memory | Incremental steady heap ≤5 MiB; old+candidate transient ≤16 MiB; total client pressure also measured |
| Readiness | Owner to approve ≤5 s target from explicit open to usable history, with cancellable progress and prior data usable |

Even 100 dense-sixty variants project ~2.7 s CPU and may exceed readiness or compilation gates on a real client. Start with 100 as an experiment, **not** a guarantee; reduce further or prove E before approval. M1.5's 1k/two-gap median 1,574 callbacks would take ~26 s at one callback/frame at 60 Hz or ~52 s at 30 Hz; actual `C_Timer.After(0)` cadence is unmeasured. Do not trade long readiness for apparently small slices without testing it.

When a working set exceeds any budget, hold the old validated projection and show the limiting bytes/identities/dates; offer explicit deselection, separate named sets, shorter user-selected history, or desktop viewing. Never split silently, silently truncate, or infer absence outside the accepted scope. A named-set switch requiring disk replacement still needs the supported reload/session boundary; it is not an instant in-game cache swap.

### Updates, offline operation and reload frequency

While WoW runs, keep the loaded generation immutable. Server/desktop may synchronize independently; do not rewrite and expect the loaded addon to refresh. Queue the newest complete valid candidate, coalesce repeated updates and let the player apply at a chosen safe session boundary. For an installed unchanged addon, expect **one player-chosen reload** to use a newly published generation; test discovery/TOC/file caching in Forever before promising this. New addon discovery may need restart. Do not rely on loading an as-yet-unloaded addon from newly changed disk content during the session.

Ordinary-player target: initial managed setup plus zero forced reloads; at most one optional coalesced refresh per play session, or next login. An occasional newly requested item may need one additional refresh when desired. Automatic SavedVariables-driven requests could require logout/reload to flush plus another apply boundary; this is why desktop selection is recommended first. Do not promise a fixed count without that UX choice. No collection-frequency reload prompts.

Desktop offline: browse its completed retained cache and select already-cached items. WoW offline: only its last published/validated scope; outside-scope history cannot be conjured until a subsequent projection. Age advances even when files do not. Display actual upstream/observation times, never reset freshness from a new desktop receipt or unchanged server check. Failed network/auth/download/schema/hash/disk/publish leaves the last completed desktop checkpoint and prior game artifact usable. Workshop preserves old active data during candidate validation/failure, as today. Cross-session recovery also needs an explicit publisher restore of the previous artifact: `Previous.lua` is **not** loaded by the TOC and does not automatically rescue a corrupt artifact after restart.

## 8. Contract and compatibility requirements

Use a **new bridge contract 2 / schema 1 / transport 2 boundary** for scoped game projections and a separately versioned complete-history desktop API. These version numbers are a recommendation to reserve during L1, not files changed here. Do not overload schema 2 of bridge-v1, which already has a different defined meaning. Representation E, if adopted, needs its own explicit required feature/encoding version. Pricing algorithm IDs, history bases and quality-policy 1 remain unchanged.

| Component | Required follow-up | Compatibility/recovery |
|---|---|---|
| Server API | Separate pinned history/checkpoint routes and explicit selection resolution/preflight; stream bounded pages; versioned derivations reused | Keep v1 routes/limits/auth meanings. Do not negotiate a scoped subset into old whole-market manifest |
| Authentication/pinning | Existing device identity/renewal; bind cursor to account, credential, issuer/market, algorithm, checkpoint, selection hash, range, format and expiry | Reject cross-scope/cross-account replay; new data arriving never mixes checkpoint pages; expiry restarts staging only |
| Manifest | Explicit requested/resolved scopes, within-scope vs whole-market coverage, observed dates/support, per-identity unavailable status, size/hash, source checkpoint and receipt | Full digest covers selection and coverage; no trust from unsealed selector text |
| SQLite | New namespaced normalized history store, transactional checkpoints/staging and persistent selections; explicit disk/WAL/retention budget | Preserve legacy scalar and bridge-v1 DBs; one-way migration cannot destroy rollback. No full `Value` reconstruction for complete archive |
| Publisher | Preserve staging, fixed grammar, owner/path/ACL/reparse checks, flush/sync/readback and previous distinct artifact | Versioned staging/addon namespace or explicit dual-reader coordination; never overwrite v1 with v2 while old consumer is active |
| TwichUI_MarketData | New strictly versioned wrapper/header carrying scoped strings; fixed trusted TOC, no SavedVariables | Prefer separate v2 addon/global namespace during transition; addon loader must select supported version explicitly, avoid loading both eagerly |
| Workshop validator | New scope/schema/integrity/ref checks; exact values unchanged; bounded validation/index; all-or-nothing activation | Unknown version/feature refused, old source remains available; mirror independent fixtures with exact upstream pins |
| History adapter | Scope-aware statuses, requested dates vs observed dates, exact variants and provenance; selected records lazily decoded | Existing local data and external v1 adapter preserved; no default source/advice changes |
| Source freshness | Distinguish content age, observed time, desktop sync, projection publication and pending newer checkpoint | Old cached data can remain useful with honest age; no quality promotion from delivery |
| M2 scheduler | Separate full-history sync cadence and bounded projection cadence; coalesce changes, selection persistence, explicit destination/profile selection | No automatic reload; interruption/cancellation/publish failure preserves completed checkpoints/artifacts |

Migration: upgraded desktop first gains new store/sync and keeps v1 behavior. New Workshop reader can support both versions in isolated namespaces. Before publishing v2, require an explicit compatible consumer choice/capability configuration; desktop cannot assume it can query game runtime. Old desktop clients continue v1 and may refuse oversized full history; they do not receive silent subsets. Old addon consumers reject v2 rather than misrepresent its scope. Stage all new checkpoint/projection files fully before switching; compare market/algorithm/scope/version/generation at every boundary. Mixed old/new manifests or records are rejected. Rollback selects the last complete supported artifact/store checkpoint without down-migrating local SavedVariables or deleting original history; previous-v2 remains an option if v1 cannot fit the same scope. Do not promise downgrade inspection by older narrow Lua inspectors.

## 9. Ranked recommendation and explicit tradeoffs

Rank for this product: **D**, **C**, **E within D**, **B**, **A as whole-market WoW**. A's streaming/materialization improvements are still desirable infrastructure work. E is an encoding technique rather than a standalone delivery policy. C is simpler than D but fails full disconnected desktop research if the companion retains only selected histories.

| Criterion | A whole | B partitions | C working set | D hybrid | E encoding alone |
|---|---|---|---|---|---|
| Correctness/completeness | Strong if it fits | Strong with global root proof | Explicit subset only | Full desktop + explicit subset | Strong if lossless/validated |
| Client responsiveness | Poor at measured scale | Conditional on few loaded parts | Best with gates | Best with gates | Improved bytes, unproven timing |
| Client memory | Whole dataset | Grows with loaded parts | Bounded | Bounded | Smaller bytes, possible table inflation |
| Recovery | Simple artifact, expensive rebuild | Most complex | Simple scoped artifact | Transactional archive + simple projection | New-format compatibility burden |
| Implementation complexity | Moderate format, difficult timing | High | Moderate | Moderate-high, justified offline value | Moderate-high new decoder |
| Maintainability | Simple concept, rising cost | Many addons/slots/versions | Clear scope policy | Two clear storage roles | Strict representation discipline |
| UX | Full browse but long waits | Hidden stalls/discovery complexity | Selections and refresh boundary | Desktop full browse + relevant in-game data | Mostly invisible |
| Existing bridge reuse | Format may change | Major loader/publisher change | Versioned extension | Reuses patterns, new archive protocol | Major validator/fixture changes |
| M2 suitability | Expensive automatic churn | Publication coordination burden | Good | Best separation of sync and publish | Supplemental only |
| Beyond 45,125 | Client scaling problem remains | Part/file count grows | Scope stays bounded | Archive scales independently | Finite constant-factor improvement |

Tradeoff accepted: unselected history is not instantly available in WoW. This costs a desktop selection and refresh boundary, but avoids forcing large startup/first-open/GC costs on every user. If the owner requires instant arbitrary in-game whole-market history while disconnected, the recommendation must be revisited; that requirement is not demonstrated by current consumers and B/E would need actual client proof. Do not optimize for hypothetical millions by adding a distributed storage system now; normalized PostgreSQL/SQLite and bounded projections are enough to prove the real requirement.

## 10. Proposed follow-up milestones

Every stage needs separate implementation authorization. No mandatory repeated multi-hour suite at research checkpoints. Run focused affected tests while developing; perform comprehensive verification once at frozen shared-runtime milestones according to repository policy.

| Stage / repositories | Main work and dependencies | Tests / performance gate | Production impact and rollback |
|---|---|---|---|
| **L1 Contract and bounded-scope proof** — both repos, contracts/fixtures and isolated harnesses | Approve selector/coverage semantics, v2 boundaries, retained-history meaning; demonstrate full selected daily history, absent/outside-scope cases; compare existing strings to positional format only if needed | Independent Python/Rust/Lua vectors; exact identity/copper/provenance; unknown versions, duplicates, mixed scopes, missing records, over-budget refusal. Measure 100 dense/sparse and small 1k probe only; no capacity matrix repeat | None. Keep proposals separate; discard candidate proof without touching v1 |
| **L2 Server and desktop** — Market | New streaming pinned history API and size/preflight, normalized SQLite history and selections, selector preview, bounded projector/publisher. Depends on L1 | Disposable PostgreSQL plans/row counts, late corrections, auth renewal/account changes, interruption/resume, SQLITE_FULL/WAL budget, independent hashes, Windows ACL/reparse/AV/replace/restart. Cold/warm CPU/RSS/query cost and real file size at 45,125-like synthetic composition | Implementation initially undeployed. Later additive API/store deployment needs authorization/backup/restore acceptance; rollback to old routes/app and preserved DB/store, no source deletion |
| **L3 Workshop consumer** — TwichUI + pinned Market fixtures | Version-aware LoD reader/adapter, scope/unavailable presentation, diagnostics; preserve local scans and all advice gates. Depends on L1 and L2 fixture artifacts | Focused reader/adversarial/source-isolation/history tests, actual UI handler tests; no startup data load. Nominal slice/heap/load/readiness gates above measured offline with old+new generation. Comprehensive suite once when shared reader freezes | No game installation in implementation task unless separately authorized. Roll back consumer and matching artifact together; preserve local SavedVariables |
| **L4 Real-client acceptance** — both + owner Windows/Forever disposable profile | Authorized genuine retained-history aggregates and selected exports; actual installed companion and game, approved hardware/perf instrumentation | Verify exact selected dates/variants/copper vs retained evidence; measured compile/load, timer cadence, first-open/readiness, p99/max slices, frame tails, global GC, old+new heap, load order/combat, no local history writes, corrupt/unknown/mixed/recovery, disk pressure/power-loss. Reduce budget or return to E if unmet | Explicit limited acceptance only; do not activate defaults. Restore prior artifact/app if any gate fails |
| **M2 Automatic delivery/freshness** — Market desktop + TwichUI | Only after L4: opt-in destination/profile, independent sync/projection scheduling, coalesced publication, request workflow, staleness UX/player-controlled apply | Scheduler/offline/auth/cancel tests; no duplicate refreshes, account leakage, live SV writes, forced reloads or trading. Actual ordinary-session reload/usability evidence | Separately approved rollout; disable automatic publisher and retain manual last-good path. Freshness chips are separate authorized work |

L1 can establish server-selected bounded proof before the complete desktop archive is implemented, but cannot claim D's full-history offline capability. L2 should not depend on a compact format redesign unless L1 exposes a material blocker. Server build preflight/streaming is part of L2, not an excuse to lift v1 limits now.

## 11. Owner decisions and real-client unknowns

Decisions required before implementation:

1. Approve D with honest scope completeness and accept that arbitrary unselected history requires a future projection; confirm no requirement for instant all-market offline history inside WoW.
2. Define “full history” retention for desktop: at minimum all retained daily evidence available from server, including older than 60 days if the product requires it. Current bridge only delivers at most 60 dates. Long-term archive protocol/retention cannot be inferred from v1. Do not discard unsupported legacy provenance or invent canonical history where originals are unavailable.
3. Approve desktop-first exact selection, opt-in tracked/crafting seeds later, and whether player-mediated request text or later read-only SavedVariables requests are worth the extra UX/validation complexity.
4. Agree initial 100-variant/byte gates and readiness threshold; these are acceptance proposals, not performance promises. Authorize a disposable Windows/Forever test profile and representative low-end hardware.
5. Confirm version rollout/namespace strategy, disk budget/retention, and the next separately scoped milestone. Architecture approval is not production deployment, policy activation or M2 permission.

Must await Forever: actual timer callback cadence, compile/load throughput and addon discovery, inability to reread loaded files in relevant client paths, startup versus first-source-open cost, combat/load order behavior, global GC/frame tails under other addons, transient replacement memory, and ordinary refresh tolerance. Offline Linux Lua and simulator timing cannot demonstrate a safe real-client bound. Until L4 passes, **no safe production operating bound has been established**.

## 12. Reproduction and verification record

This milestone ran the new streaming synthetic sizing script twice; outputs matched byte-for-byte. Its six size-equation checks and additional output-shape/size invariants passed. Python compilation, report link checks and `git diff --check` passed. Other work read existing evidence/source. It did not rerun M1.5's five-pair matrix, game simulator, full test suite, backend services or production queries. Script output includes all sizes, record percentiles and per-field value contributions. No giant payload or generated addon is committed.

From the Market research checkout:

```sh
python3 docs/evidence/large-market/measure.py > /tmp/large-market-sizing.json
cmp docs/evidence/large-market/sizing.json /tmp/large-market-sizing.json
python3 -m py_compile docs/evidence/large-market/measure.py
git diff --check
```

The script imports the pinned existing `scripts/bridge_workloads.py`; prices and dates remain synthetic. It cross-checks its canonical size equation against `generate(100, profile)` for six profiles, which asserts the actual encoded length. No synthetic record is passed off as genuine history; positional bytes are a model without a new schema or runtime implementation. Existing capacity samples can be inspected in `docs/evidence/bridge-m15/capacity.json` (`cases[].runs.candidate[].lua`); medians/maxima in this report use the five candidate samples, not a new experiment. Existing `bridge_capacity.py` is the reproduction tool for those historical measurements; do not run its entire matrix by default.

Evidence limits: production union/413/guard are owner-reported; cause/order/count semantics are source-reviewed; current production composition and final compacted bytes remain unmeasured; new bytes are synthetic sizing; old CPU/heap/compile figures are existing synthetic offline measurements; recommendations/new APIs/selection/migration remain not implemented/not tested. No real-client, production-history or Windows acceptance is claimed.
