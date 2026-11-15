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

## M4 final independent acceptance — 2026-11-15 UTC (2026-11-14 Denver)

- Functional checkpoint `90bc88f0c56185ce8d4e796b20fe6af32e7ea64b`: **301/301 PostgreSQL tests pass (146.28s)**, including **37 metadata recovery/security cases**. Both populated preservation/downgrade rehearsals pass again. The earlier full run crossed UTC midnight and exposed future-dated 10:00/12:00 sync fixtures; the fixtures now anchor to the prior day without changing product ingestion/pricing/sync behavior.
- **50/50 frontend unit tests, TypeScript/Vite build, dependency audits and 20/20 actual Chromium workflows pass.** The complete browser run took 1.8 minutes; all metadata/admin/Explorer/Deals/account/preferences/Companion/touch workflows pass together. Earlier preference polling timeout passed focused and final complete reruns.
- Nine final actual browser screenshots, byte hashes and dimensions are committed under `docs/evidence/metadata-recovery-screenshots`. They show synthetic database data and an empty secret form. Three axe scans and 390px overflow checks pass; no page errors or third-party metadata requests. Visual owner approval remains pending.
- All providers have queued connection tests. Validated Everloot keys permit an explicit bounded increase up to 240/hour and 2,000/day; keyless ceilings/cooldowns remain enforced. The retained legacy operator command only queues durable jobs. Batch recovery also selects named items without basic attributes. Pending-name measurements do not double-subtract preserved names after a 404 refresh.
- `144205d` isolates the CI-only keyring initialization from retained shared fixture steps. Direct smoke verifies this initialization creates a private ephemeral keyring without changing database row counts, then restores the previous ephemeral keyring. Source code and tests stay on the pinned baseline; no Desktop source was changed.
- Final bounded rollback-only fixture: 500 client records / 3.42s (~146/s), 2.04 CPU seconds, 84.7MiB peak process RSS. Five warm handler medians: coverage 33.06ms, name search 16.35ms, Explorer 28.29ms. Same-dependency entry JS size is unchanged; administration grows ~15.3KiB, research ~1.1KiB and CSS ~2.3KiB uncompressed. These are synthetic measurements, never production coverage or p95.
- Combined simulation evidence remains 299 complete PostgreSQL regressions against committed Companion `abe299c`, then 128 relevant PostgreSQL cases plus 15 operational/release gates against `027765a`. Latest committed head `cad6c8e9bb4ddcab8ae0f7b72f3a73c09f647366` changes private-beta fixtures/UI/workflows, not migration identities or existing security/v1 contract files. A simulated integration tree merges cleanly; no actual branch merge/rebase was performed.
- Remote backend checkpoint `af0751c` passed run 43655431454; earlier website run 43654540502 passed. Current shared website run 43657170874 passes build/unit/audit/container startup/metadata-keyring setup/main fixtures, then fails because the newly added `web/e2e/seed-private-beta.py` is absent from the pinned head-only checkout. Native/private-beta helper/legacy-installer integration likewise needs the owner-reviewed combined source. This external CI dependency is not reported as passed or worked around by importing unrelated Companion release code. The PR links the final checks.

## Delivery and exact follow-up

[Acceptance packet](item-metadata-recovery-acceptance.md), [source research](item-metadata-recovery-providers.md), [coverage boundary](evidence/metadata-recovery-coverage.json), [operations/backup/migration/rollback](item-metadata-recovery-operations.md), [screenshots](evidence/metadata-recovery-screenshots/README.md) and [draft PR #2](https://github.com/Twich-Team/TwichUI-Market/pull/2) provide the reviewable result. Independent implementation/testing is complete; genuine provider coverage remains unmeasured.

Owner-managed external steps: privately mount/back up the encryption keyring; enter actual provider keys in Data Sources; obtain permitted target-host responses and authorized ForeverDB schema evidence; measure a legitimate fixed current market-2 per-ID snapshot; review visuals; authorize combined-source integration/CI and separately any merge/deployment. No key should be sent in chat. No production/AMP/other-session action, collector start, release, migration or deployment was made in this task.

## Feature commit history through implementation/CI checkpoint

- [`9a7bad1`](https://github.com/Twich-Team/TwichUI-Market/commit/9a7bad1bfddfaa50cf6e138732e52e891817b675) docs: record isolated metadata recovery plan and baseline
- [`cafa1be`](https://github.com/Twich-Team/TwichUI-Market/commit/cafa1be69a9744fb65c110bcd3723f61d8245ab0) feat: add versioned metadata catalog and secure bounded recovery workers
- [`a828d25`](https://github.com/Twich-Team/TwichUI-Market/commit/a828d25f1a257f680d5868a60e8d7f4c5c2ed2ab) feat: integrate metadata administration local provenance and verification
- [`b2a70dc`](https://github.com/Twich-Team/TwichUI-Market/commit/b2a70dc58693dfe4f092b9987b130ff6cca26869) test: support isolated localhost verification and reconcile CI ordering
- [`f245a57`](https://github.com/Twich-Team/TwichUI-Market/commit/f245a5737679f360f054edf91fb891651518914f) fix: balance artwork requests and preserve clear unknown metadata
- [`9aebe68`](https://github.com/Twich-Team/TwichUI-Market/commit/9aebe68ad7d08eddd40367aeef136d1fc262035f) ci: run Companion release gates when present in the checked out branch
- [`daac794`](https://github.com/Twich-Team/TwichUI-Market/commit/daac794e767c2f9d049418911655c7085a646b10) test: enforce disposable database guards for metadata operations
- [`cb320d0`](https://github.com/Twich-Team/TwichUI-Market/commit/cb320d060e1f5111e1c2b2a99bafd2744e5a7467) fix: reject repeated bulk pages and clear rolled back import results
- [`af0751c`](https://github.com/Twich-Team/TwichUI-Market/commit/af0751cf42b123deede18533e0cdbba22e265afc) fix: keep metadata validation handler separate from Companion router registration
- [`7549570`](https://github.com/Twich-Team/TwichUI-Market/commit/75495704a94cbc4473daa046aa1853bf0bc4ac88) docs: preserve actual metadata recovery screenshots and performance evidence
- [`e4c38e4`](https://github.com/Twich-Team/TwichUI-Market/commit/e4c38e43ccd7574cad2624d5dd0d56a06f8db62c) feat: finish provider connection controls and bounded keyed recovery budgets
- [`517c48d`](https://github.com/Twich-Team/TwichUI-Market/commit/517c48da93423a555ea8cb55529dfcca570c0a52) fix: route legacy recovery through jobs and include missing base attributes
- [`90bc88f`](https://github.com/Twich-Team/TwichUI-Market/commit/90bc88f0c56185ce8d4e796b20fe6af32e7ea64b) fix: count preserved names correctly and make sync fixtures safe after midnight
- [`144205d`](https://github.com/Twich-Team/TwichUI-Market/commit/144205db5a843f315980e4e15b1ad2c9194fa8da) ci: isolate metadata fixture setup from concurrent Companion seed steps


## Final integration-readiness assessment — 2026-11-15 00:49 UTC cutoff

- [Precise integration plan and owner actions](item-metadata-integration-readiness.md) covers source/merge order, actual conflicts, CI, migration preservation/index preparation, separate production keyring recovery, direct Data Sources key entry, bounded isolated VM provider checks, fixed-snapshot per-ID measurement and separate visual/merge/deployment gates. Existing implementation/provider research/functional acceptance remain intact.
- Read-only Companion source progressed cad6c8e →49cbd4d→**bb6b76c6a1e73bd257130854ad76df097cbc195b** during assessment. The owner now requires zero-cost Tauri signed automatic updates; the older manual-only candidate is superseded. No active session/worktree/VM/credential access or coordination mutation occurred.
- **Compatibility commits pushed on metadata only:** `0c9e0a89d0b5878319ed49c555b48484e7968a47` adds Actions-only exact-source checks; `db08ab8298a4d97bc7a69ec22ecfc2be7e4591f6` accepts only proven forward preview-base advances; `45e14984b8f5e39c337c11f43057381a6781d634` aligns equivalent prior-day UTC fixture expressions with Companion. Six source-helper tests plus four metadata operation guards pass; 10 targeted PostgreSQL sync cases pass. These fixes change no product runtime, provider behavior, schema or desktop source.
- Two actual textual conflicts in sync fixtures appeared when Companion independently fixed the same midnight bug; they are now reconciled with all assertions retained. Five other shared workflow/app/browser-compose paths merge cleanly. Final bb6b76c simulation tree `9d58dadd30ad598d796d6fe056b02c03c1957d13` is conflict-free; one Alembic head still follows **0012 →0013 →meta_20261114**. No actual merge/rebase/branch integration occurred.
- **All three combined checks pass against frozen Companion 49cbd4d + metadata 45e1498**, actual tested PR preview `9037de672a8e7e06c286fff60e4f0cbbc9443154`, tree `af2f5b50d8af74f7fbd55a8fb9adb37af7e4dc22` matching local simulation. [Backend43659526235](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43659526235): **338 PostgreSQL tests**, **22 operational/release gates**, audit, schema drift, both preservation/populated-downgrade/empty-round-trip rehearsals. [Website43659526134](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43659526134): **60 unit tests/build/audit,22/22 actual Chromium flows** including metadata/private beta. [Windows43659526155](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43659526155): Rust/Tauri/HTTP/auth, package, actual archived legacy upgrade, installed/restart/preservation and old unsigned/updater-disabled proof pass. These PR-preview artifacts are not release approval or evidence of final signed-updater acceptance.
- The exported same combined tree independently passes **338 PostgreSQL tests in130.62s** in this task's isolated Cloud PostgreSQL test database (explicit source path, not a stale installed package). No new production/provider claims arise from these synthetic fixtures.
- **Latest Companion-only bb6b76c:** Backend43659839984 passes; website43659840016 was running at cutoff; Windows43659839992 fails Rust E0308 in `desktop/src-tauri/src/updates.rs:118,140,144,232` (SystemClock i64 vs CheckSchedule u64). Exact owner action: reconcile clock types safely, retain negative/backward-clock/backoff tests and run native/Windows acceptance. The former website logout race (49cbd4d run43658363949) is already fixed by bb6b76c's signed-out form wait, preserving401/404 assertions; do not repeat that fix. No metadata code remedy is indicated for the native failure. Fresh combined checks are required on the owner's final frozen successor.
- Corrected runbook wording: atomic host-file rename does not update a single-file bind mount, and an in-place write is not atomic. Master-key rotation needs an approved directory mount/atomic replacement or controlled API/enrichment remount; ordinary API-key replacement through the completed UI still needs no restart.
- Owner sequence: finish/freeze Companion readiness and exact combined CI; authorize separate integration candidate; operator provisions isolated VM preview/new private keyring/sanitized genuine snapshot without collector services or shared production resources; owner reviews metadata visuals and enters Everloot privately in Data Sources; run **≤20 total attempts/≤45 minutes**, export unchanged fixed ID/price manifests before/after; review real evidence; explicitly decide merge and separately deployment/automatic enablement. No production credentials, merge, VM operation, deployment, collector action or release publication occurred here.
