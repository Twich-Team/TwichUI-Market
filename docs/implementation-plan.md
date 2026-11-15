**Administration/provider review candidate:** [current findings and visual review](admin-modernization-review.md), [continuation ledger](admin-modernization-progress.md). New administration UI and authentic item-quality colors remain undeployed pending owner visual approval. The separate Explorer/Details milestone is queued only.

# Implementation plan

**Authorized combined release is live and verified:** [Complete production acceptance](combined-release-acceptance.md), [machine evidence](evidence/combined-production-release.json), [current operations/rollback](combined-release-operations.md). Release `e7d3129` integrates both frozen candidates, reaches schema `meta_20261114`, publishes the exact signed Windows 2.0.0-beta.2 installer to owner account 1, and validates the owner's privately entered Everloot key. All three final exact-source CI workflows pass. The bounded 20-attempt provider test completed with no name gains: current fixed market-2 coverage is 2,232/4,861 (45.92%). Provider recovery and automatic mode are disabled again. All original history/accounts/sessions/preferences remain; house 114 alone continues at 300 seconds; pruning is off. Remaining owner-PC tray observations and off-host keyring copies are recorded limitations, not new implementation campaigns. Earlier plans and approval gates below are historical and superseded for this release.

**Active owner authorization (2026-11-14 America/Denver):** Integrate frozen Companion implementation d9d5ae3 / review 75c6f38 with metadata PR #2 at b18927a, verify the actual combined commit, rehearse backup/restore/migrations, deploy to market.twich.gg and publish the exact signed 2.0.0-beta.2 installer. This supersedes the older stop/approval gates below for this bounded release. Preserve all history/accounts/credentials, sole house-114 collector at 300 seconds, rootless isolation, signing bytes and evidence; no pruning or unrelated infrastructure changes. Provider credentials remain owner-entered; supplemental/automatic recovery stays disabled pending validation.

**Current owner instruction: stop at the frozen beta2 owner-review boundary.** Implementation/verification d9d5ae354931bfe9276c30fde6f83da8d661e457 and installer source c7bad2f5e84213e1c69e3eb66e8daa6540f05bc9 have all CI green, including actual exact-byte signed SDK install/retained-data lifecycle. [Owner-review packet](companion-v2-owner-review.md) is authoritative for the current status and next approval. Reuse valid existing acceptance; no new beta, tray automation campaign, unrelated infrastructure or production changes. Tray actions remain unverified. Original deployment goal stays incomplete pending owner PC acceptance, controlled integration and explicit publication/deployment authorization. Earlier plans and chronology below are preserved, superseded by this stop instruction.

Active owner goal: [Companion v2 full request](companion-v2-request.md), [detailed milestone plan](companion-v2-plan.md), [durable progress and next action](companion-v2-progress.md). Prioritize native Rust scheduling and secure browser authentication foundations, then complete native utility/tray/settings, setup/device website, verified release distribution, full Windows/browser testing and approved deployment. Preserve the current approved production website, sole house-114 collector and all data; new significant designs require their own approval.

Owner-approved frontend/API promotion is complete at **https://market.twich.gg**, application release **c8f03c2**. [Plan](production-promotion-plan.md), [full production acceptance and rollback](production-promotion-acceptance.md). Visual/usability approval covers Item Experience, Market Configuration, Historical Retention controls and User Preferences. Preview containers were removed after verification. History, accounts, sessions, preferences and the single house-114 collector are preserved; destructive retention remains unauthorized.

Persistent per-user preferences are now live in production: [original plan](user-preferences-plan.md), [progress](user-preferences-progress.md), [historical preview acceptance](user-preferences-acceptance.md). Collector and all live market history remain protected.

Current milestone: [Market usability, configuration and retention](market-usability-plan.md), [progress](market-usability-progress.md).

Current deployment task: [focused preview/Traefik plan](traefik-preview-plan.md).

Active work: [Item Experience and Frontend Modernization](item-modernization-plan.md); acceptance and current next action are in [its progress record](item-modernization-progress.md). Earlier S1–S5 tasks below remain historical and retain their external evidence gates.

Each task requires tests, diff review and a committed/pushed evidence checkpoint. Status lives in progress.md.

| Task | Prerequisite | Acceptance |
|---|---|---|
| S1.1 Repository and environment | none | Instructions, plan, host safety checks recorded |
| S1.2 Repeatable API probes | S1.1 | OAuth from environment; bounded responses; metadata evidence; synthetic fixtures tested |
| S1.3 Live feasibility | developer credentials | Rulesets/houses/commodities, payload sizes, timestamps, regional mapping and repeated refresh observations recorded |
| S2.1 Backend/schema | S1.1 | FastAPI health, SQLAlchemy models, Alembic upgrade/downgrade tested on PostgreSQL |
| S2.2 Authentication/admin | S2.1 | Invitations, password hashing, sessions, roles, devices, audit and permission tests |
| S2.3 Deployment/CI | S2.1 | Limited rootless Compose, health, persistence and migrations verified; CI passes |
| S3.1 Ingestion | S1.2,S2.1 | Validated normalized observations, idempotency, deduplication and provenance tests |
| S3.2 Worker | S3.1 | Schedules, backoff, freshness/failures and recovery tests |
| S3.3 Valuation/history | S3.1 | Quantity-weighted recent, 14/60 day formulas and known fixtures; Workshop compatibility evidence separately tracked |
| S3.4 Operations | S2.3 | Retention, growth, backups and isolated restoration verified |
| S3.5 Storage longevity | S3.1,S3.3 | Compact historical daily references preserve provenance; recent raw listing retention is bounded; pricing/cursor regressions prove cleanup safety |
| S3.6 Item metadata | S3.1 | Bounded upstream metadata resolution, explicit unresolved names, indexed name search, provenance and synthetic fixtures |
| S4.1 Design review | S1.1 | Three browser-renderable high fidelity mockups presented; explicit approval recorded |
| S4.2 Explorer/deals | S2.2,S3.3,S4.1 approval | Authenticated workflows, charts, explainable filters, freshness; browser tests |
| S4.3 Administration | S2.2,S3.4,S4.1 approval | Users/markets/schedules/failures/retention/backups/devices/security browser tests |
| S4.4 Opportunity breadth | S3.5 | Supply changes and price changes with explainable thresholds/confidence and regression/browser coverage |
| S5.1 Sync contract | S2.2,S3.3 | Authenticated incremental cursor, pagination, validation, recovery tests |
| S5.2 Companion | S5.1 | Tauri credential vault, cache, offline/resumable sync, safe data-only export tested |
| S5.3 Windows releases | S5.2 | Windows CI builds/tests release artifact |

S6 addon integration is excluded. Missing live credentials and design approval affect only dependent tasks. No milestone is complete without its evidence.

Storage monitoring acceptance: independent bounded hourly sampler; cross-process idempotency; 90-day telemetry retention; signed measured growth with unknown initial rate; administrator-only history; actual browser display and migration checks.

Initial US live rollout acceptance: direct OAuth/index/house/commodity evidence; ruleset-alias and house-ID overlap checks; fresh auditable verification receipt; only one enabled feed; actual collector ingestion/conditional checks; real browser price/supply/history/listings; explicit insufficient Deal Finder history; bounded resource/error/storage monitoring; migrations/regression/backup checks. Exact player-facing routing and long-run refresh cadence must not be inferred from initial samples.
