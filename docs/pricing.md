# Asking-price definitions, version 1 (provisional)

All monetary values are copper. Listings are not transactions. Bid-only listings contribute to total observed supply but never buyout references. Item variants are calculated separately using a canonical JSON item descriptor hash. Source kinds and markets are never combined implicitly.

Recent price is the latest snapshot's quantity-weighted mean asking price: sum(stack buyouts or commodity unit_price × quantity) / sum(priced quantity). A stack buyout is a total, never a unit price. Round half up to one copper only after division. Lowest buyout uses minimum exact per-unit asking price, rounded half up. Missing current supply produces null prices, not a zero-copper price or inferred sale.

14-day market value and 60-day historical value are arithmetic means of daily recent prices, choosing the last observation on each UTC day inside the respective rolling window. This prevents polling frequency from overweighting a day. Days without a priced listing are excluded and coverage_days is exposed. No interpolation or synthetic observations are created to fill gaps. The current observation's age is exposed separately; a fresh HTTP check does not prove the upstream snapshot is fresh.

Algorithm identifier: `asking-v1-provisional`. These project definitions preserve the requested quantity weighting and time windows, but exact TwichUI Workshop compatibility has NOT been verified. Workshop reference formulas and known output fixtures remain required. Add a new algorithm version for any semantic change; do not silently change historical interpretation.

Synthetic regression cases cover unequal stacks, rounding, commodities, bid-only listings, daily sampling, empty latest supply, market isolation and variant isolation. No live fixture is currently available.
