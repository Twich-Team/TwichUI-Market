# Item Metadata Recovery progress

## Current milestone
M1: documented adapters and additive local catalog. Plan: [milestones and acceptance](item-metadata-recovery-plan.md).

## M0 verified 2026-11-14
- Exact starting commit `64ef6d2d08e7453458ed37d06d29f263ac19d126`, clean detached checkout, application files present; created independent `feature/item-metadata-recovery` after checking remote name availability.
- Read AGENTS.md, implementation/progress and modernization documents; existing metadata/provider/coverage code and evidence inspected.
- Python 3.12.14 locked venv: pip check clean; Node 24.22.1 and restored node_modules present.
- Local extracted PostgreSQL 17.12, cluster `/workspace/market-cloud/pgdata`, private Unix socket, TCP disabled, disposable `market_test`; no production connection or application credentials. Clean-environment wrapper used for all backend commands.
- No auction collector/application worker was running; no production/SSH/Docker actions. Infrastructure desktop processes left alone. Available memory >16 GiB and disk >59 GiB; proposed localhost ports free.
- Smoke: 17 PostgreSQL tests in test_metadata.py/test_auth.py pass (7.78 seconds). Setup's prior 34/50 test counts are historical setup evidence, not this task's full verification.

## Completed work
Baseline and isolation verified. Provider research underway using public documentation and bounded credential-free GETs.

## Next actions
Implement schema/catalog/adapters, verify security and worker behavior, then UI and complete acceptance evidence. Commit/push independently verifiable checkpoints.

## Commits
Starting baseline above; subsequent checkpoint hashes recorded after commit.

## External blockers and integration
No Blizzard/Everloot/ForeverDB private credentials, no production snapshot/connection, no owner master encryption key. Historical repository snapshot is 4,978 IDs / 1,191 Blizzard names (23.93%), recorded at 2026-11-14 14:08 UTC for market 1/snapshot 12; not today's current market-2 coverage. Provider source overlap cannot be extrapolated from aggregate evidence.
Companion baseline migration is 0013. Use a metadata-specific revision identifier and inspect latest committed integration head before delivery without checking it out, merging or operating its session.

## M1/M2 implementation checkpoint
- Planning checkpoint `9a7bad1` pushed to the independent feature branch.
- Added metadata-specific Alembic revision `meta_20261114` after baseline Companion `0013`, without touching existing observation/pricing/account/device columns. PostgreSQL pg_trgm index serves local substring search. Empty migration upgrade/drift check passed; populated downgrade is guarded.
- Normalized source records and immutable source versions project field-level provenance/conflicts into the existing local metadata path. Blizzard fields retain precedence; null/failed refreshes preserve good data. Existing data gets a bounded local-only backfill.
- Implemented documented Everloot card-name and paged client-attribute adapters, conservative ForeverDB minimal-envelope gate and retained optional TheWoWDB beta adapter. [Research and network limitations](item-metadata-recovery-providers.md).
- Persistent resumable jobs/tasks, dedupe and independent worker advisory lock; committed request reservations, bounded one-request concurrency, crash leases, manual controls, budgets, ETags, negative caches/cooldowns, automatic recent/view-priority/older observed items.
- AEAD AES-256-GCM envelopes, private external keyring, staged background replacement validation, previous-key preservation, rotation and expiry warnings; no secrets returned, reflected in validation errors, logged or stored in browser persistence.
- 45 focused PostgreSQL regressions passed, including 20 new recovery/security cases. Frontend build and all 50 unit tests passed. Full backend suite and expanded failure/budget cases underway.
- Draft admin UI and additive authenticated local catalog export are implemented; actual browser/visual evidence remains pending. UI remains an owner-review candidate.
- Read-only fetch of latest integration head `6d1f819d68bbc00f7629d2a7c11b92d6a141eea5` found no new migration, security.py or contract changes relative to pinned baseline. No checkout/rebase/merge or other-session action occurred.
