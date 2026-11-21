# TwichUI unified pricing specification

Status: M0.5 proposal, awaiting owner approval. Reserve `twichui-pricing-v1` for the definitions below. Retain `asking-v1-provisional` and Workshop's existing formats unchanged until a separately authorized implementation and release. The recommendation is supported by exact synthetic comparisons and narrow historical excerpts, not a full-horizon live validation.

Use an outlier-filtered lower-band mean for Recent Price, a recency-weighted lower median for Market Value, and an unweighted lower median of exact daily Recent Prices for Historical Value. Keep the all-listing mean as a separately named statistic. Competition, posting guidance, purchase costs and sale proceeds answer different questions and retain separate roles.

Read alongside [research](unified-pricing-m05-research.md), [migration](unified-pricing-m05-migration.md) and [shared fixtures](../contracts/pricing/v1/README.md).

## Audited sources and M0 boundary

TwichUI `feature/workshop` is pinned at `8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c`. Market's integrated server/companion authority is `integration/companion-v2-metadata-recovery` at `7202e07a62f1770642b50afe5a3ec671d9b488cf`. The separately reviewed polish branch is `feature/everyday-market-polish` at `09b3c1d84c976da0251e786c2931c4022f9f4e8b`. Pricing, ingestion, distribution, sync and desktop cache/protocol/synchronizer blobs match between those Market branches. Neither main branch is the research baseline. All proposals are on isolated `research/m05-unified-pricing` branches.

Engineering instructions, current implementation/progress notes, Workshop foundation/testing rules and the completed M0 architecture in the originating chat were reviewed. M0 selected a dedicated versioned data-only addon, separate imported provenance, exact currency, atomic complete generations and explicit reload. Its key findings remain: desktop v1 holds scalar references, not daily history/distributions; local and server identities differ; Workshop must work without the companion; server records never overwrite local scans. M0.5 refines metric semantics and the future bridge contract only. No bridge is implemented.

Source locators: [Market pricing](https://github.com/Twich-Team/TwichUI-Market/blob/7202e07a62f1770642b50afe5a3ec671d9b488cf/backend/market/pricing.py), [Market ingestion](https://github.com/Twich-Team/TwichUI-Market/blob/7202e07a62f1770642b50afe5a3ec671d9b488cf/backend/market/ingest.py), [Market distribution](https://github.com/Twich-Team/TwichUI-Market/blob/7202e07a62f1770642b50afe5a3ec671d9b488cf/backend/market/distribution.py), [Workshop distribution](https://github.com/Twich-Team/TwichUI/blob/8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c/TwichUI_Workshop/Dist.lua), [Workshop valuation](https://github.com/Twich-Team/TwichUI/blob/8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c/TwichUI_Workshop/Valuation.lua), [Workshop prices](https://github.com/Twich-Team/TwichUI/blob/8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c/TwichUI_Workshop/Prices.lua), [Sell safeguards](https://github.com/Twich-Team/TwichUI/blob/8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c/TwichUI_Workshop/Sell.lua) and [Advisor](https://github.com/Twich-Team/TwichUI/blob/8c1ffad9fb08e91d95c6d921e9e3b4543fe05b0c/TwichUI_Workshop/Advisor.lua).

## Existing formulas

Let an auction have stack buyout B and quantity q; a commodity has integer unit price u. Bid-only rows have supply but no buyout-price input.

| Metric | Market `asking-v1-provisional` | Workshop at the pinned revision |
|---|---|---|
| Minimum | min(B/q or u), rounded half up once | Minimum exact B/q is selected, then ceil(B/q), at least 1 |
| Recent Price | round-half-up(sum(B or u*q)/sum(priced q)) | Ceil-unit tiers; strict-quarter anchor, half-anchor lower filter, cheapest 30% of eligible quantity, fractional band edge, half-up mean |
| Market Value | Arithmetic mean of last daily Recent Prices within exact rolling 14*86400 seconds, inclusive | Lower weighted median of daily closing Recent Prices at UTC ages 0..13, weights 4 at ages 0..2, 2 at 3..6, 1 at 7..13; one day is allowed and labeled limited |
| Historical Value | Arithmetic mean within exact rolling 60*86400 seconds, inclusive; one priced day is enough | Lower weighted median over UTC ages 0..59; at least three priced days; older weekly means vote with their known Recent-day counts, explicitly aggregate/approximate |
| Distribution | Linear bands over exact per-unit prices, rounded extrema, 5..32 bands; bid-only totals separate | Quantity-weighted quartiles, anchor, band mean, maximum, near quantity; six cheapest tiers with quantity/listings/largest stack and a tail |
| Competition | Current raw listing asks; Deal Finder discount against provisional reference | Cheapest retained tier at or above half the anchor; bait quantities shown separately; may be beyond the six kept tiers |
| Purchase | Raw listing prices/supply are available; no equivalent shared Workshop Cost contract | Cost walks retained tiers: exact/range/estimate/few/none. Whole-stack uncertainty and tail bounds remain explicit. Legacy Quote is minimum-based and weaker |
| Quality | Opportunity confidence from verified feed, freshness, genuine provenance and priced-day coverage; moderate from 3 days, strong from 7 | Good/fair/limited/none, with independent completeness, age, listing count, distribution, history and mixed-variant reasons |

Market `values` first restricts observations to its rolling 60-day support window and chooses the last observation by retrieval time/ID per UTC day. Its extended history path separately primes daily references with 60 supporting days. Preserve both query paths in an audit; they do not establish desktop history availability. The inclusive rolling windows can span 15/61 UTC dates. Compact `coverage_days` and `market_coverage_days` count priced dates for the variant, not total economy completeness.

Market's [opportunity evidence policy](https://github.com/Twich-Team/TwichUI-Market/blob/7202e07a62f1770642b50afe5a3ec671d9b488cf/backend/market/opportunities.py) returns limited unless freshness is current, `market.verified` is true and contributing provenance is genuine; otherwise it returns strong at seven priced days, moderate at three, limited below three. Feed verification is distinct from the player-facing identity registry. Market source freshness is current only with a valid upstream modification time whose age is at most max(3600, 2*collection_interval_seconds); unknown/stale timestamps cannot qualify stronger opportunity confidence. Ingestion permits retrieval clock skew up to five minutes; the proposed contract instead binds accepted observations to its declared query instant.

Workshop History2 daily points are the last qualifying LISTED observations. A later whole scan in which the item is absent does not erase that daily listed close. Whole-read partial-info points can be retained with partial flags. Legacy minimum history remains frozen and does not supply Recent Prices. These details matter for migration: canonical day-close selection below is stricter and cannot be retroactively inferred from every old item string.

Market uses Decimal/SQL numeric calculations and signed-64 raw copper, with strings at JSON boundaries. Workshop accepts unit/stack copper through 99,999,999,999, counts with subsystem bounds, and Lua doubles. Its Dist flags arithmetic beyond exact 2^53 intermediates; Cost can label approximate large totals. Canonical results must not silently inherit that approximation.

Market variants hash the entire canonical upstream item descriptor. Workshop's local scan aggregates item IDs and refuses explicit variant requests; equipment may be marked mixed. Native item keys do not prove an exact mapping of every upstream attribute. Source histories, scopes and identities must not be blended merely because item IDs match.

## Canonical inputs and identity

One calculation belongs to one issuer, Forever region, verified player ruleset, house, source kind and exact variant. Preserve transport ruleset ID separately from player ruleset: upstream aliases are not economic identity. No pooled parent-item valuation across distinct variants. A local item-ID aggregate is labeled `identity_basis=local_item_aggregate`; mixed/unknown variant mappings cannot qualify precise advice or merge with an exact server variant.

Every result carries algorithm ID, metric/role, source identity, input generation, completeness, synthetic provenance, observation time, upstream content time if known, and arithmetic support/status. Daily records also carry UTC date, selected observation ID and history basis. Desktop synchronization and export times are delivery metadata, never observation freshness.

For each valid priced listing calculate integer unit tier p=ceil(B/q), or p=u for a commodity. Quantities are units, not stack counts. Aggregate equal p into sorted tiers with quantity Q and priced listing count L. Preserve original B/q or u separately for raw-ask reporting and purchase-cost analysis. Bid-only rows contribute only to total supply and listing counts.

Missing price is null. An empty complete scope is observed absence; a missing/failed observation is unknown. Partial/cut scope cannot establish absence. Never fill missing price periods, infer sales from disappearance, or invent sale proceeds.

## Shared metrics

### Observed minimum and all-listing mean

`minimum_listing_copper` is the minimum canonical unit tier, at least 1. Expose the original minimum ratio separately where retained, so ceiling does not erase fractional-unit evidence.

`quantity_weighted_ask_copper` retains Market's existing all-listing mean definition: sum of original stack totals or commodity unit*quantity divided by priced quantity, half up once. It is descriptive, can round below one copper for valid fractional stack inputs, and is not substituted for Recent Price. Zero in this descriptive statistic never makes a zero canonical listing or actionable price.

### Recent Price

Let T=sum(Q) over priced tiers. Unknown when T=0 or required distribution inputs are unavailable.

1. Anchor A is the first tier whose cumulative quantity C satisfies 4C>T, strictly.
2. Retain tiers satisfying 2p>=A. This includes exactly half the anchor.
3. Let E be remaining quantity. Take the cheapest 3E/10 units, allowing a fractional unit at the final tier.
4. Recent Price R is their quantity-weighted mean, rounded half up once.

Implement the fraction exactly: take band weights in tenths, total band weight W=3E, and sum S=sum(p*taken_tenths). Then R=floor((2S+W)/(2W)). A one-tier item has R=p.

This is a representative lower asking band, not a sale expectation, optimal liquidation price or posting recommendation. A thin cheap cluster can control the anchor. Keep low-listing, wide-spread, cheap-outlier and far-below reasons visible; do not repair the statistic by secretly changing its formula.

### Distribution

Q25, Q50, Q75 are the first unit-price tiers with 4C>=T, 2C>=T, 4C>=3T respectively. Q25 can differ from strict-quarter A. High is the highest priced tier. Near supply is priced units with 10p<=11R, including any cheap units the band filter excluded.

Spread is (Q75-Q25)/Q50. Classify with integer comparisons: tight when 10(Q75-Q25)<Q50; moderate when less than 3Q50; otherwise wide. `cheapoutlier` means 2*minimum<R. `farbelow` means fewer than five priced listings, a second tier exists, and 2*minimum<second_tier_price.

Compute these over all valid tiers before compaction. Bins and the six-tier projection are display/storage views, never substitutes from which to reconstruct unknown quartiles or the band. Current server bins remain a separately versioned display distribution.

### Daily close and coverage

For each UTC day, choose the latest complete, numerically valid, non-cut market-scope observation by `(observed_at, observation_id)`, bounded by the generation watermark and query instant. Today's close is the latest available close-so-far and is labeled provisional. Store an explicit absent close when the variant is missing from that complete scope; do not carry its earlier intraday listing to the close.

A later incomplete observation remains visible as partial snapshot evidence but cannot replace the complete close used for canonical history. Whole-read partial-info Workshop records remain legacy history unless sufficient complete original evidence exists. This is a deliberate change from existing Workshop listed-day history and is covered by fixtures.

No observation means no daily point. Bid-only/absent closes have no Recent Price and do not vote in price medians. They can carry known supply. Repeated conditional confirmations may establish observed dates but do not establish new content generations; report observed-day and distinct-content coverage separately. Coverage is a count, not a sale rate or statistical confidence probability.

### Market Value

Use canonical daily closing Recent Prices with UTC age 0..13 relative to the query day. Weight days at ages 0..2 by 4, 3..6 by 2, and 7..13 by 1. Sort values ascending and choose the first whose cumulative weight C satisfies 2C>=sum(weights). Ties therefore choose the lower median.

One priced day permits a value with `coverage_status=single_day` and quality capped at limited. With two dates report `sparse`; never label the result as validation of a full 14-day horizon. No known priced date means unknown. Multiple collections in one date provide one vote.

### Historical Value

Use exact canonical daily closing Recent Prices at UTC ages 0..59, one vote each, and the same lower-median rule. Require at least three priced dates; otherwise null with `insufficient_days` and the actual count. Three dates permit a sparse reference, not a claim that 60 days were observed.

For v1, weekly or two-week means are not admitted as exact canonical daily values. Keep Workshop's existing bucket-based result as `workshop-legacy-aggregate`; do not silently relabel it. A future approximate historical metric needs its own basis/version. This choice sacrifices some older canonical coverage in exchange for cross-project reproducibility and prevents a median-of-means proxy from being presented as the median of original days.

## Separate decision roles

Competition remains current-listing evidence: the first known tier satisfying 2p>=A. If it is beyond retained tiers, say unknown/beyond; never use R or a historical median as a substitute. Posting guidance remains a separate match policy over competition and current eligibility. There is no automatic undercut, scan or transaction.

Purchase costs use original stack totals and quantities. For verified divisible commodities, walk known ascending unit-price depth for the requested quantity. For whole auctions, an explicit selected listing plan has an exact observed total, but is not necessarily the globally cheapest plan. With only tier summaries preserve lower/upper whole-stack ranges; beyond retained tiers preserve estimate bounds; insufficient total supply is `few`. Never label R*quantity a proven purchase cost. No quote guarantees the listing still exists.

Confirmed sale proceeds require actual invoice/transaction evidence. `Sell.Proceeds` today is a hypothetical gross listing total with unknown fees/deposits and no guaranteed sale; preserve that distinction. Do not infer revenue, demand, sell-through or fees from auction observations.

## Quality and selling safeguards

Preserve Workshop policy-1 thresholds for usable comparable current evidence:

| Level | Requirements |
|---|---|
| good | Complete, not cut; content age <=24h; >=5 priced listings; known distribution whose spread is not wide; >=7 listed/observed dates in last 30; no mixed variants or farbelow |
| fair | Content age <=72h; >=3 priced listings; not cut; full source scope; no mixed variants |
| limited | A supported price exists but requirements above are unmet |
| none | No supported price or identity |

Synthetic observations, unverified market identity, unknown content age or unresolved precision cap decision quality at limited. Every unmet requirement retains a reason. When upstream content time is known, do not use a newer collection/desktop check to make old content fresh; otherwise say content age unknown. Local scan observation time is its content evidence. The status-chip freshness thresholds from M0 remain presentation policy and do not alter these valuation/selling thresholds.

Preserve Sell.Suggest's stronger gates: quality good/fair, complete current evidence, not cut, <=72h, known competition, no explicit/mixed variant uncertainty, and no farbelow. Preserve Advisor's auction eligibility, reserved-crafting priority, 1.5x vendor margin, player gain threshold, unknown fees and explicit weaker tentative-observation role. Two-day history never upgrades an observed listing into strong supported advice. Existing Posture still requires five historical priced days, >=3 current listings, fair quality, no farbelow and compares Recent/Historical at 85%/115%. Trend still needs two days in each half of its supported window and never forecasts sales.

## Integer precision and rejection

Raw copper remains a canonical nonnegative decimal string through signed-64 maximum. Preserve raw observations outside the shared computational range. Canonical unit-price calculations support 1..99,999,999,999, matching Workshop's current price bound. Counts must fit both the source contract and the particular consumer; no silent truncation.

Use exact integer/rational intermediates and half-up division, never binary floating-point accumulation followed by rounding. Python arbitrary integers and checked Rust u128 cover the bounded listing domain; validate aggregate limits before calculation. Lua must use an exact checked method for wide intermediates or refuse recomputation with `numeric_range`; it may display a validated precomputed canonical decimal value in its supported output domain without pretending to have recomputed it. Never silently emit an approximate canonical result or clamp an out-of-range input. Existing Workshop approximate legacy results keep their legacy algorithm/basis.

Reject noncanonical money strings, negative/fractional counts, unsupported algorithms, invalid identities and observations beyond the declared query instant. Currency, algorithm, schema, storage and quality-policy versions are separate. Changing formulas, inclusivity, thresholds that affect a result, or rounding requires a new pricing/policy version and shared expectations.
