# Versioned data contracts

REST base: `/api/v1`. Responses with a contract_version use integer 1. Browser sessions authenticate with an HttpOnly cookie and use X-CSRF-Token for mutations; desktop devices use a revocable Bearer token. Administrator operations require an administrator browser session.

Money is represented as a decimal string of integer copper (or null if unknown). Auction IDs are strings because upstream identifiers can exceed JavaScript's exact integer range. Counts/item IDs are bounded JSON integers. Timestamps are UTC ISO 8601. Never substitute zero for a missing reference price.

Research endpoints:

- GET /markets: explicit source mapping, enabled/verified flags, source/check freshness separately.
- GET /markets/{id}/items?q={name or numeric item ID}&after_id=0&limit=50: current item variants; item-ID pagination retains variants together. Name search is case-insensitive and escapes wildcard characters. Names are region-scoped cached Forever metadata; unresolved names retain item-ID fallback. Responses distinguish verified, synthetic and unresolved metadata and expose its last successful observation timestamp.
- GET /markets/{id}/items/{item_id}/{variant_key}: prices, 60-day daily history, current listings (bounded at 200, truncation flag), algorithm/provenance and synthetic flags.
- GET /markets/{id}/deals?minimum_discount=15&maximum_spend=5000000&minimum_coverage=3&minimum_confidence=limited: explainable below-reference listings. maximum_spend is copper. Set-based SQL evaluates all current listings against retained daily references; results are bounded to 100 with candidates_truncated indicating more matches. Confidence is limited for stale/unknown sources, unverified mappings or synthetic data. Daily coverage is measured within the 14-day reference window.
- GET /markets/{id}/signals?kind=supply|price&minimum_change=20&minimum_coverage=3&minimum_confidence=limited&direction=any: compares current values with prior UTC-day observations within 14 days, excluding today. Price references average priced daily values; supply averages include zero when the market was observed but this variant was absent. Completely vanished supply remains a signal and never implies sales. Results include current/reference values, signed percentage change, coverage, confidence and reasons. direction accepts any/increase/decrease; minimum_confidence accepts limited/moderate/strong. Results are bounded at 100.

Current price algorithm is asking-v1-provisional; Workshop compatibility is not verified. All synthetic fixture outputs are labeled synthetic. Missing or unverified metadata is never replaced by invented live names. An explicit item search can return retained historical variants when no current variant matches; historical_results identifies this case and a missing raw variant descriptor remains null.

## Incremental desktop synchronization

GET `/sync/markets/{id}?cursor={opaque cursor}&limit=50` requires normal private authentication (device Bearer recommended). Page size is 1–100 scanned item variants. Response includes contract_version=1, market_id, algorithm, changes, cursor, has_more, target_observation_id (string), observed_at and synthetic. Changes contain operation (`upsert` or `delete`), item_id, variant_key and value (compact valuation object or null for deletion). The value contains precision-safe recent_price, lowest_buyout, market_value, historical_value, supply, priced_supply, listing_count, coverage_days, market_coverage_days and synthetic.

No cursor starts a complete cache rebuild. A signed cursor binds market, base/target watermarks and scan position. Pages remain pinned to the selected observation watermark, including price-reference history, so retries remain stable while newer data arrives. Apply each validated page and its cursor in one local database transaction. Keep downloading while has_more is true even if changes is empty. A completed cursor starts the next incremental comparison on the next request; unchanged items are omitted and disappeared variants receive deletions. Historical imports update references without replacing current supply. Export only a completed generation, or explicitly label a partial cache. Preserve the last completed generation for offline use while a new generation is downloading.

Cursors are HMAC signed with SYNC_CURSOR_SECRET (at least 32 characters). Persist the secret privately; rotation invalidates cursors and requires full synchronization. Invalid/cross-market cursors or unavailable history return HTTP 409. Missing operator configuration returns 503. There is no executable payload, addon script or SavedVariables write in this contract. Live Blizzard and Workshop compatibility remain separate verification requirements.

Extended history: GET `/markets/{id}/items/{item_id}/{variant_key}/history?days=365` (1–3650 days) returns retained UTC-day points with compact prices/supply, algorithm, observation ID, payload hash, namespace, upstream modification header and synthetic provenance. Money remains decimal copper strings. Daily reference points remain after opt-in raw compaction. Statistics preserve their algorithm version; unsupported or unavailable detailed cursor history triggers a complete refresh rather than a silent incomplete incremental result. The companion performs that refresh automatically and preserves its last completed offline generation meanwhile.

Formal JSON Schema 2020-12 definitions live in `v1/`; shared TypeScript types live in `v1/types.ts`. Resolve schema references by their URN identifiers. Validators must implement the `copper-i64` format (nonnegative signed-64-bit copper) and timezone-aware `date-time` checks. Required nullable fields must be present; unknown fields and contract versions are rejected. `fixtures/` contains explicitly synthetic precision/regression examples, including copper above JavaScript's exact integer range. Python verifies actual authenticated responses against these schemas; Rust consumes the same wire fixture and enforces field, version, identifier and monetary bounds. TypeScript treats money as strings.

Opportunity responses include `history_coverage`: `observed_days`, `required_days`, `status` (`insufficient`/`available`), and `basis` (`utc_days_within_14_days`/`prior_utc_days`). This is overall market coverage; individual item coverage can be lower and remains a per-result field. It never fills missing history. The data-only export bound is 150,000 item variants, matching the bounded listing ingestion ceiling. Live US payloads exceeded the former 100,000-listing ceiling; the 32 MiB response and desktop cache byte budgets remain enforced.

## Personal website preferences (schema 1)

Additive browser-session endpoints: `GET /api/v1/me/preferences`, `PATCH /api/v1/me/preferences`, and `POST /api/v1/me/preferences/reset`. No user ID is accepted as input. Standard session, origin and CSRF checks apply; device credentials cannot access these website settings. Responses include the authenticated `user_id` so a stale tab can reject a changed session principal before caching values. Legacy REST and desktop/export contracts are unchanged.

A preference resource contains `schema_version`, `user_id`, `revision`, validated `values`, `effective_market_id`, `market_fallback` and `updated_at`. An untouched account reads revision 0 with defaults without inserting a row. PATCH accepts `{schema_version:1, expected_revision:N, changes:{...}}`; reset accepts only the version and expected revision. A successful mutation advances the per-user revision. Concurrent/stale writes return HTTP 409; clients refetch and merge only pending fields before retrying. Reset is ordered after any in-flight save and supersedes previous local dirty settings.

| Values | Bounds/defaults |
|---|---|
| `market_id` | Existing positive market ID or null (automatic fallback); default null |
| `explorer_days` | 7, 14, 60, 365, 3650; default 14 |
| `item_page_size` | 25, 50, 100; default 25 |
| `item_columns` | Boolean visibility for recent_price, market_value, supply, listing_count, item_id; default all visible; item/name always visible |
| `item_sort` | One `{id,desc}`; id is name or one of the five columns; default item_id ascending |
| `deal_mode` | listings, supply, price; default listings |
| `deal_change` | Integer 1–1000; default 15; effective listings limit 99 |
| `deal_spend_gold` | Finite number 0.01–100000000; default 500 |
| `deal_coverage` | Integer 1–15; default 3; effective change-signal limit 14 |
| `deal_confidence` | limited, moderate, strong; default limited |
| `deal_direction` | any, increase, decrease; default any |

Only known fields/values are accepted; requests and stored JSON are bounded to 4 KiB. Column PATCHes merge individually. Preference selection never enables a collector. All configured markets, including disabled historical feeds, are available for research. If a previously saved market disappears, GET resolves to the collecting feed, then another available feed, without rewriting the saved ID; an absent market cannot be newly selected. Compatible fields receive defaults through the schema; incompatible evolution requires a new version/migration. A populated preference table cannot be silently downgraded away.
