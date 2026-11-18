# Owner Workshop failure: missing deployed server support

2026-11-18 UTC. Owner DEV3ba8013 reports the generic “Workshop needs attention” message. Its diagnostics export contains only the price worker's transient Network error while another price download is pending, and omits the durable Workshop delivery error. `workshop_setup=null` is not a failing setup check. The 24,584-record completed cache remains present; no claim of completed current download or game consumption follows.

Read-only production inspection confirms that the running API registers **zero `/api/v1/workshop/` routes**. Bounded API logs (last 40 minutes, at most 6,000 lines, aggregated without cursors or credentials) contain **two summary 404 responses**, **543 price-sync 200 responses**, one price-sync 401 and no exception types. The deployed service is retention base fe92999 with patch 3ebd8b3, as documented in the release acceptance. The integrated Companion requests the summary endpoint after successful price synchronization. An installer or Windows ACL change cannot supply the missing endpoint. The owner's separate transient price-download Network error is not attributed to the 404 without evidence.

The focused DEV correction distinguishes a missing summary endpoint from an expired partition, authentication and transient service errors. Workshop displays “Server update required” and explains the server API requirement. Diagnostics now include the separate durable delivery result/error and bounded counters/timestamps through a fixed-field projection, excluding installation paths, account identity, signed cursors and arbitrary fields. This is a reporting correction; it does not make the absent server deliver summaries.

## Concrete server rollout candidate and approval boundary

The already implemented, reviewed [automatic delivery candidate](workshop-automatic-delivery-review.md) contains the missing support. Relative to deployed code, the application scope is:

- Register the Workshop router in `market/app.py`.
- Permit only the exact authenticated summary/partition GET routes in `market/security.py`.
- Add `market/workshop_summary.py` and `contracts/workshop-summary/v1` schemas.
- Retain the independent nonblocking snapshot-derivation reservation in `market/bridge_api.py`.

Existing bridge models and disposable export tables are reused; no Workshop schema migration, collector/retention/provider configuration, website asset, signing key, addon or signed Companion publication is required. Preserve the deployed two-module retention recovery/selector patch and existing overlay chain. Deploy only matching API/local API images after exact-source backend/contract tests and bounded resource/recovery validation. Verify authenticated summary preparation, eventual complete validated manifest/parts and warm unchanged response; a 202 alone is not delivery acceptance. Preserve all last-good files/caches and immutable releases. Roll back only these API images if necessary; do not run incompatible pre-unified readers. Current genuine-history availability and actual owner-PC loaded generation remain checks, never assumptions.

**Owner subsequently approved “Approve Workshop API rollout.”** The earlier approval boundary is superseded for this concrete API-only scope. [Current deployment, validation and rollback](workshop-api-release-acceptance.md). The independent sync-performance goal remains paused, its edits/evidence preserved in its separate worktree, with task-owned fixture services stopped.

## Focused verification

Local actual HTTP response-classification regression and sanitized diagnostic projection pass. Mocked native-IPC Chromium Workshop flows pass, including the explicit missing-server message, ordinary retries, preparation, account/market changes, mobile/focus and WCAG checks. These are fixture/UI evidence, not owner-PC or deployed Workshop acceptance. The fast Windows DEV workflow adds these focused native checks and verifies that the installed diagnostics command includes the separate delivery section. Full release/performance certification is outside this repair.
