# Mobile experience review candidate

Draft PR: https://github.com/Twich-Team/TwichUI-Market/pull/23

Baseline: `8c52b70afe8db4d514a46daf7dd13f27cccc8014` on integration/companion-v2-metadata-recovery. Implementation milestones: M1 `abb13a4`, M2 `a5084fe`, M3 `5265815`, M4 `3095c50`. Final application: `9fbd10e` (landscape, long labels and stable environment discovery follow-ups). Source audit: [page-by-page findings](mobile-experience-audit.md). No production checkout, database, provider, release artifact, native Companion, addon, collector or schedule was changed. All local API observations use isolated market_test fixtures. Production revision could not be independently read from Cloud (403); repository deployment evidence is labelled accordingly.

## Candidate behavior

- At <=800px, a compact in-flow navigation disclosure replaces the horizontal strip. All destinations, current page and sign-out remain available. Escape returns focus, outside pointer interaction closes it, navigation closes it, and the menu creates no focus trap or fixed content obstruction. Desktop retains its sidebar.
- Search uses an explicit narrow grid with a single column below 375px. Inputs use 16px on touch layouts; zoom remains enabled. Safe-area padding and dynamic viewport bounds protect navigation and dialogs.
- At <=700px, Explorer mounts compact records instead of the desktop table. One existing TanStack model/query provides sorting, page size, page, prices, ranges, supply and exact variant links. Item tooltips retain touch/keyboard operation. No blended variant prices, second pricing engine, new dependencies or unbounded fetches.
- Mobile variants reuse the existing bounded query and show labelled price/reference/supply/listing records with exact Inspect actions. Sorting and pagination use existing URL/preference/restoration logic.
- Item Details retains all charts, local-time labels, UTC buckets, exact current listings and provenance. Range controls wrap into comfortable targets. Dense material-data tables remain contained, focusable scroll regions with a visible instruction.
- Deal Finder filters, account/device actions, Companion consent, login and invitation controls fit narrow content widths. Administration uses a compact section selector on phones; desktop tabs and all server-side table behavior remain.
- All existing provider credit text and visible links remain. Terms in item-metadata-providers.md require linked attribution wherever relevant data appears; no shortening/removal has been assumed licensed. Mobile credit spacing/type is compact; details retain full provenance.

## Verification and limits

Local: 605 backend tests, 129 frontend tests, TypeScript/Vite build and six new responsive Chromium workflows pass. Matrix: 320,344,360,375,390,430,600,768,1024,1440. Populated administration passes at 320/390/768/1440; exact variants and browser return state pass. Geometry explicitly asserts selector/Search separation and document width, including 768px Deal Finder. Tests exercise long labels, missing icons, 300ms response delay, reduced motion, 200% root text, menu focus, and Account WCAG A/AA axe. Existing browser and remote CI results are recorded below.

Local WebKit installation was attempted; both official download endpoints returned 403 Domain forbidden. Linux WebKit verification is now wired into the existing isolated CI image; see the final CI receipt below. No real iPhone, Android, foldable, software keyboard, physical safe-area or dynamic Safari toolbar acceptance is claimed. Enlarged root text and emulated viewports are distinct from real browser zoom/device acceptance. The owner's screenshot files were not attached to this conversation: the comparison below addresses the supplied written observations, not an image-to-image match.

| Owner observation | Candidate response |
|---|---|
| Clipped navigation / oversized header | Single compact brand/Menu row; vertical disclosure; ledger header omitted on mobile |
| Search overlaps market selector | Content grid, zero intrinsic minimum widths, automated non-overlap assertion at every specified width |
| Wide Explorer / hidden important columns | Compact price/reference/supply records with no horizontal catalogue table on phones |
| Tall rows / repeated attribution | Purposeful two-column price facts and compact linked credit; legally required credit retained |
| Awkward table navigation | Visible mobile sorting, thumb-sized Previous/Next, current page and full-width page-size control |

## Real-phone acceptance checklist

Owner should use a review preview, not deploy this PR merely to test it.

1. iPhone Safari (narrow and larger phone): sign in/invitation; focus each input and show/hide keyboard; verify no unwanted input zoom, no obscured submit/confirmation, portrait/landscape and expanded/collapsed browser toolbar. Check notch/home-indicator spacing and 200% page zoom/increased text.
2. Android Chrome: repeat navigation, search/market submit, sort/direction/page size/Next/Previous, long item names, exact single/multiple variants and Back/Forward restoration. Scroll without accidental navigation; verify missing-icon fallback and popover tap/close.
3. Narrow foldable front display (320–344px): verify every key price, variant Inspect, Search and menu action stays reachable. Open/close menu, rotate, unfold to tablet and refold without losing filters/page/selection.
4. Larger phone/tablet: verify intentional transition between compact records and desktop catalogue, contained table scrolling, and all administration sections/actions. Use hardware keyboard Tab/Shift-Tab/Escape and screen reader labels/focus.
5. Item Details: inspect 24H/48H/14D/longer history, tap chart points, zoom/pan and read exact chart data; verify local labels/current listings quantities, stacks and prices. Repeat Deal Finder filters/cautions/Inspect/return.
6. Account/Companion/Admin: open consent, deny/cancel safely, view connected devices, test non-destructive forms, type into confirmation then cancel. Confirm masked secrets/redacted events; do not invoke live collection, provider recovery, retention, rate changes or destructive account/device operations for acceptance.
7. Enable reduced motion and slower network; repeat search/page changes and retry/error recovery. Record device/OS/browser/viewport and screenshots for any failure.

Stop at owner visual review. No merge, deployment, publication, pruning or provider campaign is authorized.

## Measured mobile impact

[Machine measurements](evidence/mobile-experience/performance.json), [bundle sizes](evidence/mobile-experience/bundle.json). Three fresh authenticated Chromium contexts per build at 390×844, loopback synthetic API, while other isolated verification was running; timings are small-sample observations, not phone/cellular benchmarks.

- Median catalogue-ready: baseline 545ms; candidate 485ms. Median search response: 113ms vs 123ms. Exactly one catalogue request for initial page plus one for search in each sample; no duplicate mobile/desktop catalogue request.
- Heap snapshots after a one-item search: baseline roughly 10.3MB, candidate roughly 9.1MB; browser heap only, not full process memory. Median layout-shift sum 0.317 vs 0.181 (all three final candidate samples 0.181). Initial authentication/preferences/shell transitions still contribute substantial shift; these measurements do not establish a Core Web Vitals pass. Existing scoped previous-data retention and bounded skeleton area preserve pagination content.
- All lazy JavaScript chunks together: +4,025 bytes raw / +955 bytes gzip. CSS +7,930 bytes raw. No dependency added. Deferred chart engine remains byte-identical at 573,272 bytes, with the same lazy loading.

[Before/after gallery](evidence/mobile-experience/review.html) contains 23 paired scenes (46 full-resolution screenshots) from synthetic fixtures, including narrow/wide/tablet/desktop, navigation, variants, prices, administration, rate controls, connected devices, Companion and consent. Timestamps and fixture state can differ as existing regression workflows update synthetic records; no market value is presented as live production evidence.

Additional scale acceptance: [5,000-item fixture](evidence/mobile-experience/scale.json) renders 25 rows, uses two catalogue requests over two pages, and retains exact 10000/10025-copper prices and quantities 1/6. Final catalogue-ready observation was 485ms, DOM 1,207 nodes; local fixture only. [Existing navigation measurements](evidence/mobile-experience/navigation-performance.json) also confirm zero catalogue requests on cached return and no chart-engine load from Explorer.

[Desktop/history receipt](evidence/mobile-experience/desktop-and-history.json): the frozen baseline and candidate have exactly equal sidebar width/position, navigation button positions/heights, catalogue column labels/order and table width at 1440px. A 344px real-API browser Back → Forward → Back sequence retains the exact item URL and 25-item page size.

Reproduction uses only the prepared isolated Cloud database and localhost services, or the repository's separate `compose.browser.yaml` CI stack. Optional `seed-mobile-scale.py` refuses every database except market_test. `mobile-scale.cjs` and `mobile-regression.cjs` assert bounded rows, request counts, exact money/supply, wide geometry and mobile history. `playwright.mobile.config.ts` accepts BASE_URL/CHROMIUM_PATH; `playwright.webkit.config.ts` uses WebKit already bundled in the isolated CI image. Native source, contracts, pricing/backend and Compose deployment files have zero diff against the baseline. Spare verification servers were stopped; candidate/API and static gallery remain localhost-only, backed solely by synthetic market_test.

[Constrained Chromium emulation](evidence/mobile-experience/throttled-performance.json): one synthetic 390px sample with 4× CPU slowdown, 150ms latency and 250,000/100,000 bytes/s down/up measured catalogue-ready 2,222ms, search response 262ms, and item navigation plus visible lazy-chart canvas 2,428ms, with no document overflow. This is deliberate browser throttling, not a physical-phone benchmark or mobile-network p95.

## Final exact-application acceptance

Application **9fbd10efa3d747d322ddeefc5d21cd57465f4b14** passes all three exact-source CI workflows:

| Workflow | Result |
|---|---|
| [Backend 44106327889](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44106327889) | Success: regression, migrations, preservation and existing operational/contracts checks |
| [Private website 44106328001](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44106328001) | Success: unit/build/audit, ordinary Chromium workflows including six new mobile cases, six Linux WebKit mobile cases, existing ForeverDB/provider-rate/usability/IPC checks |
| [Windows 44106327882](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44106327882) | Success: existing native/HTTP/auth/archive/Tauri, upgrade/installed and signed-update verification |

[Machine CI receipt](evidence/mobile-experience/ci.json) and [local verification receipt](evidence/mobile-experience/verification.json). Linux WebKit screenshots are retained in the [CI artifact](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44106328001/artifacts/14339291978); its local transfer is blocked by Cloud network policy. The 46 Chromium gallery images were captured locally, inspected and fingerprinted. Linux WebKit is engine coverage, not actual iOS Safari acceptance.

Review/evidence-only closing commits use `[skip ci]` to preserve these exact-application runs without repeating native builds. Runtime source and CI configuration have zero diff from the tested application. The extra local comparison script is inert verification code. Original checkout is clean, the remote integration branch remains 8c52b70, and the feature branch alone was pushed. No merge or deployment occurred. Implementation is complete as an owner visual-review candidate; physical-phone acceptance remains with the owner checklist above.
