# TwichUI Market bridge contract v1

Frozen M1a contract: `format=twichui-market-bridge`, contract/schema/transport versions all **1**. The normative machine schema is [generation.schema.json](generation.schema.json); [validate.py](validate.py) adds semantic, integrity and size checks. Both representative generations are explicitly synthetic: [canonical](canonical-generation.json) and [provisional](provisional-generation.json). This directory defines data, not a server route, installer, Lua file writer, desktop delivery or Workshop ingestion.

## Algorithm and source identity

One generation contains exactly one pricing algorithm/history basis pair:

| Algorithm | Required history basis | Current Recent Price basis |
|---|---|---|
| `asking-v1-provisional` | `market_rolling_daily_means` | `quantity_weighted_mean` |
| `twichui-pricing-v1` | `canonical_complete_scope_close` | `lower_band_mean` |

Every current/daily record repeats the algorithm. Mixed generations or mislabeled fields are rejected. Separate generations can coexist; never merge their daily values or present the provisional mean as canonical Recent Price. The original APIs/cache/export v1 remain unchanged and continue rejecting unsupported algorithms. Pricing specification: [M0.5](../../../docs/unified-pricing-m05.md).

Identity is issuer UUID plus Forever game, region, player ruleset, house and source kind. `transport_ruleset_id` is retained separately because API ruleset URLs can alias the same house feed. `server_market_id` is issuer-local. `realm_scope=ruleset_house` does not invent a server realm. Mapping verification requires player ruleset and an evidence hash; an unverified mapping remains display evidence and cannot qualify strong advice. A separate per-account local realm binding is future M1b work.

Each record has an item ID, full upstream variant SHA-256 and the exact canonical descriptor JSON string, or an explicitly hash-only identity after descriptor loss. Canonical descriptors use sorted keys, no whitespace and ASCII escaping. A retained descriptor must hash to its key and contain the same integer item ID. Native level/suffix/pet keys and local base-item scans are not assumed equivalent to the full upstream descriptor. Hash-only means unknown attributes, never base item.

## Generation and observation metadata

The closed schema lists every required field, including nullable fields. A generation carries producer build IDs, the watermark, current observation reference, pricing as-of UTC date, transfer/coverage status and synthetic provenance. Observation IDs are decimal strings; the watermark bounds IDs but current selection follows `(observed_at, observation_id)` chronology, preserving late historical imports without replacing current supply.

The shared observation table carries actual observation/snapshot IDs, UTC date, observation time, parsed and raw upstream modification timestamps, namespace, payload and snapshot-content hashes, synthetic provenance and source-scope completeness. Current references point to the newest included observation; canonical daily references point to the latest complete observation of their UTC date. Producers must select those closes from all eligible source observations under the watermark, not merely a currently mutable daily-winner table. A receiver cannot independently prove observations omitted by a producer.

Times are UTC RFC3339 strings ending in Z, with at most six fractional digits. Preserve observation precision. `generated_at` is artifact creation; `desktop_sync_completed_at` is the successful complete bridge-data acquisition, not just the old scalar-cache sync; `server_checked_at` is a separate successful collection check. `observed_at` preserves the collector's timestamp semantics (currently check/request start), not an invented response-completion instant. Upstream modification time describes content; a newer 304, desktop check or artifact never makes old content fresh. Unknown upstream time stays null. Future timestamps beyond the generation instant are rejected.

Synthetic provenance is the conservative OR of every contributing source, including reference support omitted from the delivered daily subset. An omitted synthetic supporting date must not be hidden by a genuine current snapshot. Receivers can check included provenance but cannot prove the absence of omitted inputs; producers own this invariant.

Required features are exactly `exact_copper`, `current_summaries`, `daily_history`. Unknown versions, required features, algorithms, fields or incompatible bases reject the generation. Quality-policy version 1 retains the approved safeguards. Capabilities in Rust/Lua check header compatibility only; they are explicitly not full generation validation or ingestion.

## Records and daily history

Records sort by `(item_id, variant_key)` and include current summaries, per-date records and an optional distribution. The union includes historical-only variants even when current supply disappears. Current metric names are `minimum_copper`, `quantity_weighted_ask_copper`, `recent_copper`, `market_value_copper` and `historical_value_copper`. Interpretation always includes their algorithm/basis. Canonical minimum uses ceiling unit copper; provisional minimum uses its original half-up rule. The all-listing mean remains descriptive and may round to zero; canonical representative prices must be positive and within the supported range.

Presence states are separate:

- `listed`: observed listings, possibly bid-only. Supply includes bid-only units; priced supply excludes them. With priced supply zero, current/daily minimum and Recent Price are null.
- `absent`: proved by a complete observation of this source scope; supply/counts zero, current/daily prices null. Historical references may remain known.
- `unknown`: no proof of presence/absence; counts and current/daily prices null.

No source observation means no date point. Missing dates are not synthesized, interpolated or filled with zero. A date intentionally omitted for size is reported through coverage/truncation, not absence. Canonical Historical Value remains null with fewer than three priced dates; two available dates still provide two useful chart points. The fixtures include this distinction and a historical-only variant. Listings/disappearance are not confirmed sales.

Per-current coverage distinguishes priced dates in the 14/60 windows, observed dates and whether the supporting reference window is complete. Provisional rolling windows can span 15/61 UTC dates; canonical windows permit 14/60. A reference count can exceed the delivered daily subset only when that subset/support limitation is explicit. Whole-generation coverage describes the requested export window, not the full duration of server retention or the entire WoW economy. `generation_complete=true` means a complete transfer, independently of upstream/current completeness.

## Distributions and quantities

Canonical distributions use `canonical-tiers-v1`: full-source quartile/anchor/high statistics, up to six cheapest exact ceiling-unit tiers, and tail quantity/listing counts. Compute summaries before compaction. Tier quantities count units; listing counts count stacks; largest-listing size preserves whole-auction bounds. Tail summaries never establish an exact unknown tier or quote.

Provisional distributions use `linear-unit-price-bands-v1`: up to 32 rounded min/max bands with unit/listing totals, no canonical quartiles/tiers. Bands cannot reconstruct a band mean or exact purchase cost. Both declare `basis=current_asking_listings`, availability, completeness and truncation; priced/unpriced totals reconcile with the current observation. An unavailable, omitted-budget or unsupported distribution is null with its explicit status.

All money is null or a canonical decimal string through signed-64 maximum. Never transport JSON numeric money, exponents or leading zeros. Canonical computational prices support 1..99,999,999,999; raw descriptive values remain exact strings outside that range. Counts are JSON integers within 2^53-1 and narrower field limits. No floats, nonfinite numbers, booleans-as-counts, rounding through a double or silent clamping. `arithmetic_status=unsupported` carries no derived minimum/Recent Price. Lua can reject recomputation requiring wide intermediates while preserving a separately validated precomputed string; it must never claim an approximate result is canonical.

## Canonical serialization and integrity

Canonical JSON recursively sorts string object keys, emits no insignificant whitespace, ASCII-escapes strings, and permits only integers/booleans/null as scalar numeric-like values. Arrays preserve order. Nesting is bounded to 12. This is the defined project encoding, not a claim of RFC JCS compatibility.

Let body be the generation without `generation_id` or `integrity`; manifest is body without `records`:

```text
generation_id = SHA256(canonical(body))
integrity.records_bytes = len(canonical(records))
integrity.records_sha256 = SHA256(canonical(records))
integrity.manifest_sha256 = SHA256(canonical(manifest))
```

The offline validator checks hashes AND semantic invariants; recomputing a checksum cannot legitimize a false identity, version, basis, count or absence claim. Reject duplicate JSON object keys and record identities. SHA-256 detects corruption; it does not authenticate arbitrary local addon code. TLS/authorized acquisition and companion ownership remain separate trust boundaries.

| Bound | Limit |
|---|---:|
| Serialized generation input | 32 MiB |
| Canonical manifest | 64 KiB |
| Canonical record | 64 KiB |
| Records | 150,000 |
| Observation references | 61 |
| Daily records per variant | 60 |
| Variant descriptor | 4,096 ASCII bytes |
| Canonical retained tiers / provisional bands | 6 / 32 |
| Future Lua decoded-string chunk | 64 KiB |

The union of historical identities can exceed the upstream per-snapshot listing bound. Fail an oversized generation rather than claiming a sampled generation is complete. Future producer compaction removes optional distributions first, then oldest whole daily dates uniformly, retaining the two newest available observed dates in the requested window. Declare every omission. If current data plus those dates still cannot fit, retain the previous valid generation and report the limit. These are contract bounds; real Forever load-time/memory acceptance remains open.

## Future transport and recovery

The M0 mechanism remains a dedicated companion-owned `TwichUI_MarketData` addon with no SavedVariables. Its future fixed TOC loads one self-contained generated Data.lua generation. The wrapper may contain only fixed trusted assignment syntax and bounded quoted strings/chunks; quote backslashes, quotes/control bytes and use fixed-width escapes. Never interpolate server text as Lua syntax, use long-bracket text or deserialize using load/loadstring. No credentials, account names, device tokens or private desktop paths enter the game files.

No transport writer exists in M1a. M1b must validate completely outside the game directory, atomically replace one self-contained file on the destination filesystem, verify readback and preserve prior validated artifacts. Replacement failure leaves the installed generation intact. WoW keeps the loaded generation until a player-controlled reload/restart; no unsupported file-change detection, automatic reload or live SavedVariables edits. Initial addon discovery and actual Windows/Forever file caching remain acceptance gates.

A receiver accepts a generation atomically after full checks, never partially mutates local scans, and retains local functionality when the bridge is absent/corrupt/newer. Separate canonical/provisional/imported sources from `TwichUIWorkshopDB` local history. Restore a complete prior artifact on rollback without downgrading saved schemas or deleting original observations.

## Reproducible offline validation

```sh
python3 contracts/bridge/v1/validate.py \
  contracts/bridge/v1/canonical-generation.json \
  contracts/bridge/v1/provisional-generation.json
```

Use the existing backend JSON Schema test dependency. The addon mirror pins these exact schema/generation/checksum bytes; it does not add a JSON parser or ingestion path. Future conformance must additionally test pinned server export, chunk serialization, cursor/staging consistency, Windows replacement and real-client loading before delivery is enabled.
