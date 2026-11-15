# Explorer / Item Details owner review

**Complete, tested visual candidate — not deployed.** [Draft PR #4](https://github.com/Twich-Team/TwichUI-Market/pull/4), branch `feature/explorer-item-details`, targets the verified Phase 1 branch `integration/companion-v2-metadata-recovery`. Production remains the approved administration release **`e9c4d29`**. Final visual approval is required before any Phase 2 production promotion.

Implementation checkpoints: navigation foundation **`75fffd1`**, complete application **`b3e48bd8408cfb7ba09115abfc3ccc12a721d480`**. The integration baseline is **`9ce465a00c159283b9b64d5abfcb089d8056f5a5`**; [Phase 1 acceptance](admin-modernization-release-acceptance.md) records its release, backup, restoration, preservation, HTTPS and collector evidence. Later review documentation preserves the frozen application tree.

## Result and data semantics

Explorer now contains market/search controls, current auction freshness and the existing TanStack catalogue with sorting, pagination, icons, quality-colored names and expandable variants. It makes no first-item variant/detail/history/distribution request and does not load ECharts. Names are real shareable anchors; research no longer appears beneath the table. Existing column preferences remain available.

The independently loaded research destination is `/markets/{marketId}/items/{itemId}`, optionally `?variant={64-character lowercase hex key}` and a validated `days` range. Positive supported integer identities are required; names never determine identity. Parent URLs show actual ranges and total supply across current variants. They request an explicit variant before showing exact prices or charts, including when only one variant currently exists. Exact URLs retain their identity even when the variant disappears. An unavailable linked market never silently switches to an account default. Unknown paths have an explicit fallback. Direct navigation, authentication, page reload and new-tab links work without first visiting Explorer.

Item Details reuses the existing profile/provenance, item tooltip/facts/name, currency, chart and listing components/APIs. Exact current lowest buyout, quantity-weighted recent asking price, 14-day reference, supply and listing counts remain unchanged. Price history preserves 7D–10Y ranges, reference overlays, zoom, historical gaps, exact copper tooltips and accessible/virtual long-history tables. Supply distribution and current auctions retain bid-only distinctions, unit/stack prices and server pagination. Selecting a variant replaces the canonical URL and preserves a linked chart range. Single-variant exact pages omit a redundant selection table so analysis follows the current overview.

Metadata, source attribution, supplemental licenses, verified/unknown fields and build identity load independently for direct links. Shared `ItemName` retains all seven exact WoW colors and neutral unknown quality. No new pricing algorithm, schema, API endpoint, dependency, table library, chart library, provider integration or desktop release was introduced. Asking listings are never labelled completed sales; parent ranges are never blended into an exact variant price.

## Navigation and isolation

Applied market, search, sort/direction, page index and page size live in the Explorer URL. Deal Finder uses its own URL for applied mode/threshold/spend/coverage/evidence/direction. Existing preference defaults initialize a fresh browsing URL; they cannot override restored navigation. Existing calculations and submitted-filter behavior remain intact.

Opaque history-entry keys point to a bounded 50-entry memory map for optional drafts, expanded parents, scroll and focused row. No private API response or credential is stored there or in browser storage. The map clears with the existing private cache on logout/account change. Back/Forward restores controls before catalogue requests; invalid saved result pages clamp with an explanation. The focused link survives because cell identities remain stable when expansion state restores. Safe contextual returns preserve their own Explorer/Deals origin; direct entries fall back to Explorer scoped to the linked market. Item Details is not a permanent sidebar entry.

## Verification

All canonical PR workflows pass for frozen source `b3e48bd`. GitHub's PR preview **`b18cf9b82712fc29801b976360c2263df0bb863f`** has the same application tree as that head and the verified integration base; the workflow's source check validates its actual combined checkout. These are review checks, not production release approval. [Full workflow/job/step receipt](evidence/explorer-details/ci.json).

| Verification | Result |
| --- | --- |
| [Backend 43684211780](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43684211780) | Green: complete unchanged 380-test PostgreSQL suite, schema/migration rehearsals, 34 operational checks and Python dependency audit. |
| [Website 43684211813](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43684211813) | Green: TypeScript/Vite, 109 frontend tests, npm audit, all **34** fresh Chromium workflows and evidence upload. |
| [Windows 43684211957](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43684211957) | Green: native/protocol checks, installed release, actual legacy upgrade and signed SDK updater/retained-data acceptance. |
| Local full browser regression | 32 passed before the two final attribution/disappeared-history cases were added. All nine new research workflows subsequently passed again on frozen source; CI passes the complete 34-workflow inventory. |
| Accessibility | Zero WCAG A/AA/2.1 AA axe violations in Explorer, exact Details, missing-data Details, rare variant and 390px layouts. Separate pinned-image scans cover both exact Details and parent variant tables. Keyboard tooltip, long-table and navigation checks pass. |
| Preview packaging | Revision-labelled image `sha256:d813a468dc57e01df276b19ef5b52ff9b901ea9beb0692133cf88c40e200addf`; all 13 assets match the verified local build. Direct route/reload and actual screenshots pass from this image against isolated fixture APIs. |
| Compatibility | Existing invitation/sign-in, administration, account/preferences, Companion download/approval, ownership/revocation and all `/api/v1` contracts remain covered. Backend/schema/contract/desktop source is unchanged from Phase 1. |

The new workflows cover invalid IDs/variants, direct-link sign-in, new tabs, parent/exact links, preserved search/sort/pages/size/expansion/focus/scroll, Back/Forward, live-result page clamping, Deal Finder returns, two distinct variant prices/quantities, exact market isolation, independent failures/retries, attribution, rarity colors, lazy chart loading and narrow layouts. The disappeared-variant case is an explicitly synthetic response transition retaining fixture history; it does not mutate a database or claim a live market event.

Raw local verification excerpts are committed alongside [performance](evidence/explorer-details/performance.json), [accessibility](evidence/explorer-details/accessibility), [asset receipts](evidence/explorer-details/pinned-assets.json) and [screenshot hashes](evidence/explorer-details/screenshots.json). The successful website run also retains the review artifact, ID **14148959160**, digest `sha256:3fa44c98ab93a59c8598b0b696affbedec43ad0964374d56e912c6e761a626ca`. Direct unauthenticated job-log download was denied; workflow/job/step status and source identities were verified through the available GitHub APIs instead.

## Screenshot gallery and visual inspection

[Open the ten-scene gallery](evidence/explorer-details/review.html). Every image is an actual Chromium capture of **isolated synthetic acceptance data**, not live market evidence. The final required scenes were recaptured from the pinned image. The main gallery uses America/Denver browser dates; the supplementary rare-variant workflow uses UTC. Unknown artwork retains the existing placeholder rather than invented game assets.

| Scene | Actual capture |
| --- | --- |
| 1. Explorer, normal results | [Open](evidence/explorer-details/screenshots/explorer-normal.png) |
| 2. Explorer, applied search and controls | [Open](evidence/explorer-details/screenshots/explorer-search-filters.png) |
| 3. Common exact item | [Open](evidence/explorer-details/screenshots/details-common.png) |
| 4. Epic exact item | [Open](evidence/explorer-details/screenshots/details-epic.png) |
| 5. Multiple variants and parent ranges | [Open](evidence/explorer-details/screenshots/details-multiple-variants.png) |
| 6. Historical price and supply charts | [Open](evidence/explorer-details/screenshots/details-price-supply-charts.png) |
| 7. Current auctions | [Open](evidence/explorer-details/screenshots/details-current-auctions.png) |
| 8. Missing metadata/history | [Open](evidence/explorer-details/screenshots/details-missing-metadata-history.png) |
| 9. Deal Finder → Details | [Origin](evidence/explorer-details/screenshots/deal-finder-origin.png) · [Destination](evidence/explorer-details/screenshots/deal-finder-to-details.png) |
| 10. Narrow/mobile research | [Open](evidence/explorer-details/screenshots/details-mobile.png) |

Inspection confirms the espresso/walnut surfaces, restrained bronze controls, ivory supporting text and exact rarity colors remain consistent with the approved direction. Identity and current market values lead; charts and auctions follow, with provenance lower down. Single-variant exact pages avoid redundant controls. Variant price ranges, unit/stack quantities, missing-data notices and source credits remain readable. Narrow pages have no document overflow; wide data tables scroll within their sections. Route navigation focuses the main heading, and returning to browsing restores the originating link. This engineering review does not constitute owner visual approval.

## Performance and limits

Three isolated one-CPU Chromium contexts measured median **1,302 ms** from initial navigation through fixture sign-in to populated catalogue, **1,082 ms** for parent-plus-exact item navigation, and **207 ms** for Back. Return navigation made **zero catalogue requests** in those samples. Initial encoded JavaScript was **148,782 bytes**, with no ECharts request from Explorer. These are bounded local fixture measurements, not production p95 or a before/after speedup claim. Existing 3,651-calendar-day history still uses a bounded virtual/paginated row window.

Applied controls survive refresh through URLs; optional draft/expansion/scroll/focus extras are bounded and disposable across logout, account changes or a full new process. Live results can change, so an identical historical result population is not promised. Catalogue rows open the parent overview; the user chooses an exact variant for analysis. Fixture artwork can be unavailable; no icon coverage increase is claimed. The established large lazy ECharts chunk remains. Owner-PC tray behavior and off-host keyring copies remain the earlier documented limitations; this feature does not add a desktop release or claim new manual Windows acceptance.

The isolated, resource-limited pinned preview is HTTP at `127.0.0.1:18444`, backed only by `market_test`, with no collector/provider worker. It is not connected to production data. [Final read-only production check](evidence/explorer-details/production-unchanged.json) verifies trusted public HTTPS, unchanged production container identities, schema `meta_20261114`, sole house-114/market-2 collector at 300 seconds with zero failures, and zero retention batches. Phase 2 performed no production promotion or data mutation.

## Exact promotion boundary

1. Obtain explicit final owner visual approval of this implementation and gallery. No approval is inferred from tests, elapsed time, a draft PR or this report.
2. Refresh the actual production/integration identities and the owner's current provider/account settings. Integrate the frozen approved feature with only genuine conflict repairs; require canonical CI on the **exact final integrated commit**. PR preview checks alone are not release-admissible.
3. Preserve existing images/environment/keyring/volumes and prepare the immediately preceding frontend rollback. Take a fresh checksummed backup, verify it through isolated restore and confirm all original data/permissions and the unchanged schema; no migration is expected. Preserve collector identity/schedule, accounts, sessions, preferences, device authorizations, encrypted credentials and source budgets/settings.
4. Build/pin the approved revision and use the established complete production configuration with a narrowly scoped frontend image overlay. Backend source is unchanged, so retain compatible API/worker images unless a separately verified integration repair requires replacement. Do not start a collector or alter Traefik, AMP, Komodo, networks, retention, provider enablement or budgets.
5. Verify actual public HTTPS authentication/session/preferences continuity, Explorer/Deals returns, direct/reloaded parent/exact research, charts, listings, provenance/colors, administration and Companion compatibility. Confirm ongoing house-114 collection, history/credential preservation and bounded resources. Roll back only the frontend for a genuine release regression, retaining every database record/schema and diagnostic receipt.
6. Commit/push deployment acceptance only after those checks. **None of these production promotion steps is authorized by completion of this review candidate.**
