# Item Experience and Frontend Modernization

Status: active. This milestone supersedes routine S1–S5 continuation as the engineering priority; previous acceptance gates remain recorded. Keep the single live collector running. Existing espresso/chestnut/bronze/ivory styling is the design foundation. Significant populated-interface changes remain review candidates until explicit owner approval.

## M0 — Evidence and design constraints

Prerequisites: inspect repository, current contracts, worker and deployment.
Acceptance: record read-only live-data API/query baselines and frontend bundle/browser measurements; reproducible benchmark commands; explicit fixture versus live provenance. Research primary library/provider documentation. No production data resets, extra markets, host services or privileged host changes.

## M1 — Efficient item catalogue API

Prerequisites: M0 measurements.
Implement an additive authenticated catalogue endpoint over compact snapshot statistics, never a per-item listing scan. Server-side allowlisted sorting/search/pagination, stable tie-breakers, bounded page sizes and explicit snapshot identity. One parent per item with variant count, aggregate supply/listing totals and explicit price ranges; expand to variant-specific prices/references without conflation. Preserve old endpoints and desktop contracts.
Acceptance: variant separation, correct quantity/price bounds, null prices, stable page boundaries/sorting/search/permissions and query-count tests on isolated PostgreSQL. Representative live and large synthetic benchmark comparisons, query plans/index verification. Use daily references in batch; preserve pricing rounding and UTC-day semantics.

## M2 — Rich, provenance-aware metadata

Prerequisites: provider research and M1 identity design.
Extend metadata additively for quality, verified attributes, structured tooltip properties, media/icon provenance and request/refresh status. Resolve missing media independently from names without starving auction checks; bounded scheduled requests with shared cooldown and negative caching. Validate identities, fields and trusted media destinations. Preserve metadata sources, payload hashes, namespace and observed times; missing fields stay unknown. Never use another game edition's item-ID match as verified Forever data.
Acceptance: migrations round trip/parity; success/partial/missing/malformed/retry/rate-limit/region/source tests; actual bounded Blizzard item/media probes and captured minimal evidence. Research fallback providers' version coverage, access rights, attribution/licensing and availability. Enable a fallback only with a supported contract and trustworthy identity; otherwise document a real blocker and show explicit unknown information. Safe local icon delivery, caching limits and CSP verification.

## M3 — Catalogue and shared item experience

Prerequisites: M1/M2 contracts; library research.
Introduce TanStack Query with account-scoped cache clearing on logout/credential changes, stable keys, cancellation and invalidation. TanStack Table handles accessible sortable/paged catalogue and substantial administration/account tables. Keep row windows bounded; apply TanStack Virtual to measured large expanded/scrolling lists when it materially reduces DOM work, with accessible alternatives. Shared item identity/icon/quality and WoW-style tooltip components. Base UI hover/focus tooltip plus persistent touch/click popover, Escape dismissal and keyboard interactions. Separate verified item attributes from market estimates and always identify variants and source uncertainty.
Acceptance: populated catalogue search/sort/page/expand/select workflows; variant-specific details; hover/focus/touch tooltip checks, unknown/error/loading states, no executable external HTML or tooltip scripts. Shared components used in Explorer/Deal Finder and relevant administration/account controls. Screenshots at desktop/mobile sizes presented for review, without declaring final design approval.

## M4 — Interactive history and distribution

Prerequisites: batched history endpoint and M3 query layer.
Apache ECharts with tree-shaken imports, responsive sizing/disposal and accessible textual/table alternatives. Price/supply/distribution views, precise integer-copper tooltip labels, range controls, zoom, overlays and explicit missing-day gaps. Preserve exact API money strings; visual scales are approximate when numbers exceed JS precision. Fetch bounded daily samples for years of history, not all observations.
Acceptance: known fixtures and real populated-browser interactions; no gap interpolation; zoom/ranges/overlays work by keyboard/touch where appropriate; no leaks on unmount/reselection; meaningful empty/single-point states. Compare reference math to existing known outputs.

## M5 — Integration, performance and deployment

Prerequisites: M1–M4 implemented and integrated.
Acceptance: PostgreSQL regressions/migrations, Vitest, real Chromium workflows, axe accessibility scans plus manual keyboard/touch checks, screenshots of populated Explorer/Deal Finder/admin/account. Compare reproducible API latency/query count and browser DOM/render/network/bundle baselines on specified hardware/data; quantify improvements and document limits without fabricated targets. Verify caching reduces repeat calls without stale private data across accounts. Audit dependencies, inspect diff, commit/push checkpoints and inspect CI. Back up real history before additive deployment, verify Docker startup/HTTPS/persistence and live collector health afterward. Isolated restore/schema checks; no synthetic data presented as live. Record all evidence and remaining visual approval explicitly.

## Initial decisions

- Keep REST v1 legacy/desktop contracts intact; introduce additive catalogue and rich-metadata surfaces.
- Group item rows by item ID, show price ranges for mixed variants, and put exact prices on variant rows only.
- Prefer server pagination (25/50/100 items) to downloading the entire market. Virtualization is conditional on measured expanded-row size, not a blanket replacement for native tables.
- Keep authenticated server-state memory-only and clear it on identity changes. No private API cache in service workers/localStorage.
- Remote names/images never become executable HTML; icons are fetched only through bounded allowlisted server-side media handling.

## Verified checkpoint status

M0–M2 backend/research and M3–M4 integrated candidate implementation are verified in the progress/evidence records. M5 local tests, accessibility, measured query/browser behavior, genuine-data preview and actual backup restoration are verified. Final code checkpoint 1430b32 passes backend/website/Windows CI, and its exact-image preview passes genuine-data and trusted-TLS checks. Owner design approval and subsequent production frontend promotion remain required; a successful candidate build or screenshot is not approval.
