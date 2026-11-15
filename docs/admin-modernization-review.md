**Current release:** Administration modernization PR #3 is owner-approved, merged, deployed and accepted at `e9c4d29`. [Production acceptance, current image overlay and rollback](admin-modernization-release-acceptance.md) supersede historical review/deployment instructions below. Explorer / Item Details implementation is separately authorized on a feature branch; its production promotion requires final owner visual approval.

# Administration tables and metadata provider review

**Review candidate only — not deployed.** Production still runs release `e7d3129`. Administration changes and the separately requested item-quality correction need owner visual approval before promotion. [Draft PR #3](https://github.com/Twich-Team/TwichUI-Market/pull/3) targets the deployed integration branch. [Inventory and milestone plan](admin-modernization-plan.md), [continuation ledger](admin-modernization-progress.md), [visual gallery](evidence/admin-modernization/review.html).

## Result

All administration record displays use the existing shared TanStack table. Large security, collection, recovery-job, attempt and unresolved-item histories query bounded server pages. Provider results distinguish a successful HTTP request from returned metadata and fields actually added to the local catalog. Record details use an explicit safe field allowlist. Credential forms, settings, charts and static summaries remain purpose-built controls.

The bounded live investigation made **93 external API requests total**, within the owner-authorized 200-attempt ceiling. It stored **12 previously missing names: 3 Everloot and 9 TheWoWDB**. No automatic provider was enabled or its configured budget raised. No third-party prices, raw tooltip HTML, contributor identifiers, credentials or raw provider failures were imported.

### Fixed population

Snapshot **27**, observation **293**, US Normal Horde / market 2 / house 114. Before: **November 14, 8:48:26 PM MST** (November 15, 03:48:26 UTC). After: **9:20:44 PM MST** (04:20:44 UTC). This is the same 4,893-ID population, independent of newer live snapshots.

| Measure | Before | After |
| --- | ---: | ---: |
| Distinct item IDs | 4,893 | 4,893 |
| Usable names | 2,250 | 2,263 |
| Unresolved names | 2,643 | 2,630 |
| Named coverage | 45.9841% | 46.2497% |
| New supplemental names | — | 12 |
| New primary Blizzard names, independent existing worker | — | 1 |
| Lost names | — | 0 |

The supplemental-only contribution is 12/4,893 (0.2452 percentage points); it must not be credited with the unrelated Blizzard gain. No 90% coverage or broad provider-corpus coverage claim is made. Exact IDs, initial availability, sample selection and hashes are in [fixed population](evidence/admin-modernization/fixed-population.json), [sample](evidence/admin-modernization/sample.json) and [committed after measurement](evidence/admin-modernization/coverage-after.json).

ID SHA-256: `bbbacaf1ed0d9d35f997a16f83d92b6f0f009bd126284d3868d7115f8b076fc1`. Price/supply SHA-256 before and after: `91a89965afb73887ebee713ebf0053f5bcca93f3997125e5dc16ae60505025b5`.

### Requests and actual provider coverage

The window allowed requests until **9:30 PM MST / 04:30 UTC**. Actual outbound requests ran **8:49:10–9:19:59 PM MST / 03:49:10–04:19:59 UTC**. Persistent job/task reservations account for every call. Existing metadata-worker locks, source negative caches, provider intervals, quotas and cooldowns remained in force. A cached item-720 check was skipped; local lock/quota waits did not send requests.

| Evidence | Everloot | TheWoWDB | Total |
| --- | ---: | ---: | ---: |
| External API requests | 67 | 26 | 93 |
| Actual HTTP 200 | 17 | 11 | 28 |
| HTTP 404 | 50 | 15 | 65 |
| Named single-item responses | 4 | 11 | 15 |
| Newly stored usable names | 3 | 9 | 12 |
| Named controls already known, not imported | 1 | 2 | 3 |
| Attribute-only pages | 1 | 0 | 1 |
| Public-observation pages (no direct import) | 12 | 0 | 12 |
| Identity/build/payload rejections | 0 | 0 | 0 |
| Access blocks / rate limits | 0 / 0 | 0 / 0 | 0 / 0 |

The 12 observation pages are one 100-record probe plus eleven pages covering the complete 10,971-record public corpus. They are not 12 named item responses. The corpus contained 942 distinct named item/name groups; only 96 item IDs met the three-public-contributor rule. These counts describe inspected public observations, not theoretical item coverage or imported names.

The reproducible unresolved sample used a fixed SHA-256 seed, round-robin across observed primary lookup state, icon, previous attempts/attribute-only records, known quality and ID range. Five strata were present. Everloot checked 48 unresolved IDs; TheWoWDB checked the first 24 of the same sample. All 48 Everloot sample requests returned 404. TheWoWDB returned nine valid names and fifteen missing responses. The later Everloot corpus-led checks are explicitly a separate, evidence-directed selection.

[Sanitized response evidence](evidence/admin-modernization/provider-responses.json) includes public field excerpts, response classifications, exact safe cache/rate headers, body hashes, request numbers and committed gains. [Persistent ledger](evidence/admin-modernization/provider-ledger.json) independently records the 93 completed attempts. All investigation jobs are terminal.

## Why Everloot previously recovered zero

The deployed adapter uses the documented `/api/tooltip/item/{id}` name endpoint and correctly parses its `title`, exact integer ID, attribution and optional Forever build. It does not mistake `/api/items` attributes for names. A genuine Linen Cloth response and all three new names parse successfully without relaxing identity or licensing checks.

The earlier 19-item recovery sample was IDs **647, 720, 727, 754, 776, 789, 790, 791, 809, 811, 812, 833, 863, 865, 866, 867, 868, 869, 870**. Persistent evidence shows 18 HTTP 404 results and item 789's HTTP 200 with no recovered fields. That small, closely clustered ID selection supplied no usable consensus title. It did not prove that the key or parser was broken, or that Everloot had no names elsewhere. [Prior sample evidence](evidence/admin-modernization/prior-everloot-sample.json).

The bulk attribute feed currently reports **31,981 records**, build **1.60.1.70938**. Its authentic page contains categories/slot/quality facts, without a name field. The app's 500-record page ceiling is deliberate local bounding; a keyed provider allowance of 5,000 does not turn this feed into a name catalog. The optional bulk job is therefore labelled client attributes.

The documented public corpus is a more useful discovery route. An inspected, stable `dataAsOf` of **02:10:16 UTC** held 10,971 records. Named observations are available for shared records, but individual uploads are not consensus facts. The inspection kept public pseudonyms in process memory, required three distinct contributors agreeing on one plain name, rejected competing quorums and wrong builds, and emitted no contributor identifiers. Nineteen quorum item names intersected the fixed market population; sixteen were already locally named. IDs **3283, 3308, 5071** remained unresolved. All three subsequently returned valid names through the ordinary tooltip endpoint and were stored through existing source precedence: Battle Chain Tunic, Barbaric Cloth Gloves, Shadow Wand. The corpus itself was not imported. [Corpus evidence](evidence/admin-modernization/everloot-corpus.json).

Documented immutable exports can be discovered from `data.everloot.app/latest.json` and their size/hash/license index. They share API dataset shapes and can be older than the live feed. No export files or undocumented site search endpoints were fetched. A future local catalog can efficiently index permitted named observations and validate quorum candidates with the tooltip route; attributes and single reports must remain distinct. This investigation verified the live API path with eleven bounded 1,000-record pages; it did not presume an export is current or complete.

Official contracts reviewed: [API overview](https://everloot.app/docs/api), [tooltips](https://everloot.app/docs/api/tooltip), [items](https://everloot.app/docs/api/items), [public corpus](https://everloot.app/docs/api/corpus-public), [data files](https://everloot.app/docs/api/data-files), [limits and keys](https://everloot.app/docs/api/keys). Derived names retain Everloot CC BY-SA 4.0 attribution. Game-file attributes keep their separate unconfirmed/Blizzard credit.

### Limits actually established

Everloot documents **2,000 account-wide keyed requests/hour, 5,000 records/page, bearer authorization and 429/Retry-After**, with no extra data unlocked by a key. Actual keyed responses succeeded, retained license headers, and omitted rate-limit counters and Retry-After. We did not deliberately exhaust the account quota, so the 2,000/hour ceiling is documented, not independently stress-measured. The existing app configuration **240/hour, 2,000/day, 15-second minimum interval** was preserved; all 67 calls shared those counters with existing account usage.

## TheWoWDB findings

The documented keyless GET `https://thewowdb.com/api/v1/forever/item/{id}` succeeds from the actual deployed API environment with the ordinary existing client identity, JSON Accept header and no provider authorization. No redirects, special browser cookies, IP rotation, proxies or access-policy circumvention were used. The older 403 was not reproducible; the available historical evidence does not establish its original cause. Do not claim that Market fixed a provider firewall or authentication policy.

The control returned Worn Shortsword, exact Forever ID 25, beta build `wow_classic_beta-1.60.1.70532`, required attribution, public one-hour caching and an ETag. The response explicitly reported **X-RateLimit-Limit: 120; X-RateLimit-Remaining: 119**. The documented refill of two/second/worker was not stress-tested; the app retained its much slower 60-second interval. The bounded If-None-Match check returned HTTP 200 with a changed ETag, rather than 304; an unchanged deployed 304 is not claimed. Adapter 304 preservation/ETag paths are covered by regression tests. Long Retry-After windows on temporary 503 responses now delay other item requests and connection validation as well; the same cooldown and credential-preservation safeguards remain in force.

All nine sampled names passed exact item/version validation and the qualified beta provenance path. No third-party market values, Retail IDs or rendered HTML entered the catalog. A genuine validation gap was tightened: TheWoWDB's beta-build parser had accepted any numeric beta version family. The adapter now requires Forever's verified **1.60** family and records wrong identity/build separately from invalid payloads. This is a validation correction, not a claimed parser-based coverage increase. The provider remains **disabled, automatic=false**. Manual diagnostic success does not authorize automatic recovery.

[Official API, paging, caching, rate and attribution terms](https://thewowdb.com/developers/). If forbidden responses return, honor the resulting cooldown and use the provider's official site/support links; no bypass is authorized.

## Next legitimate source decision

Twelve supplemental gains leave **2,630 unresolved** in the fixed population. These sources help, but this experiment does not materially close the overall gap. The next candidate is the pending **approved ForeverDB API integration**, after the owner obtains authorized access and a genuine schema/build fixture. Its current official site describes client-derived item data and current-build updates; its advertised corpus size is not evidence of overlap with our missing IDs. Confirm licensing, exact Forever build/locale and permitted named-record/bulk routes before a small representative high-ID test. Do not scrape the website or guess a richer parser from sample descriptions.

An alternative is an **owner-permitted exact-build game-client name catalog**, with documented extraction rights, locale, tool/layout revisions and hotfix identity. Client layouts/tools do not grant asset redistribution rights, and hidden/encrypted fields must remain unknown. No client catalog, third provider, larger automatic budget or scraping campaign was started here. Both options require a separate operational decision and genuine coverage evidence. The existing official Blizzard resolver can continue under its unchanged controls.

## Quality-color correction

Stored quality is already normalized and projected through catalog provenance and exposed by Explorer/profile/deal APIs. The visible defect was presentation: later button colors overrode earlier quality classes, the existing palette was softened, and Deal Finder omitted an already available quality field from its initial item identity.

One shared `ItemName` and mapping now apply the owner's exact seven game colors, with a neutral unsupported/unknown fallback. Names retain color on hover and across Explorer/search, the current research heading, Deal Finder/signals, tooltips and administration attempts. Values, selection handlers and variant identities are unchanged. No dedicated Item Details routing was implemented.

The exact blue and purple have only about 3.4:1 contrast on the espresso panel, so names use at least 19px bold text (while preserving larger headings), satisfying the large-text contrast threshold without changing the requested hex colors. Supporting text remains muted. Unit tests cover all seven qualities and unsupported values; browser assertions and inspected screenshots prove common white, uncommon green, rare blue and epic purple. Axe checks pass. [Quality screenshots](evidence/admin-modernization/review.html#quality), [read-only live stored-quality distribution](evidence/admin-modernization/live-quality.json). A supplemental isolated Chromium check rendered read-only Blizzard/Forever metadata for Worn Shortsword (#25, common), Knightly Longsword (#864, uncommon), Night Watch Shortsword (#935, rare) and Hammer of the Northern Wind (#810, epic); all four exact colors persisted on hover. No market prices were copied. [Stored metadata receipt](evidence/admin-modernization/known-quality-items.json), [browser receipt](evidence/admin-modernization/known-quality-browser.json). Artifact is supported only when that actual metadata value exists; no rarity is inferred from a name/icon.

## Verification and limits

- PostgreSQL: **380 passed**, 127.99 seconds, isolated `market_test`; no schema changes.
- Frontend: TypeScript/Vite and **79 unit tests passed**.
- Operational checks: **34 passed**, including quota guards and public-contributor consensus/identity/conflict checks.
- Fresh isolated browser suite: **25 passed**, 2.5 minutes. Additional focused review checks cover every administration section with axe, keyboard expansion, sorting, member filters, server pages, local date filters, collection outcomes, loading/error recovery, device ownership/revoke, color persistence and narrow screens.
- Final 10,000-record synthetic benchmark: provider first page mean **73.50 ms**, deep filtered page **236.54 ms** (max **290.96 ms**); security **6.86 ms**, filtered security **14.60 ms**. At most 25 rows and about 12 KB per response. These are constrained local handler/browser-test measurements, not production p95 or unlimited-history guarantees. No overall speedup is claimed. [Full measurements](evidence/admin-modernization/performance.json).
- Stable IDs preserve expansion/action targets. Client pages survive live data refreshes; filters reset to the first page. Large histories are never fetched in full for client search. Job detail search explicitly applies to its bounded cursor batch. Existing finite roster/device endpoints retain their established limits; no claim is made to expand their legacy 200-device limit.
- Full administration inventory and justified form/chart/settings exceptions are documented. Before/after screenshots are synthetic isolated acceptance evidence, never live coverage evidence. No real key appears in browser fixtures, screenshots, Git or diagnostic artifacts.

### Final source, CI and image receipts

Frozen application source: `a81a4e395f8367571c6188c23dff143611fb1f1c`. All three remote workflows passed: [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43678852944), [Private website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43678852973), [Windows companion](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43678852969). The website run retained the administration/quality review artifact. Local full suites ran on `53fb829`; the final source adds only accurate provider wording and CI artifact upload. [Exact CI receipt](evidence/admin-modernization/ci.json).

Uniquely tagged rootless API/frontend images carry the full source revision. The API image, without a source mount, authenticated and returned all five bounded record endpoints; the frontend image contains exactly the 14 tested build assets. [Image IDs](evidence/admin-modernization/images.json), [API smoke](evidence/admin-modernization/pinned-image-api-smoke.json), [asset hashes](evidence/admin-modernization/pinned-web-verification.json). These images were built for review and were not deployed. Documentation-only follow-up commits preserve this application tree.

Implementation checkpoints: `6091e18`, `cd73a68`, `7033bf4` (quality), `23c9b94`, `1a2ea68`, `53fb829`, `a81a4e3`. Queued UX direction was committed separately as `505b9c3`. [Requirement completion audit](admin-modernization-completion-audit.md).

## Production preservation

All original **293 observations, 27 snapshots, 2,938,760 listings and 651,470 statistics rows** match their initial hashes; the live collector continued appending newer observations. Accounts, preferences, mappings and retention hashes also match. The aggregate credential hash changed only because credential 14 was revoked by the owner and native device 3 performed normal token rotation, revoking credential 146. A read-only comparison substituting only those two old flags exactly reproduces the original full hash, proving all other original credential fields are unchanged. No credentials were restored, reset or silently re-enabled. [History/account comparison](evidence/admin-modernization/preservation-comparison.json), [credential reconciliation](evidence/admin-modernization/credential-preservation.json).

House 114 alone continues at 300 seconds, with successful scheduled 200/304 checks after the experiment and zero current market failures. The one collection failure at 03:38 predates the fixed baseline; no zero-failures claim is made for the entire day. Historical pruning remains disabled with zero retention batches. No collector, database, production API/frontend, metadata worker, backup or monitor container was replaced by this task; no AMP, host-network, Traefik or unrelated infrastructure changes occurred. Existing production backup services/keyring/release artifacts were preserved. [Production health](evidence/admin-modernization/production-health.json).

## Deployment and rollback boundary

After explicit owner approval of the gallery and the separate quality correction:

1. Pin the reviewed source commit and require its backend, website and companion CI checks to pass. Build uniquely tagged API/frontend images; retain current approved images and existing compose/environment/keyring files. Do not retag the collector's `dev` image.
2. Take a fresh existing-method SQL backup, verify its manifest and rehearse restore with the separately protected keyring in isolated PostgreSQL. Confirm schema remains `meta_20261114`; this change needs no migration. Do not reset or downgrade a populated database.
3. Use the established complete production compose stack and a narrowly scoped image overlay to replace **api, local-api, proxy** only. Replace the independent **enrichment** image separately if promoting the new durable outcome recording. Preserve every provider enabled/automatic/budget/cooldown value; no recovery budget or new automatic provider is part of UI approval.
4. Verify authenticated public sessions, permissions, old desktop contracts, fresh table pages, names/quality/attribution, valuation/variant references, current collector checks and original history fingerprints. Keep the single collector, DB, monitor and backup services intact.
5. Roll back the same scoped API/frontend/enrichment services to retained `e7d3129` images if acceptance fails. The schema and existing source/metadata values remain compatible. Retain all new metadata/audit/job evidence; never restore an old dump over live history, clear projections for convenience or revoke owner sessions as rollback.

These are future steps, not a deployment authorization or an executed production change. The next Explorer/Item Details milestone is separately recorded and still requires another owner instruction before implementation.
