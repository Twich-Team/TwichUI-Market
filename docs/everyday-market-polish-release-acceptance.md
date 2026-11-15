# Everyday Market Polish production release

The owner explicitly approved PR #5's visual design and implementation for integration and production deployment. The approval covers the reviewed application `dfb645b8946f0d158e8da9855fef01768e382674` and review/evidence head `09b3c1d84c976da0251e786c2931c4022f9f4e8b`. Earlier review-only instructions are superseded for this bounded release.

Fresh inspection confirmed production frontend `4ddf137712084292b899e7b352fe41b751e8e70b`, APIs/metadata worker `e9c4d299cdf781be0e362edb26b4de6097a33e6a`, and integration base `e34b1498b078454869da7905b3b498ef99060e4c`. PR #5's application/test/workflow files still matched the frozen candidate. [PR #5](https://github.com/Twich-Team/TwichUI-Market/pull/5) was marked ready and merged without conflicts as **`7202e07a62f1770642b50afe5a3ec671d9b488cf`**. [Approval receipt](evidence/polish-release/approval.json).

## Exact integrated CI

All required workflows ran on **the actual integration push at `7202e07`**, not the prior PR preview:

| Workflow | Result |
| --- | --- |
| [Backend 43725495169](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43725495169) | **383 PostgreSQL tests**, **34 operational checks**, dependency audit and isolated upgrade/check/downgrade plus metadata/Companion migration rehearsals passed. |
| [Website 43725495277](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43725495277) | TypeScript/Vite, **115 frontend tests**, production dependency audit and **39 Chromium workflows** passed. |
| [Windows 43725495227](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43725495227) | Core/native/protocol, HTTP authorization, packaged release, actual legacy installer upgrade and installed-release compatibility passed. No new desktop release was published; the gated signed-updater job found no new signed candidate, so no new signed-SDK acceptance is claimed. |

[All jobs/steps](evidence/polish-release/ci.json), [backend excerpt](evidence/polish-release/ci-backend-excerpt.txt), [website excerpt](evidence/polish-release/ci-website-excerpt.txt), [Windows excerpt](evidence/polish-release/ci-windows-excerpt.txt).

## Backup, isolated restore and data preservation

Fresh archive **`market-development-20261115T144140952029Z.dump`**: **232,493,758 bytes**, SHA-256 **`588e89f76a83e00c8846286d13baccf1969110da31a2051bf1d42e883bed1a28`**. It restored successfully into disposable `market_restore`, retaining **85 users, 423 observations, 4,328,867 listings, 934,662 statistic rows and 17 preference records**, with zero synthetic observations. PostgreSQL validated restored constraints; original history/account/session/preference/market/retention fingerprints match the pre-release baseline. The candidate reports no schema drift, and the restored owner's authorization plus the existing encrypted provider credential decrypt with the protected existing keyring, without an external provider request. Schema remains `meta_20261114`; no production migration ran.

All **26** archives pass size/SHA-256 verification, including all 25 earlier archives. The existing backup service's conservative guard rejected its estimate of 1,452,209,843 uncompressed database bytes plus 1,971,438,564 archived bytes against the existing 3 GiB budget. A one-shot `pg_dump` through that same service streamed into a private `.partial` file with a hard remaining-budget cap of 1,249,786,908 bytes and at least 2 GiB disk reserve. The actual new archive fits comfortably; no earlier archive was rotated, and no backup budget, schedule, service image or retention policy was changed. The established bounded 3 GiB restore disk / 4 GiB memory rehearsal was reused and removed afterward.

[Backup/restore manifest](evidence/polish-release/backup.json), [budget bounds](evidence/polish-release/backup-budget.json), [restored preservation](evidence/polish-release/restored-preservation.json), [archive checksums](evidence/polish-release/archives.json). The conservative backup preflight remains a known scheduling limitation: a future scheduled dump may be rejected even when its compressed archive would fit. This release preserves the existing capacity policy and all archives; the fresh bounded dump and its restoration are verified.

## Deployment and immediate rollback

Only **`api`, `local-api` and `proxy`** were replaced, at **2026-11-15 14:51:16–14:51:35 UTC / 7:51:16–7:51:35 AM MST**. Matching revision-labelled images:

- API/local API: **`sha256:48caf6befd76baa96460d2096e6c71280b961e2e8060ccc3d39a05b2f86bd5a8`**, tag `twichui-market-backend:polish-release-7202e07`.
- Frontend: **`sha256:06605be1c7b4651c4bc2fa763af30e1a517177189fd861e5c1404960f37f4c79`**, tag `twichui-market-web:polish-release-7202e07`.

[Complete configuration comparison](evidence/polish-release/compose-preflight.json) proves only those three image fields change. The collector, metadata worker, PostgreSQL, monitor and backup retain their original identities/images/start times; every service's runtime environment matches. Provider flags, automatic mode, quotas, credential ciphertext/key identity, connection state and expiry are checked directly against the actual pre-release state, rather than copied from older reports.

Append the new overlay **last** to the complete production configuration; never run an unscoped `up` or print rendered secret-bearing configuration:

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml -f compose.explorer-release.yaml \
  -f compose.polish-release.yaml up -d --no-deps --wait api local-api proxy
```

The immediately preceding APIs `e9c4d29` and frontend `4ddf137` are retained in [compose.polish-rollback.yaml](../compose.polish-rollback.yaml). For a genuine release regression, preserve diagnostics, append that rollback overlay **last after the complete command above**, and replace only `api local-api proxy`. Keep every schema, database volume, provider setting/credential, collector/metadata worker, market mapping and history record. Do not restore an archive over production or downgrade its populated schema.

## Acceptance findings and limits

The first public run established audited temporary public/local admin/member sessions, a legacy device cursor and stored preferences before the actual swap. The same identities, secure cookie, cursor and preference values/revision survived the replacement; CSRF/origin rejections and the member/admin boundary passed before the subsequent name-search timeout. [Across-deployment continuity receipt](evidence/polish-release/session-continuity.json) preserves that distinct boundary. Later complete verification is a post-deployment recheck, not a second deployment.

That search timeout reproduced in both the unchanged preceding API and `7202e07` under a three-second read-only statement limit. The estimated plan expected **one row** in current snapshot 38, where **21,752** statistic rows actually existed, reproducing the existing planner-statistics freshness issue documented in the preceding release. Only the failed verifier query was cancelled, matched by exact PID/start time and its 29.94-second assertion window; no collector query was touched. Standard **`ANALYZE snapshot_statistics, item_metadata, observations`** refreshed planner statistics. The same name search then completed in **228.62 ms** on the old handler and **128.45 ms** on the new handler. These are bounded local-handler samples, not public p95 or a general speedup claim. No query, index, schema, pricing, market or collector setting changed. Recurring planner-statistics freshness remains an operational consideration; no automatic tuning feature was added.

The verifier initially measured the table before its first results finished loading; waiting for an enabled Next control and a completed first page corrects that readiness error. It also corrected the expected first sort direction and the exact Numeric item ID form label. No product change or rollback followed from those harness failures. Original failed-run evidence is retained under ignored `artifacts/polish-release`; final acceptance uses real public HTTPS data and does not mock provider/application responses. The injected pagination delay postpones the actual request rather than fabricating its response.

Known limits inherited from the reviewed candidate: historical attempts lacking field deltas remain labelled unrecorded; old operator probes without recovery-task records cannot be reconstructed; daily aggregation remains UTC-based while observation instants display locally; no new artwork coverage, owner-PC manual tray result, desktop distribution or signed-updater candidate is claimed.

## Final public HTTPS acceptance

The full production browser run passed at **2026-11-15 15:05:55 UTC / 8:05:55 AM MST**, using the actual public hostname, trusted TLS 1.3 and real authenticated APIs. Certificate errors were never ignored; source observations report `synthetic=false`. No application/provider responses were fabricated. [Complete public receipt](evidence/polish-release/verification.json), [research measurements](evidence/polish-release/research-evidence.json), [provider results and recovery guards](evidence/polish-release/provider-results-evidence.json). Public HTML and all entry JavaScript/CSS bytes match the deployed image by SHA-256: [asset receipt](evidence/polish-release/public-assets.json).

| Surface | Production result |
| --- | --- |
| Explorer | Compact search/market/column/refresh controls; real name search, sorting, pagination and shared column-menu Escape behavior pass. With 1,200ms imposed request delay, the catalogue remains **620 → 620px**, footer movement **0px**, internal scroll **80px** retained. Rapid page changes reject stale results. |
| Variants and navigation | Far-right expansion only expands; item names navigate. Sole-variant Bent Staff #35 resolves directly to its verified exact URL. Destiny #647 has a real multi-variant selector and exact links. Reload, new tab, sign-in return, Back/Forward and Explorer/Deal Finder return state pass. |
| Item Details | Actual supply/price/history/asking auctions match authenticated API data. Concise local Last seen date has an exact local timestamp tooltip. Player tooltips omit expanded provenance by default; optional technical details stay on the same URL. Required linked credits remain visible. Common/uncommon/rare/epic quality colors pass on four known real items. |
| Time and responsive display | America/Denver chart labels use real observation instants; exact history retains UTC daily buckets and timestamps. Local date-boundary/DST/other-zone regressions are covered by exact integrated CI. At 390px, Details has no document overflow; wide tables scroll internally. |
| Provider results | Default all-market view displays real persisted attempts; explicitly selecting older market 1 shows its actual **3** records. Provider/outcome/name-or-ID/local-date filters, pagination, sorting and expanded redacted diagnostics pass. An actual ineligible diagnostic retry returns **409**, without creating work. Recovery preview shows the bounded item scope and Start recovery action; **Start was not clicked**. Successful enqueue/persistence cases are covered by isolated CI, rather than a new production recovery campaign. |
| Account and administration | All nine administration sections load. Saved preferences persist through sign-out/sign-in. Public/local authentication, CSRF and origin rejection, member/admin boundary, logout and device revocation pass. The first-run receipt separately proves sessions/preferences/device cursor survived the actual deployment. |
| Companion | Owner-authorized existing private download returns the original **2.0.0-beta.2** installer, SHA-256 **`0fbc53603c218ffa85c8ee7b4e54f25e53c52a6fc3b2330ae914337714d41869`**. Unauthenticated download is denied; original website download/integrity controls pass. Exact-source Windows CI covers native and API compatibility. |

The [12-scene production gallery](evidence/polish-release/review.html) includes the compact catalogue, delayed pagination, expanded rows, sole/multiple Details, player/technical tooltips, local chart, persisted results, linked attribution, mobile and existing Companion download. Completed-load/unobstructed catalogue and sole-variant/chart screenshots were refreshed at 15:13:20 UTC; the complete acceptance run is preserved separately. The [original 15-scene before/after gallery](evidence/everyday-polish/review.html) and [root causes, source changes, shared components and attribution review](everyday-market-polish-review.md) remain the implementation record. Those earlier fixture scenes are explicitly isolated test data, not production observations.

## Final preservation, health and cleanup

[Final original-row fingerprints](evidence/polish-release/final-preservation.json) match the [pre-release baseline](evidence/polish-release/before.json) exactly: all original 85 users, 191 credentials, 17 preferences, 422 observations, 38 snapshots, 4,328,867 listings, 934,662 statistic rows, verification receipts, mappings and retention policy. The backup captured the naturally arriving 423rd observation as well. No production migration or destructive retention ran. Existing metadata storage was reused, and the normal automatic worker continued; no historical metadata erasure or replacement occurred.

[Final health](evidence/polish-release/final-health.json) confirms **only market 2 / house 114 at 300 seconds**, **zero new collection failures**, and successful post-deployment upstream **304** checks at **14:55:32, 15:00:35, 15:05:37 and 15:10:40 UTC**. Destructive retention has zero authorizations and zero batches. All provider enablement/automatic flags, hourly/daily budgets, encrypted credential digest/key ID, expiry and connection status equal the actual baseline. No operator recovery job was created.

[Before](evidence/polish-release/containers-before.json) and [final](evidence/polish-release/containers-final.json) identities confirm that only matching APIs and frontend were replaced. Collector, metadata worker, PostgreSQL, monitor and backup retain their original container IDs, images and start times. All production environments, CPU/memory/process/log limits are unchanged. AMP, Traefik, Komodo, host listeners/networking and unrelated services were untouched.

Twelve temporary audited browser accounts were created across acceptance attempts and the supplemental screenshot capture; all are disabled and their credentials revoked. Every temporary owner acceptance session is revoked, the private temporary environment file is removed, and original owner credentials were never reset. Disposable restore/browser containers are removed. The related localhost:18444 review proxy/API/test-DB containers were retired after successful public acceptance; retained rollback images and production data remain intact.

The production source is **`7202e07a62f1770642b50afe5a3ec671d9b488cf`**. This acceptance checkpoint adds only release/rollback image overlays, documentation and evidence; application, contracts, tests and workflow source remain identical to that fully tested integrated commit. [Evidence checksums](evidence/polish-release/manifest.json).
