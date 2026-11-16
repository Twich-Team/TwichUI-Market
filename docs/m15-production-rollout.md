# M1.5 production rollout and real data acceptance

The existing production Market APIs are deployed, and the verified Windows companion **2.0.0-beta.3** is published through the existing private account-controlled channel. **Manual Forever delivery is held:** the genuine complete house-114 generation exceeds the initial test budget and the server refused its construction with HTTP 413. No partial generation, fixture replacement or generated Lua was delivered. Owner Windows and Forever acceptance remain open.

## Integrated and deployed identities

| Component | Actual identity |
| --- | --- |
| Market PR #9 | Merged first as `5b27cc754795f554b08a8d2d4ce7366c27c11bfb` into `integration/companion-v2-metadata-recovery` |
| TwichUI PR #23 | Merged second as `732ccf87b825c7f93d7dbb73cae9fa9bfb001fd8` into `feature/workshop` |
| Reviewed PR heads | Market `529e7ba354e1ceaec9a02fb0f7e2b089cf7af6a9`; addon `4e08bdceec5d717ffe5855bd8351bd19bd06ae88`; merged trees match those candidates |
| Previous production APIs and website | `7202e07a62f1770642b50afe5a3ec671d9b488cf` |
| New production APIs | `5b27cc754795f554b08a8d2d4ce7366c27c11bfb`; image `sha256:39b28f3d18506efd5e9e710cac6450302e7dabdd002b64f5841c1d9cb5689e54` |
| Website | Existing approved `7202e07` image retained; no web source changes between the previous release and the integrated Market candidate |
| Companion payload source | `bd656f19b68f10418e966c8a6418fb3aeaff045e`, integrated M1.5 plus version-only beta.3 changes |
| Exact signed updater harness | `64a758ebf2e333d7f223dfaa274f952ad5686821` |

Deployment started the replacement APIs at **November 15, 2026, 7:52 PM MST** (`2026-11-16T02:52:16Z`). Only `api` and `local-api` were replaced. An explicit `APP_COMMIT` marker was added to identify bridge producer provenance. Website, collector, enrichment worker, PostgreSQL, monitor and backup retain their original container identities, limits and settings. PR #10 was not merged.

All 14 mirrored contract fixtures match byte for byte. Contract/transport v1, schemas 1/2 and the existing amendment remain unchanged. Frozen compatibility evidence covers old Lua readers with compact output, new readers with legacy output, candidate readback of legacy staging, all-byte literals and injection controls. An older desktop inspector may refuse compact artifacts on downgrade and fails closed. No runtime source was changed during rollout, and the capacity matrix and comprehensive addon simulator suite were not repeated.

The exact merged Market commit passed [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794052297), [website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794052279), and [Windows plus signed updater compatibility](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794052461). There were no unresolved PR review threads or merge conflicts. The addon repository has no PR checks configured for this branch; its committed frozen-source Cloud/negative-control evidence was reviewed, not relabeled as a new CI run.

## Backup and schema recovery

Fresh archive: `backups/market-development-20261116T024547046843Z.dump`, **307,046,545 bytes**, SHA-256 **`23eb3cdfd9d7490f08e9f60022b55198818180239ad4a568a25cdb4ad035c470`**. All **27** archives match their size/checksum manifests; all 26 earlier archives were preserved within the existing 3 GiB policy. No archive rotation, schedule or backup budget changed.

An actual bounded disposable PostgreSQL restore contained **559 genuine observations, 50 snapshots, 5,806,623 listings, 1,243,274 statistic rows, 97 users and 22 preference records**, and zero synthetic observations. Restored constraints and original-column fingerprints passed. Two encrypted provider envelopes decrypted using the existing protected keyring. The separately encrypted keyring backup also decrypted to exactly the mounted runtime keyring bytes. An off-host backup copy has not been verified.

The required additive migration is **`meta_20261114 → bridge_20261115`**. Upgrade/check, downgrade to the prior revision, re-upgrade/check and original-data fingerprints passed **only on the disposable restored database**. The previous application also read the upgraded schema and decrypted the restored provider envelopes. Production received only the forward upgrade. Its new tables hold disposable bridge derivations/generations; observations, listings and existing pricing were not rewritten.

The production fingerprint comparison matches every original history, user, preference, verification, mapping and retention row. Its sole credential difference is normal owner-device renewal **before deployment**: security event 7565 at `02:51:22Z` revoked expired credential 233 and issued credential 234 for the same active Windows device 3. Independently normalizing that single `revoked` field recovers the exact original credential-table digest. No account reset or device revocation was performed by this rollout.

## Live production verification

Trusted public HTTPS checks passed for health, scoped device identity, market discovery/bootstrap, the owner browser session and an existing desktop sync cursor established before deployment. A real authenticated Chromium session loaded Explorer, Deal Finder, Administration, Account and Companion with no page errors. Missing credentials are denied; browser sessions cannot use device-only bridge exports; scoped companions cannot access browser-only research/admin routes; unsupported bridge algorithms are rejected.

The sole enabled collector remains **market 2 / house 114 every 300 seconds**. Successful post-deployment upstream 304 checks continued, including `02:56:48Z`; no new collection failures occurred. Provider enablement, automatic flags, quotas, encrypted credential fingerprints and expiry/status equal the captured baseline. Existing metadata work continued independently. Retention authorizations and destructive batches remain zero. Pricing remains **`asking-v1-provisional`** in existing website/desktop results; `twichui-pricing-v1` was requested only as an explicit bridge export algorithm.

## Genuine historical findings and delivery hold

The genuine market identity is **US / transport ruleset ID 2 / house 114 / auctions / server market ID 2**. The API reports player-ruleset mapping as **unverified**; its friendly Normal/Horde label is not independent verification. No mapping was changed to make acceptance pass.

Three actual UTC daily closes were available: **November 14, 15 and 16, 2026**. All are nonsynthetic. There are no intervening missing market dates between those three; earlier dates in a requested 60-day range were not observed. Item absence at an observed daily close is distinct from a missing observation.

An authenticated small research export of four exact Destiny (#647) variants was compared independently with retained PostgreSQL daily statistics and rational half-up daily means. Exact copper, supply/counts, current absence, historical-only variants and provisional references agree. For variant `bd06e80e4090c7ea5e683c4997f73a753ad0b57d9f9d30379d991531ddff63ef`, November 15/16 Recent Prices are **1,499,999 / 1,699,900 copper**, and the provisional Market/Historical reference is **1,599,950 copper**. The November 14 observation has no listing for that variant. Variant `cdd8fb2e3934817e43af42f8b230fa6900254eb50149bbed7219c325acc46a6c` is historical-only on November 16: its prior prices are **2,300,000 / 1,699,900 copper**, current Recent Price is unavailable, and its provisional reference is **1,999,950 copper**. These are asking observations, not completed sales. Canonical bridge values were not verified by this provisional research export.

The complete retained daily union contains **45,125 exact variants**. The authenticated canonical full-house manifest request returned **HTTP 413** after **155.989 seconds**: `Bridge build exceeds bounded working set; request a narrower history window`. Serialized record construction crossed **64 MiB**; no complete canonical input size, generation ID, paginated payload or generated Lua size exists. The failed transaction left zero bridge generations/derivations and preserved the original observations. The API stayed healthy with no restart/OOM, and collection continued.

This fails the proposed initial **2 MiB canonical / 1,000 records / 3 MiB Lua** budget. Delivery is held. No variants or observations were removed, no history-window workaround was used, and bridge-v1 completeness semantics were not changed. Full generation integrity, genuine paginated export, canonical-value acceptance, actual Rust promotion/manual output from genuine history, and Windows/Forever bridge-load acceptance remain **open**. Three dates do not establish empirical 14-day or 60-day validation. A separately reviewed bounded-scope mechanism is required; it was not implemented in this rollout.

## Windows companion distribution

The exact beta.3 installer is **4,515,855 bytes**, SHA-256 **`d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183`**. Original artifact **14194540087** and native acceptance **14194068002** are preserved locally with verified ZIP digests. Payload-source [Windows](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794191014), [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794190925) and [website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43794191023) checks passed. Installed/native CI exercised device authorization, existing SQLite/settings retention, legacy installer upgrade, reconnect/sync/export, startup and uninstall preservation.

The owner's existing encrypted updater key signed only these verified original bytes inside the established isolated signing process. Independent verification checked the Tauri signature and authenticated beta.3 version. [Windows signed-SDK acceptance](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43795607148), artifact **14194685818**, installed the exact signed payload, checked the installed executable SHA-256 `0b1f7a661064d74233423f48270ce22bb3b9776d5850faf4e6fd0262ecbc6b82`, reconnect/sync/export and retained data, and rejected corrupted bytes and a wrong signed version. The harness observed successful installed state rather than claiming an installer-process exit code.

The existing private publisher admitted beta.3 and atomically moved its pointer from beta.2, audit **00000002.json**. Actual public owner-authenticated metadata, installer download size/hash, beta.2-to-beta.3 update response, beta.3 no-update response and unauthenticated denial pass. Beta.2's original downloadable bytes remain intact. The owner-only allowlist is unchanged. This is a **Tauri-signed private beta with Windows publisher `NotSigned`**, matching the established release policy; Windows reputation warnings and owner-PC tray checks remain explicit. No signing bypass or normal unsigned-update distribution was introduced.

The owner computer was not accessed or modified. Windows CI establishes its disposable-runner checks; it does not establish owner filesystem/interruption/antivirus behavior, actual installed bridge export of genuine history, tray acceptance or Forever timing/assets/combat/taint. No automatic game-directory writing or UI reload was enabled.

## Exact rollback

For an application regression, retain diagnostics and run from `/home/marketdev/projects/TwichUI-Market`:

```sh
docker --context rootless compose -p twichui-market \
  --env-file .env --env-file .env.combined-release \
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml \
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml \
  -f compose.admin-release.yaml -f compose.explorer-release.yaml \
  -f compose.polish-release.yaml -f compose.m15-release.yaml \
  -f compose.m15-rollback.yaml \
  up -d --no-deps --wait api local-api
```

This selects the retained `7202e07` API image `sha256:48caf6befd76baa96460d2096e6c71280b961e2e8060ccc3d39a05b2f86bd5a8`. Configuration preflight confirms preserved original settings/credentials, with an explicit previous-source marker. Keep schema `bridge_20261115`, database volumes, all history, credentials, collector, enrichment and website. Verify public health, authenticated routes, the running revision and next normal collection afterward. Never downgrade production or restore an archive over the live database.

For a desktop distribution regression, use the **same full Compose command through `compose.m15-release.yaml`**, omit the application rollback overlay, and replace its final `up` line with:

```sh
  --profile private-beta-tools run --rm --no-deps -T \
  private-beta-publisher rollback 2.0.0-beta.2 --actor m15-owner-authorized-rollback
```

Recheck the private current metadata and beta.2 installer SHA-256 `0fbc53603c218ffa85c8ee7b4e54f25e53c52a6fc3b2330ae914337714d41869`. The pointer change retains all assets/audits and does not force installed clients to downgrade. Use a newer corrective signed version if installed beta.3 requires repair.

The [manual Windows and Forever preparation and rollback procedure](m15-manual-forever-acceptance.md) is ready, with the delivery hold at its start. The owner's absolute Forever directory remains unverified. No generated data-addon pair is offered until a complete generation passes all three budgets. M2 delivery, freshness chips, automatic reload, pricing-default changes, auction transactions, provider-management integration and unrelated enhancements remain outside this work.

Operational evidence is retained under the existing deployment checkout's `artifacts/m15-rollout`; public summaries are under `docs/evidence/m15-rollout`. Temporary acceptance tokens are revoked and removed at final cleanup. The version-only release and public signed proof are on `integration/m15-companion-release`; production's API revision remains the exact merged `5b27cc7`.
