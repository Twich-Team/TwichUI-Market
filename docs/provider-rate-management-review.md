# Provider rate management review candidate

Implemented on `feature/provider-rate-management` from exact pushed baseline **`68c075138d5f50608c741b0e51b7013d9bf8769d`**. Core checkpoint: **`8588f1a90f5bd491acd804540f985fad4e1a8568`**; the subsequent visual/evidence checkpoint adds the verified mobile-select constraint, large-page hash optimization and review artifacts. The final commit hash is supplied with delivery.

Production, the original checkout, the concurrent Workshop branch and the addon repository were not modified. Nothing was merged or deployed. No real provider credentials were read and no live provider quota was consumed.

**Remaining delivery gate:** automatic approval review rejected draft-PR creation, including a retry that explicitly named the authorized repository/head/base and quoted the uploaded request. Its stated reason is that it cannot recognize the user's authorization in the uploaded file and considers publishing PR metadata unauthorized. No alternative PR-creation path was used. The prepared [draft PR](provider-rate-management-pr.md) targets `integration/companion-v2-metadata-recovery`; direct user confirmation is needed to unblock that action and hosted CI. No PR URL or hosted CI success is claimed.

## Result

- Data Sources exposes provider-specific finite allowances, verified ForeverDB free/paid presets and approved custom allowances. Changes are independent of keys, enablement and campaigns, require acknowledgement above documented defaults and preserve existing usage/cooldowns.
- The existing scheduler uses atomic PostgreSQL provider-row reservations, conservative rolling minute/hour/day accounting, preserved legacy counters and a shared TheWoWDB token bucket. Configuration, quota observations, cooldown/adaptive state and concurrency leases survive restarts. All existing recovery paths, validation, metadata/media compatibility entry points and provider diagnostics share the correct pool.
- 429/Retry-After seconds or dates, clock skew, repeated throttling and temporary 503 recovery persist safely. Retry delay starts at response receipt. Other providers remain eligible. Queued rate-limited work is preserved; a spent campaign budget pauses for explicit retry allowance instead of marking the item permanently failed or silently overspending.
- The UI distinguishes configured maximums, officially documented values, provider observations and application estimates. It separates successful HTTP calls from useful field recovery, shows cooldown/next eligibility and local-time job waits, preserves unsaved edits during polling and keeps advanced accounting optional.
- Blizzard item safeguards, auction collection/schedules, source identity/build checks, attribution, secret encryption, historical observations, valuation and desktop/addon contracts remain intact. No additional service was introduced.

The original rate-control audit is in [progress](provider-rate-management-progress.md). [Official provider research](provider-rate-management-research.md) identifies exactly what is documented versus unknown. ForeverDB's actual approved exception cannot be discovered from `/meta`; that endpoint describes game data. Administrator-entered limits remain statements, not independently verified entitlement.

## Verification

| Check | Actual result |
| --- | --- |
| Full PostgreSQL backend suite | **550 passed**, 290.95 seconds, isolated `market_test` |
| Frontend unit tests | **119 passed** |
| Operational/security guard checks | **36 passed** |
| Existing local browser workflows | **38 passed**, 4.6 minutes; includes Companion auth/device and metadata/collector-administration regressions |
| New provider browser workflow | **1 passed**, 14.9 seconds; ten actual screenshots |
| Accessibility | Zero WCAG A/AA violations in desktop and 390px provider views; keyboard advanced-controls and retained unsaved edits verified |
| Narrow screens | No document overflow; preset select explicitly remains within its provider card (a clipped native select found during visual inspection was fixed) |
| TypeScript / production Vite build | Passed |
| Dependency audits | npm production: zero vulnerabilities; backend lock: no known vulnerabilities |
| Migrations | Single head `rates_20261115`, parent `bridge_20261115`; provider, legacy metadata and Companion preservation, protected downgrade and re-upgrade rehearsals passed |
| Source identity | All 50 backend module hashes and frontend index match the tested Cloud workspace/image; [runtime receipt](evidence/provider-rates/runtime.json) |
| Hosted backend/website/Windows CI | **Not run**: draft PR remains blocked; native Windows execution is not claimed |

One unchanged private-download browser workflow requires hostname `proxy`; it was not run locally because the managed Cloud Chromium proxy blocks that hostname. It remains in normal hosted CI. The other private-download retry workflow and all seven Companion authorization/device workflows passed at the supported localhost origin. Early blocked-hostname runs left synthetic records; the final 38-workflow run used a fully recreated disposable database and passed cleanly. No unrelated desktop tests or contracts were changed to hide an environment failure.

[Machine-readable verification](evidence/provider-rates/verification.json), [browser receipt](evidence/provider-rates/browser-verification.json), and the [ten-scene gallery](evidence/provider-rates/review.html) provide the review evidence. All provider/quota data shown are **synthetic**. Screenshots retain the established espresso/walnut/bronze styling and are review candidates, not visual approval.

## Database and accounting

The additive migration adds ten nonsecret state/configuration columns and `metadata_quota_buckets`, keyed by provider/resolution/start time. It does not rewrite secrets, existing budgets, committed counters, schedules, cooldowns, jobs or historical data. Minute guards use second buckets; hour/day guards conservatively retain intersecting minute buckets for at most 59 seconds extra. Token refill/burst is separate from daily quota. Existing anchored counters remain additional guards until their original expiry; individual pre-upgrade request timestamps are unavailable.

Quota is charged before I/O and never refunded after interruptions. The provider lease conservatively blocks abandoned in-flight requests for up to 120 seconds. Account-wide quota remains shared when credentials rotate. Other consumers of an account or public IP remain unknowable locally, so a provider observation includes its capture time and application remaining values stay estimates.

## Performance and isolation

A warm synthetic full-day fixture with 1,441 minute buckets measured **21.244 ms median** reservation, 93.588 ms maximum over ten calls, six SQL statements; status view 18.515 ms / one statement. Relation allocation: 237,568 bytes. An earlier run measured 18.000 ms median; timings vary with concurrent test load. The initial implementation's 56.265 ms / nine statements was reduced through scalar reads and one atomic bucket upsert. These are local handler measurements, not production p95 or real upstream throughput. Large Everloot pages hash their common envelope once rather than once per record.

The separate rootless `provider-rate-review` project runs only PostgreSQL, migration, API and frontend on localhost:5173, with unique review image tags and temporary `market_test`. No auction collector, enrichment worker, production network or production volume was started. API PID 1 measured 147,184 KiB RSS / 147,332 KiB high-water at capture. Requested container limits are API 384 MiB / 0.5 CPU, frontend 128 MiB / 0.25 CPU, DB 512 MiB / 1 CPU.

**Cloud measurement limitation:** Docker records those limits, but this Cloud runtime exposes a shared 16 GiB cgroup and identical aggregate Docker statistics. Per-container enforcement/CPU statistics cannot be claimed here. No host cgroup or proxy configuration was changed; production collector/resource settings remain untouched. The actual runtime receipt distinguishes requested limits from observed process memory.

Container builds used the unchanged locked dependencies downloaded on the host and the verified host Vite build, because nested build DNS and the Playwright image pull were unavailable. Temporary Dockerfiles correct Cloud checkout file ownership for the existing non-root API user. These adaptations are isolated under ignored `.local`; normal repository Dockerfiles and production Compose files are unchanged.

## Concurrent integration and owner next steps

Final fetch resolves integration to the same baseline `68c075138d5f50608c741b0e51b7013d9bf8769d` and Workshop to `e2116007638b23228eace44d524b9fe2a43c2249`. There are no new upstream changes to reconcile. The complete backend suite already contains that merged bridge/pricing/worker baseline; the feature adds one linear migration after its head. No moving-branch rebase, unrelated cherry-pick or other worktree modification occurred. Original checkout remains clean at `64ef6d2d08e7453458ed37d06d29f263ac19d126`.

After PR authorization: create the prepared **draft**, attach it to the task, inspect hosted backend/website/Windows CI and address any relevant failures on this feature branch only. Retain draft/visual-review status; do not merge or deploy. The actual ForeverDB grant remains an owner input before any separately approved production limit change. No live keys are required for the candidate's mocked tests.

[Deployment and data-preserving rollback](provider-rate-management-operations.md) require explicit later release approval, preserve the additive schema and accounting on rollback, and never start the collector profile wholesale. Production's actual approved migration ancestry must be checked before any release; parent bridge changes must not be silently skipped or promoted without their own approval.
