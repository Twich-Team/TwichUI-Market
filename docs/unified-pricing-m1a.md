# TwichUI M1a unified pricing foundation

The owner approved M0.5 decisions D1–D5. Market research PR #6 merged into the integrated companion/server branch as `4cb4d86f4402cd3c6508914549f697507d69c0c6`; TwichUI PR #20 merged into `feature/workshop` as `5b6e4e9f4dd3908042831bf6496133fbd8154960`. Both used permitted merge commits without force or protection bypass. Market's Backend/website/Windows research checks passed; TwichUI had no PR workflow runs, with static fixture and source arithmetic checks verified. The five shared research files were byte-identical and the intervening Market changes were release documentation/overlays, with no pricing incompatibility.

## Implemented shadow interfaces

`backend/market/canonical_pricing.py` implements exact copper validation, snapshot minimum and lower-band Recent Price, quantity-weighted descriptive ask, full-input quartiles with a six-tier projection, complete UTC-scope close selection, 4/2/1 lower-weighted 14-day median, exact-daily 60-day lower median requiring three priced dates, coverage, and a separate quality projection. It is not imported by app, worker, legacy pricing or sync paths. No table, migration or persisted generation changes.

`desktop/core/src/pricing.rs` supplies strict exact-copper/tier validation, checked-u128 band arithmetic, complete daily-close/median conformance and a bridge-header capability check. It is an unused core module; existing protocol ALGORITHM, sync/cache and tray scheduler stay unchanged. Header support is not full schema/integrity validation and does not accept data for delivery.

Workshop `PricingV1.lua` is a pure dormant module outside every TOC. It calculates the same supported snapshot/history values, validates copper/identities and rejects unsafe intermediates before claiming a canonical result. It has no frames, timers, persistence, local history or Advisor/Sell integration. Legacy Market APIs and saved schema/retention remain intact. No live work runs, so no runtime perf scope/gauge is required; future M1b loading/decoding must add them.

## Frozen contract

[Bridge contract v1](../contracts/bridge/v1/README.md) includes a closed machine schema, representative canonical and provisional generations, and an offline semantic/integrity validator. It preserves exact market/variant identity, explicit algorithm/basis, source timestamps, synthetic provenance, coverage, historical-only variants and separate distribution representations. Two genuine dates can reach a chart without establishing three-date Historical Value. The contract does not implement export routes, installation, generation delivery, JSON ingestion, reload or a bridge addon.

## Verification and shadow comparison

The authoritative M0.5 JSON fixtures remain unchanged. Python, Rust and Lua test the same 19 supported priced snapshots and eight calendars; out-of-range raw money stays an exact string or produces an explicit range refusal. Python also checks raw all-listing means against legacy fixtures, quality cases, randomized Fraction-reference properties, identity/version/time rejection, canonical day-count boundaries and isolated critical mutations. Workshop uses the existing mutation runner with new catalog entries for half-anchor, Historical minimum and exact rounding range.

`scripts/compare-pricing-shadow.py` accepts an explicit local original-snapshot export or the approved research fixture file. It executes only the audited existing pure legacy functions and the new canonical calculator, with no app imports, database or network calls. Captured excerpts retain their original scope/timestamp; synthetic cases remain synthetic. No representative full production snapshot is available to this Cloud task, and the owner previously confirmed no alternate export. The real-data gate remains open; no full 14/60-day claim follows from synthetic calendars or two available service dates.

Exact test counts, performance, observed failures and remaining client gates are recorded in the [acceptance report](unified-pricing-m1a-acceptance.md). No code from these implementation PRs is approved for automatic merge or production deployment.

## Recommended M1b sequence

1. Review and merge the Market M1a implementation, then the dependent addon fixture/validation PR; require green relevant CI and retain algorithm coexistence.
2. Add a bounded, authenticated, watermark-pinned server history export using the frozen contract. Derive canonical data only from retained sufficient originals; do not relabel provisional means or local legacy buckets.
3. Add a separately versioned desktop bridge cache and manual sandbox generation. Preserve old completed caches and account/market isolation. Keep automatic installation and the scheduler unchanged until their own milestone.
4. Implement the non-executing Workshop reader and source-aware charts, with no writes into local scan/history containers; instrument parsing and retained memory.
5. Perform representative authorized full-snapshot shadow comparisons and Windows/Forever load/reload/size acceptance. Enable defaults or automatic delivery only under separate authorization.
