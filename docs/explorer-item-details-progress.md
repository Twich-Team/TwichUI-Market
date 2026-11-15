# Explorer / Item Details implementation ledger

Owner authorization: implement fully, push a separate feature branch and open a draft PR; stop before production promotion pending final visual approval. Phase 1 is deployed at `e9c4d29`, with integration acceptance through `9ce465a`. Feature branch: `feature/explorer-item-details`; target: `integration/companion-v2-metadata-recovery`.

## Navigation foundation

Added strict supported-integer and exact lowercase 64-character variant route parsing, canonical item URLs, bounded Explorer query serialization, safe internal browsing origins and account-cleared bounded transient restoration. Added focused unit cases for valid/invalid identities, missing routes, browsing round trips, limits and unsafe redirects. This checkpoint does not yet change the existing UI. Existing deep-link inventory finds no prior persistent item route: Deals used an in-memory Explorer selection. Existing invitation, Companion authorization/download and API paths remain separate contracts.

Next: wire controlled catalogue/Explorer state and dedicated independently loaded Item Details; switch Deal Finder anchors; complete restoration, responsive/error/accessibility checks, update browser workflows for the new navigation, and produce the final ten-scene visual gallery with exact-source CI. Production image pins and collector remain untouched by Phase 2.

## Dedicated experience candidate

Explorer now uses controlled TanStack catalogue state from the URL and contains no research or automatic first-item variant/detail request. Item names and variant actions are real canonical anchors. The dedicated route independently loads metadata/provenance and current overview; exact variants reuse price history, supply distribution and current auctions. Parent overview ranges never select a variant. Missing routes/markets/variants and independent section failures have explicit states and retries. Single-variant exact pages avoid redundant selection tables. Shared item colors, tooltip/icon behavior, copper formatting, algorithms and all API/schema contracts remain unchanged.

Applied Explorer and Deal Finder controls are URL-backed; preference defaults cannot overwrite restored links. Bounded, account-cleared transient history entries retain draft input, expanded parents, scroll and focus, without storing API responses or browser-storage payloads. Exact variant switches replace the item URL; safe returns point to their own browsing origin. The catalogue page clamps when live counts shrink and explains the adjustment. Cells retain stable identities so restoring expansion does not replace a focused link.

Verification: navigation/default/identity/cache-isolation unit cases added; TypeScript and the 109-test frontend suite pass. Targeted restored-focus/scroll/paging and 3,651-day chart workflow pass. A fresh full **32-workflow browser run passed** against the isolated `market_test` stack. All seven new research/navigation/performance workflows passed again after the final tooltip, title and range-state refinements. Final source CI and the reviewed visual/performance packet are still pending. No production image, market data, provider settings, collector or infrastructure changes are part of this feature branch.

The final candidate also tests direct supplemental attribution/neutral quality and an explicitly simulated disappeared-variant response that retains real fixture history without mutating any database. The full CI browser inventory is now 34 workflows; final CI remains pending.
