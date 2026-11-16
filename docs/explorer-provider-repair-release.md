# Explorer and provider administration production repair

Owner-authorized scope: repair Explorer, reconcile/review/merge provider rate-management PR #10, deploy and verify persistence on the existing single-user service. M2 and bridge-capacity work remain excluded.

## Diagnosis and correction

The authenticated public production site initially ran API/local API `5b27cc754795f554b08a8d2d4ce7366c27c11bfb`, website `7202e07a62f1770642b50afe5a3ec671d9b488cf`, schema `bridge_20261115`. A genuine Linen search remained pending after 20 seconds, with no result links or actionable error. Browser authentication succeeded and no JavaScript error explained the failure. A bounded read-only handler probe hit the five-second database deadline.

The newest snapshot (51 at diagnosis) had 29,155 current variants but PostgreSQL estimated one row; sampled statistics covered older snapshots. Nested-loop plans repeatedly evaluated matching IDs and historical aggregates. Name sorting and broad searches exposed additional repetitions. No production ANALYZE or global database setting change was used to hide the defect.

The final query combines current variants and historical references with UNION ALL, groups by exact item/variant, discards historical-only variants, and then builds parent ranges. Both large inputs are evaluated once. Existing 14/60-day reference formulas, variant identity, unknown values, provenance and precision-safe currency are preserved. Independent pricing comparisons and vanished-variant tests guard against historical variants leaking into current ranges. Catalogue SQL has an eight-second request-local deadline; browser requests have a 15-second deadline, actionable error and Retry, and do not show retained results from another query. Navigation cancellation remains cancellation.

Read-only genuine-data probes of blank/name, blank/market-value, broad name, Linen and numeric search completed in 0.2–0.4 seconds before deployment. These are handler probes, distinct from the post-deployment public-browser acceptance below. A synthetic PostgreSQL regression recreates a newly ingested snapshot absent from sampled statistics, tests narrow/broad/unfiltered/name/price sorts under the unchanged two-second deadline, and verifies results. The old query fails the negative control; the final candidate passes. Hosted exact merged-source CI caught a remaining broad-search plan in the first candidate; that candidate was never deployed. PR #11 supplies the final bounded aggregation.

The old ForeverDB daily form had a hard maximum of 2,000. Filling 2,001 caused native range validation and sent no Save request; the legacy API also returned 422. This was validation before persistence. The new independent Save rate limits API/form supports explicitly configured allowances while preserving credentials, connection enablement, campaigns, counters and cooldowns.

## Provider review

PR #10 was reconciled with integrated M1.5, preserving bridge code and contracts. Review covered persisted row-locked reservations committed before network I/O, shared worker accounting, minute/hour/day buckets, retained legacy counters, one shared in-flight request, bounded crash leases, charged retries, cooldown/Retry-After parsing and adaptive throttling, retained queued work, finite retry allowances, and administrator/session/CSRF authorization. Tests include concurrent reservations and fresh-process persistence; synthetic HTTP 429/503 recovery is not claimed as a live provider observation.

Documented allowances were checked against primary provider documentation: [ForeverDB](https://foreverdb.net/developers), [TheWoWDB](https://thewowdb.com/developers/), [Everloot](https://everloot.app/docs/api/keys). ForeverDB documents free 5,000/day and 30/minute, paid 10,000/day and 60/minute, account-wide. TheWoWDB documents a shared refill of two requests/second with burst capacity 120. Everloot documents 2,000/hour for a free key, and a separate 30/hour keyless pool. These documentation values do not establish the owner's actual entitlement. Configuration is labelled separately from documented and observed limits; unusual allowances require acknowledgement and validation where applicable. No active limit was raised to match a published maximum.

Original production limits are retained: ForeverDB 60/hour and 500/day; TheWoWDB 60/hour and 500/day; Blizzard metadata 240/hour and 2,000/day; Everloot's existing configured settings. The auction collector has separate preserved scheduling. The live persistence check temporarily lowers ForeverDB to 499/day, verifies browser → API → database → refresh → API/local-API/metadata-worker restart → refresh, then restores the original 500/day. Values above 2,000 are checked for form validity without saving an increased active budget.

## Backup and migration

Verified archive: `market-development-20261116T033956666546Z.dump`, 314,364,523 bytes, SHA-256 `8f0a81246d3963f3a379afe87f3c28fc6827e460f2691efdee993b6a4f153530`. It was created at 03:41:32 UTC and restored at 03:45:31 UTC on 2026-11-16. The isolated restore preserves 97 users, 570 observations, 5,950,417 listings, 1,272,429 snapshot statistics, four daily observations, 22 preferences and zero synthetic observations. All prior archives are retained within the existing budget.

On the isolated restored database, additive migration `bridge_20261115` → `rates_20261115`, schema checks, a disposable-only downgrade/re-upgrade, and the previous API reading the additive schema pass. Original provider settings, encrypted credentials, counters, jobs, tasks and source/version rows are unchanged; protected credential envelopes decrypt with the existing runtime keyring. Production rollback retains the additive schema, quota state and all current data; no production downgrade or database restoration is part of normal rollback.

## Release acceptance

**Deployed and accepted on 2026-11-16 UTC:** application/API/local API/website/metadata worker `73617a9e2ce6b32f539700c72caab4592a443a2f`, schema `rates_20261115`. PR [#10](https://github.com/Twich-Team/TwichUI-Market/pull/10) merged as `afb411a2da7d40c6950cf7ca4b5b414094fdbd1f`; the follow-up [#11](https://github.com/Twich-Team/TwichUI-Market/pull/11) supplies the final integrated release. The first merged candidate was held after CI detected the remaining slow broad query.

Exact final integrated CI:

- [Backend 43804981828](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43804981828): 553 PostgreSQL tests, 39 operational checks, metadata/provider/Companion migration verification.
- [Website 43804981898](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43804981898): 121 unit tests, build, 40 browser workflows plus the separate provider-rate Save/reload/accessibility workflow.
- [Windows 43804981822](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43804981822): installed Windows compatibility and actual signed-update SDK lifecycle checks. No new desktop release was published.

[Genuine production screenshots](evidence/explorer-provider-repair/review.html), [sanitized acceptance receipt](evidence/explorer-provider-repair/acceptance.json), [Linen results](evidence/explorer-provider-repair/live-explorer-linen.png), [final ForeverDB card](evidence/explorer-provider-repair/live-foreverdb-final.png).

Authenticated public-browser acceptance uses trusted HTTPS and real market data without mocks. The saved default loads 25 rows in 992 ms; the complete 5,083-parent name sort loads in 839 ms. Linen returns 33 matches in 751 ms, Destiny returns one in 708 ms, item 647 returns one in 1,468 ms, and an unmatched term displays a meaningful empty state in 1,541 ms. These are observed full-navigation timings, not a performance guarantee. Pagination and Destiny item navigation pass; there are no browser errors and the owner's full saved preferences are unchanged.

ForeverDB Save sends the independent rate-limits PATCH and returns the visible saved notice. The browser reload and database both show 499/day. API, local API and metadata worker are then actually restarted; database and browser reload still show 499/day. Credentials, configured rates, anchored usage and all unexpired rolling buckets survive (9 bucket rows before; 12 after, with normal additional reservations). The original 500/day is restored through the same Save/reload path. Final limits for every provider and their enabled/automatic settings equal the original configuration; no usage counter was reset. A 2,001/day form value is valid, but is never saved live. The separate synthetic browser workflow exercises higher custom values and acknowledgement. Actual provider grants and provider-reported remaining quota are not invented: the live screen explicitly labels application estimates. Concurrent reservations, crash leases and 429/503 recovery are verified by isolated tests; no artificial live throttling campaign was started.

Before migration, the metadata worker was drained and no task remained running. The additive migration left every original provider column identical. Compose preflight proves only four services differ, only in images/API revision; the rollback configuration exactly reconstructs the previous services. After deployment, schema-aware fingerprints preserve all 52 original snapshots, 581 observations, 6,094,525 listings, 1,301,793 variant statistics, 97 users, 237 credentials and 22 preference rows at the predeployment cutoffs. Additional scheduled observations continue normally. The temporary repair session is revoked only after the fingerprint check, its cookie returns 401, and its private session file is deleted; owner desktop credentials and other sessions are retained.

The collector, database, monitor and backup container IDs, images and start times are unchanged. House 114 alone remains enabled at 300 seconds, zero failures, with a normal post-promotion HTTP 304 at 04:42:56 UTC. Destructive retention remains disabled. Application logs contain no tracebacks. An existing predeployment legacy sync cursor remains accepted with its original target generation. The private beta.3 payload remains exactly 4,515,855 bytes / SHA-256 `d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183`, and unauthenticated download is denied. Missing-CSRF and wrong-origin administration mutations return 403. The isolated repair test containers/network are removed.

## Deployment and rollback

The installed release appends `compose.explorer-provider-release.yaml` **after** `compose.m15-release.yaml`. The release overlay pins API/local API/enrichment to `sha256:7aad395c64c26f388ee0720cf368b9f0ae6c4d2be3c25fb58dcf399fd3cc8b7e`, and website to `sha256:6543a36bd81c2bea72bcf804ccdd85284fc73aaffd6be14cf5784abe6f028712`. Existing private ingress bindings, secrets, volume mounts, profiles and resource/log budgets are unchanged. Do not omit older overlays or start the collector profile wholesale.

For application rollback, append the retained `compose.explorer-provider-rollback.yaml` last. It restores API/local API `5b27cc7`, website `7202e07` and the preceding enrichment image. Keep `rates_20261115`, all current market data, credentials, quota buckets and cooldown state. The preceding API was verified against this additive schema in the isolated restore.

Run from `/home/marketdev/projects/TwichUI-Market`:

```sh
repair_rollback() {
  docker --context rootless compose -p twichui-market \
    --env-file .env --env-file .env.combined-release \
    -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
    -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
    -f compose.admin-release.yaml -f compose.explorer-release.yaml \
    -f compose.polish-release.yaml -f compose.m15-release.yaml \
    -f compose.explorer-provider-release.yaml \
    -f compose.explorer-provider-rollback.yaml --profile metadata "$@"
}
repair_rollback stop -t 45 enrichment
repair_rollback up -d --no-deps --wait api local-api proxy enrichment
```

Then verify public health, authentication, current history, saved limits, credentials and the unchanged collector again. Normal rollback never restores an older database over newer observations and never downgrades/deletes quota accounting.

## Separate bridge hold

The M1.5 full production bridge construction previously returned HTTP 413: 45,125 variants exceeded the 64 MiB build bound. That is a recorded earlier observation, not a new current-size measurement. Limits, generation membership, pricing, automatic addon delivery and the bridge protocol are unchanged. Real addon acceptance remains held for a separately authorized capacity milestone; this repair does not begin M2 or publish another desktop release.
