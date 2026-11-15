# Item Metadata Recovery progress

## Current milestone
M4: independent implementation verified and delivered for review; external provider/coverage/keyring/owner gates remain pending. Plan: [milestones and acceptance](item-metadata-recovery-plan.md).

## M0 verified 2026-11-14
- Exact starting commit `64ef6d2d08e7453458ed37d06d29f263ac19d126`, clean detached checkout, application files present; created independent `feature/item-metadata-recovery` after checking remote name availability.
- Read AGENTS.md, implementation/progress and modernization documents; existing metadata/provider/coverage code and evidence inspected.
- Python 3.12.14 locked venv: pip check clean; Node 24.22.1 and restored node_modules present.
- Local extracted PostgreSQL 17.12, cluster `/workspace/market-cloud/pgdata`, private Unix socket, TCP disabled, disposable `market_test`; no production connection or application credentials. Clean-environment wrapper used for all backend commands.
- No auction collector/application worker was running; no production/SSH/Docker actions. Infrastructure desktop processes left alone. Available memory >16 GiB and disk >59 GiB; proposed localhost ports free.
- Smoke: 17 PostgreSQL tests in test_metadata.py/test_auth.py pass (7.78 seconds). Setup's prior 34/50 test counts are historical setup evidence, not this task's full verification.

## Completed work
Implemented and tested the versioned local catalog, documented adapters, persistent bounded workers/jobs, secure provider administration, local website/desktop metadata APIs and review-candidate UI. Historical checkpoint entries below retain their original status.

## Next actions
See the acceptance packet and PR checks for final verification. Owner follow-up: provision the private external keyring, supply keys through Data Sources, validate real provider contracts/access, obtain a legitimate recent per-ID snapshot and measure real coverage, then review visuals and separately authorize integration/deployment. Do not request keys through chat.

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

## M3 verified checkpoint
- Backend `cafa1be` and UI/verification `a828d25` pushed; [draft PR #2](https://github.com/Twich-Team/TwichUI-Market/pull/2) targets `dev/s1-s5-implementation`, attached to this chat. No merge/deployment.
- Full backend checkpoint: 284 tests passed (110.32s). Expanded focused suite: 40 recovery/media cases passed; patched cryptography 50.0.0 and both dependency audits pass. All 50 frontend unit tests/build pass.
- Real built-frontend Chromium metadata workflow passes with nine screenshots, three WCAG A/AA axe scans, no horizontal overflow at 390px, no page errors and zero third-party metadata requests. Styling refinements fixed oversized native checkboxes and unstyled secondary buttons found by inspecting actual screenshots.
- Migration rehearsal preserves nonempty synthetic prices/history/users/credentials/preferences and names across upgrade/downgrade/re-upgrade; populated metadata downgrade refuses. Existing Companion rehearsal now derives the actual additive head and passes original-row preservation and full empty round trip.
- Rollback-only benchmark: 5,000 observed fixture IDs, 500 client-record import 3.97s (~126/s); five warm handler medians: coverage 28.25ms, name search 9.33ms, Explorer 18.43ms; process peak RSS ~84.4MiB. These are synthetic handler measurements, not production coverage or p95.
- First full local browser run: 17/20 pass; three failures traced to Docker-only `http://proxy` fixture/context assumptions, not metadata functionality. Bounded loopback opt-in and matching fixture origin are being added; production/browser auth behavior is unchanged.
- Read-only integration check at `abe299c22639e9d067a2b8f0817ffb578e6e17cc` still has no schema conflicts. A simulated merge found a workflow append conflict; moving the metadata check ahead of the retained Companion check reconciles it on this branch without merging/rebasing or modifying Companion history.
