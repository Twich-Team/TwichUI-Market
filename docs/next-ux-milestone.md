# Next UX milestone: Explorer and Item Details

Owner direction, November 14, 2026 (America/Denver). This is queued work. It does not expand or interrupt the Administration Table Modernization / Metadata Provider Investigation goal.

## Problem and intended experience

Selecting an Explorer row currently updates research farther down the same page, often offscreen. Explorer should focus on browsing, and an item selection should open a dedicated research page.

## Recorded requirements

1. Keep Market Explorer focused on search, filters, sorting and browsing through the existing shared TanStack table.
2. Navigate item selections to a dedicated Item Details page.
3. Carry all existing research into that page: current price/supply, history charts, listings, variants, metadata and tooltips, including provenance and freshness.
4. Preserve pricing algorithms, market scope, currencies and exact variant identities.
5. Provide stable shareable item URLs compatible with existing authentication.
6. Restore Explorer search, filters, sorting and pagination on Back.
7. Route Deal Finder item selections to the same details page.
8. Reuse existing charts, APIs, icons, coin formatting and shared table components; do not duplicate analytics.
9. Keep Item Details out of permanent sidebar navigation.
10. Preserve the approved clean espresso/bronze design.
11. Include responsive accessible layouts and loading, empty and error states.
12. Preserve legacy deep links or provide safe redirects where possible.

## Sequence and authorization

Finish the current administration/provider goal first. Then prepare a separate implementation plan covering routing/authentication, Explorer state restoration, reusable research components, legacy links and acceptance tests. No implementation or deployment is authorized by this recorded direction; both require another owner instruction. Keep collection and historical data untouched. Planning documentation must remain a separate Git commit from administration implementation changes.

## Prepared implementation plan

The current administration/provider goal reached its complete review boundary at `96f88a0`, with production unchanged. The separately prepared [implementation plan](explorer-item-details-plan.md) now covers inspected routing, reusable research/API components, exact variant URLs, authentication, Back restoration, legacy compatibility and acceptance evidence. No implementation or deployment is authorized.
