**Active owner-authorized production repair:** PR #10 is reconciled with integrated M1.5 `5b27cc7`; no bridge code/limits change. Actual live Linen search stalls because the newest snapshot is estimated as one row and its nested-loop plan repeatedly computes the matching-items subquery. Candidate materialization plus scoped history returns 33 genuine matches in about 0.22 seconds without ANALYZE. Catalogue SQL/browser deadlines now produce an actionable retry state. The old ForeverDB form/API cap at 2,000 rejects saves before persistence; PR #10 supplies independent validated quota controls. Local checks pass 100 focused PostgreSQL tests, 121 frontend tests and ten Explorer browser workflows; the old-query negative control fails the stale-snapshot deadline. Fresh backup/restore and additive rates migration preserve original market/provider/credential/counter/job rows. The provider browser round trip/accessibility workflow also passes; current-source CI, merge and production promotion follow; previous rollout and bridge-capacity hold remain intact.

# Provider rate management progress

**Current status:** implementation and local visual verification complete; [draft PR #10](https://github.com/Twich-Team/TwichUI-Market/pull/10) is created and attached after direct owner confirmation. Hosted backend/website/Windows CI is running; final results are recorded in the PR description/checks. [Review packet](provider-rate-management-review.md), [ten screenshots](evidence/provider-rates/review.html), [prepared PR destination/body](provider-rate-management-pr.md), [deployment/rollback](provider-rate-management-operations.md). No merge or deployment.

## Isolation and baseline

- Separate Cloud worktree and feature branch created from pushed integration SHA `68c075138d5f50608c741b0e51b7013d9bf8769d`. No other branch/worktree is modified; production and addon repository are untouched.
- Read AGENTS.md, implementation/progress and item modernization plans/progress plus existing metadata provider decisions. The integration head already includes bridge migration `bridge_20261115`; the additive provider migration must descend from it.
- Initial Cloud resources: 18,007 MiB RAM, ~17 GiB available, 60 GiB free disk. Proposed ports 19432/19480/19481 unused. Docker reports rootless; no production services, volumes, networks or secrets are present/used.
- Git HTTPS reads work. GitHub CLI's inherited token is invalid; connected GitHub tools work. Push access and PR creation will be verified separately.

## Audit

Existing `metadata_recovery.reserve_budget` charges persistent anchored hourly/daily counters and spaces calls; a session advisory lock serializes recovery workers. Task leases commit before I/O and preserve charged usage on crashes. Credential tests share this reservation. Enrichment artwork uses the same counters but currently holds its transaction during I/O. Legacy optional resolver paths and operator diagnostic scripts need to share the same reservation as well.

Current ceilings are application choices, not key entitlements: ForeverDB 60/hour, 500/day; Everloot keyless 20/hour, 100/day or validated 240/hour, 2,000/day; TheWoWDB 60/hour, 500/day; Blizzard metadata 240/hour, 2,000/day. No minute window or token bucket exists. Editing settings does not reset counters. 429 supports Retry-After dates but lacks bounded adaptive pacing and response quota observations. A queued 429 retry can be skipped by source caching or an exhausted job budget. Validation selects one provider before checking cooldown, potentially delaying others. Existing UI shows raw cumulative counters even after a window expires.

## Next

Implement scheduler/schema and independent limits API; research findings and test evidence follow in dedicated review documents. No live-provider verification is authorized or performed.

## Implementation checkpoint

The existing reservation entry point now uses row-locked, committed rolling buckets plus preserved legacy guards. Per-provider configuration, TheWoWDB refill/burst state, concurrency leases, numeric quota observations and 429 adaptive cooldown are persisted separately from secrets. Validation, automatic/manual/bulk/stale recovery, legacy name/media/community calls and operator diagnostics share accounting. Public Blizzard artwork CDN is independent of the authenticated API; TheWoWDB-hosted artwork shares that provider's pool. No collector code, pricing, desktop/addon contracts or deployment configuration changes.

Rate editing is independent from connection settings and credential replacement. The UI distinguishes documented limits, configured maxima, observed quota and estimates; expired windows display zero current usage. Jobs retain queued work across cooldown and do not count it as permanently failed. An exhausted finite campaign pauses for explicit retry allowance rather than silently overspending or discarding a 429 item. The metadata worker wakes for configured pace, capped at four ticks/second and sleeping normally when idle; existing resource limits remain unchanged.

Verified locally: full baseline-plus-feature PostgreSQL suite **543 passed** (238.85s); subsequent scheduler refinement suite **106 passed**; artwork/community and quota follow-up **57 passed**; API/accounting follow-up **50 passed**. Frontend **119 unit tests**, TypeScript/Vite build and **34 operational checks** pass. Provider, legacy metadata and Companion migration preservation/downgrade/re-upgrade rehearsals pass at `rates_20261115` descending from `bridge_20261115`. Additional cross-process/wakeup/hot-reload checks and actual browser verification are in progress.

Synthetic full-day bucket benchmark improved from 56.265 ms median / 9 SQL statements to **18.000 ms / 6 statements** after using scalar rows and a bounded atomic bucket upsert. Status view: 10.208 ms / 1 statement; quota relation 237,568 bytes for 1,441 minute buckets. These are local warm handler measurements, not production p95 or real provider throughput.

The browser review uses a separately named rootless `provider-rate-review` Compose project, uniquely tagged images, temporary `market_test`, localhost port 19482, bounded memory/CPU/logs, and only db/migrate/api/proxy. No collector, enrichment worker, live credentials, production networks or volumes are used. Synthetic quota fixtures are applied after ordinary browser workflows to keep those tests independent.

## Verified delivery state

- Core implementation pushed at `8588f1a90f5bd491acd804540f985fad4e1a8568`; initial isolation/plan checkpoint `96374be`. Final visual/verification checkpoint follows this entry.
- Final PostgreSQL run: **550 passed in 290.95 seconds**. Frontend: **119 passed** plus TypeScript/Vite; operations: **36 passed**. Both dependency audits report no known findings.
- A new slow-response regression proves Retry-After begins at response receipt rather than request start. 503 resumes after its appropriate cooldown; HTTP success is tracked independently from schema/name recovery. A 5,000-row authenticated Everloot fixture preserves page/request distinctions and hashes the page once.
- Final clean ordinary Chromium run: **38 passed in 4.6 minutes**, including all seven Companion auth/device flows. The provider flow: **1 passed in 14.9 seconds**, ten actual screenshots, zero desktop/mobile axe violations, keyboard expansion, saved configuration, retained drafts, 429/job waits, source labels and credential controls. Visual inspection found/fixed a native preset-select clip at 390px; a bounding-box regression now guards it. Synthetic waiting work belongs to an enabled provider with automatic mode off and no worker.
- One unchanged private-download test requires hostname `proxy`; not run locally because managed Chromium blocks that hostname. CI retains it. Initial blocked-hostname attempts contaminated synthetic device fixtures; the final ordinary suite ran after recreating the disposable project/database. No unrelated source/tests were changed to force a pass.
- Browser fallback uses the supported **localhost:5173** origin. The earlier localhost:19482/temporary alias probes are retired; no host DNS/proxy setting was modified. Locked wheels and the verified host build support temporary offline review images after nested build DNS / Playwright image pull failures. All 50 backend module hashes and frontend index match current source.
- Provider, metadata and Companion migration verifiers pass with one linear head `rates_20261115` → `bridge_20261115`. Final synthetic full-day reservation median **21.244 ms / 6 SQL statements**, status **18.515 ms / 1**, relation **237,568 bytes**. API RSS **147,184 KiB** at capture. Docker records requested API/frontend/DB resource limits, but Cloud exposes a shared 16 GiB cgroup; per-container enforcement/CPU statistics are not claimed. Production collector limits are unchanged.
- Final integration fetch remains `68c075138d5f50608c741b0e51b7013d9bf8769d`; Workshop remains `e2116007638b23228eace44d524b9fe2a43c2249`. No actual upstream conflict or migration ancestry change exists. Full backend/Companion browser checks include that pinned merged baseline. Original checkout remains clean at `64ef6d2d08e7453458ed37d06d29f263ac19d126`.

### Remaining external gate

Automatic approval review rejected both an incomplete PR-tool request and a fully specified retry for Twich-Team/TwichUI-Market, feature/provider-rate-management → integration/companion-v2-metadata-recovery. It states that the trusted transcript does not contain the authorization carried in the uploaded file and therefore refuses PR publication. The request's repository/PR instructions were read back from the attachment; no alternate PR-creation route was used. All unaffected work continues to a concrete pushed packet. Ask for direct confirmation only after that packet is complete; then create/attach the **draft**, inspect hosted CI and stop at owner review. No PR URL, hosted CI or native Windows success is fabricated.

## Draft publication authorized

The owner directly confirmed **Open the draft PR** in the chat. [PR #10](https://github.com/Twich-Team/TwichUI-Market/pull/10) was created from `65b0d27363c9005c637b4a9911c171022a384abd`, attached to the task and verified draft/unmerged/mergeable. The earlier automatic-review publication gate is resolved. Hosted backend, website and Windows workflows started. This documentation checkpoint records the changed status; final hosted CI evidence is maintained on the PR to avoid recursive documentation-only reruns. No merge or deployment is authorized.
