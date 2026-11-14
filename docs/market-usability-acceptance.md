# Market usability, configuration and historical retention review

Implementation is ready for owner review in the existing read-only preview at https://localhost:18444. The design remains unapproved. Production retains the previous frontend and existing ingress configuration. No live historical pruning or market switch was performed.

## Market identity

Fresh authenticated Blizzard requests verify US house 110 as Alliance and 113 as Horde. House 113 returns the same 99,451 listings through ruleset 1 and 2 URLs; the returned ruleset link changes with the request. Neither the URL nor that link verifies Normal versus PvP. Forever Mastery reports deriving Normal from an in-game scan, but the public pages obtained do not expose its numeric house correspondence. Character/player-associated numeric evidence is still missing. Confidence and source receipts are in [market findings](market-identity-findings.md).

**US Normal — Horde cannot safely be activated yet.** Its guided choice is blocked. One existing Alliance house 110 feed continues on its five-minute schedule with its complete history. The verified registry, duplicate alias guards, diagnostics and confirmed atomic single-market transition are implemented. Transition leaves the previous market disabled with history intact.

## Names and presentation

A fixed 4,978-item snapshot increased from 1,147 Blizzard names (23.04%) to 1,191 (23.93%) over a bounded 50-request primary enrichment pass. Concurrent scheduled enrichment can contribute to that delta. Later genuine-data browser verification saw 1,192 names among 4,981 current item IDs, also 23.93%. The independent, bounded metadata service continues resolving items without holding the auction collection lock.

Fresh runtime requests for six actually missing IDs and the TheWoWDB developer page return HTTP 403. Current successful fallback coverage cannot be verified, so supplemental enrichment remains disabled. Its adapter preserves primary precedence, exact edition/build identity and linked beta attribution; no current Blizzard verification is inferred from beta data. See [coverage and provider findings](item-name-coverage-findings.md).

Catalogue rows select directly; single variants need no expansion; multi-variant expansion is separate. Selection survives sorting, paging and refreshes. Heading, row, variant and tooltip artwork share components. Normal browsing hides internal hashes. Original SVG coins, exact BigInt amounts and textual equivalents are shared across prices. Zero denominations are omitted visually without losing the complete accessible amount. Sparse ECharts retain actual points, units, legends and explanations; technical controls are disclosed and comparison UI is removed. Shared TanStack tables cover all meaningful administration lists and server-paged current auctions, including fractions of a copper, commodities and bid-only rows.

## Verification and measurements

- 136 PostgreSQL regressions and 23 frontend unit tests pass. All six browser workflows passed the integrated implementation; the three affected catalogue/explorer/administration workflows also pass after the final refinements.
- Final application commit f7df30e passes Backend 43605289573, Private website 43605289498 and Windows companion 43605289511. The Windows workflow exercises the existing native companion and full-refresh recovery behavior; the new server tests cover old cursors after historical compaction.
- Migration 0011 upgrade, model parity, downgrade to 0010 and re-upgrade pass on isolated market_test. Destructive retention tests are isolated; partial rehydration, shared references, exact retained valuations, authorization, backup identity and stale cursor recovery are covered.
- Genuine-data preview verification uses trusted project CA roots, with no ignored TLS errors. Explorer, market configuration, retention and mobile axe scans have zero violations. Final screenshots are visually inspected and include loaded artwork/charts and populated listings after sorting.
- Current catalogue handler: 32.209 ms median over five runs, six SQL statements, 50 item groups / 35,209 bytes. Retention dry run: 167.495 ms on the populated database. Handler timings exclude HTTP/browser costs.
- Three fresh Chromium contexts on the same read-only origin: previous preview median 1,589 ms; refined preview 1,802 ms, **13.4% slower** in this sample. Initial decoded JavaScript grows from 484,631 to 529,741 bytes, DOM nodes from 640 to 1,527; extra coin identities and listing controls cost rendering work. Catalogue remains bounded to 25 rows, current listings to 25 per server page, and return navigation makes zero API requests. These are small samples with authentication/network-idle settle, not production p95. No overall speedup is claimed.

## Retention proposal, impact and recovery

Proposed raw listings: **7 days**. Intraday statistics and observations: **90 days**. Daily market history: **365 days**, with an additional **60 days of supporting daily observations/statistics** to preserve rolling references. Collection logs: 90 days; security logs: 365 days. Longer durations, including six months and multiple years, are configurable within safe bounds.

The actual current dry run has **zero eligible rows and zero estimated logical bytes** because the collected history is younger than these thresholds. PostgreSQL allocation is reported separately; filesystem recoverability remains unknown. Future DELETE batches permit database reuse and do not promise filesystem shrink. No VACUUM FULL is used.

A populated current-schema archive restored successfully into isolated market_restore: 137 genuine observations, 1,324,933 listings, 320,105 statistics, the daily reference and market verification receipt, with zero synthetic observations. A separate nonempty synthetic recovery rehearsal also rejects a corrupted archive. The original 512 MiB rehearsal capacity was insufficient; after checking host headroom, only the disposable restore service was bounded at 2 GiB tmpfs / 3 GiB memory / 1 CPU. Production was never reset.

Policy changes have complete before/after audit records. Destructive application requires exact-policy owner/operator authorization, a fresh restored archive identity and administrator confirmation of the actor-bound signed preview. Each transaction removes at most 5,000 rows; another preview is required for the next batch. Latest heads, current snapshots, shared daily references, source provenance and current 14/60-day values are protected. Old unsupported sync cursors receive the existing 409 full-refresh contract. Recovery and rollback limits are in [retention operations](retention-operations.md). **No live policy is authorized; no historical batches have run.**

## Review artifacts and remaining gates

Screenshots are local ignored artifacts under `artifacts/market-usability/`:

- `catalogue-desktop.png`
- `item-details-desktop.png`
- `item-tooltip-desktop.png`
- `current-auctions-desktop.png`
- `markets-configuration-desktop.png`
- `retention-controls-desktop.png`
- `explorer-mobile.png`

Committed evidence is under `docs/evidence/usability-*.json`. The deployed frontend image is sha256:1fae01d96e4aada104f73da5457f89497abd226e7bf35da6b68b8b4cd914ed94 and preview API image sha256:9fe1f98e78e86eae9821d2c5e02a6e0f48cc9899cb259c63a4a05416118413a0. Production frontend remains sha256:0abc0d5ebf24b3f01dfaaaa52ffddb8c6ecc63973632289fb3f240ff9ec8da0f.

Remaining gates: explicit final visual approval before promotion; independently evidenced numeric US Normal Horde identity and confirmed collection switch; explicit approval of the saved retention policy before live destructive application. Supplemental provider availability remains an external blocker. The initial broad verifier expected the earlier HTTP 403 public state; a fresh trusted HTTPS probe instead returned HTTP 200. This task did not change ingress configuration. The enabled-public verifier passes trusted public HTTPS, authentication, CSRF, member permissions, device synchronization/revocation, logout, and continued local/preview isolation. Local and preview HTTPS health/static responses are independently trusted.

Development checkpoints: e985227 (plan), 13599b0 (market/retention), 45f4ce0 (UI/tables/enrichment), f7df30e (exact backup binding and final rendering refinements). No forced pushes, secrets, AMP changes or production frontend promotion.
