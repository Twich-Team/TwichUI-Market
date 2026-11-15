# Explorer and Item Details implementation plan

Status: **planned, implementation and deployment require another owner instruction**. Prepared after completing the Administration Table Modernization / Metadata Provider Investigation review boundary at `96f88a0`. The administration/quality candidate remains undeployed. This document implements no application behavior and authorizes no provider, collector or infrastructure changes.

[Owner requirements](next-ux-milestone.md), [completed administration review](admin-modernization-review.md). Retain the approved espresso/bronze design and the new shared WoW quality-name component.

## Existing behavior and reusable parts

`web/src/main.tsx` routes by pathname with `pushState`/`popstate`. Explorer is `/`, Deals is `/deals`; unknown paths currently fall through to Explorer. Authentication renders before the workspace without rewriting the requested pathname. Caddy already serves the SPA entry for non-API paths. Companion authorization is a special route and must retain that behavior.

`research.tsx` combines Explorer controls/catalogue with selected-item research. `ItemCatalogue` in `catalogue.tsx` already uses TanStack and bounded server pages; selection loads the first variant and updates research below the table. Search/draft search and page index are component state. Sort, page size, market and chart range already have per-account preferences. Deal Finder's `inspect` callback sets an in-memory item/variant focus and opens Explorer. That transient focus is not currently a shareable item link.

Reuse `PriceHistory`, `SupplyDistribution`, `CurrentListings`, `ItemInfo`, `ItemFacts`, `ItemAttribution`, `ItemName`, `Currency` and `variantLabel`, plus the existing React Query/private-cache lifecycle. The catalogue has an established TanStack implementation distinct from the general `DataTable` wrapper; preserve its current grouped/variant rendering. Use the shared `DataTable` for any details-page variant rows that need it. Do not create a third table system or rewrite catalogue internals merely to move research.

Existing read APIs already cover catalogue parents/ranges, paged variants, exact-variant detail, item profile/provenance, paged listings, historical charts and supply distribution. They remain the analytics authority. No valuation or collection changes and no new aggregate analytics endpoint are planned.

## Proposed URL and navigation contract

Use `/markets/{marketId}/items/{itemId}` as the stable item route, with optional `?variant={variantKey}` for an exact variant and optional validated chart-range state. IDs identify the item; names/slugs do not determine identity. Validate positive supported integers and exact 64-character lowercase hex variant keys before requesting data. Market identity includes its existing region/ruleset/house mapping; never fall back to a different preferred market when a linked market is unavailable.

An item route without a variant opens an item overview, shows the current variant table and price ranges, and requests selection before presenting a variant-specific exact price. A link with a variant opens that exact variant. Single-variant catalogue rows may link directly to their sole verified key; grouped parent rows open the parent overview and expanded variant rows link to their exact key. Do not select an arbitrary first variant on a parent research page. A disappeared/stale variant retains its URL and an honest unavailable/current-listings-empty state; historical information may still render when supported. The detail API's syntactically valid key is not proof of current market presence, so check actual returned observations/variant membership before labelling it available.

Explorer and Deal Finder use the same link builder and navigation function. Provide actual anchors for item names/actions so keyboard activation, Copy link and opening a new tab work. Preserve tooltip buttons and variant expansion as separate controls; avoid nested interactive elements. Add a clearly visible Back to Explorer link and contextual breadcrumb. Item Details gets a page title and heading but no permanent sidebar entry. Details can retain Explorer as the contextual navigation section.

Keep existing session cookies, CSRF handling, permissions and private cache clearing. A pasted item URL must survive sign-in, session expiration and reload. No token or credential belongs in the URL. Resolve the route after session restoration; preserve companion/invitation flows. Accept only internal, validated return destinations. On direct entry without a history origin, Back to Explorer uses a safe Explorer URL scoped to the linked market rather than an unrelated external browser-history entry.

## Explorer state restoration

Define one validated Explorer-state model and make the table controlled by it: market, applied search, all supported filters, sorting, page index and page size. Current sort/page-size preferences remain defaults; navigation state takes precedence. Encode applied state in the Explorer query string using a bounded allowlist, for example `/?market=2&q=cloth&sort=name&direction=asc&page=2&page_size=25`. Page indexes stay zero-based to match the API. Add only filters actually supported by the existing table/API, with explicit serialization as implementation discovers them.

Before leaving Explorer, replace the current Explorer history entry with its complete normalized URL/state, then push the item destination. Store optional draft input, scroll position, focused row and expanded parent IDs in that history entry or an account-scoped in-memory restoration map. These extras are not required to understand a shareable URL. Clear restoration state on account change/logout, alongside the existing private query cache. Never put private API responses into browser storage for restoration.

On Back/Forward, restore state before starting catalogue requests; do not allow default preferences or mount effects to reset the restored page. Apply market/query/page atomically and cancel obsolete requests. Preserve the existing preference choices without writing transient search/page state into the global server preference schema. Use the existing query cache to render quickly, then show freshness while refreshing. If a changed population invalidates the old page, clamp to a valid page and explain the refresh; promise restored browsing controls, not an unchanged live dataset. Restore focus/scroll after rows mount. A new-tab details link must work without any restoration memory.

Variant changes within Details should replace its variant query by default so one Back returns to the originating Explorer/Deals entry. The visible return link uses a validated saved origin; direct links fall back to Explorer. Preserve Deal Finder filters/results while returning through its own history entry, without conflating them with Explorer state.

## Item Details content and data behavior

Move the existing research presentation into an independently mounted details component, with a route-derived market/item/variant rather than catalogue selection as its source of truth. Keep Explorer's page focused on its search/filter controls, freshness and item table. Remove automatic offscreen research updates and speculative first-item research fetches from Explorer.

The details header contains the existing icon, quality-colored name, numeric identity, variant caption/selection, market identity, source attribution and freshness. Use the existing profile endpoint for metadata/provenance even on direct entry; do not rely on props inherited from an Explorer row for quality or attribution. Keep unknown fields readable and neutral, preserve community/beta qualifications, and retain source build/locale and observed timestamps.

For an exact variant, retain current lowest buyout, recent price, market reference, supply/listing counts, price-history range controls, supply distribution and paged current listings. Continue treating listings as asking prices rather than sales. Parent prices remain labelled ranges; individual listing stack quantity never becomes market supply. Keep copper values as existing strings and render through `Currency`; preserve algorithm identifiers, historical gaps and coverage notices. Changing market or variant changes every relevant query key, and stale responses must not appear under a new identity.

Load charts using their current lazy/explicit controls and bounded endpoints. Avoid duplicate profile/history/listing fetches from copying components. Reuse cache keys where semantics match and include account, market, item, variant and range dimensions as applicable. Keep normal polling/cancellation/freshness behavior; a component split must not increase background collector/provider work or change request budgets.

Use an accessible heading hierarchy and main-content focus on route navigation. Retain table horizontal scrolling on small screens, stack summary/chart panels responsively, and keep touch targets usable. Show skeleton/status text during initial load, independent retryable section errors, missing metadata, no listings, no history, unavailable market and invalid-link states. Existing metadata can remain visible when a chart or listings request fails. Honor reduced motion and preserve tooltip/dialog focus behavior. Supporting text stays muted; item names use the shared exact-quality mapping and readable text size.

## Legacy links and compatibility

Before implementation, inventory actual UI, documentation, email templates and companion links. Preserve `/`, `/deals`, `/administration`, `/account`, `/companion`, `/companion/authorize`, invitation query handling and all `/api/v1` contracts. No persistent item deep-link format was found in the inspected workspace: current Deals-to-Explorer focus is in memory. Do not invent redirects for a nonexistent format or claim a lost in-memory selection can be recovered after reload.

For any genuine old item link discovered, parse only its documented ID/market/variant fields and replace with the canonical internal item URL, preserving meaningful state. Use a client-side replacement for SPA/hash aliases where a server cannot see the fragment. Never redirect by item name or guess a variant. Incomplete but recognizable links may open the parent overview; malformed or ambiguous ones show a safe explanation and Explorer link. Unknown routes should have an explicit fallback rather than silently behaving like an unrelated item. Test Caddy direct navigation/reload and ensure API paths and signed companion downloads are unaffected.

## Small implementation checkpoints after authorization

1. Add the route/state parser, canonical link builder and controlled Explorer-state interface. Cover direct entry, auth restoration and browser history before changing research layout. Keep the current sidebar and other routes working.
2. Extract the existing research body into Item Details, wire route identity and reuse profile/variant APIs. Add the parent variant overview without inventing parent exact prices. Verify existing price/history/listing fixtures and shared quality rendering.
3. Switch Explorer row/variant links and Deal Finder inspect actions to the common destination. Remove offscreen selection-driven research, implement complete Back/Forward restoration and safe known legacy aliases.
4. Complete responsive/accessibility/error handling, capture isolated desktop/mobile visual evidence and inspect it. Run appropriate backend contract/regression, frontend, browser and Windows CI checks on the exact candidate; commit/push review checkpoints. Deliver a separate visual review before any deployment.

All implementation commits belong to this milestone, separate from administration source changes. Start from the reviewed integration state applicable at authorization; do not assume the current candidate has already been deployed. No schema migration is expected. If an actual API/provenance gap is demonstrated, propose the smallest additive compatibility change and test it; do not expand into analytics redesign.

## Acceptance matrix

| Owner requirement | Required evidence before requesting visual approval |
| --- | --- |
| Focused shared-table Explorer | Search/filter/sort/page remain usable; no research panels or automatic first-item analytics below the table. Existing grouped variants remain browseable. |
| Dedicated research destination | Parent, exact variant and Deal Finder links reach the same details route; keyboard/new-tab/copy-link behavior works. |
| Complete existing research | Current values/supply, both charts, listings, variants, metadata/tooltips, provenance and freshness survive extraction. Existing algorithm fixtures match before/after. |
| Identity and money preservation | Two distinct variants retain distinct URLs/queries/prices; wrong market/key never silently substitutes; exact copper strings and ranges remain correct. |
| Authentication/shareability | Pasted URL → signed-out login → same item; reload, expired session, cross-account cache clearing and unavailable market states pass. |
| Restored browsing | Set search/filters/sort/page/page size → open item → Back restores all; Forward, scroll/focus, cache refresh/page clamp and direct-entry fallback pass. Return from Deals preserves its own browsing state. |
| Reuse and visual design | Existing chart, API, icon, `Currency`, `ItemName`, tooltip/provenance and table implementations are reused. Espresso/bronze screenshots show no permanent Details sidebar entry. |
| Responsive/accessibility/states | Desktop/narrow screenshots, axe/keyboard/focus checks, chart/listing empty/error/loading, missing metadata and unavailable variant checks pass. Exact common/uncommon/rare/epic names retain their stored colors. |
| Legacy compatibility | Verified legacy aliases safely resolve; Caddy reloads canonical URLs; companion auth/downloads, invitations and old API tests remain green. |
| Operational preservation | Isolated fixtures only; no collector, valuation, market configuration, provider budgets or historical-data mutation. Production unchanged until separately authorized promotion. |

No implementation or deployment follows from this plan. The next owner instruction must authorize implementation; a completed, tested visual candidate then comes back for its separate promotion approval.
