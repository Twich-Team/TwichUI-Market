# Crafting Writs

Open **Crafting Writs** in Market. Select a profession, market, price basis and completion method. **I already own the writ** removes the writ purchase from this estimate. Select **Details** to see the required delivery, craft batch, materials, whole auction stacks and reward source. Maximum recipe skill limits the crafting scenario. Confirm recipes you can use in the row details. Each confirmation applies to the current browser scenario.

The default order is ascending copper per base reputation point. Eligible totals and ratios use exact rational arithmetic before display rounding. Each comparison is for a single completion. Writs with unconfigured reputation can still show purchase and completion costs. Auction house seller fees, bonus reputation, Legacy effects, coin pouches, item rewards and resale proceeds are excluded.

## Price bases

- **Current minimum buyout** uses one pinned observation in the selected market, with exact base-item identities and posted buyouts. An indivisible auction stack is charged in full. Divisible commodity lots can fill exactly the required quantity. The calculator combines repeated quantities before allocating stock. The cheapest whole-stack combination that covers the quantity at the observed minimum is charged, including overshoot. A minimum unit valuation may display when stock cannot cover the purchase at that price. It cannot enter the current-purchase ranking. Bid-only listings are excluded.
- **14-day price** uses Market's quantity-weighted asking-price reference from the last observation on each UTC day. Priced days enter the window with Market's existing coverage and quality safeguards. It represents a reference valuation with no promise of available stock.
- **Regional price** remains unavailable until Market has a regional reference with defined ruleset and faction scope.

Direct recipe cost uses the ceiling of delivery quantity divided by deterministic output. It sums all inputs for the required craft count and compares the lowest fully eligible direct recipe or recipe combination. Variable output, unknown skill, and unconfirmed recipes cannot produce an eligible craft ranking. The calculation buys direct inputs and excludes recursive subcrafting.

## Administration

**Administration → Crafting Writs** shows the local coverage and the worker's latest status. Per-writ override takes precedence over a tier value, followed by any verified provider reward. Clearing a setting restores that inheritance. Positive whole-number edits use revision checks and create a Security Events audit entry. The comparison reads current settings, and the website invalidates its private comparison cache after a save.

The additive Alembic revision `writs_20261125` creates the separate reward table with all defaults unconfigured. Follow the established deployment sequence to migrate before replacing the API. Application rollback uses the previous images with the additive schema in place. The migration refuses downgrade after an administrator has recorded a setting. Provider refreshes write catalogue and metadata data independently of rewards.

See the [Forever edition sources, catalogue scope and worker cadence](crafting-writs-sources.md). Market data freshness and catalogue confirmation have separate timestamps.

## API

| Method and path | Access | Operation |
| --- | --- | --- |
| `GET /api/v1/crafting-writs` | Signed-in member | Compare by `market_id`, `basis`, `method`, `owned`, optional `profession`, `max_skill` and repeated `confirmed_recipes` |
| `GET /api/v1/admin/crafting-writs` | Administrator | Review coverage, metadata jobs, provider observations and saved reward values |
| `PUT /api/v1/admin/crafting-writs/rewards/{scope}/{key}` | Administrator + CSRF | Save `{"reputation":80,"revision":0}` for a tier or exact writ ID. Use `null` to inherit. Concurrent edits return HTTP 409. |
| `POST /api/v1/admin/crafting-writs/refresh` | Administrator + CSRF | Queue bounded work through the existing provider worker |
