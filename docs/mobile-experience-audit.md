# Mobile experience audit and implementation ledger

Baseline: `8c52b70afe8db4d514a46daf7dd13f27cccc8014`, pushed integration/companion-v2-metadata-recovery, inspected 2026-11-17. Dedicated feature/mobile-experience-modernization worktree: /workspace/TwichUI-Market-mobile. Original detached checkout and every release/provider/Companion branch remain unchanged. Open PRs inspected: #1, #2 (historical work), #21 and #22 (inactive Advisor work). No merge/deployment authorized.

Latest available deployment record: usability-release-acceptance.md reports application 2920f366, schema usability_20261117. Production HTTP probes return 403 from Cloud; this is not live revision verification. No owner screenshots were attached to this conversation; comparison uses the owner's written observations, not claimed image inspection.

## Before implementation: source audit

| Page or component | Finding / cause | Priority and intended treatment |
|---|---|---|
| Shared shell / all pages | <=800px changes sidebar to overflowing horizontal nav, retains branding, account row and ledger header | P0: compact disclosure navigation, current page, Escape/outside close and focus return; retain desktop sidebar |
| Explorer search | wrapping flex plus 220px minimum grow input and intrinsic market select exceeds narrow content box | P0: explicit responsive grid, min-width:0, stacked narrow layout |
| Explorer catalogue | 740px mobile minimum table width; 72px rows plus repeated credits; essentials require horizontal scroll | P0: same TanStack rows/state, compact mobile records, exact variant links/ranges, shared variant query, visible credits |
| Explorer sorting/pagination | sort only in offscreen headers; verbose pagination labels compete with page size | P0: labelled mobile sort and direction using existing state; wrapping thumb-sized pager |
| Item Details overview | summary grid uses two narrow columns; long variant identity can dominate | P1: one-column narrow summaries, wrapping labels, preserve exact monetary values |
| Price history / comparison | lazy chart and resize behavior already present; controls and captions compete at narrow widths | P1: contain chart, wrap ranges/actions, test geometry and touch; no UTC/calculation changes |
| Current listings | dense columns carry material quantity/price distinctions | P1: retain bounded scrolling with visible affordance and accessible region |
| Deal Finder | stacked page grid exists; flex filters retain minimum widths; opportunity heading/price content can stretch | P1: grid filters, wrapping heading, compact prices; preserve confidence/cautions |
| Administration Overview | cards and coverage charts share dense grids | P1: minmax(0,1fr), narrow stacked summaries |
| Members / Invitations | dense shared DataTable, long action captions and invitation URLs | P1: contained scrolling, visible scroll hint, wrapping controls; preserve confirmation flows |
| Market configuration / Collection | multi-control forms and schedule actions; long labels | P1: narrow grid and wrapping actions, no scheduler changes |
| Storage / Backups / Retention | dense financial/storage records, long paths, destructive confirmation | P1: contained table, wrap paths; preserve typed confirmation and disabled operations |
| Security Events | long redacted identifiers/detail JSON | P1: contained scroll/anywhere wrapping, no redaction changes |
| Item Metadata / Recovery Jobs / Provider Results | multiple TanStack tables and record filters; disclosures already exist | P1: same shared table treatment, bounded expanded details |
| Data Sources / Rate limits | provider grids already collapse; quota forms/min-width controls can exceed available width | P1: grid/min-width containment, full action access and masked credentials |
| Account / Devices / preferences | device cards collapse at 600px; password forms/action rows still compete | P1: wrap actions and labels; retain ownership, revocation and CSRF |
| Companion setup / download | step navigation wraps; pending release, hash and status content long | P1: compact padded cards, wrapping actions and hash; no native/release changes |
| Companion authorization | consent action minimum 190px and padding on 320px; long device/account names | P1: remove narrow intrinsic minima, stacked actions |
| Login / invitation | max-width panel exists; input text 14px risks Safari focus zoom | P1: 16px touch inputs, responsive padding; preserve validation and zoom |
| Dialogs / tooltips | confirmation uses dvh already; provider/popover content may exceed viewport | P1: bound popup width/height, retain library focus behavior and touch triggers |
| Loading / slow responses | catalogue retains scoped previous data and skeletons already | Preserve; never introduce independent queries or unbounded lists |

## Verification plan

Widths 320,344,360,375,390,430,600,768,1024,1440; portrait and selected landscape, 200% text, reduced motion, long labels/items, missing icons, variants, delayed API and history restoration. Chromium real API/synthetic database first; WebKit if installable. No claim of real iPhone acceptance. Screenshot before/after gallery and measurements must distinguish fixtures from production. Full backend/frontend/browser checks plus existing Windows CI requested. No production connections, provider calls, pruning, collection, native changes or deployments.

## Milestones

- M1: audit, shell and search.
- M2: mobile catalogue, shared variants, sorting and pagination.
- M3: details, charts, deals, account/Companion.
- M4: administration, geometry/regression, gallery and acceptance report.

Status: source audit complete before application edits; browser audit follows isolated fixture setup. Review-only candidate, not visual approval.
