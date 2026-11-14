# Implementation plan

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
