# Administration Modernization production release

The owner explicitly approved PR #3's administration tables, metadata diagnostics, and exact WoW item-quality colors for controlled integration and production deployment on November 15, 2026. This supersedes the older review-only gates for this release. Explorer / Item Details has separate implementation authorization and remains prohibited from production until its final visual approval.

The PR acceptance report pins application source `a81a4e395f8367571c6188c23dff143611fb1f1c`; `0527d6d5a21ea0a668a476c948af873f5192d2f4` is the later documentation checkpoint. Fresh remote inspection confirmed integration branch `integration/companion-v2-metadata-recovery` at `35f5fddb4b5a7a6dccdd77f4d8ae3ef097c79463`, and production running `e7d3129`. The reviewed branch merged without conflicts as **`e9c4d299cdf781be0e362edb26b4de6097a33e6a`**. Its application tree matches the frozen candidate. No database migration was added or run: production and restored schema remain `meta_20261114`.

## Exact integrated verification

- [Backend 43680926793](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43680926793): passed PostgreSQL, schema/migration checks, Python dependency audit and operational checks.
- [Private website 43680926791](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43680926791): passed build, frontend tests, npm production audit, browser workflows and accessibility.
- [Windows Companion 43680926809](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43680926809): passed core/native/protocol, installed release, legacy upgrade and actual signed SDK updater/retained-data acceptance. No new desktop release was published.
- Independent local runs against the integrated source: **380 PostgreSQL tests**, **79 frontend tests**, **34 operational tests**, **25 Chromium workflows**, TypeScript/Vite build and npm audit with zero findings. Isolated fixture databases are `market_test`; screenshots from those suites are synthetic, not live observations.

One shared `ItemName` retains exact Poor `#9D9D9D`, Common `#FFFFFF`, Uncommon `#1EFF00`, Rare `#0070DD`, Epic `#A335EE`, Legendary `#FF8000`, Artifact `#E6CC80`, and neutral unknown. Existing source attribution and provider controls remain. The approved [review gallery](evidence/admin-modernization/review.html) remains the visual baseline.

## Preservation and recovery

Fresh archive `market-development-20261115T052439755689Z.dump`: **177,056,249 bytes**, SHA-256 **`be53ae5abb8aacdc2b513f23de3bddbac8de0fa2129b2f0dd982a7d956868564`**. It restored into isolated `market_restore`, retaining 71 users, 313 observations, 3,222,487 listings, 706,437 statistic rows, 10 preference records and zero synthetic observations. Original history/accounts/credentials/preferences/mappings/retention fingerprints match both restoration and post-deployment production. Restored owner authorization and the actual encrypted provider envelope were verified with the protected existing keyring, without an external request. All 24 backup archives passed checksum verification.

The first isolated restore exhausted its 2 GiB temporary disk during index construction. A bounded 3 GiB temporary disk, 4 GiB memory limit, 128 MiB WAL limit and single-worker 64 MiB index build completed successfully; production storage/configuration was not changed. The raw initial failure and successful rehearsal remain in ignored `artifacts/admin-release`.

Production replaced only `api`, `local-api`, `proxy`, then independent `enrichment`, using revision-labelled, uniquely tagged images pinned in [compose.admin-release.yaml](../compose.admin-release.yaml). Collector, PostgreSQL, monitor and backup container identities, images and resource limits are unchanged. Complete production environment comparison found no changed runtime settings. No volumes, mappings, pruning, credentials, collector schedule, Traefik, Komodo, AMP or unrelated services were changed.

Current provider configuration was inspected rather than copied from old reports: Blizzard enabled/automatic=true, 240/hour and 2,000/day; Everloot disabled/automatic=true, 240/hour and 2,000/day; ForeverDB and TheWoWDB disabled/automatic=false, 60/hour and 500/day. These values, credential ciphertext, key identity and connection status match exactly after promotion. Disabled providers stayed disabled through the completed acceptance at 05:35:21 UTC; no provider credential validation or recovery request was started by this release. At 05:35:53–05:35:58 UTC, separate owner-account actions enabled TheWoWDB and Everloot with automatic=true. These later choices were preserved, not reverted; [audit timing](evidence/admin-release/concurrent-owner-actions.json) distinguishes them from deployment.

## Production commands and rollback

Always use the complete configuration and private environment; never print a rendered configuration:

```sh
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml up -d --no-deps --wait api local-api proxy
docker --context rootless compose --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml --profile metadata up -d --no-deps enrichment
```

The immediately preceding API/frontend/enrichment images are retained in [compose.admin-rollback.yaml](../compose.admin-rollback.yaml). For a release regression, stop only enrichment; append this rollback overlay **last** after the complete stack above and replace `api local-api proxy`, then independently replace enrichment if appropriate. Retain every provider setting, schema and volume. Never restore over production or downgrade its populated schema. Archive recovery remains isolated and requires a separate incident decision for any database cutover. No rollback was required for this release.

## Public acceptance

[Final public results](evidence/admin-release/public-acceptance.json) and [actual screenshot gallery](evidence/admin-release/review.html) record the release. House 114 completed scheduled HTTP 304 checks at 05:29:32 and **05:34:35 UTC**, spanning deployment, with zero current failures and unchanged 300-second configuration. All original data fingerprints match after deployment; retention batches remain zero. API memory was 120.7 MiB / 384 MiB after full browser acceptance, local API 110.7 / 256, metadata worker 61.9 / 192, collector 110 / 384, proxy 22.8 / 128 and database 625 / 768; these are point observations, not production peak or p95 guarantees. No significant resource regression was observed. Trusted public HTTPS, pre-deployment public/local session and preference continuity, legacy sync cursor continuity, administration permissions, all nine administration sections, bounded records and masked credential forms were exercised. An initial acceptance-harness failure used an obsolete bootstrap password for the owner-only Companion check. No password was reset. The final check uses an explicitly audited temporary owner session solely for owner-scoped download/pairing acceptance and revokes it afterward; temporary verification accounts and devices are also disabled/revoked. This is distinct from automated Windows execution and owner-PC tray acceptance.

Phase 2 must branch from this verified integration source, preserve the deployed Phase 1 image pins, and return a tested screenshot candidate plus draft PR for owner review. Its production promotion is not authorized.

Known nonblocking limits: actual owner-PC tray actions remain unverified; no off-host keyring recovery copy is claimed. The restore scratch-space adjustment and obsolete-bootstrap-password harness correction are documented above. Phase 1 is complete; Phase 2 remains undeployed.
