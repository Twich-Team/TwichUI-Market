# Forever API feasibility — US live evidence

Authenticated requests succeeded on 2026-11-14 using the privately configured client credentials. One independently tested US auction feed is collecting genuine data. No credential, OAuth response, access token or authorization header is included in evidence. Original synthetic fixtures remain explicitly synthetic; new two-listing live excerpts identify their capture time and full-source counts separately.

Evidence: [discovery/response summaries](evidence/2026-11-14-us-discovery.json), [collection/browser/house comparisons](evidence/2026-11-14-live-collection.json). These are direct project observations. The earlier [firsthand forum report](https://us.forums.blizzard.com/en/blizzard/t/wow-forever-api-what-works-so-far-plus-a-ts-client/60334) is background only, not the basis for declaring a mapping verified.

## Observed US structure and identity

OAuth client credentials succeeded at `https://oauth.battle.net/token`. Requests used `https://us.api.blizzard.com`, `dynamic-forever-us`, and `en_US`. The live ruleset index lists 1 (PvP), 2 (Normal), 3 (Roleplay), and 15 (Roleplay PvP), each reporting Up. Every tested ruleset lists the same 15 house IDs through `/data/wow/ruleset/{id}/auctions/` (trailing slash).

| House IDs | Upstream name | Auction listings in the sampled response |
|---|---|---|
| 110, 111, 112 | Alliance Auction House | 96,924; 107,564; missing array |
| 113, 114, 115 | Horde Auction House | 113,803; 109,986; missing array |
| 116, 117, 118 | Blackwater Auction House | 7,477; 8,339; missing array |
| 119, 120, 121 | Alliance; Horde; Blackwater | 23,736; 17,532; 412 |
| 123, 124, 125 | Alliance; Horde; Blackwater | 22,620; 23,156; 526 |

For houses 110 and 113, the listing arrays are identical through all four ruleset URLs. House 110 commodities are also identical through all four. House 113 has the same 113,803 records and canonical listing-array hash `58de5fd2855d1392…` across rulesets; house 110 has 96,924 and `ee969c2922f6dc08…`. Response-byte hashes may differ because embedded URLs echo the requested ruleset. Therefore ruleset URL differences must **not** be counted as independent economies.

A separate sequential comparison of all 15 houses found 12 explicit nonempty auction arrays and zero shared auction IDs across their 66 pairs. Those are distinct sampled upstream listing feeds. This does not prove which player-facing ruleset uses each house, nor whether all feeds are simultaneously reachable in game. The API names and echoed ruleset links do not settle that question. Preserve house identities, choose one ruleset URL as a transport alias, and do not invent a PvP/Normal assignment. Houses 112/115/118 return HTTP 200 without an `auctions` array; they remain unverified/disabled rather than being silently ingested as empty.

## Listings, commodities and size

The house endpoint returns `_links`, `id`, `name`, `ruleset`, `commodities`, and (when present) `auctions`. Auction entries include `id`, `item`, `quantity`, `buyout`, `time_left`, and optional bid/variant attributes. Commodity endpoints are house-scoped `/data/wow/ruleset/{ruleset}/auctions/{house}/commodities`, with `unit_price` instead of stack buyout. Commodity counts were 81,471 (110), 97,516 (113), 15,539 (116), 25,124 (119), and 24,446 (123). Full validation also normalized all 81,471 live house 110 commodity listings successfully (221,364 KiB peak RSS under the same worker limits; see the commodity normalization evidence). No commodity feed is enabled.

House 110 auctions: 9,454,413 response bytes. House 113 auctions: 11,190,219 bytes; its commodities: 8,366,563 bytes. The former 100,000-listing ingestion guard was too small for a genuine response, so the bounded guard is now 150,000 while the 32 MiB response cap remains. Actual 113,803-listing normalization completed at 290,920 KiB peak RSS inside the existing 384 MiB / 0.5 CPU worker limits. This is normalization capacity evidence; first actual PostgreSQL ingestion of the selected 96,924 listings completed in nine seconds under the same worker limits.

## Timestamps and refresh observations

Ruleset metadata advertised `Cache-Control: public, max-age=30`. House/index/commodity responses advertised `public, max-age=86400`; no ETag was observed. These headers do not establish an actual one-day update cadence. House 110 `Last-Modified` was `Sat, 14 Nov 2026 02:17:50 GMT`; house 113 was one second later. Repeated observations retained the same listing hashes. An explicit `If-Modified-Since` probe returned HTTP 304 with zero body bytes, and the scheduled collector also received 304 on its next five-minute check. Retrieval/check timestamps remain distinct from upstream modification times.

An upstream content-change transition and its repeat interval have **not yet** been observed. Continuous collection remains running to record that behavior; do not label a guaranteed hourly/daily refresh interval or manufacture new historical prices. Current evidence establishes working conditional requests and unchanged-snapshot preservation.

## Initial enabled mapping

Only market 1 is enabled: `us / ruleset transport alias 2 / house 110 / auctions`, labeled “US Forever — Alliance house 110 (ruleset aliases)”. Live receipt 1 binds the mapping, fresh index membership, house identity, normalization, response metadata/hashes and an administrator identity. Its audit hash is in the evidence file. Only its five-minute schedule is active. Do not broaden collection based on this initial activation.

Real Chromium checks pass for authenticated item search, current listings, quantity-weighted price, supply and a one-point genuine history chart. Worn Shortsword variant `af047f1e…` has seven units/seven listings and a 2,805-copper recent price in this sample. Default Deal Finder filters report one observed day versus three required; prior-day change modes have zero days. An explicit one-day/limited-confidence query evaluates genuine below-reference listings without implying sufficient long-term evidence or completed sales.

## Reproduction

Run only within the approved rootless environment, using ignored `.env` credentials:

```bash
docker --context rootless compose -f compose.yaml -f compose.tls.yaml run --rm --no-deps worker python -m market.probe --region us --ruleset 2 --house 110
docker --context rootless compose -f compose.yaml -f compose.tls.yaml run --rm --no-deps worker python -m market.feasibility --region us --house 110
docker --context rootless compose -f compose.yaml -f compose.tls.yaml run --rm --no-deps worker python -m market.feasibility --region us --compare-houses 2
```

Discovery is sequential (one-second spacing), bounded to 16 rulesets/64 indexed houses; overlap comparison is at most 16 houses/one million identifiers. All responses retain the 32 MiB/45-second transport bounds, redirect refusal and shared rate-limit cooldown. Stop on upstream failures. Regional behavior outside US, exact player-facing routing, and long-run refresh cadence remain unverified. Workshop formulas, design approval and original retention clarification remain separate outstanding requirements.
