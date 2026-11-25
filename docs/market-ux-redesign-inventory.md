# Market UX redesign inventory

The route and table maps below identify implementation and behavioral checks. See the [review guide](market-ux-preview.md) for access and fixture provenance.

## Routes and shared implementation

| Route / view | Implementation mapping | Focused evidence |
|---|---|---|
| `/` Explorer; expanded variants | `research.tsx` + catalogue table in `catalogue.tsx`; TanStack Table drives catalogue sorting/filtering/visibility and specialized artwork/cards; variant data remains exact identity. | variant-label, catalogue and explorer-detail tests; phone Chromium/WebKit matrix |
| `/markets/:market/items/:item[?variant=…]` Item Research | `item-details.tsx`, charts in `charts.tsx`, optional `intraday-history.tsx`; ECharts with exact-data `DataTable`; Query cache/state in shared navigation/query. | chart-data, intraday-data, listing-prices, navigation tests; pricing-shadow and exact-stack logs; phone matrix |
| `/deals` Below Reference, Supply Changes, Price Changes | `deals.tsx`; shared `DataTable` for listing rows, shared Query/preferences, grouped opportunities and expandable stacks. | opportunities/preferences/listing-prices tests; `.local/review/exact-stack-review.log` (11 passed), `pricing-shadow.log` (2 passed), screenshots/matrix |
| `/administration` Overview | Module status cards in `admin-overview.tsx` link to the underlying evidence. Independent queries supply market, collection, metadata, provider, storage, backup and access status. The admin-only `/admin/access-summary` returns active account and invitation counts and the latest security event time. | Admin access summary authorization and aggregation tests, module link and status browser checks, desktop and phone visual review |
| `/administration?admin_tab=markets` | market configuration/schedules; `DataTable` markets. | market-configuration tests, admin screenshots/matrix |
| `?admin_tab=collection` | Health cards and a UTC activity timeline. A bounded server aggregate counts retained checks and snapshots independently. The paged run history uses `DataTable`. | admin-histories tests, admin screenshots/matrix |
| `?admin_tab=metadata` and `?metadata_view=tracker` | metadata coverage/records, recovery jobs and tracker; shared tables, Query, filters and server pagination. | metadata-coverage, metadata-attempts, recovery-tracker tests; admin/recovery matrices |
| `?admin_tab=sources` | Provider recovery summaries, rolling request meters, and provider-reported quota on the default cards. Source records and attempts use the shared tables. | provider-rate and metadata tests; admin screenshots/matrix |
| `?admin_tab=members`, `invitations`, `devices`, `security` | Account access views in `settings.tsx`; `DataTable` members/invites/devices and security history. | settings/admin-history tests; all four phone views in both browser matrices |
| `?admin_tab=storage` + `storage_view=overview\|backups\|storage\|maintenance` | `storage-dashboard.tsx`; shared shell/status, `DataTable` backup inventory, maintenance diagnostics and retention policy stages; `react-day-picker`-backed calendar in `backup-calendar.tsx`. | storage/backup/retention tests; phone screenshots; UTC calendar test log |
| `/account` | preferences, authorized devices and security; shared tables/Query. | preferences, account/cache tests and phone matrix |
| `/companion` | setup, connection/delivery status and beta download; shared Query. | companion-download tests, beta focused log and phone matrix |
| `/companion/authorize` | approval route; authentication/session gate then approval view. | companion callback/auth tests |
| unknown path | not-found view; navigation parser rejects malformed identities. | navigation tests |
| unauthenticated entry (including invitation registration) | login/register form in `main.tsx`; session restoration and invitation flow. | auth and browser checks |

Shared libraries verified in `web/package.json`: TanStack Table, Query and Virtual; Base UI; ECharts; React DayPicker. Application data grids use `DataTable` (`data-table.tsx`) except the catalogue’s specialized markup, which directly uses TanStack `useReactTable`. Calendar internals are semantic calendar markup, not an application data grid. Mobile adaptations use catalogue/variant cards and contained tables; screenshots are layout evidence only.

## Logical application data tables

The catalogue uses TanStack directly with specialized link, art and card rendering. Exact variants and the other data grids use the shared `DataTable`. The calendar supplies its own semantic grid.

| Logical table | Route(s) | Shared mapping / mobile behavior |
|---|---|---|
| Catalogue items; exact variants | Explorer | TanStack catalogue with phone item cards. Expanded variant comparison uses shared `DataTable`, a stable variant key, server sorting/paging and responsive cards. |
| Current auction listings | Item Research / listing detail | `DataTable`; contained mobile table |
| Matching listings / grouped deal stacks | Deal Finder | `DataTable`; expandable grouped results |
| Exact price-history observations; intraday observations; supply-by-price bands | Item Research | `DataTable` disclosures beside ECharts; scroll-contained on narrow screens |
| Markets and collection runs | Admin Markets, Collection | `DataTable`; phone matrix covers both |
| Metadata provider health, unresolved names, field coverage, provider attempts, recovery jobs and job results | Admin Metadata / Sources, Recovery Tracker | `DataTable`; large records paginated; phone matrix covers views |
| Recovery efficiency by provider; recovery items | Recovery Tracker | `DataTable`; server pagination/sorting for items |
| Members, invitations, authorized devices | Admin access; Account | `DataTable`; phone matrix covers these routes |
| Security events | Admin Security, Account | `DataTable`; filtered/server-backed history |
| Managed backup inventory | Storage Backups | `DataTable`; inventory selection/actions retained in responsive contained presentation |
| Ingestion/cleanup counts, measured database allocation history, retention policy stages | Storage Maintenance | `DataTable` in progressive disclosures |
| Backup calendar day outcomes | Storage Backups | Calendar component, intentionally not forced through TanStack; selectable date summaries |

This inventory was assembled from all `DataTable`/`useReactTable` call sites and application `<table>` markup under `web/src` (catalogue’s table is the only separate application grid found).

## Behavioral checks

| User task | Implementation and verification |
|---|---|
| Compare exact items and return to search | The pinned item identity and separate variant headings keep the two tables legible while scrolling. Both engines restored focus to the original variant after Back and a background refresh. A 40-variant synthetic item exercised comparison and paging. |
| Read prices and supply | Currency axes use copper, silver or gold according to the range. The history keeps extreme daily observations, with a separate recent-detail view and exact tables. Cheapest-tier concentration is measured from current supply. A touch swipe starting on the chart moved the page 129 CSS pixels in Chromium. |
| Interpret freshness | Source age comes from the freshest applicable upstream observation. Last checked records a successful check, including an unchanged result. View refreshed comes from the current query. Regression tests cover the separate clocks. |
| Decide whether a reference helps | Seven synthetic daily unit asks reproduce the reported 373,157,356-copper average, including both recorded extreme asks. The original source listings are unavailable. The website flags daily asks spanning at least 100×, a current average at least 10× away from the reference, or a unit ask rounded to zero. Fewer than three priced UTC days gives limited evidence when no review flag applies. Freshness and coverage are independent. Focused PostgreSQL and SQLite tests cover normalization, questionable references and all 65 grouped stacks. Historical data, Workshop and Companion calculations retain their existing semantics. |
| Find a problem in Administration | Navigation groups operations, metadata and access. Separate permission and activity evidence informs device status. Focused browser tests exercise recovery outcomes, quota cooldowns and saving, intentional configuration, and security history. Fourteen Administration/Account screens passed focused WebKit axe checks. |
| Inspect backup safety and time | React DayPicker preserves UTC and a locale-aligned week. Tests exercise leap days, outside-month dates, mixed and missing evidence, keyboard selection, protected eligibility, bulk confirmation, and focus and scroll restoration. All four Storage pages passed focused reflow tests at 200% in both engines. Preview archives are simulated. |
| Download the existing Windows beta | Forty-eight backend checks cover signed-in and disabled accounts, publication and download integrity, website and device authentication, and update eligibility. Fresh member sessions fetched the actual 4,972,080-byte installer and matched the published SHA-256. Signed-out and ordinary-member admin requests returned 401 and 403 as appropriate. |
| Check the integrated application | The PostgreSQL suite passed 778 tests. The Alembic upgrade, drift check, downgrade and re-upgrade passed. The production web build and 150 frontend tests passed. Operational and contract suites passed 157 and 16 tests respectively. The deployed page-by-page results are in the [acceptance matrix](evidence/market-ux/acceptance.md). |

Device testing used Chromium and Playwright WebKit. The [review guide](market-ux-preview.md) includes the physical iPhone Safari, software keyboard and VoiceOver checks that require an owner device.

## Implementation and review ownership

| Worker configuration | Ownership |
|---|---|
| GPT-6-Luna, medium | Initial route and table inventory |
| GPT-6.2-Sol, medium | Explorer, exact variants, chart interactions, and responsive player-page acceptance |
| GPT-6.2-Sol, medium | Administration, Account, UTC calendar, backup tables, and responsive operations workflows |
| GPT-6.2-Astra, high | Normalization, reference suitability and exact-variant opportunity grouping |
| Fresh GPT-6.2-Astra, high | Independent review of active-member authorization, stack ordering, setup state, fresh-session isolation and regressions |

The coordinator integrated the shared UI, active-member beta access, isolated deployment and final checks. Independent review caught closely spaced fractional stack prices ranking incorrectly in PostgreSQL and an abandoned additional-PC setup hiding the last delivered sync. Both received regressions.

The [Administration visual comparison](evidence/market-ux/admin-comparison/README.md) records the later owner requirements, independent review and paired screenshots.
