# Storage & Backups implementation review

Draft PR: https://github.com/Twich-Team/TwichUI-Market/pull/58

The original long administration page is now four focused pages with direct URLs and browser history. Overview is the default. Market's espresso, bronze, gold, ivory and muted teal styling is retained.

| Page | What it provides |
|---|---|
| Overview | Four primary metrics, conditional issues/active migration, database growth, filesystem capacity and actionable health links |
| Backups | Recovery-point inventory, server search/filter/sort, paging/bulk selection, size history, recorded reliability, details drawer and Backup Policy dialog |
| Storage | Device cards, true filesystem free/account-available distinctions, measured Market archive segments, NAS settings/folder dialogs, connectivity/diagnostics, actual migration stages and conditional PostgreSQL filesystem forecast |
| Maintenance | Maintenance/recovery health, dynamic retention lifecycle, allocation composition, recorded ingestion/removal activity, expandable execution history, original retention controls and sortable diagnostics |

## Functionality and safety

[Feature parity inventory](storage-redesign.md) maps the original operations. Create, download, manifest/checksum details, isolated restore, protection, single/bulk protected deletion, policy, native SMB credentials/options, connectivity, folder creation/browsing, migration preview/copy/verification/activation, interrupted partial cleanup, explicit original-copy cleanup, retention dry run/apply/enable/pause and advanced diagnostics remain available. Protected/reserved/recovery-loss acknowledgements, active-use prohibitions, audit receipts, CSRF/admin authorization, credentials encryption and backend locking/revalidation are unchanged.

No production operation was executed. Development used a separate feature worktree and bounded synthetic infrastructure. Existing release files and the original dirty checkout were preserved. The independently running live migration completed successfully on November 24 at 11:30:35 a.m. America/Denver: six copied recovery points, 9,420,978,411 bytes, originals_preserved=true in durable manager state. [Read-only observation](evidence/storage-redesign/operational-observation.json). This task did not initiate that migration or remove its originals.

## Visualizations and measurement

Capacity bars distinguish Market archives from other filesystem usage when physical sizes and true free space are measured. Otherwise totals remain unsegmented or unavailable. Database filesystem availability can include reserved blocks, so it is labeled used or unavailable rather than exact occupied bytes. Multiple filesystem totals are not added together. Deduplicated recovery point counts are distinct from physical original/destination copies.

Database growth uses actual hourly samples, range controls, tooltips, an area line and explicit gaps. Backup bars preserve each timestamped archive, distinguish local/network and manual/release outlines, and open details. Reliability uses retained execution receipts; unknown days are not invented missed schedules. Migration progress reflects completed copy/checksum counts and confirmed activation. The filesystem forecast requires fresh continuous observations and a meaningful declining-free-space fit; measured and projected lines differ. Retention uses configured values, with actual coverage separate. Database composition separates table/TOAST bytes from table indexes. Ingestion and cleanup use recorded counts, never claimed disk reclaimed. Execution history retains reasons and category counts.

[API documentation](storage-dashboard-api.md): additive fields on existing storage/maintenance/backup APIs; server inventory filters and bounded existing execution receipts. No new schema, endpoint, dependency, sampler, worker or telemetry storage.

## Validation and visual refinement

- 776 PostgreSQL tests pass in 442.68 seconds in an independent temporary market_test PostgreSQL container; it was removed after testing.
- 157 operational checks pass in 25.385 seconds, including 26 manager and 30 NAS safety checks.
- 149 frontend tests and TypeScript/production Vite build pass.
- 17 isolated dashboard Chromium scenarios pass in 52.7 seconds, including direct navigation/history, dialogs, filters, bulk safeguards, empty/stale/error states, local/NAS health, active/failed/interrupted/completed migration, recovery expiry and cleanup pause.
- axe checks pass in the dashboard workflow. Responsive captures cover 1280×720, 1920×1080, 2560×1080 and 2560×1440, 800px desktop and 320px phone widths.
- Three existing backup-management fixture scenarios also pass locally in Chromium (9.4 seconds) and WebKit (21.7 seconds), including empty/unavailable inventory. An additional 2560×1440 check passes across all four pages (7.4 seconds); its captures were visually reviewed.
- A separate unmodified c6946cd baseline screenshot capture passes. Existing integration browser selectors were updated while retaining their assertions.
- All four pages, drawers/dialogs, warning/failure and narrow states were actually viewed. Refinements fixed chart-axis/legend collisions, drawer sizing, excessive header height, incomplete capacity attribution and lazy-chart capture.

[Before/after gallery](evidence/storage-redesign/review.html). All screenshots use synthetic fixtures and are not live operational evidence. Fixture full-page height fell from 7,143px for the original combined page to 1,171px for Overview (84% reduction); monitoring content through capacity fits approximately 1080px, with footer below. At 1280×720 primary cards are visible immediately while charts/details require vertical scrolling. No text was globally shrunk to achieve this.

All four CI workflows pass test commit `8d12051a95f410b1204c6dec24f5088add731069`, whose application code is `1137602dd7d7c1fb2917b7df2f2b3f7d204200c5`:

- [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45469809879): success.
- [Private website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45469810015): success.
- [Native NAS storage](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45469810010): success.
- [Windows companion](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45469810364): success.

The website workflow includes Chromium and WebKit backup administration against the actual isolated management boundary. Native NAS CI exercises real SMB configuration, folders, migration, protected/bulk deletion, outage and accessibility checks. Windows CI includes prepared package consumption, signed SDK updates and installed release checks. Initial failures identified a status selector mismatch, terminal-operation cached-inventory refresh race, phone unavailable-metric overflow and an incorrect empty-state test expectation; each was corrected and rerun. [CI record](evidence/storage-redesign/ci-results.json).

The closing evidence commit does not change application code. Its baseline-only fixture paging correction was exercised separately against the original build; the baseline test remains skipped in ordinary CI.

## Performance and limits

Shared private query keys avoid duplicate polling. Ordinary capacity/health refreshes once per minute, active jobs and busy cached inventories every five seconds. Charts load lazily; diagnostics stay collapsed. Composition adds one relation-metadata query and activity two date-filtered metadata aggregates, with the existing three-second statement deadline. No raw-listing scan is introduced for charts. No production load benchmark or production resource improvement is claimed.

The production bundle retains the existing ECharts chunk-size warning. Compared with the unmodified baseline, administration JS grows approximately 10.9 KiB gzip, the shared chart chunk 7.0 KiB gzip, and administration CSS 4.5 KiB gzip. No new dependency is added.

Historical schedule changes/missed executions are not reconstructible from current records. NAS utilization history is absent, so no NAS forecast is fabricated. Backup chart history is bounded to 100 latest archives; receipt outcomes are bounded and disclosed. Migration worker does not report current-file speed/ETA or a distinct per-byte verification phase, so copy/checksum progress remains combined. Separate filesystem identity cannot prove database/backup colocation; no guessed database segment or summed capacity is presented. Record deletion does not imply physical disk reclamation.

Before deployment the owner must review/approve this draft, verify current destination/recovery health and choose a safe window with no active manager operation. Deploy matching API/private manager/frontend artifacts together because filtering and physical accounting are additive across that boundary. Preserve the existing deployment chain, secrets, keyring, data and retention authorization. No merge or deployment is authorized by this review candidate.

## Commits

- d822c12: bounded read models, inventory and physical storage accounting.
- 2ec9c88: unknown-size accounting assertions.
- 4ca32e4: four-page administration redesign and browser contracts.
- d0e0375: measurement honesty, responsive refinement and chart layout.
- 2ad5d30: bounded history and axis readability.
- 24bf8d4: busy cached inventories retain fast refresh until current measurements return.
- 467135a: regression reproduces the terminal-job cache race under the real manager lock.
- 94c579d / c98663b: phone navigation wraps and unavailable summary metrics remain readable without horizontal overflow; the actual service-error phone state has a browser regression.

- 0e3e24b: compact charts reserve space for wrapped legends.
- 1137602: sparse and isolated database measurements retain visible markers while dense continuous lines remain clear.

- 8d12051: retain the distinct empty-inventory assertion in the existing backup-management suite.
- Final evidence-only commit: corrected baseline fixture paging, reviewed screenshots and reports; no application behavior changes.
