# Companion v2 acceptance and remaining gates

**Engineering candidate; goal remains active.** Production is still the approved c8f03c2 website/API with schema0012. No v2 frontend, migration, release store or stable installer is live. Significant new designs, tray actions and owner signing remain separate gates.

## Verified Windows checkpoint

Source **e55807c58c4cf68560729471019b88cc518fb5b0** passes [Windows43652127596](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43652127596), [Backend43652127610](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43652127610) and [Website43652127630](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43652127630). Exact-source verification passes268PostgreSQL tests,6release-gate tests,50website unit tests,19Chromium workflows,64Windows core tests (including real Credential Manager), SDK cryptographic acceptance and both actual installed flows. The additional owner-signed SDK launch test compiles and is explicitly ignored until owner keys are supplied; it is not counted as passed.

The actual installed executable, real Rust IPC and actual Edge browser establish first launch, browser login/explicit approval/strict loopback return, native automatic initial and manual hidden sync, current-user startup enable/disable, unchanged machine startup, second-launch restore, real OS minimize/close hide, process restart/vault/cache/settings/hidden startup, export, server revocation and retained offline cache. The real pinned0.1 installer→v2 installer flow preserves the legacy credential, exact connection file, SQLite cache, migrated metadata, sync and export. Actual uninstalls retain exact settings/cache or connection/cache hashes and remove executable/owned startup entry. Disposable runner data is retained separately rather than erased. Tests do not touch production or game files.

Acceptance artifact14136671504 ZIP SHA256 **7e5ddcde7fa5bf061a18ecd12f8378eb1ad50a124b765339ae70accd918c8fb4**; candidate artifact14136930503 ZIP SHA256 **727d884409cc9ea4ff920b165932a6296efeeda45f117106a42385f9dc3b142f**. Downloaded archives were SHA-verified and bounded/path-checked before extraction. Raw beta installer4,404,245bytes SHA256 **da9dc6d9a00ec716211d5a716a2a5bc5902373b5b938c3576e0c8482732c5f00**. These are engineering artifacts with expiry, not stable delivery links. Ordinary users will use the controlled permanent store only after its gates pass.

## Tray classification

**Rendering verified; actions/full tray acceptance UNVERIFIED.** Initial captures selected the taskbar Pin/Close menu, an identified harness target error. The one focused corrected notification-area run selected `NotifyItemIcon` / `SystemTray.NormalButton` inside the notification overflow and captured the actual companion menu. The popup belongs to the companion, but the runner exposes its #32768 popup as UIA Pane with zero MenuItem descendants. No application action defect has been established by these failures. No action success is inferred from rendering, IPC quit, second launch or a green independent suite.

[Precise runner evidence](evidence/companion-v2-tray-runner.json) retains source/run/archive hashes and control identity; [manual owner PC checklist](companion-v2-windows-manual-acceptance.md) gives the reproducible action sequence. The strict optional automation assertions are retained. Default CI records the gap explicitly and does not retry it indefinitely. Stable release acceptance still requires the exact signed installer's real manual result.

## Measured performance

Actual e55807c installed-run samples; synthetic API and CI-only CDP enabled. These are measurements, not configured user-device guarantees.

| Measurement | Result and limit |
|---|---|
| Cold start to native window | 570.294ms,50ms polling; excludes installer, browser approval and cache download |
| Second-launch restore | 93.491ms |
| Private memory | 128,155,648bytes across native process and six owned WebView2 helpers |
| Summed working set | 376,655,872bytes; shared pages may be counted repeatedly |
| Idle CPU | 0.4655% of one core /0.1164% of four-core host over10.069s; short runner sample, not a user-device guarantee |
| Idle Market traffic | Zero extra bearer/token/sync requests during the sample |
| Established TCP | One connection, with runner CDP enabled; not evidence of production telemetry |
| Initial sync | 1754.008ms; two synthetic variants, page limit1,500ms injected/page |
| Incremental no-op check | 917.281ms under that same synthetic latency; not live-market throughput |
| Installer | 4,404,245bytes, beta/unsigned engineering candidate |
| Desktop frontend | 28,603bytes, vanilla UI; no heavy frontend framework |
| Website chunks | Local verified build: entry270,663bytes, setup10,308bytes, device cards5,093bytes; research/chart chunks stay lazy and are not required by standalone consent |

The isolated PostgreSQL100-variant/61-day benchmark identified a concrete backend bottleneck:300SELECTs/.310802s became1SELECT/.078907s with exact wire-value equivalence. That optimization retains time-window, provenance, missing/bid-only/rounding and no-op semantics. Fixture timings do not imply real Blizzard download speed. Original detailed metrics remain in the SHA-verified acceptance archive; source-bound receipts are retained in [committed evidence](evidence/companion-v2-windows-checkpoint.json).

## Full-request coverage

| Request sections | Status / remaining proof |
|---|---|
| 1 Autonomous plan/checkpoints | Full request, plan, durable ledger, focused commits/pushes and evidence retained |
| 2 Native utility UI | Implemented compact Tauri/Rust utility; real installed screenshots/accessibility reviewed; owner significant visual approval pending |
| 3 Tray | Real integration implemented, render verified; actions and owner PC restoration/double-click/menu Quit remain unverified |
| 4 Persistent settings | Versioned atomic nonsecret settings, interval choices, migration, opt-in/reversible HKCU startup, window state; actual restart/upgrade/uninstall proof passes |
| 5 Native scheduling | Rust-owned worker independent of WebView; deterministic clock/single-flight/pause/cancel/backoff/offline/wake tests and actual hidden initial/manual sync pass |
| 6 Browser sign-in | Real strict PKCE loopback, system-browser approval, vault renewal/replay and ownership/CSRF/rate security tests; actual Windows approval/restart/revocation passes |
| 7 Market preferences | Saved-choice bootstrap/fallback/local override tests pass; desktop cannot change collection settings |
| 8 Website setup | Lazy guide, honest unavailable download, server-confirmed pairing/final delivery, resume/error/accessibility/mobile tests pass; significant visual/public promotion pending |
| 9 Installer/updater | Controlled public read side and audited immutable publisher prepared; SDK signatures/tamper/version tested; owner signing, actual signed SDK installer execution and approved permanent publication pending |
| 10 Devices | Own metadata/rename/revoke, admin inspect/revoke and secret/ownership isolation tested; no cache-deletion claims |
| 11 Failure states | Safe native/browser statuses, cancellation/expiry/denial/offline/revocation/recovery and redacted diagnostics implemented/tested |
| 12 Addon boundary | Existing data-only JSON export contract retained; no game, addon, Lua or SavedVariables changes/import claims |
| 13 Production isolation | Original services/images/collector preserved, rootless resource limits retained, retention off; no AMP/host/ingress changes |
| 14 Tests | Backend/Rust/browser/actual installed Windows suites pass at e55807c; tray/signing/public deployment gaps remain explicit |
| 15 Performance | All named metrics sampled with scope/precision/synthetic limitations; demonstrated backend bottleneck optimized |
| 16 Eight screenshots | All eight actual native/web/OS captures inspected and retained in the [review packet](companion-v2-visual-review.md); owner approval pending |
| 17 Completion | Incomplete until manual tray, visual/signing, permanent release and compatible production verification gates close |

## Production preservation and deployment gate

Read-only23:12UTC check: trusted public HTTPS200/schema0012; market2/house114 alone enabled300s with zero failures and lastsuccess23:11:11.394088UTC. House110disabled with145observations intact; zero retention batches. PostgreSQL780,940,979bytes remains below5GiB guard. Original worker start14:24:43.267611827UTC, zero restart/OOM,384MiB/.5CPU; sample98.12MiB worker and183.3MiB database. This is an unchanged-deployment check, not v2 deployment acceptance.

Additive0013 populated migration/downgrade-preservation and retained old API fail-closed compatibility pass in isolation. The schema-aware audit projects original columns and preserves original history/account/credential/preferences at recorded cutoffs; a fresh production baseline and backup/checksum/isolated restoration are still mandatory immediately before deployment. Do not reuse stale restoration evidence. Preserve original image rollback, worker start/schedule, all backups/history/accounts/sessions/preferences and legacy contracts. No additional collector or destructive retention activation is authorized here.

[Owner release procedure](companion-v2-release-operations.md) documents protected dispatch, separate Authenticode/updater keys, exact-source CI, immutable installed/manual acceptance receipts, bounded publication and audited pointer rollback. No private key is requested in chat. Signing/provider expense and significant visual approval are owner decisions. Compatible public/native pairing and permanent download verification follow approved deployment; current production must not be presented as already supporting v2.
