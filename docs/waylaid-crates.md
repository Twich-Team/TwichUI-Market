# Waylaid Crates

Sign in to Market and open **Waylaid Crates**. Use the selected market, compare the cheapest complete filling choice, and open **Choose one** to inspect all alternatives. **I already own the crate** compares cash to spend now and removes only the purchase cost of the empty crate.

Administrators can edit the Common crate tier settings and queue a refresh under **Administration → Waylaid Crates**. Initial settings are Apprentice 5, Journeyman 10, Expert 15 and Artisan unconfigured. Saving a blank field records an explicit unconfigured value. A stale form cannot replace a newer edit. The Security Events ledger records each accepted change with its actor, time and revision.

## Catalogue and rewards

The authenticated ForeverDB v1 response from 2026-11-25 05:32:59 UTC, build `1.60.1.71091`, identifies 30 Waylaid Crate item IDs and 96 accepted one-material options. One option fills a crate. Each quantity and required level comes from the response. The cache retains source/build, digest, attribution, generation time and last successful confirmation. [ForeverDB developer documentation](https://foreverdb.net/developers)

The endpoint lists 15 distinct sealed items and describes sealing as a general outcome. Exact empty-to-sealed item mappings and per-crate payouts are absent. Three sealed qualities can share a tier name. The calculator applies locally configured baseline favors to the 18 Common empty crates with supported filling mappings. The 12 Uncommon crates display available costs with their reward unavailable. Bonus Favor and cash turn-in rewards are excluded. A new source-backed tier starts unconfigured. Unrecognized mappings remain visible with an unavailable state.

The enrichment runner checks the catalogue daily through the shared ForeverDB quota, worker lease and retry logic. It queues at most 12 missing exact metadata IDs per successful refresh. Conditional requests reuse the response ETag when supplied. A failure preserves the last validated generation and its last successful confirmation. That confirmation becomes stale after two refresh intervals. Set `FOREVERDB_MERCHANTS_FAVOR_REFRESH_SECONDS` in the runner environment to change the cadence (3,600–604,800 seconds), or set it to `0` to pause scheduled requests and retain manual enqueue. Manual enqueue uses the same budget and backoff.

## Price bases

- **Current minimum buyout** values the required quantities at the selected market's lowest observed buyout per unit for the exact base item. A commodity lot supports partial quantities. An auction listing requires its entire stack. Stock at the minimum is checked against observed buyouts, including whether whole stacks can add up to the required quantity. Bid-only listings contribute no buyout stock. A price estimate with insufficient or unknown depth is ineligible for the current recommendation.
- **14-day price** is Market's asking-price reference for the selected market and exact base item. It averages each priced day's quantity-weighted unit ask from the last observation on that UTC day. Missing days are skipped. Limited coverage and suspect price distributions retain Market's reference-quality safeguards. This is a reference estimate and does not require current listings.
- **Regional price** remains unavailable until Market has a regional reference with a defined ruleset and faction scope. Selecting it leaves price inputs unknown.

The fill cost adds the required quantities times their unit prices for **one** accepted option. The total adds the empty crate purchase, or zero for a crate already owned. The ratio divides the total by configured Favor. The comparison keeps unrounded ordering and rounds coin displays. Missing inputs stay unknown. Purchases exclude selling fees, recursive crafting, turn-in cash and resale assumptions.

## API

| Method and path | Access | Purpose |
| --- | --- | --- |
| `GET /api/v1/waylaid-crates?market_id=2&basis=current&owned=false` | Signed-in website member | Local catalogue and quotes for `current`, `regional` or `14d` |
| `GET /api/v1/admin/waylaid-crates` | Administrator | Reward revisions, catalogue status and last refresh result |
| `PUT /api/v1/admin/waylaid-crates/rewards/{tier}` | Administrator + CSRF | Save `{"favor":5,"revision":1}`, or set `favor` to null. A stale revision returns HTTP 409. |
| `POST /api/v1/admin/waylaid-crates/refresh` | Administrator + CSRF | Queue or reuse the active bounded refresh job |
