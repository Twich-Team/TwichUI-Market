# Item metadata providers — researched 2026-11-14

Blizzard Forever data remains the primary source. Missing information must stay unknown unless an explicitly identified source supplies it. A matching item ID in Retail, Classic Era or a community database is not evidence of identical Forever attributes, nor of the selected auction variant's bonuses.

This research used only primary provider documentation and bounded, credential-free public API requests. It did not read Blizzard credentials, modify collection or contact providers privately. [Probe evidence and minimal attributed excerpts](evidence/item-provider-probe.json) contain real observed responses; they are not synthetic fixtures or complete item dumps. External market-price fields were excluded.

## Blizzard item and media data

The project already requests `/data/wow/item/{id}` in `static-forever-{region}`. Media should be resolved independently via the fixed `/data/wow/media/item/{id}` route and that same Forever namespace, with identity/asset validation before accepting an icon. The current official [Game Data API documentation URL](https://develop.battle.net/documentation/world-of-warcraft-classic/game-data-apis) redirected to an inaccessible community.developer.battle.net page in the research browser, so it does not establish a current Forever response contract here. Authenticated project probes must provide that evidence.

Preserve requested and resolved namespaces, item ID, hash, retrieval time and source per field. A base item preview is not verification of a listed variant's extra bonuses, random suffix or context-specific stats. Keep valid primary attributes when a secondary source fills other gaps.

## TheWoWDB — usable optional community enrichment

Its [developer documentation and terms](https://thewowdb.com/developers/#terms) describe separate `forever` and `retail` JSON namespaces, with no API key. Project use is permitted with visible linked attribution wherever data appears; raw dataset resale is excluded. Documentation calls Forever item IDs beta-client data. Cache guidance is one hour with ETag revalidation; the documented IP burst is 120, refilling at two requests/second, with HTTP 429 and Retry-After. Our process should remain much slower and bounded.

Direct probes returned HTTP 200 for [item 25](https://thewowdb.com/api/v1/forever/item/25) and [item 720](https://thewowdb.com/api/v1/forever/item/720). Conditional revalidation of 25 returned HTTP 304 and zero body bytes. Both records explicitly identify `kind=item`, `version=forever`, and **`build=wow_classic_beta-1.60.1.70532`**. That is provider-reported Forever beta metadata, not verified current live Blizzard data. Edition identity and live-build identity are separate.

Item 720's observed shape includes ID/name, quality, icon URL, item/required levels, slot, type/subtype, binding, stats, armor, weapon, vendor sell value, effects, flavor, uniqueness, sockets, class restrictions, item set, links and required attribution. Nulls and empty arrays occur. Preserve them as unknown or empty as returned; do not fabricate armor or stats.

Observed icon URLs:

- Item 25: `https://render.worldofwarcraft.com/us/icons/56/inv_sword_04.jpg`
- Item 720: `https://thewowdb.com/assets/icons/inv_gauntlets_05.jpg`

Thus an icon handler restricted to `render.worldofwarcraft.com` alone would not cover all of this provider's records. If community images are supported, explicitly allow the exact HTTPS host/path pattern, refuse credentials/query strings/redirects, cap content size, validate image signatures, and serve a local cached asset. Do not broaden the allowlist from arbitrary returned URLs. Attribution is supplied in each record; store and render a validated linked text credit, never provider HTML.

## ForeverDB — documented contract, unavailable without approval/key

The [provider's developer page](https://foreverdb.net/developers) describes Forever client extraction and player observations, with build/source distinctions and explicit uncertainty fields. Access requires an account, approval and a key. Item details document stats, weapon properties, binding, effects and earlier-build/current-client differences. Free access is documented at 5,000 requests/day and 30/minute, with account-wide quotas. HTTP 429 carries Retry-After; the free quota/subscription gate may return 402. The page contains both general credit-required text and a paid-plan exception; retaining visible credit is the conservative implementation choice.

A direct credential-free [metadata request](https://foreverdb.net/api/v1/meta) returned HTTP 401. No approved access or successful item response was obtained. Do not represent it as a verified fallback implementation. A future adapter requires a privately configured key and contract fixtures from successful authorized requests; provider claims alone do not verify current item values.

## Wowhead — approved embed differs from a data adapter

[Wowhead's tooltip documentation](https://www.wowhead.com/tooltips) documents its own external JavaScript embed, domain/version options, item bonuses and hover/mobile behavior. It does not provide a standalone metadata-ingestion contract or an explicit Forever namespace in the page reviewed. Do not infer that Retail or Classic item IDs/variant options describe Forever. Embedding its executable script would also expand this private application's CSP/trust boundary; scraping undocumented tooltip endpoints is not a substitute for an approved data contract. Do not enable it as a backend fallback on this evidence.

## Recommended integration and acceptance

1. Use authenticated Blizzard Forever item/media responses first, with separate bounded refresh/error states for attributes and icons. A missing image must not erase a valid name or vice versa.
2. Add **opt-in** TheWoWDB community enrichment only after a primary field is genuinely missing. Validate exact ID/kind/version/build, lengths/enums/structure, source links and media paths. Store the source, build, hash, observed time, ETag and attribution separately. Keep a clear “community source / beta build” label. Do not call these fields current Blizzard-verified.
3. Never ingest community `price` or `faction_prices` into TwichUI valuations. Do not replace primary fields or guess variant-specific bonuses from a base item record. Tooltips should clearly separate verified/base attributes, unresolved variant attributes and this platform's market prices.
4. Render plain validated fields in local accessible components. Do not execute provider scripts, insert remote tooltip HTML or send private market/account context to a fallback. Negative-cache missing items, honor Retry-After and cache headers, and do not let enrichment delay scheduled auctions.
5. Do not enable ForeverDB until approved credentials exist. Leave unsupported or contradictory information unknown, with source-specific diagnostics. Add regression fixtures for wrong edition/ID, missing/null values, malformed links/images, beta labels, attribution, unavailable providers and independent refresh failures.

This recommendation is an engineering inference from the documented contracts and the recorded probes, not independent proof of live-game item correctness or a blanket legal license to redistribute Blizzard artwork.
