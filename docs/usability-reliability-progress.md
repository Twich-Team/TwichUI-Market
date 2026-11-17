# Owner observations — four milestone ledger

Started 2026-11-17 UTC. Owner authorizes implementation, tests, pushes and draft PRs; no merge, deployment, destructive production retention or permanent account/device removal.

## Exact baseline and isolation

Production API/local API/enrichment image `b25a1b319916a158107aba0d882cdb217861610e0012015193adf766d6955e94`; frontend `83d808b1fb145433cbd6127fe3250053f883b71bcb14db9f59229cd1afc12af7`. All carry revision `6bb71a61fa3493da3f418288c3af1841fabfb0fc`. Read-only database schema `fdb_20261116`; sole active house 114, interval 300 seconds, zero failures. Owner device 3 Windows PC beta.3 is authorized and has genuine recent sync activity. No online heartbeat guarantee.

Latest integrated source is `6cef35797f28d562c7ee3db3aa290cfe876f418d`, including newly merged PR #15 / L2 `15e2775dab6ceff7a4449d78d6c00c63afc54a60`. Production does not contain L2. Preserve its manual-only delivery/contract safeguards. Prior worktrees: release/explorer-provider-repair-73617a9 `4b90bff`; integration/m15-companion-release `4daef96`; original release/foreverdb-6bb71a6-acceptance `f4fbbaf`. Original untracked release overlays untouched. GitHub PR search reports older open umbrella PRs #1 and #2. Default main remains initial commit; combined PR must target integration/companion-v2-metadata-recovery.

Dedicated branch `feature/market-usability-admin-reliability`, worktree `.worktrees/usability`. Rootless Docker only. Initial available RAM 11 GiB / filesystem 3.7 GiB. Use unique disposable market_test services, bounded resources, no collector/provider workers. No production mutations for reproduction.

## Acceptance matrix

“Pending” is work in progress, not a verified result. Each row becomes completed, verified existing behavior, externally blocked or requiring owner approval only with evidence.

| # | Milestone | Observation | Status / evidence |
|---|---|---|---|
| 1 | 1 | Device status | Completed candidate: logical Companion + unlinked legacy counts, recent 15-minute requests, explicit unknown live status; read-only persisted proof and isolated assertions |
| 2 | 1 | Deal icons | Completed candidate: bounded batched local media delivery, card identity, single observer lazy gate; actual no-hover/delayed/filter/scroll/reload/mobile browser checks |
| 3 | 1 | Test members | Completed candidate: typed-confirmation archive/reversible listing restoration, revoke all access, self/last-admin guards; 96 production identities with creation+closure receipts, none modified |
| 4 | 1 | Stale Companion entries | Completed candidate: owned/admin typed archive requires prior revocation, retains security history; isolated cleanup, API ownership/revocation and actual browser controls verified |
| 5 | 1 | Retention/compaction | Completed candidate: deliberate production gates verified; fixed credential-FK cleanup failure and legacy ungated compaction path, actual 5,000+1,201 batch/replay/resume/price-preservation fixture |
| 6 | 2 | Metadata summaries | Pending |
| 7 | 2 | Coverage charts | Pending |
| 8 | 2 | Provider coverage | Pending |
| 9 | 2 | Database growth | Pending; hourly measurements already exist |
| 10 | 2 | Storage units | Pending; formatter stops at MiB |
| 11 | 2 | Overview | Pending |
| 12 | 3 | Loading system | Pending |
| 13 | 3 | Explorer notices | Pending |
| 14 | 3 | Metric tooltips | Pending |
| 15 | 3 | Actual 24H/48H history | Pending |
| 16 | 3 | Listing freshness | Pending |
| 17 | 4 | Updater/bridge contracts | Pending; inspect latest integrated L2 and addon before changes |

## Checkpoints

Initial inspection complete. No services allocated, production records changed or credentials read. Historical pruning remains disabled. Significant visual changes require final owner review.

### Milestone 1 — correctness and administrative cleanup

Confirmed roots: Overview used `/admin/devices` (legacy `kind=device`) instead of browser-approved Companion registrations; Deal Finder dropped `icon_url` from its ItemInfo props and the API omitted media for opportunities; historic production verifier scripts intentionally retained disabled users with security receipts but no display archive existed. Existing device cards incorrectly called authorization “Connected.” Counts now aggregate logical registrations, excluding rotated native tokens, and never claim online status.

Archive controls retain users, devices, FK ownership, preferences and audit; no permanent-delete API is offered. Accounts cannot archive themselves or the last active administrator. Devices must first be revoked, and owner operations enforce ownership. Restore only restores list visibility; credentials stay revoked and accounts stay disabled. Test fixtures are confined to market_test, pytest tears down their schema, CI tears down disposable volumes, and the two historical account-creating verification scripts now refuse non-test databases before creating identities. Production cleanup candidates and exact audit evidence are in `evidence/usability-reliability/production-cleanup-review.json`: 96 disabled accounts, each with one creation and one closure receipt, zero unrevoked credentials; four revoked Companion devices, plus owner device 3 explicitly protected. No production cleanup occurred.

Retention defaults and disabled compaction are deliberate. No scheduler calls the destructive engine. Policy authorization and exact fresh restored-backup binding, actor-bound expiring confirmations, changed-candidate/replay rejection, partial rehydration and cursor full refresh are retained. New realistic fixture removes exactly 5,000 then 1,201 eligible old raw rows while preserving the current listing and price calculations. A legacy CLI could previously apply unbounded snapshot-based history compaction without these gates; it now refuses outside disposable fixtures and directs production to signed bounded batches. Old credential cleanup could violate the authorization FK; referenced approval sessions and native credentials are now retained as evidence. Historical retention and destructive batches remain disabled in production; live batch count is zero, runtime `HISTORY_COMPACTION_ENABLED=false`.

Verification so far: PostgreSQL migration upgrade/check/downgrade/re-upgrade passed; focused cleanup/auth/opportunity/retention tests passed (28). Earlier native authorization regressions passed while one existing self-demotion test exposed an over-broad guard; corrected to preserve existing permitted demotion and the focused auth rerun passed. Frontend 123/123 unit tests, TypeScript and Vite build passed. Two actual synthetic Chromium acceptance flows passed (18.6s), with axe checks and 390px no-overflow. Inspected screenshots exposed crushed table-cell confirmation controls; fixed with shared accessible native modal dialogs, then reran the two flows successfully. Viewport screenshots and final expanded maintenance/sync checks follow in the checkpoint record. Screenshots are explicitly synthetic; production observations are read-only SQL/image-label evidence only.

Milestone 1 final expanded check: **40/40 PostgreSQL tests** across cleanup, auth, opportunities, retention, maintenance, long history and sync. Application TypeScript/build and 123 frontend tests passed. Two actual synthetic browser flows passed; gallery at `evidence/usability-reliability/review.html`. Diff reviewed, no production user/device/account changes, no live deletions, no collector/provider or bridge changes.

M1 pushed checkpoint **bdd6e4c456e1e393a8631e8eeae00dbc2e017125**, [draft PR #17](https://github.com/Twich-Team/TwichUI-Market/pull/17). Remote website 43994382008 and Windows 43994382049 passed. Backend 43994382010 passed migrations/pytest but its older metadata-preservation harness incorrectly compared new schema columns to old rows. Corrected to compare original columns; the integrated archive-migration harness now also inserts baseline-compatible fields and hashes original columns. All five populated preservation/downgrade/re-upgrade rehearsals pass locally at usability_20261117. Added a dedicated archive-column preservation rehearsal with separate populated user/device downgrade refusal; no production migration occurred.
