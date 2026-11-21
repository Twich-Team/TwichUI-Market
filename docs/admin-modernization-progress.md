**Current release:** Administration modernization PR #3 is owner-approved, merged, deployed and accepted at `e9c4d29`. [Production acceptance, current image overlay and rollback](admin-modernization-release-acceptance.md) supersede historical review/deployment instructions below. Explorer / Item Details implementation is separately authorized on a feature branch; its production promotion requires final owner visual approval.

# Current review result

Implementation checkpoints are pushed through `23c9b94`, with separate queued-UX planning `505b9c3` and quality correction `7033bf4`. Live diagnostics are closed: **93 requests, 3 Everloot + 9 TheWoWDB names stored**. Same-snapshot coverage rose from 2,250/4,893 to 2,263/4,893; one additional gain belongs to the independently running Blizzard worker. No names were lost, and all original auction/history/account/preference hashes match. Only two owner/native-session revocation flags changed, reconciled against exact original credential hashes.

[Consolidated findings and deployment/rollback boundary](admin-modernization-review.md), [25-image review gallery](evidence/admin-modernization/review.html), [request/coverage/safety evidence](evidence/admin-modernization/provider-ledger.json). Production UI is still release `e7d3129`; no visual approval or deployment is inferred. Provider settings/budgets were preserved exactly. The next Explorer/Details milestone remains separately queued, with implementation explicitly unauthorized.

Final isolated checks include a fresh 25-workflow browser run, 79 frontend cases, 34 operations/consensus checks, all-nine-section axe checks, 10,000-row performance evidence and focused device/date/error/color checks. The final Retry-After safeguard also honors long temporary-error windows across items; its 53-case metadata regression run passes. Final PostgreSQL suite: 380 passed (127.99 seconds). All three final-source CI workflows passed: Backend 43678852944, Private website 43678852973, Windows companion 43678852969. Frozen application source: `a81a4e395f8367571c6188c23dff143611fb1f1c`; immutable local API/frontend images passed a no-source-mount API smoke check and exact 14-asset comparison. Four real stored Forever item identities also passed browser color/hover checks. Earlier checkpoint detail below is chronological and superseded where it differs.

# Administration modernization continuation ledger

## Checkpoint 1 — inventory and controls

Plan/inventory committed and pushed at `bbad9b7` on `development/admin-tables-provider-diagnostics`. Existing production source file digests match release `e7d3129`; no candidate code has been deployed. The current provider configuration differs from historical release acceptance and was preserved exactly. House 114 / market 2 remains the sole enabled collector, every 300 seconds.

A repeatable-read fixed baseline at 03:48:26 UTC on November 15 (8:48:26 PM MST, November 14) freezes snapshot 27, observation 293, **4,893 IDs / 2,250 names / 2,643 unresolved (45.9841%)**. ID hash `bbbacaf1ed0d9d35f997a16f83d92b6f0f009bd126284d3868d7115f8b076fc1`; price/supply hash `91a89965afb73887ebee713ebf0053f5bcca93f3997125e5dc16ae60505025b5`. Full per-ID evidence is retained under ignored `artifacts/admin-modernization`. Blizzard recovery was already running, so its gains must be separated from supplemental imports.

## Checkpoint 2 — implementation and isolated verification

Implemented one shared TanStack table system: loading/error/empty states, stable IDs, keyboard-operated expansion, column filters, page-size controls, server filtering, safe page clamping and compact styling. Converted metadata jobs/results, unresolved records, provider status, overview repeated records and administration desktop companions. Existing members/invitations/markets/retention/measurements/legacy devices retain their shared tables and controls. Account companion cards remain a justified account-specific exception.

New administration-only record endpoints page, search, sort and filter histories in PostgreSQL; no provider requests happen in a table read. Old APIs and desktop contracts remain compatible. Retries are server-checked against enabled state, source caches, credentials, quotas, cooldowns and active jobs; bulk/diagnostic attempts require an explicit preview/operator window. Credential forms stay separate and masked.

Attempt outcomes now distinguish request success, returned fields and genuinely missing fields added to the selected local catalog. Old records lacking gain evidence are explicitly qualified. HTTP 200 with no usable fields is never called recovered. Details expose an allowlist, not arbitrary JSON/headers. Provider emblems use original restrained symbols and text, avoiding unverified third-party logo rights.

Authentic deployed responses verified: Everloot consensus name for Linen Cloth, its attribute-only page (build 1.60.1.70938), and TheWoWDB Worn Shortsword (qualified beta 1.60.1.70532). Regression fixtures retain attribution and exclude prices/private responses. Tightened TheWoWDB build validation to the Forever 1.60 family; wrong identity/build outcomes are separate from generic invalid responses. Normal provider budgets and automatic settings are unchanged.

Verification so far:

- Full isolated PostgreSQL suite: **376 passed** in 139.53 seconds.
- Frontend TypeScript/Vite and **65 unit tests passed**.
- Operational tests: **29 passed**, including the bounded diagnostic runner guards.
- Affected administration/research/preferences Chromium workflows: **13 passed**; new table workflow includes axe, narrow screens, server pagination/filtering, status meaning and keyboard expansion. Final screenshots/checks follow the latest filter polish.
- Ten-thousand-record synthetic history benchmark: provider first page mean 44.66 ms, deep filtered page 109.83 ms (max 145.30 ms); security 7.54 ms, filtered security 14.92 ms. Responses contain at most 25 rows. No history download or external requests.
- Nine baseline screenshots captured from the retained released frontend/API against isolated synthetic data; candidate desktop/mobile/focused screenshots retained separately. No live credentials are present.
- Production before fingerprints captured read-only for accounts, sessions, preferences, history and retention. Final comparison remains required after diagnostics.

## Active provider experiment

Owner authorization: one verification window ending **04:30 UTC November 15 / 9:30 PM MST November 14**, at most 200 total external attempts across both providers, with existing quotas/cooldowns intact. The operator runner charges and records each request before I/O, holds the existing metadata lock, deduplicates requests and stops on access/rate/schema failures. No automatic provider is enabled. Strictly validated named sample records may be manually stored through existing catalog precedence; credentials never leave the server.

Deterministic stratified sample: 48 unresolved IDs for Everloot, first 24 shared with TheWoWDB, SHA-256 seed `admin-investigation-v1`, round-robin across primary missing/pending, icon, prior attempts/attribute-only, quality and ID-range categories. Five strata are actually present. Positive controls and the attribute/corpus checks count toward the same cap. Requests skipped by caches/locks/intervals do not consume an outbound attempt.

At this checkpoint TheWoWDB's documented endpoint succeeds from the deployed server, returning ETag/cache and **X-RateLimit-Limit 120 / Remaining 119** on the control. Historical 403 is not currently reproducible; no IP/client disguise, proxies or access bypass were used. Everloot authentic named responses parse correctly, but sampled unresolved IDs have so far returned missing. Exact final counts, committed gains, same-population coverage and production preservation remain pending; do not infer the final result from this interim record.

## Next actions

Finish the bounded sample and permitted bulk/corpus/conditional-response inspection; publish exact per-provider findings and same-snapshot coverage. Verify final screenshots, permissions, row actions, current test evidence and secret scan, then push the consolidated review candidate. Prepare data-preserving deployment/rollback and request visual approval only after the candidate is concrete. Do not deploy the new UI before that approval.
