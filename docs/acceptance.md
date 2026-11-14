# Acceptance evidence and external dependencies

Current ingress task: **https://localhost:18444** is the verified interactive, authenticated read-only modernization preview. Existing production assets remain unchanged at localhost18443. **https://market.twich.gg** has trusted TLS and the correct Traefik route but intentionally returns403 because rootless forwarding obscures the peer address. Public authentication is not verified until administrator source restriction/guarded activation completes. See [exact administrator commands and review setup](traefik-preview-operations.md), [progress](traefik-preview-progress.md), and [actual evidence](evidence/traefik-preview-verification.json). Source checkpoint ece9100 passes120 backend tests,17 frontend tests, six Chromium regressions and backend/website/Windows CI. Live schema is0010; collector/history are intact. No modernized frontend promotion is approved.

This is an implementation review candidate. S1–S5 is not complete while required external evidence remains missing. Detailed chronological checks and workflow IDs are in [progress.md](progress.md).

| Area | Verified implementation evidence | Acceptance still required |
|---|---|---|
| S1 API feasibility | Bounded repeatable credential-safe probes, structural summaries, redirect refusal and synthetic fixtures | US OAuth, house/commodity structure, duplicate ruleset contents, payload sizes, timestamps and HTTP 304 are now observed directly. Remaining: exact player-facing house routing, other regions and long-run refresh guarantees beyond one observed 3,599-second source interval |
| S2 Foundation | PostgreSQL migrations and schema parity, permissions/invitations/admin/device tests, real browser workflows, resource-limited Docker startup/persistence, certificate-validated localhost HTTPS and owner provisioning | Deployment-specific external routing/certificate trust if access beyond localhost is desired |
| S3 Collection/history | Transactional/idempotent fixture ingestion, worker scheduling/rate limits/recovery, versioned asking-price algorithms, long-term daily retention, metadata resolution fixtures, bounded storage monitoring, real backup restoration and corruption rejection | One US feed now collects genuine listings with browser verification; broader collection remains disabled. Remaining: exact Workshop formulas and known outputs; original owner-provided private-retention clarification |
| S4 Website | Real authenticated Explorer, three opportunity modes and administration; real PostgreSQL/Chromium workflows; three high-fidelity mockups | Explicit approval of the three major player-facing designs; initial US live-data browser workflows now pass |
| S5 Companion | Versioned precision-safe contracts, native credential vault, resumable cache/migration/offline recovery, real HTTP sync, schema-validated data-only export, native TLS trust checks, Windows builds and installed-release/native WebView2 workflow 43542957765 | Workshop pricing compatibility depends on its reference formulas; actual addon integration remains S6 |

The local application is at `https://localhost:18443`, bound only to the dedicated VM's loopback interface. Caddy's public local CA is in ignored `artifacts/tls-root.crt`; no host certificate trust was changed. Initial owner credentials remain in private ignored `.local/bootstrap.env`; never send them or Blizzard secrets in chat.

The design review candidates are `/design/#explorer`, `/design/#deals`, and `/design/#admin`. They are explicitly illustrative. The implemented application also remains labeled as under design review.

Credentials are configured privately, and the initial US house 110 auction feed is enabled. See [actual upstream evidence](api-feasibility.md). Do not broaden this initial rollout. Do not enable or mark mappings verified until recorded observations establish their semantics. Provide the Workshop formula/fixture source read-only; the main addon repository remains outside the modification scope. Record explicit design approval in progress.md before finalizing those designs.

No AMP, firewall, SSH, system Docker daemon, existing reverse proxy, unrelated user resources or main addon files were modified. The Windows runner's temporary exact-app WebView2 test policy is isolated to disposable GitHub CI and removed by the test's finally block.

## Item Experience and Frontend Modernization

The active milestone is an integrated review candidate, **not visually finalized**. Detailed criteria and chronology are in [the milestone plan](item-modernization-plan.md) and [progress](item-modernization-progress.md).

| Area | Verified evidence | Remaining gate |
|---|---|---|
| Item catalogue | Authenticated grouped server-side search/sort/25–100-row pagination; exact variant ranges/references, stable ordering and changed-snapshot rejection | Owner visual approval |
| Metadata/tooltips | Additive migration 0009; bounded background official item/media enrichment, source/build/hash/time, independently missing names/icons, optional attributed Forever beta fallback disabled by default; keyboard/hover/touch Base UI popovers | Unknown upstream facts remain explicitly unavailable; no invented attributes |
| Interactive research | ECharts daily price/14/60-day overlays, supply, all-listing distributions, gaps, exact copper labels, 7D–10Y ranges, zoom and responsive resize/disposal; accessible data alternatives | Owner visual approval |
| Management/account | Shared Query isolation and table controls for devices, collection, unresolved metadata and audit records; enrichment monitoring; existing permissions/device flows retained | Owner visual approval |
| Performance | Legacy metadata SQL 153→5; catalogue bounded queries; rollback-only 10,000 groups/30,000 variants/3,651 days/100,000-listing workload with EXPLAIN; compact history 61.5% smaller; first-view JS ~41% lower; cache return calls 2→0; virtual history renders 17 rows for 3,651 calendar days | Rich cold view remains slower than the simpler old site (median 1.439s versus .889s); no overall speedup claimed |
| Regression/deployment | 115 PostgreSQL tests, 16 frontend tests, Chromium workflows, axe A/AA scans, real populated preview; successful local-CA validation, backup and isolated restoration; backend deployed, continuous genuine collection preserved | All six local workflows and backend/website/Windows CI pass at 1430b32. Production frontend promotion waits for design approval |

Evidence: [API/scale measurements](evidence/item-experience-scale.json), [browser measurements](evidence/item-browser-performance.json), [deployment/accessibility/restore record](evidence/item-modernization-verification.json), [metadata providers](item-metadata-providers.md). Screenshots remain ignored artifacts and are uploaded by website CI. Live Explorer/tooltip screenshots contain genuine market data; administration/account/large-history browser fixtures are explicitly synthetic and isolated.

The candidate frontend runs in the project-only `twichui-market-modernization-preview` container without a host port. The production frontend at `https://localhost:18443` remains the previous version until explicit owner approval. The additive backend is deployed at 0009. No market was added or enabled, no real history was reset, and the main addon remains untouched.
