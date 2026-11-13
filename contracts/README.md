# Versioned data contracts

REST base: `/api/v1`. Responses with a contract_version use integer 1. Browser sessions authenticate with an HttpOnly cookie and use X-CSRF-Token for mutations; desktop devices use a revocable Bearer token. Administrator operations require an administrator browser session.

Money is represented as a decimal string of integer copper (or null if unknown). Auction IDs are strings because upstream identifiers can exceed JavaScript's exact integer range. Counts/item IDs are bounded JSON integers. Timestamps are UTC ISO 8601. Never substitute zero for a missing reference price.

Research endpoints:

- GET /markets: explicit source mapping, enabled/verified flags, source/check freshness separately.
- GET /markets/{id}/items?q={numeric item ID}&after_id=0&limit=50: current item variants; item-ID pagination retains variants together. Names are explicitly unverified placeholders until upstream metadata integration exists. Name search returns a notice, not fabricated matches.
- GET /markets/{id}/items/{item_id}/{variant_key}: prices, 60-day daily history, current listings (bounded at 200, truncation flag), algorithm/provenance and synthetic flags.
- GET /markets/{id}/deals?minimum_discount=15&maximum_spend=5000000&minimum_coverage=3: explainable below-reference listings with filters. maximum_spend is copper. Candidate scans are bounded to 1,000 listings/50 variants and 100 results; candidates_truncated explicitly indicates limits. Confidence is limited when source freshness is unknown or stale. Daily coverage is measured within the 14-day reference window.

Current price algorithm is asking-v1-provisional; Workshop compatibility is not verified. All synthetic fixture outputs are labeled synthetic. Missing or unverified metadata is never replaced by invented live names. Supply opportunities, broader price-change detection and indexed name search remain planned.

## Incremental desktop synchronization

GET `/sync/markets/{id}?cursor={opaque cursor}&limit=50` requires normal private authentication (device Bearer recommended). Page size is 1–100 scanned item variants. Response includes contract_version=1, market_id, algorithm, changes, cursor, has_more, target_observation_id (string), observed_at and synthetic. Changes contain operation (`upsert` or `delete`), item_id, variant_key and value (compact valuation object or null for deletion). The value contains precision-safe recent_price, lowest_buyout, market_value, historical_value, supply, priced_supply, listing_count, coverage_days, market_coverage_days and synthetic.

No cursor starts a complete cache rebuild. A signed cursor binds market, base/target watermarks and scan position. Pages remain pinned to the selected observation watermark, including price-reference history, so retries remain stable while newer data arrives. Apply each validated page and its cursor in one local database transaction. Keep downloading while has_more is true even if changes is empty. A completed cursor starts the next incremental comparison on the next request; unchanged items are omitted and disappeared variants receive deletions. Historical imports update references without replacing current supply. Export only a completed generation, or explicitly label a partial cache. Preserve the last completed generation for offline use while a new generation is downloading.

Cursors are HMAC signed with SYNC_CURSOR_SECRET (at least 32 characters). Persist the secret privately; rotation invalidates cursors and requires full synchronization. Invalid/cross-market cursors or unavailable history return HTTP 409. Missing operator configuration returns 503. There is no executable payload, addon script or SavedVariables write in this contract. Live Blizzard and Workshop compatibility remain separate verification requirements.
