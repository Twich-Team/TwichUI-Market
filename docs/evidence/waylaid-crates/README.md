# Waylaid Crates review

Desktop Chromium (1440 × 1000 CSS pixels) and iPhone 13 WebKit (390 × 844 CSS pixels), reviewed on 2026-11-25. Both authenticated views use the isolated `market_test` review stack. The account names are review identities.

| Scene | Desktop | iPhone |
| --- | --- | --- |
| Member comparison | [Table and summary](member-desktop.png) | [Priced crate cards](member-iphone.png) |
| Choose one | [Accepted filling alternatives](alternatives-desktop.png) | [Material costs and stock](alternatives-iphone.png) |
| Administration | [Catalogue and reward settings](admin-desktop.png) | [Catalogue status](admin-iphone.png) |

## Evidence

The local cache was imported by the existing quota-controlled worker in the isolated environment using a replay of the authenticated ForeverDB build `1.60.1.71091` response. The screenshot's catalogue confirmation time records that replay. The price comparison uses 29,159 real listing rows copied read-only from production snapshot 225 on market 2, with 12 captured UTC daily observations and matching local metadata. The source was captured at 05:34:48 UTC. These are fixed observations and do not represent the current auction inventory.

| Scenario | Lowest comparable crate | Comparable rows |
| --- | --- | ---: |
| Current minimum buyout, buying the crate | Apprentice Herbs, 20 × Silverleaf, 10s 60c total for 5 Favor | 11 |
| Current minimum buyout, already owned | Journeyman Herbs, 10 × Bruiseweed, 7s 10c total for 10 Favor | 11 |
| 14-day reference, buying the crate | Earthly Expert Herbs, 72s 19c total for 15 Favor | 13 |
| Regional reference | No regional price source configured in Market | 0 |

Both engines exercised authenticated member and admin journeys, the chosen material icon and item link, the details control, the market-scoped Item Research route, return focus, basis changes, owned-crate mode and access denial. Both viewports had zero page overflow or API/server errors in that run. Isolated API access checks confirmed a member cannot read administration or queue or edit rewards, and an isolated Expert setting of 150 changed the ranking and persisted across an API restart. The test setting was reset to 15 before these captures.

The dedicated Chromium and WebKit fixture runs also cover numeric and sub-copper sorting, loading and retry, stale and missing data, reward validation and concurrent edits, and the 320px layout. The phone accessibility scans reported zero violations. Those fixture prices are synthetic. The captured runs made no in-game purchase or turn-in.
