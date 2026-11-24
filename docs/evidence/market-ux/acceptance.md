# Browser acceptance

Application source `0c2b3540bffa0ac55a6e7c2de8f500ab4737e258` was deployed to the isolated review environment and tested on November 24, 2026. The environment uses synthetic auctions and simulated backup management. [Review access and fixture provenance](../../market-ux-preview.md)

The matrix covers 22 views as a member or administrator in Playwright Chromium and WebKit. Phone profiles used touch and mobile emulation at 375×667, 390×844, 430×932, and 844×390 CSS pixels. Desktop profiles used 980×800, 1280×900, and 1728×1080, plus 1280×800 with 200% document CSS zoom. The zoom case exercises CSS zoom. Native browser toolbar zoom and physical iPhone Safari were outside this run.

A pass requires the expected authenticated view, no page-level horizontal overflow beyond one CSS pixel of rounding, and no uncaught JavaScript exception or unexpected HTTP 5xx. Axe checked all views at 390×844 on phones and 1280×900 on desktop with WCAG 2.0 and 2.1 A/AA tags. Every row uses each profile’s four sizes.

| View | Chromium phone | WebKit phone | Chromium desktop | WebKit desktop | What rendered |
| --- | ---: | ---: | ---: | ---: | --- |
| Explorer | 4/4 | 4/4 | 4/4 | 4/4 | Search results for Training Sword, item cards on phones, and market controls. |
| Explorer · variants | 4/4 | 4/4 | 4/4 | 4/4 | Expanded exact variants with inspect links and contained comparison. |
| Item Research | 4/4 | 4/4 | 4/4 | 3/4 | Tough Jerky’s canonical detail view, price summary, and history. |
| Deal Finder · Below Reference | 4/4 | 4/4 | 4/4 | 4/4 | Selected mode and grouped opportunity results. |
| Deal Finder · Supply Changes | 4/4 | 4/4 | 4/4 | 4/4 | Selected mode and supply-change results. |
| Deal Finder · Price Changes | 4/4 | 4/4 | 4/4 | 4/4 | Selected mode and price-change results. |
| Account & devices | 4/4 | 4/4 | 4/4 | 4/4 | Preferences and device access. |
| Desktop Companion | 4/4 | 4/4 | 4/4 | 4/4 | Ordinary-member setup and Windows beta view. |
| Admin · Overview | 4/4 | 4/4 | 4/4 | 4/4 | Needs Attention and administrative summaries. |
| Admin · Markets | 4/4 | 4/4 | 4/4 | 4/4 | Configured markets and scheduling. |
| Admin · Collection | 4/4 | 4/4 | 4/4 | 4/4 | Collection health and check history. |
| Admin · Item Metadata | 4/4 | 4/4 | 4/4 | 4/4 | Metadata coverage and recovery entry points. |
| Admin · Data Sources | 4/4 | 4/4 | 4/4 | 4/4 | Provider review and statuses. |
| Admin · Members | 4/4 | 4/4 | 4/4 | 4/4 | Member access records. |
| Admin · Invitations | 4/4 | 4/4 | 4/4 | 4/4 | Separate invitation view. |
| Admin · Devices | 4/4 | 4/4 | 4/4 | 4/4 | Device authorization records. |
| Admin · Security | 4/4 | 4/4 | 4/4 | 4/4 | Security event view. |
| Admin · Recovery Tracker | 4/4 | 4/4 | 4/4 | 4/4 | Tracker and its dedicated heading within metadata. |
| Storage & Backups · Overview | 4/4 | 4/4 | 4/4 | 4/4 | Selected overview and storage summaries. |
| Storage & Backups · Backups | 4/4 | 4/4 | 4/4 | 4/4 | Selected backups view and archive inventory. |
| Storage & Backups · Storage | 4/4 | 4/4 | 4/4 | 4/4 | Selected storage view and destination management. |
| Storage & Backups · Maintenance | 4/4 | 4/4 | 4/4 | 4/4 | Selected maintenance view and retention health. |

**351/352 route checks passed on `0c2b354`.** All 88 Axe scans reported zero violations. The one failure was Item Research at WebKit 200% CSS zoom. The chart initially widened the page to 1720px in a 1280px viewport and returned to 1280px once the canvas resized.

Follow-up `8182b50` contains the chart canvas during the resize. The sequence Explorer → expanded Training Sword variants → Tough Jerky reproduced the overflow in five of five WebKit runs. With the containment rule applied in the browser, all five runs held the page to 1280px immediately and after the resize. The repository regression measures page width immediately after applying zoom.

## Focused interactions

- Explorer covered Enter/Search, Clear, Training Sword’s stable bonus IDs, sort and filter across 40 variants, pagination, and browser Back restoring the comparison, scroll, and focus. The dedicated desktop check used 1024×720 and 1220×720 in both engines. [Explorer and Item Research browser tests](../../../web/e2e/explorer-details.spec.ts)
- Research touch checks covered a long exact reference, a bounded item sheet and its restored trigger focus, tap tooltips, the lower-price view, full exact history, and the hourly range selector. A Chromium touch swipe beginning on the chart scrolled the page. [Research browser tests](../../../web/e2e/usability-reliability.spec.ts)
- Deal Finder browser tests cover grouped exact variants, stack expansion and paging, questionable references, and saved filters for all three modes. [Deal Finder browser tests](../../../web/e2e/deal-redesign.spec.ts)
- Backup browser tests cover UTC calendar navigation and daily summaries, inventory paging, protected eligibility, dialog dismissal, and empty and unavailable states. Preview data represents simulated operational outcomes. [Backup browser tests](../../../web/e2e/backup-management.spec.ts)
- Each profile signed in with fresh administrator and member sessions and verified both roles against the API. The member received HTTP 403 from the admin backup API and downloaded beta.12 with the advertised SHA-256 digest. [Installer provenance](../../market-ux-preview.md#provenance-and-isolation)

The [implementation inventory](../../market-ux-redesign-inventory.md) maps the routes and tables. The [physical iPhone checklist](../../market-ux-preview.md#what-to-review) covers the software keyboard, rotation, chart gestures, VoiceOver, and Safari Back.
