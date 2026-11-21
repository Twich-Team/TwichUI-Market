# Owner review — usability, administration and reliability

Implementation is complete for all technically unblocked work. Production remains `6bb71a61fa3493da3f418288c3af1841fabfb0fc`. Nothing was merged, deployed, pruned, published or irreversibly cleaned up. A [final read-only production guard](evidence/usability-reliability/production-final-guard.json) confirms schema unchanged, house 114 alone at 300 seconds with zero failures, owner beta.3 device unrevoked and zero retention batches. [Market draft #17](https://github.com/Twich-Team/TwichUI-Market/pull/17) and [addon draft #42](https://github.com/Twich-Team/TwichUI/pull/42) stop at owner review.

The [17-item acceptance matrix and detailed progress](usability-reliability-progress.md) records each observation, confirmed causes, evidence and limitations. Items 1–16 are completed candidates. Item 17's implementation and available tests are complete; Windows/game-client acceptance and the absent addon simulator remain externally unverified. All significant visual changes require owner approval.

## Review evidence

[19 actual screenshots](evidence/usability-reliability/review.html) cover every requested website scene plus the Companion dashboard notice. They use disposable synthetic `market_test` fixtures. The Companion screenshot uses mocked IPC and proves browser rendering only. Screenshots were inspected; they are not owner approval or production observations. Hashes are in [screenshots.json](evidence/usability-reliability/screenshots.json).

[Read-only production coverage/growth](evidence/usability-reliability/production-coverage-growth.json): the measured current market contained 5,147 base item IDs, 4,860 named (94.42%), 4,858 with useful attributes, 287 tried/unavailable unnamed items and two pending items. These are explicit current-observation denominators; provider overlaps are not summed. Unknown fields/recovery prospects remain unknown. The 73 hourly size measurements span November 14–17; allocation was 2,842,375,859 bytes. Growth is measured allocation, not future demand or space immediately recoverable by SQL deletion. The candidate's same-transaction coverage probe preserved all shared counts and took 1.383s versus 2.406s previously; this is one operator measurement, not a statistical benchmark.

[Retention verification](usability-reliability-progress.md): production defaults are deliberate safety gates. Synthetic destructive batches removed exactly 5,000 then 1,201 old raw rows, preserved current prices/history, rejected replay and resumed safely. Signed policy/backup/fresh-restore/actor controls remain required. The ungated legacy CLI path now refuses production and points to the bounded engine. A credential/authorization FK cleanup defect is repaired. No automatic pruning schedule or production authorization was introduced.

[Production cleanup review](evidence/usability-reliability/production-cleanup-review.json) identifies 96 already-disabled historical verifier accounts, each with creation/closure audit receipts and no unrevoked credentials; four revoked Companion entries are separate from protected owner device 3. Their historical origin was intentional production verification, not current isolated CI. No guessed-name deletion occurred. New fixtures refuse production and tear down disposable schema/volumes. Typed-confirmation account archival revokes access, retains all security/owned records and hides ordinary listings. Device archival requires prior revocation. Restoring visibility does not restore authorization. Permanent deletion is deliberately unavailable where security/ownership must be retained.

[24H/48H semantics and bounds](intraday-history.md): last actual observation in each UTC hour, exact market/item/variant, at most 25/49 edge-inclusive buckets, 4,096-header cap and three-second SQL deadline. Gaps remain null/unobserved, not interpolated; compacted/unsupported statistics remain unknown. Local timestamps disambiguate DST. Prices remain observed per-unit asks in exact copper, not completed sales. A real stored-data read-only probe returned 13,201/25,164 bytes in 14.4/7.8ms for 24H/48H respectively; this is not a deployed route observation or latency guarantee. No collection frequency or retention changed.

[Compatibility contract](../contracts/bridge/compatibility/README.md): reuse receipt `desktop_build`, transport 1, manifest contract 1, receipt schema 1 and explicit generation schemas 1/2/3 with minimum reader capability profiles 1/2/3. Marketing versions never determine data compatibility. Future supported identifiers require explicit implementation and fixtures. Unknown newer versions tell players to update TwichUI; obsolete versions direct them to update Companion and export again. Full bounded validation and atomic activation preserve the last valid dataset on refusal. No pricing, hashing, identity, protocol limits, local history or SavedVariables changes.

Companion updates already checked automatically at eligible startup/connection, then daily with one-hour failure backoff. The confirmed issue was Settings-only visibility. The candidate adds a dashboard banner, tray review/tooltip and hidden/minimized notification. A bounded persisted atomic version watermark suppresses duplicate/older notices across restarts. Transient offline failures retain the known update hint. Pinned signing key, secure metadata, owner installation confirmation and offline behavior remain. No new Companion version was published; OS delivery can be suppressed by Windows settings and has not been observed here.

## Source checkpoints

| Milestone | Market commit(s) |
|---|---|
| 1 — correctness/cleanup | `bdd6e4c456e1e393a8631e8eeae00dbc2e017125`, migration harness `2a502c59f9ff2a302ec107d1626c5cca30628378` |
| 2 — administration | `af58c8f565014e170d4ce4fbfb66f69f6aeb0bf0` |
| 3 — player experience | `9cf6a436caa5c3385edddcf77367e7e69073679e`, stable toolbar follow-up `0a7c8d92c3805b4e7448a902b9121fc5320bcf62` |
| 4 — Companion/contracts | `a260b7273e8664bda1ca67cac7a7b97693ee7838` |
| Final access-race hardening | `df4d974bec1adb157fbca8b0eabb99f5190c6286` |

Addon remote `46b4074d007b7b182d8b9e2f4eb7a1a9a1e90e0b` is based on main `3a33269fc75d9daa5c24525c4e66f0095e2a194f`; its fetched tree matches local tested checkpoint `f5a388db936818a9ca02272733a23fe09cf12908`. The branch was delivered using the authorized GitHub connector because the existing Market deploy key cannot write to TwichUI. No SSH configuration was modified. Policy source/hash is pinned across repositories.

## Verification and remaining acceptance

Local verification passes 129 frontend tests, TypeScript/Vite, five owner-observation browser flows with axe/reduced-motion/390px checks, the unchanged pagination height/scroll/racing-response test, Companion mocked-IPC keyboard/layout/confirmation checks, 92 passing Rust workspace tests (one pre-existing opt-in capacity workload ignored), producer contract tests, migration preservation/downgrade refusal and realistic retention checks. Four additional administrator identity-cache regressions prove a request authenticated before concurrent disable/demotion cannot remove the remaining administrator. Existing account isolation, native sync/export and signature checks remain in their suites.

Addon feature selection: 48 offline checks pass. The runner's overall result is **FAIL** solely because its selected simulator cannot find the separate `wow-ui-sim-lab` checkout; this is not a successful simulator run. After the final policy pin and UI assertions, all 14 reader/compatibility checks and the actual scoped Workshop page test pass separately. Lua 5.1 syntax passes. No automatic addon PR CI is configured; manual release workflows were not invoked. No real-game or simulator visual acceptance is claimed.

Final combined CI for application `df4d974bec1adb157fbca8b0eabb99f5190c6286` is green, testing integration preview `2b166c76e7f757069c102b8ccad00f6cb686ddac`:

| Workflow | Result |
|---|---|
| [Backend 44005390956](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44005390956) | 605 PostgreSQL tests, migrations/preservation/downgrade guards, dependency audit, 44 operational Python and 16 scoped-contract checks pass |
| [Website 44005391032](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44005391032) | 129 frontend tests, build/audit, 48 Chromium workflows and mocked-IPC Companion layout/archive checks pass |
| [Windows 44005391081](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44005391081) | Native compilation/tests, authenticated sync/export/renewal/revocation, installed hidden-window synchronization, legacy upgrade, NSIS install/uninstall retention and original signed SDK acceptance pass |

[Machine CI summary](evidence/usability-reliability/ci.json). Actual Windows update toast/tray behavior is separate and remains unverified. GitHub validates its PR integration preview; release promotion still requires exact integrated-source CI and explicit approval. Earlier failed/skipped/cancelled attempts and repairs remain in the ledger. The closing evidence/docs-only commit skips duplicate CI; the application is unchanged from this green checkpoint.

The isolated review containers/network are retired after verification; their database used disposable tmpfs. Source worktrees, local evidence and the committed gallery remain available. No production containers or host listeners were allocated or changed for reproduction.

## Integration steps requiring owner authorization

1. Review the gallery and both draft PRs. Complete real Windows tray/minimized notification acceptance and the missing addon simulator/game-client import checks before treating those platform behaviors as accepted.
2. Reconcile against the then-current integration branch and addon main; preserve concurrent work. Market baseline includes integrated L2, which is newer than production. Keep manual bridge/history-delivery holds, pricing defaults and experimental scope unchanged. Obtain separate merge/deployment authorization.
3. For an approved website/API release, take a fresh verified backup and restore it in an isolated `market_test` database; apply the complete reviewed migration chain through `usability_20261117`. This adds nullable archive columns after `archive_20261116`; original data/credentials/preferences must retain fingerprints. Run exact-source CI and public authenticated smoke checks. Use the current ForeverDB release procedure as the starting point, with a reviewed new overlay/service scope. Do not reuse a frontend-only overlay for the new API fields.
4. Keep original collector/metadata workers/database/monitor/backup settings and identities, house 114 at 300 seconds, provider quotas/keys, market mappings and destructive-maintenance disablement. Website/API rollback can retain additive columns; migration downgrade refuses populated archive state to avoid silently losing it. Do not drop history or restore a database over live records as an ordinary application rollback.
5. Companion notification changes require a separately authorized signed release using the existing updater key and standard install/upgrade acceptance. The beta.3 distribution stays unchanged. The addon reader change needs separate owner-approved integration/publication; existing validated Companion exports remain compatible. No publishing is authorized by this report.
