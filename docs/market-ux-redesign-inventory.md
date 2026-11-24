# Market UX redesign inventory

Evidence reviewed: current source and focused artifacts under ignored `.local/review/`. This is a source/verification map, not an access guide. No credentials or private review details are included. Physical iPhone Safari and real operational services are outside this verification; browser fixtures/simulated states are not evidence of live operations.

## Routes and shared implementation

| Route / view | Implementation mapping | Focused evidence |
|---|---|---|
| `/` Explorer; expanded variants | `research.tsx` + catalogue table in `catalogue.tsx`; TanStack Table drives catalogue sorting/filtering/visibility and specialized artwork/cards; variant data remains exact identity. | variant-label, catalogue and explorer-detail tests; phone Chromium/WebKit matrix |
| `/markets/:market/items/:item[?variant=…]` Item Research | `item-details.tsx`, charts in `charts.tsx`, optional `intraday-history.tsx`; ECharts with exact-data `DataTable`; Query cache/state in shared navigation/query. | chart-data, intraday-data, listing-prices, navigation tests; pricing-shadow and exact-stack logs; phone matrix |
| `/deals` Below Reference, Supply Changes, Price Changes | `deals.tsx`; shared `DataTable` for listing rows, shared Query/preferences, grouped opportunities and expandable stacks. | opportunities/preferences/listing-prices tests; `.local/review/exact-stack-review.log` (11 passed), `pricing-shadow.log` (2 passed), screenshots/matrix |
| `/administration` Overview | `settings.tsx`; grouped admin navigation and shared status/table primitives. | admin focused checks and phone matrix |
| `/administration?admin_tab=markets` | market configuration/schedules; `DataTable` markets. | market-configuration tests, admin screenshots/matrix |
| `?admin_tab=collection` | collection health and check history; `DataTable` run history. | admin-histories tests, admin screenshots/matrix |
| `?admin_tab=metadata` and `?metadata_view=tracker` | metadata coverage/records, recovery jobs and tracker; shared tables, Query, filters and server pagination. | metadata-coverage, metadata-attempts, recovery-tracker tests; admin/recovery matrices |
| `?admin_tab=sources` | provider/source records and attempts; shared tables and status primitives. | provider-rate and metadata tests; admin screenshots/matrix |
| `?admin_tab=members`, `invitations`, `devices`, `security` | Account access views in `settings.tsx`; `DataTable` members/invites/devices and security history. | settings/admin-history tests; all four phone views in both browser matrices |
| `?admin_tab=storage` + `storage_view=overview\|backups\|storage\|maintenance` | `storage-dashboard.tsx`; shared shell/status, `DataTable` backup inventory, retention stages and maintenance evidence; `react-day-picker`-backed calendar in `backup-calendar.tsx`. | storage/backup/retention tests; phone screenshots; UTC calendar test log |
| `/account` | preferences, authorized devices and security; shared tables/Query. | preferences, account/cache tests and phone matrix |
| `/companion` | setup, connection/delivery status and beta download; shared Query. | companion-download tests, beta focused log and phone matrix |
| `/companion/authorize` | approval route; authentication/session gate then approval view. | companion callback/auth tests |
| unknown path | not-found view; navigation parser rejects malformed identities. | navigation tests |
| unauthenticated entry (including invitation registration) | login/register form in `main.tsx`; session restoration and invitation flow. | auth and browser checks |

Shared libraries verified in `web/package.json`: TanStack Table, Query and Virtual; Base UI; ECharts; React DayPicker. Application data grids use `DataTable` (`data-table.tsx`) except the catalogue’s specialized markup, which directly uses TanStack `useReactTable`. Calendar internals are semantic calendar markup, not an application data grid. Mobile adaptations use catalogue/variant cards and contained tables; screenshots are layout evidence only.

## Logical application data tables

Each item below is rendered through shared `DataTable`/TanStack except **Catalogue + variants**, which use TanStack directly with specialized rendering. Exact historical chart data and supply bands are disclosed tables, not separate chart-specific sorting engines.

| Logical table | Route(s) | Shared mapping / mobile behavior |
|---|---|---|
| Catalogue items; exact variants | Explorer | TanStack catalogue; phone item cards and expandable variant cards |
| Current auction listings | Item Research / listing detail | `DataTable`; contained mobile table |
| Matching listings / grouped deal stacks | Deal Finder | `DataTable`; expandable grouped results |
| Exact price-history observations; intraday observations; supply-by-price bands | Item Research | `DataTable` disclosures beside ECharts; scroll-contained on narrow screens |
| Markets and collection runs | Admin Markets, Collection | `DataTable`; phone matrix covers both |
| Metadata provider health, unresolved names, field coverage, provider attempts, recovery jobs and job results | Admin Metadata / Sources, Recovery Tracker | `DataTable`; large records paginated; phone matrix covers views |
| Recovery efficiency by provider; recovery items | Recovery Tracker | `DataTable`; server pagination/sorting for items |
| Members, invitations, authorized devices | Admin access; Account | `DataTable`; phone matrix covers these routes |
| Security events | Admin Security, Account | `DataTable`; filtered/server-backed history |
| Managed backup inventory; retention stages | Storage Backups | `DataTable`; inventory selection/actions retained in responsive contained presentation |
| Ingestion/cleanup counts, database growth samples, storage measurements | Storage Maintenance | `DataTable` in progressive disclosures |
| Backup calendar day outcomes | Storage Backups | Calendar component, intentionally not forced through TanStack; selectable date summaries |

This inventory was assembled from all `DataTable`/`useReactTable` call sites and application `<table>` markup under `web/src` (catalogue’s table is the only separate application grid found).

## Focused verification and concrete gaps

- Dependencies and per-route implementation were verified in current source; targeted test logs include exact-stack review (11 passed), pricing shadow (2 passed), and beta checks (48 passed). Phone screenshot matrices cover member/admin views at 375, 390, 430 and landscape 844 CSS px in Chromium and WebKit emulation. They do not establish physical iPhone Safari behavior.
- Existing browser artifacts record WebKit serious color-contrast violations on Markets, Collection, Members/Invitations, Security, Account and Companion selector controls. These remain concrete accessibility follow-ups unless fixed in newer source/evidence.
- The recorded phone matrices pass layout checks, but their 844-wide variant action locator times out in both browsers; the separate player verification also records a desktop focus-restoration failure for the Training Sword variant link. Treat variant focus/automation coverage as unresolved, not a demonstrated phone layout failure.
- `.local/review/backend-tests.log` records 770 passed and two failures in pricing-shadow tests; the later focused `pricing-shadow.log` records 2 passed. The full recorded run therefore needs a clean rerun before claiming the broader backend suite is green. No full suite was run for this inventory task.
- No physical iPhone, native Safari, authenticated live operational service, or production mutation was verified here. Verify these through the review procedure separately; simulated operational states and desktop-browser WebKit remain limited evidence.
