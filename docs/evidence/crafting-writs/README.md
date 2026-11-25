# Crafting Writs browser review

Authenticated application review in the isolated `market_test` environment on November 25, 2026. Chromium used 1440 CSS pixels of width. WebKit used the iPhone 13 device profile at 390 CSS pixels.

| View | Desktop | iPhone |
| --- | --- | --- |
| Member comparison and profession filters | [Comparison](member-desktop.png) | [Filters](member-iphone.png) · [Comparison card](member-card-iphone.png) |
| Recipe, eligibility and direct inputs | [Delivery details](details-desktop.png) | [Delivery details](details-iphone.png) |
| Administration | [Status and tier settings](admin-desktop.png) | [Status](admin-iphone.png) · [Tier settings](admin-settings-iphone.png) |
| Captured observations | [Stale current-buyout view](captured-prices-desktop.png) | |

Market 3 is the review fixture. Its prices, lot sizes and reputation settings are controlled sample values. The review also used 2,133 exact-item listing rows and 12 daily observations copied read-only from market 2, with current snapshot 236 retrieved at 10:22 a.m. Mountain Time. The copied observation aged out of the current ranking, while its available prices continued to display with the stale status. The screenshots include cached item art.

Before the settings edit, unknown reputation kept every row out of the ranking, while priced delivery costs remained visible. Saving the three sample tier settings enabled ranking in the fixture market. Those settings persisted across an API restart. A member received HTTP 403 on the administrator API. Confirming Elixir of Defense changed the preferred route from buying to crafting in the fixture, for 1,586 copper at a configured reward of 80. Already-owned mode removed 1,121 copper of writ cost. The craft basket included a whole stack of three Wild Steelbloom with two extra units.

Both browser engines displayed the authenticated member and admin pages with zero horizontal page overflow, zero JavaScript or API server errors, and zero axe violations in the member page scan. Focused browser tests separately exercised keyboard disclosure, item-link return focus, 320px layout, concurrent edits, pricing errors and Waylaid Crates. All settings edits and refresh simulations used the isolated database.

The final local application verification passed 866 PostgreSQL tests, 164 frontend tests, and 174 operational and bridge contract tests. The Windows workflow initially failed inside its native folder picker. On retry, the publisher passed and uploaded the complete acceptance artifact. The Lua consumer downloaded the artifact from the failed attempt, which lacked the large-market publication. A fresh run reproduced the folder-picker failure. The workflow now passes the exact uploaded artifact ID from the Windows publisher to the Lua consumer, so a same-commit retry exercises the complete publication. [Earlier Windows attempts](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45673993408).
