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

Next: verify final ingestion checkpoint, then collection worker/API queries and operational backup/restore. No live collection is enabled. Credentials and explicit design approval remain pending.
