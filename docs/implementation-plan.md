# Implementation plan

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
| S4.1 Design review | S1.1 | Three browser-renderable high fidelity mockups presented; explicit approval recorded |
| S4.2 Explorer/deals | S2.2,S3.3,S4.1 approval | Authenticated workflows, charts, explainable filters, freshness; browser tests |
| S4.3 Administration | S2.2,S3.4,S4.1 approval | Users/markets/schedules/failures/retention/backups/devices/security browser tests |
| S5.1 Sync contract | S2.2,S3.3 | Authenticated incremental cursor, pagination, validation, recovery tests |
| S5.2 Companion | S5.1 | Tauri credential vault, cache, offline/resumable sync, safe data-only export tested |
| S5.3 Windows releases | S5.2 | Windows CI builds/tests release artifact |

S6 addon integration is excluded. Missing live credentials and design approval affect only dependent tasks. No milestone is complete without its evidence.
