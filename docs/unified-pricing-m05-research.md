# TwichUI pricing comparison and evidence

M0.5 compares existing Market and Workshop calculations against equivalent retained input rows and explicitly synthetic stress cases. The proposed policy is [twichui-pricing-v1](unified-pricing-m05.md). It is not selected by any production path.

## Available real observations

A bounded read-only request to `https://market.twich.gg/api/v1/markets` failed at the Cloud network proxy with `Tunnel connection failed: 403 Forbidden`. This was not an authenticated application response and does not establish a Market authorization failure. The owner confirmed there is no alternate export or endpoint for this task. No credentials were requested, read or written; no collector/provider request, production SQL, migration or deployment occurred.

The authorized repository contains `backend/tests/fixtures/live-us-2026-11-14.json`, pinned at Market commit `7202e07a62f1770642b50afe5a3ec671d9b488cf`. It records two genuine auction excerpts and two genuine commodity excerpts from direct authenticated Blizzard captures. The shared fixtures preserve their full item descriptors, auction IDs, retrieval times, original full-response counts and upstream hashes, plus the source-file hash. None is a new live capture by this research.

| Item | Exact descriptor | Quantity | Original ask | Capture UTC | All-listing mean on excerpt | Workshop band on excerpt |
|---|---|---:|---:|---|---:|---:|
| 6537 | id 6537, bonus_lists [12718] | 1 | stack 4099c | Nov 14 02:41:15.710982 | 4099c | 4099c |
| 14917 | id 14917, bonus_lists [12725] | 1 | stack 32500c | Nov 14 02:41:15.710982 | 32500c | 32500c |
| 252437 | id 252437 | 10 | unit 948c | Nov 14 02:41:17.605752 | 948c | 948c |
| 1081 | id 1081 | 18 | unit 50c | Nov 14 02:41:17.605752 | 50c | 50c |

All four rows belong to US house 110, transport ruleset URL 1, namespace `dynamic-forever-us`. Do not relabel them as the later house-114 Normal Horde feed. The exact player-facing ruleset is deliberately null in these fixtures. Each item appears only once in the excerpt, so these equal numbers are arithmetic sanity checks, not proof that the full variant's market statistics agree. Commodity excerpts have different quantities, but there is no genuine retained multi-price depth for one commodity here.

`docs/evidence/2026-11-14-live-collection.json` reports item 25 with supply 7, Recent Price 2805c and one daily history point. It does not contain the seven original price rows; reconstructing a Workshop band from that mean would fabricate information. `2026-11-14-refresh-transition.json` records repeated 304 observations and two distinct snapshots on the same UTC day, not two days of raw item history. Those receipts support timestamp/content distinctions only.

Consequently, high-volume materials, expensive/outlier depth, sparse/missing dates and same-item alternative variants are exercised synthetically below. Genuine category-wide conclusions, full-distribution stability and 14/60-day historical validation are unavailable. Approximately two days retained in a service would still be insufficient to validate the intended 14/60-day horizons; this accessible excerpt is narrower still.

## Snapshot comparisons

All following rows are synthetic; `price x units` notation describes commodity-style tiers. The unequal-stack case retains actual stack totals. Each method sees identical input, with ceiling unit tiers for Workshop/median/trimmed calculations; Market's all-listing mean uses original totals. Numbers are copper, rounded half up where a mean is used. Trimmed mean keeps the middle 80% of quantity, splitting boundary units.

| Scenario | Input | Market mean | Workshop band | Weighted lower median | 10%-90% trimmed mean |
|---|---|---:|---:|---:|---:|
| Healthy material | 100x20, 110x20, 120x20 | 110 | 100 | 110 | 110 |
| One low outlier | 1x1, 5000x40, 5200x10 | 4941 | 5000 | 5000 | 5024 |
| One high outlier | 5000x10, 9990000x1 | 912727 | 5000 | 5000 | 5000 |
| Large quantity difference | 4500x5, 6000x200 | 5963 | 5878 | 6000 | 6000 |
| Thin cheap third | 1x1, 9000x1, 9500x1 | 6167 | 1 | 9000 | 6521 |
| Exactly 25% cheap | 2000x7, 5000x21 | 4250 | 5000 | 5000 | 4438 |
| Above 25% cheap | 2000x8, 5000x20 | 4143 | 2143 | 5000 | 4304 |
| Cheap cluster just over half-anchor | 2510x12, 5000x38 | 4402 | 3008 | 5000 | 4564 |
| Cheap cluster just under half-anchor | 2490x12, 5000x38 | 4398 | 5000 | 5000 | 4561 |
| Large expensive wall | 5000x20, 9000x1000 | 8922 | 8739 | 9000 | 9000 |
| Unequal stacks | total 201/2 units; total 1600/8 | 180 | 134 | 200 | 188 |

The exact lower-band mechanism limits sensitivity to a small high-price tail and describes lower asking depth. It is not robust to every adversary: strict-quarter selection creates discontinuities, and cheap supply just above half the anchor remains eligible. The thin-third case proves the output can be 1c with an otherwise expensive book. Its three listings and farbelow/spread facts must prevent supported posting advice.

The all-listing mean is transparent and retains economic total/quantity information, but a high tail can dominate it. Keep it as a named descriptive statistic, not the common representative price. The lower weighted median resists either tail below half the volume and is a strong alternative; it often selects the dominant higher wall rather than a lower asking band. The trimmed mean damps tails without a half-anchor discontinuity, but still gives 6521c in the thin-third case and can average distinct clusters into a price with little actual depth. Neither alternative makes thin or mixed markets safe to sell into.

The recommendation keeps the existing lower-band role and its approved parameters to avoid an unmeasured wholesale semantic change while introducing common exact arithmetic and stronger provenance. It is a conservative policy choice, not a finding that band means empirically outperform medians on live markets. The median remains the preferred temporal aggregator because one extreme daily reference should not dominate a historical value. A representative full-snapshot shadow comparison remains a gate before enabling the policy.

## Temporal comparisons

The eight calendars are synthetic, with one-tier observations so snapshot algorithms agree and only time/coverage rules differ. No synthetic point is attributed to Blizzard.

| Scenario | Market MV / HV | Workshop MV / HV | Proposed MV / HV | Meaning |
|---|---|---|---|---|
| Two dates: 100, 120 | 110 / 110 | 100 / unknown | 100 / unknown | Two equal recency weights choose lower median; three-day Historical minimum remains |
| Ages 7,6,3,2,0: 100,150,200,400,500 | 270 / 270 | 400 / 200 | 400 / 200 | Recency weights 1,2,2,4,4; historical days have equal weight |
| Missing middle day: 100, gap, 300 | 200 / 200 | 100 / unknown | 100 / unknown | Gap is not a third observation |
| Exact rolling-age-14 boundary: 100 then current 200 | 150 / 150 | 200 / unknown | 200 / unknown | Calendar ages differ from rolling seconds |
| Age-60 value plus two recent dates | 250 / 200 | 200 / unknown | 200 / unknown | Inclusive Market support spans a boundary date; canonical has only two eligible dates |
| Three dates: 10000,100,200 | 3433 / 3433 | 200 / 200 | 200 / 200 | A daily high outlier affects the arithmetic mean |
| Age-3 price 100, today's 500 then complete absence | 100 / 100 | 500 / unknown | 100 / unknown | Existing Workshop keeps last listed close; proposed history selects absent scope close |
| Today complete 100 then incomplete 500 | 500 / 500 | 500 / unknown | 100 / unknown | Canonical history keeps complete evidence; Market result is a formula counterfactual for an input it does not expose |

Temporal values were checked by an independent Fraction-based research calculation against authored expectations and audited source semantics. The DB-backed Market `values` query and full Workshop history API were not executed by this checker. The snapshot source comparisons described below do execute existing pure functions.

## Precision and quantity findings

- A 301c stack of three yields exact unit 100 1/3: Market minimum/recent round to 100c; Workshop ceil tier and band are 101c. A 1c stack of three produces Market's rounded descriptive zero versus Workshop's 1c tier. Preserve original totals and declare the shared metric's rounding.
- `9007199254740993` and signed-64 maximum survive Market's exact raw arithmetic. They must remain strings and are outside the common unit-price domain; Lua may not round or clamp them.
- Bid-only units count in supply, not price weights or quantiles. One fixture has total supply 10 and priced quantity 3.
- Buying three commodities from two at 100c and three at 200c costs 400c for the observed depth. A ten-unit whole auction at total 1000c does not establish a 300c three-unit purchase; a whole purchase spends 1000c and obtains ten.
- Two descriptors differing only in bonus lists have different hashes and must never pool. Local base-item scans cannot prove either exact variant price.

## Verification evidence

Unit-tested research scope: 61 authored cases (23 snapshot, eight temporal, 30 boundary), closed-schema and checksum checks. Existing Market pure `summarize`/`rounded` execute against all 23 snapshot cases. Existing Workshop Lua 5.1 `Dist.Stats` and `Valuation.WeightedMedian` agree on the 19 supported, priced cases, including anchor and quartiles. Four cases intentionally have no supported priced distribution: two exceed the shared range, one is bid-only, one empty.

The rational oracle compares independently authored constants; it is not a new production engine. See `contracts/pricing/v1/research-results.json` for source/file hashes, matrix and evidence boundaries. Rust/serde conformance is specified but not executed; Rust is not installed in this research environment. No simulator, screenshot or real-client pricing verification is claimed. Production regression suites were not run because no product code, schema or runtime behavior changed.

## Later real-data acceptance

Use a separately authorized read-only export with full per-variant listings and day-close provenance, excluding credentials and player-private fields. Stratify by priced units, priced listing count, price, spread, low/high outliers, variant multiplicity and observed-day coverage; retain deterministic selection criteria and full-source hashes. For the same rows calculate mean, band, median and trimmed candidates, then replay daily closes under their own algorithm IDs.

Report paired differences, rank stability, sensitivity to removing a single listing/large stack, missing-day/absence handling, distinct-content dates and advice refusal reasons. Perturbed rows are labeled counterfactual, never historical captures. Two-day results remain two-day results; retain the full 14/60-day longitudinal gate rather than declaring horizon validation from a replay of synthetic calendars.
