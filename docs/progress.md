# Progress

## 2026-11-13 initial inspection

Repository began with README only at ec3dfc7, clean main. Development branch: dev/s1-s5-implementation. Rootless Docker 29.9.2 is available; security options confirm rootless. Host: 16 logical CPUs, 14 GiB RAM, about 13 GiB available; 35 GiB disk available. Existing listeners include 8080, 8085, 8120, SSH and AMP/game ports; none modified. Proposed development port 18780 must be rechecked before launch.

Python 3.12 exists but pip/ensurepip and Node/npm are absent. Use bounded rootless development containers rather than host administrator installation. Default executor sandbox fails before commands start (bwrap loopback RTM_NEWADDR); reviewed commands run as marketdev without root.

S1 live verification pending: credentials have not been supplied, and no authenticated API observations exist. Official developer documentation redirected to an inaccessible endpoint in research tool. Community endpoint reports are hypotheses, not verification.

S1.1 complete. S1.2 initial probe implemented: five sequential ruleset/house requests, bounded payloads, safe metadata output, credential-safe failures. Three synthetic regression tests pass using Python unittest. Missing credentials exits 2 with an explicit blocker; no live API success claimed. S1.3 remains blocked. See api-feasibility.md for research and reproducible procedure.

S2.1 verified locally: PostgreSQL migration upgrade, schema drift check, downgrade to base and re-upgrade pass. S2.2 initial identity foundation verified: ten pytest tests pass against isolated PostgreSQL (including three probe tests). Includes Argon2 passwords, atomic invitation redemption, hashed/revocable sessions/devices, CSRF, origin checks, shared login throttling, admin role checks, final administrator protection and audit events. Device bearer credentials cannot exercise admin endpoints. Further security hardening/recovery and administrative features remain.

S2.3 local Compose starts with healthy API and database. Actual HTTP `GET http://127.0.0.1:18780/api/v1/health` returns 200 and contract_version 1. Database cgroup reads memory.max=805306368 and cpu.max=100000 100000 (limits enforced). PostgreSQL has no host port; proxy binds 127.0.0.1:18780. Ignored .env contains random local database password. No initial administrator created in persistent development DB. GitHub Actions workflow added; remote run not yet checked. Transitive dependency lock captured from tested image. HTTPS, persistence restart, backup/restore verification remain pending.

S4.1 mockups rendered and verified in actual Chromium: three desktop/mobile pages, six screenshots, no page errors or horizontal overflow; navigation and review dialogs pass. See design-review.md. Explicit visual approval requested; pending. Final player-facing design remains gated.

GitHub combined status tool returned no statuses for c34659e; this does not verify Actions success.

S3.1/S3.3 foundation: markets, canonical listing snapshots, fetch observations and variant-specific listings implemented. Snapshot contents deduplicate per market; repeated fetches preserve provenance and idempotency keys. Strict normalization covers auction stack totals, commodity unit prices, bid-only listings, bounds and explicit empty arrays. Missing auctions arrays fail closed pending live verification. New migration passes PostgreSQL upgrade/check/downgrade/re-upgrade. Twenty-one source regression tests pass against PostgreSQL. A first source-mounted run imported the older installed package; rerunning with `python -m pytest` correctly tested the current source. Provisional quantity-weighted recent and daily-sampled 14/60-day references are documented in pricing.md; Workshop compatibility remains unverified.

S3.2 worker foundation verified with 30 total PostgreSQL regression tests. Global advisory lock enforces sequential collection across worker processes; per-market transaction and savepoint preserve good history on malformed payloads. Conditional ETag/Last-Modified requests, 304 observations, token caching/invalidation, shared schedules, bounded backoff/Retry-After, failure monitoring, missing credentials and 5 GiB database budget tested. Monitoring migration passes upgrade/check/downgrade/re-upgrade. Worker runs only with the Compose collector profile, and only enabled plus verified markets are eligible. No live collection is enabled or claimed verified.

Authenticated research/admin API foundation passes 34 total PostgreSQL tests: explicit market freshness, current item variants, variant history/listings, explainable below-reference deals with spend/discount/coverage filters, disabled market creation, schedule guards, collection runs and storage size. Monetary amounts and auction IDs are precision-safe strings. Query work is bounded with truncation flags. Name metadata is not implemented; numeric ID search works and name searches explicitly explain the limit. Daily valuation queries batch snapshot listings to avoid one database request per historical snapshot. API contracts documented under contracts/README.md. This is not completion of the website or all opportunity types.

Security maintenance: pip-audit found vulnerabilities in initial pytest 8.4.2 and Starlette 0.49.3. Updated FastAPI 0.162.7, Starlette 1.10.0, pytest 9.2.0 and matching httpx2 test client; regenerated the transitive lock. All 34 PostgreSQL tests pass with no warnings, and a repeat audit reports no known vulnerabilities. CI now audits the lock with pip-audit 2.10.1.

Next: operational backup/restore and incremental desktop sync contracts. Credentials and explicit design approval remain pending.
