# Explorer / Item Details production release

**Live at https://market.twich.gg.** The owner explicitly approved PR #4's implementation and visual design, frozen application `b3e48bd8408cfb7ba09115abfc3ccc12a721d480` and final review `f3d9172ecad611b49fb4ce52585c35e7a3a1bdea`, for integration and production deployment. This supersedes the earlier review-only promotion gates for this exact release.

Fresh inspection confirmed production administration release `e9c4d299cdf781be0e362edb26b4de6097a33e6a` and the latest integration head `9ce465a00c159283b9b64d5abfcb089d8056f5a5`. [PR #4](https://github.com/Twich-Team/TwichUI-Market/pull/4) merged without conflicts into `integration/companion-v2-metadata-recovery` as **`4ddf137712084292b899e7b352fe41b751e8e70b`**. Its application files match the approved frozen candidate. Backend, schema, contracts, pricing, provider adapters and desktop source are unchanged.

Only the production **proxy/frontend** was replaced, at **2026-11-15 09:40:24–09:40:25 UTC**. The full public browser recheck passed at **09:49:40 UTC**. Backend APIs, local API, independent metadata worker, collector, PostgreSQL, monitor and backup retain their exact previous container identities/images/start times. No migration ran; schema remains `meta_20261114`. [Source approval](evidence/explorer-release/approval.json), [container comparison](evidence/explorer-release/containers-after.json), [actual production gallery](evidence/explorer-release/review.html).

## Exact integrated CI

Every required workflow ran on the actual pushed integration commit, not just the PR preview:

| Workflow | Result |
| --- | --- |
| [Backend 43699729924](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43699729924) | **380 PostgreSQL tests**, **34 operational checks**, dependency audit and isolated schema/migration rehearsals passed. |
| [Private website 43699729878](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43699729878) | TypeScript/Vite, **109 frontend tests**, npm audit and **34 Chromium workflows** passed; visual artifacts uploaded. |
| [Windows companion 43699729913](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43699729913) | Native/protocol, installed release, actual legacy installer upgrade and signed SDK updater/retained-data compatibility passed. No new desktop release was published. |

[Run receipt](evidence/explorer-release/ci.json), [backend excerpt](evidence/explorer-release/ci-backend-excerpt.txt), [website excerpt](evidence/explorer-release/ci-website-excerpt.txt); all job/step receipts are adjacent in the evidence directory.

Revision-labelled frontend image: **`sha256:e996c241a2e128aeb1512801596ecae009e2d84020e6e92b4860e57acaeee9f4`**, tag `twichui-market-web:explorer-release-4ddf137`. All **13 reviewed JS/CSS assets** match the frozen candidate exactly. Public HTTPS independently serves those assets and matching index HTML by SHA-256. The configuration preflight found exactly one change, `proxy.image`. [Image/build assets](evidence/explorer-release/image.json), [public asset hashes](evidence/explorer-release/public-assets.json), [configuration preflight](evidence/explorer-release/compose-preflight.json).

## Fresh backup, restore and preservation

Archive **`market-development-20261115T093350867055Z.dump`**, **204,783,629 bytes**, SHA-256 **`4ffb420049ead98bf24b6ba90b0bd7c4647f86c1704ac3bb1abd6f5913603f59`**. It was created through the existing backup service and its existing 30-archive/3 GiB budget, then restored into disposable `market_restore` using the established bounded restore configuration. No production database was restored over or reset.

The restore retained **77 users, 362 observations, 3,771,457 listings, 816,369 statistic rows and 13 preference records**, with zero synthetic observations. All original schema-aware history, account, credential, preference, mapping and retention fingerprints match both the isolated restore and final production verification. The protected existing keyring decrypts the restored Everloot envelope; no external validation call was made. All **25 backup archives** pass checksum verification, including the preserved prior 24. [Backup/restore manifest](evidence/explorer-release/backup.json), [restored fingerprints](evidence/explorer-release/restored-preservation.json), [final preservation](evidence/explorer-release/final-preservation.json), [archive checksums](evidence/explorer-release/archives.json).

The first restore orchestration selected the preceding manifest before the new dump finished. That disposable attempt was stopped and removed; the successful rehearsal explicitly checks the fresh archive's timestamp, size and hash. Initial diagnostic logs remain in ignored `artifacts/explorer-release`. This did not touch production records.

Actual provider state was inspected rather than copied from older reports. Existing owner choices have **Everloot and TheWoWDB enabled/automatic=true**; ForeverDB remains disabled/automatic=false. Blizzard remains enabled/automatic=true. Existing budgets remain Blizzard/Everloot **240/hour, 2,000/day**, ForeverDB/TheWoWDB **60/hour, 500/day**. All flags, credential ciphertext hash/key identity and connection state match before/after. This deployment did not enable or disable a provider, raise a budget, change a key or start diagnostic recovery jobs. [Before](evidence/explorer-release/providers-before.json), [after](evidence/explorer-release/providers-after.json).

## Actual public HTTPS acceptance

[Public browser receipt](evidence/explorer-release/public-acceptance.json) and [nine actual screenshots](evidence/explorer-release/review.html) use genuine production market data through trusted public HTTPS, with no mocked responses or ignored certificate errors. The browser uses UTC dates. They verify:

- Explorer submitted search, market filtering, name sorting and paginated results; Back/Forward restores its complete applied URL state.
- Parent ranges and total supply, explicit variant selection and exact variant research. Direct/reloaded/new-tab URLs and a signed-out deep link through sign-in retain the requested market/item/variant/range.
- Actual historical price and supply charts, current paginated auctions, exact copper formatting and variant identities. A currently listed Tattered Cloth Vest (#193) supplies the genuine exact research example; no assumption is made that a previously observed item is still listed.
- Deal Finder links open the same Item Details destination and return to its own saved browsing URL. Item Details remains absent from permanent sidebar navigation.
- Common white, uncommon green, rare blue and epic purple match stored Forever metadata for Worn Shortsword, Knightly Longsword, Night Watch Shortsword and Hammer of the Northern Wind. Source/build attribution is visible. Narrow research has no document overflow.
- Login, preference persistence through relogin, all nine administration sections, member/admin boundaries, CSRF/origin rejections and existing private Companion download metadata/bytes. The current signed installer is unchanged; Windows execution is covered by CI, not claimed as a new owner-PC test.

Audited temporary public/local sessions, a legacy device cursor and preferences were established before the actual frontend swap. Their identity, secure cookie, cursor and preference values/revision survived the swap before a later catalogue assertion failed. [Across-deployment continuity receipt](evidence/explorer-release/session-continuity.json) preserves that distinct boundary. The final complete acceptance is a subsequent recheck, not a second deployment. Eight temporary verification accounts were retained but disabled; all their credentials and four temporary owner-scoped acceptance sessions were revoked afterward. No existing owner password/session/device authorization was reset. [Cleanup receipt](evidence/explorer-release/temporary-access-cleanup.json).

### Catalogue statistics maintenance during acceptance

The first browser run exhausted its default five-second wait; a 30-second recheck also showed the catalogue still loading. Bounded read-only calls reproduced the issue on the **unchanged previously deployed backend**. `EXPLAIN` estimated one row in snapshot 33 where 27,155 variant rows actually existed, causing an unsuitable plan. Only the two outstanding verification queries were cancelled, identified by exact PID/start time; no auction collection query was cancelled.

A standard **`ANALYZE snapshot_statistics`** refreshed PostgreSQL planner statistics. The same text-search/name-sort request then completed in **0.11 seconds**, and default browsing and text search sorted by item ID completed in **0.10–0.17 seconds**. Full public acceptance passed afterward. No index/schema/query/algorithm, collector schedule, observations or price values changed. [Bounded before checks](evidence/explorer-release/bounded-api-diagnostics.json), [after checks](evidence/explorer-release/bounded-api-after-statistics.json), [estimated plan](evidence/explorer-release/catalogue-plan.json). These are local handler timings on real data, not public p95 or a general speedup claim. No automatic maintenance feature or backend tuning was added; recurring statistics freshness remains an existing operational consideration.

The acceptance harness also corrected an exact-label selector for the existing market select and ignored decorative sort-arrow text. Those locator corrections changed no application source. Original failed-run evidence is retained. No genuine frontend regression was found, so no frontend rollback was needed.

## Collector and resource acceptance

House **114 / market 2 remains the sole enabled collector at 300 seconds**, with **zero new failed collection runs since the pre-release baseline** and zero current failures. Scheduled HTTP 304 checks continued across and after frontend replacement. Historical retention remains unauthorized with **zero retention batches**. [Final collector/retention health](evidence/explorer-release/health-final.json).

Resource limits and production runtime configuration are unchanged. After the full public run, frontend memory was 26.33 MiB/128 MiB, API 261.5/384, local API 151/256 and metadata worker 64.27/192. These are point observations, not peak guarantees; [full receipt](evidence/explorer-release/resources-final.txt). No AMP, Traefik, Komodo, host-network, firewall, signing or unrelated service changes were made.

## Current release procedure and immediate rollback

Use the full private production configuration, appending the frontend overlay last. Never print the rendered configuration or run an unscoped `up`:

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml -f compose.explorer-release.yaml \
  up -d --no-deps --wait proxy
```

For a genuine frontend release regression, retain diagnostics and append the prepared rollback **last**, replacing only the frontend:

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml -f compose.explorer-release.yaml \
  -f compose.explorer-rollback.yaml up -d --no-deps --wait proxy
```

The rollback pin retains administration frontend `sha256:2c16372dc3254d897e57d980529f62c9a1550ed356cdc66e121e23b64cf267c9`. Keep all API/worker images, provider flags/budgets/keyring, schemas, volumes and observations untouched. Do not restore a dump over production or downgrade the schema for a frontend incident. This release is complete; no further feature, provider investigation or desktop publication is authorized by it.
