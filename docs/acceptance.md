# Acceptance evidence and external dependencies

This is an implementation review candidate. S1–S5 is not complete while required external evidence remains missing. Detailed chronological checks and workflow IDs are in [progress.md](progress.md).

| Area | Verified implementation evidence | Acceptance still required |
|---|---|---|
| S1 API feasibility | Bounded repeatable credential-safe probes, structural summaries, redirect refusal and synthetic fixtures | US OAuth, house/commodity structure, duplicate ruleset contents, payload sizes, timestamps and HTTP 304 are now observed directly. Remaining: exact player-facing house routing, other regions and a measured content-change cadence |
| S2 Foundation | PostgreSQL migrations and schema parity, permissions/invitations/admin/device tests, real browser workflows, resource-limited Docker startup/persistence, certificate-validated localhost HTTPS and owner provisioning | Deployment-specific external routing/certificate trust if access beyond localhost is desired |
| S3 Collection/history | Transactional/idempotent fixture ingestion, worker scheduling/rate limits/recovery, versioned asking-price algorithms, long-term daily retention, metadata resolution fixtures, bounded storage monitoring, real backup restoration and corruption rejection | One US feed now collects genuine listings with browser verification; broader collection remains disabled. Remaining: exact Workshop formulas and known outputs; original owner-provided private-retention clarification |
| S4 Website | Real authenticated Explorer, three opportunity modes and administration; real PostgreSQL/Chromium workflows; three high-fidelity mockups | Explicit approval of the three major player-facing designs; initial US live-data browser workflows now pass |
| S5 Companion | Versioned precision-safe contracts, native credential vault, resumable cache/migration/offline recovery, real HTTP sync, schema-validated data-only export, native TLS trust checks, Windows builds and installed-release/native WebView2 workflow 43542957765 | Workshop pricing compatibility depends on its reference formulas; actual addon integration remains S6 |

The local application is at `https://localhost:18443`, bound only to the dedicated VM's loopback interface. Caddy's public local CA is in ignored `artifacts/tls-root.crt`; no host certificate trust was changed. Initial owner credentials remain in private ignored `.local/bootstrap.env`; never send them or Blizzard secrets in chat.

The design review candidates are `/design/#explorer`, `/design/#deals`, and `/design/#admin`. They are explicitly illustrative. The implemented application also remains labeled as under design review.

Credentials are configured privately, and the initial US house 110 auction feed is enabled. See [actual upstream evidence](api-feasibility.md). Do not broaden this initial rollout. Do not enable or mark mappings verified until recorded observations establish their semantics. Provide the Workshop formula/fixture source read-only; the main addon repository remains outside the modification scope. Record explicit design approval in progress.md before finalizing those designs.

No AMP, firewall, SSH, system Docker daemon, existing reverse proxy, unrelated user resources or main addon files were modified. The Windows runner's temporary exact-app WebView2 test policy is isolated to disposable GitHub CI and removed by the test's finally block.
