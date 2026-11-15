# TwichUI pricing migration and bridge amendments

M0.5 delivers a proposed policy, research fixtures and migration design only. No production function, deployment, database migration, companion protocol or addon saved-data schema is changed. Owner approval of the model is distinct from approval to implement or deploy it.

## Immutable observations and versioned derivations

Preserve original listings, stack totals, quantities, variants, market mappings, snapshot hashes and observation timestamps. A new algorithm creates a new derived projection; it never edits an old observation or relabels an old value. Keep existing `asking-v1-provisional` statistics readable.

Market's current SnapshotStatistic primary key is snapshot/item/variant and its algorithm is a column. Do not overwrite those rows to implement coexistence. Propose an additive derived table keyed by `(snapshot_id,item_id,variant_key,pricing_algorithm)` with source/input digest, exact canonical outputs, quality/input flags and derivation build. Separate daily projections key the selected market/day close and algorithm/basis. Design retention and indexes before a migration; do not run it as part of this milestone.

Recompute canonical Recent Price only where complete raw listings or sufficient exact full-distribution inputs remain. An all-listing mean, minimum, supply or coarse histogram cannot recover the lower-band mean. Raw retention may already make older days unavailable. Do not promise a 60-day backfill or manufacture canonical days from the old Market recent field. Missing derivations remain unavailable with a reason.

## Workshop history compatibility

Keep `TwichUIWorkshopDB.v=2`, market format 3, local `items/dist/hist/h2/c2` and retention unchanged during M0.5 and the first implementation shadow phase. Existing Dist alg=1 has the candidate snapshot formula, but the containing records do not prove canonical daily-close selection, exact variants or exact arithmetic in every case.

Do not rename all old `r` fields as `twichui-pricing-v1`. Existing daily points may retain the last listed price after a later observed absence, may contain partial-info evidence, and may have been condensed into means. Keep them under a documented legacy algorithm/history basis. Historical Value from existing weekly means remains `workshop-legacy-aggregate`, with aggregate/approximate flags; it is not an exact canonical 60-day median.

Where original complete observation evidence can prove equivalence, a future adapter may derive a separate canonical record with its own provenance. Otherwise start canonical daily recording prospectively. Do not rebuild missing dates from the ring: it retains only eight observations and cannot establish all intervening closes. Keep existing saved strings intact. Any additive persistent canonical container or migration requires a separately reviewed held/newer-schema, idempotence, cancellation, retention and rollback plan.

Exact server variants and local item-ID aggregates are separate evidence identities. A local aggregate cannot silently inherit an exact server variant's history or satisfy precision/variant requirements for advice.

## Market and companion changes after approval

1. Implement the shared arithmetic and exact validation in an isolated shadow module, using the shared fixtures plus independent reference and property tests. Preserve legacy outputs in every existing endpoint.
2. Add versioned derived storage and bounded recomputation from retained original inputs. Compare input/output row counts and source hashes before/after; rehearse migrations on isolated databases only. No source observation is rewritten.
3. Expose both algorithms through a new negotiated contract or endpoint. Current Rust v1 validation accepts only `asking-v1-provisional` and rejects unknown fields/algorithms, so changing the existing string in place is a breaking change.
4. Introduce a separate versioned canonical cache namespace/store. Preserve existing schema-2 SQLite caches and offline generations. Download manifest, records, algorithm/basis and completion provenance into staging, then promote together. Do not mix cached old-reference scalars into a new generation.
5. Key derivations/caches by issuer, market, exact variant or declared local identity basis, algorithm, input generation, as-of UTC day and history basis. Quality/freshness also depends on actual evaluation time and policy version; invalidate it independently as needed. A reused content snapshot on a new calendar date may change references or coverage.
6. Record shadow differences and advice refusal reasons. Enable a new default only after model approval, real-data acceptance, compatibility tests and separate release authorization. Roll back by selecting the previous derived projection and contract/cache namespace; retain observations and all previous generations.

No change to collector schedules, enabled houses, provider jobs, pruning or signing/release infrastructure is required to implement pricing research.

## M1 bridge contract amendments

The completed M0 contract is still a proposal, so freeze these amendments before its first implementation rather than assigning a misleading version to already deployed data. Preserve the distinct bridge format and strict future-version rejection.

Require:

```text
pricing_algorithm
quality_policy
history_basis
input_identity_basis
arithmetic_status
metric_id / role
input_generation
as_of_utc_day
priced_day_count / observed_day_count / distinct_content_count
coverage_from / coverage_through / missing_or_omitted_periods
selected_observation_id / observed_at / upstream_updated_at
```

Snapshot and daily fields must identify the algorithm that produced them. For exact canonical history, require `history_basis=canonical_complete_scope_close`; for legacy records use an explicit understood legacy basis. A bridge-wide label cannot override an individual legacy field. Reject an unknown required algorithm or basis; an optional legacy comparison may be omitted with a reason.

Carry separately named `minimum_listing_copper`, `quantity_weighted_ask_copper`, `recent_copper`, `market_value_copper`, `historical_value_copper` and their coverage/status. Do not map `asking-v1-provisional.recent_price` into canonical `recent_copper`. Coarse server bands cannot establish canonical quartiles/Recent Price; calculate before compaction, then transmit scalar outputs and evidence summaries under their actual algorithm.

The bridge continues to preserve complete generations, exact copper strings, raw variant identity, source timestamps and synthetic flags. It never writes server data into local scans and never infers actual sales. At least two available genuine dates can improve a separately labeled chart, but two dates leave canonical Historical Value unknown. Preserve available historical-only variants when current supply disappears.

## Cross-repository fixture ownership

Market `contracts/pricing/v1` owns the specification fixtures. TwichUI `tests/fixtures/pricing_v1` vendors identical fixture/schema/checksum bytes with an upstream commit pin. A fixture edit changes fixture version/expectations only through a reviewed policy change, never by running an implementation to regenerate its own expected output. Both repositories verify manifest equality; Python, Rust and Lua use the same source records and decimal representations.

Add domain/property cases for listing permutation, duplicate identity rejection, quantity/stack conservation, exact half-up ties, strict-quarter boundaries, calendar ages, same-day replacement, absent/incomplete closes, mixed algorithms, future schemas and overflow. Actual implementations need full API/cache/storage tests beyond this milestone's pure arithmetic checks. Preserve all existing Advisor tests and add negative tests proving legacy/partial/synthetic/unknown-variant data cannot satisfy stronger evidence requirements.

## Owner decisions and acceptance gates

| Decision | Recommendation | Consequence |
|---|---|---|
| D1 Shared representative price | Approve band mean with strict 25%, half-anchor and 30% parameters | Keeps the lower asking-band role; thin/adversarial weaknesses remain explicit |
| D2 Temporal references | Approve UTC calendar windows and lower medians, weights 4/2/1, Historical minimum three dates | Replaces Market rolling-second means only in a future versioned implementation |
| D3 Canonical day/history basis | Approve last complete scope close, absent close preservation and exact daily-only Historical Value | Some old Workshop points/buckets remain legacy and canonical coverage may start prospectively |
| D4 Decision safety | Preserve existing Advisor/Sell gates; cap synthetic, unknown-age and unverified identity evidence | Unified display metrics do not enable weaker selling advice |
| D5 Rollout | Require a representative authorized full-snapshot shadow comparison before enabling defaults | Available excerpts cannot establish live robustness or 14/60-day validation |

Model approval authorizes none of: production formula changes, deployment, live migrations, data bridge implementation, automatic scanning or a client reload. Those remain separate tasks.
