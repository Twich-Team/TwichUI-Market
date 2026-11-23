# Prepared Market and Companion beta.12 release acceptance

**Release completed November 23, 2026.** The verified backend is live and signed Companion **2.0.0-beta.12** is available through the existing private channel. Final packaging is **25 Market data addons**. No software was installed on the owner's PC and no public TwichUI addon release was created.

## Exact integrated source

| Repository / PR | Actual merge commit |
| --- | --- |
| [TwichUI reader #131](https://github.com/Twich-Team/TwichUI/pull/131) | `d1ae3cffc4dc48b87d3e1c91727736eb51e50659` |
| [TwichUI containers #136](https://github.com/Twich-Team/TwichUI/pull/136), final addon main | `84ca4842b9fdeac3aa9e2a3f697686fbb39eb655` |
| [Market prepared/container stack #50](https://github.com/Twich-Team/TwichUI-Market/pull/50) | `e5576c9d66e50914d4bcbbf27aad962a8c9f372f` |
| [Market signed proof / CI repair #53](https://github.com/Twich-Team/TwichUI-Market/pull/53), final Market main | `f1492cdc8264e00309c07aba1492d9d207e43ac0` |

Market #50 incorporates the ordered #46–#49 ancestry and collector repair #51. GitHub marks #46 merged; #47–#49 were closed as incorporated through #50, with branches/commits retained. They were not separately remerged from historical failing checkpoints. All merges used normal GitHub enforcement without force pushes or protection bypass. Probe #135 and chart #117 were kept separate.

Addon main's tree is exactly the full-tested `2da68dc6674fa71c92edfce38902197133177191` tree, `340bb00c4360897ae4cbdf2467b5d56e3dcd3f85`. Market's final main differs from deployed/payload `e5576c9…` only in public proof/docs and the preference-test helper; runtime/version files are identical. [Source comparison](evidence/market-regression-cleanup/final-proof-main-source.json).

## Verification and corrected failures

[Complete cloud run 45207055063](https://github.com/Twich-Team/TwichUI/actions/runs/45207055063) passed the original full command, exit **0**: **328 offline modules, 846 Lua syntax files, all 10 default catalogs, 233 simulator launches and 40,826 check executions** in 3,281.717 seconds. Its six failing assertion markers are the checked intentional controls; 40,820 markers pass. No catalog was omitted. [Exact catalog counts and source](evidence/market-regression-cleanup/full-summary.json), [lossless raw report](evidence/market-regression-cleanup/full-report.json.gz).

The established Ubuntu 24.04 / glibc 2.39 environment, unmodified pinned simulator v0.1.37, Bubblewrap isolation, executable-specific temporary AppArmor profile and documented Mesa runtime were retained. Policy cleanup passed. Cloud mode does not set local/native certification flags and does not establish game assets, fonts, visual fidelity or actual Forever behavior.

Reminders assumed logical IDs appeared in filenames; it now verifies approved catalog resolution and retains real TGA dimensions/content and refused-file controls. Workshop expectations were reconciled with approved outcomes, tooltip and heading changes. Advisor fixtures exposed unrelated native bag slots alongside declared fake inventory; both APIs now agree, preserving exact identities, variants, quantities, filters and economic assertions. No gameplay/pricing runtime correction was necessary. [Diagnosis and preserved failures](market-regression-cleanup.md).

A later browser trace proved a correct 8 ms save and a correct authoritative read delayed 10 seconds, beyond an outer five-second poll. The test now waits for the existing UI acknowledgement, then asserts persisted values directly. The UI deadline, request/test budgets and privacy/logout assertions remain. Both corrected push/PR browser runs and final main passed; the original failure remains retained.

All nine original Market candidate checks passed, including repeated Windows comparison. Both coordinated mains passed their applicable checks. Corrected proof source passed all 16 push/PR checks; final Market main passes all eight checks across [Backend 45229899975](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45229899975), [website 45229900108](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45229900108) and [Windows 45229901410](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45229901410). The actual deployed image separately passed **193 isolated PostgreSQL checks**, with all **65 runtime modules** matching the merged source in both image locations.

The accepted offline layout comparison remains unchanged: physical-load **p95 4.326 ms / max 5.499 ms** for 25 addons. These are offline host measurements, not actual WoW frame times. No architecture comparison was repeated.

## Actual backend deployment

- Live API/local API image: `sha256:cae89b4d481ef017b1376b276e4792412172c38022103948df2a430c9c863cb9`.
- Reviewed module source: `e5576c9d66e50914d4bcbbf27aad962a8c9f372f`.
- Retained API rollback image: `sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c`.
- Repaired collector image remains `sha256:ec94420d36baf501d312f3cbc85e38b77222e5b5bff92b76aae82dd8df95575d`.

Only `api local-api` were replaced at **10:01 a.m. Mountain**, using the actual 26 overlays, collector repair overlay and immutable API overlay, with `up -d --no-deps --no-build --pull never --wait api local-api`. Both API environments, users, commands, limits, mounts, ports and network membership are preserved. The nine other production container IDs/images are unchanged. No production migration, worker replacement, polling/backoff reset, provider campaign, frontend promotion or data cleanup occurred. Schema remains `retention_20261118`. [Actual promotion](evidence/market-regression-cleanup/final-promotion-result.json).

Authenticated HTTPS validates Contracts 1, 2 and 3 with **30,336 genuine exact variants**. The frozen native core validates the prepared **32 current partitions**, all **64 history partitions** and **10 dated observations**, then reuses one bound 304 with zero payload bytes. This is Linux native-core/data validation, separate from installed Windows fixture publication and actual Forever execution. Source-bound validation remains exact when a normal collection advances; preparing a newer source legitimately returns 202. [Genuine acceptance](evidence/market-regression-cleanup/backend-live-acceptance.json).

Fresh protected archive `market-release-20261123T152456556825Z-1c1734c7fc7d.dump`: **1,922,461,549 bytes**, SHA256 `d0ae48ea244e08d5b1fc2804edc6dd8859ea06fceffe953f27bac4e087e5119e`. Actual isolated restore recovered 31,194,205 listings, 2,127 observations and 5,102,118 statistics with constraints. Recorded historical cutoff hashes match; two provider envelopes decrypt and candidate Alembic check passes without migration. The own rehearsal volume was retired after success. No fresh complete-table production equality beyond those stated checks is claimed. Current backup policy remains enabled revision 2; old disabled-policy descriptions are historical. [Restore proof](evidence/market-regression-cleanup/restore.json).

## Actual Companion publication

| Identity | Value |
| --- | --- |
| Version / payload source | `2.0.0-beta.12` / `e5576c9d66e50914d4bcbbf27aad962a8c9f372f` |
| Original Windows run / artifact | `45219466787` / `14840208468` |
| Original installer bytes | `4,972,080` |
| Installer SHA256 | `08200ab7f7600ebd7a005d049122d712de0b76036babaddc1307538830692096` |
| Installed executable SHA256 | `2c5696be4bd53e9a6898a743273193686dec4f72fbae2033ddac8df4beb3c4e2` |
| Updater key SHA256 | `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf` |
| Final actual SDK run / harness | `45229901410` / `f1492cdc8264e00309c07aba1492d9d207e43ac0` |

The existing no-network isolated signer used the unchanged key, pinned Tauri 2.12.4, read-only private inputs and suppressed internal output. Private material was not copied or exposed. Independent verification passed before publication and again on the actual HTTPS download. The actual supported Windows SDK installed these original bytes, verified the original installed executable, reconnected/synced/exported, retained uninstall data and rejected corruption and a wrong signed version. Installer-process exit was not observed; final installed identity/state was independently verified. Windows publisher remains **NotSigned** under the approved free private-beta policy; the required Tauri signature is valid. Actual PC tray/UAC/game acceptance remains unobserved.

The existing private publisher atomically selected beta.12 at **10:55:53 a.m. Mountain**, durable audit **00000011**. All **112 prior non-pointer files** remain byte-identical; beta.11 remains downloadable; **11 new files** were added. Store usage is **52,637,781 bytes** within the unchanged **128 MiB** budget. The operator uses the existing store-owner identity in the marketdev rootless namespace (container UID 0 maps to host UID 1002); volume modes/ownership and host security were unchanged. [Publication](evidence/market-regression-cleanup/publication.json), [preservation](evidence/market-regression-cleanup/publication-store-preservation.json), [published manifest](evidence/market-regression-cleanup/beta12-published-manifest.json).

Live HTTPS offers beta.12 to eligible beta.5–11 clients; equal beta.12, newer beta.13 and stable 2.0.0 return 204. Browser/native downloads reproduce the exact signed hash/size, anonymous downloads return 401 and native access to browser-only current metadata returns 403. Beta.11's original hash remains intact. [HTTPS proof](evidence/market-regression-cleanup/publication-https.json), [downloaded-byte signature](evidence/market-regression-cleanup/https-downloaded-signature.json).

Only readback grant 458 and publication grants 462/463 were revoked, each independently verified 401; raw token/bootstrap snapshots were removed. Original accounts/devices were not reset. All 11 post-API container IDs/images/start times remain unchanged through publication. Final health is 200; house 114 collected at **10:57:19 a.m. Mountain**, both feeds zero failures at the original **300 seconds**. Bounded post-publication API/local/worker/database logs contain no critical markers. [Final health](evidence/market-regression-cleanup/production-final-release.json), [bounded service checks](evidence/market-regression-cleanup/final-service-validation.json).

## Owner installation and gameplay checks

Private addon ZIP: `TwichUI-Market-25-84ca4842b9fd-private.zip`, **26,505,073 bytes**, SHA256 `75513e53c6380788fd9acb28bc287a538e6d33dc94b1d09b38ca8f2a3f7e0d5c`. Internal version `0.0.0-dev.g84ca4842b9fd`; standard archive checker passes. It contains seven TwichUI runtime folders; the Companion generates the separate 25 Market data addons. Local artifact directory: `/home/marketdev/projects/TwichUI-Market/.local/regression-cleanup/private-addon/`.

1. Exit WoW. Install the provided runtime ZIP directly into `Interface\AddOns`, preserving `WTF`/SavedVariables, unrelated addons and existing Market recovery files.
2. Confirm/install Companion beta.12 through the existing private updater/account download. With WoW closed, allow the existing Workshop connection to synchronize. Compatible addon capabilities enable the 25-folder migration automatically; older addons retain safe legacy delivery until upgraded.
3. Start WoW after synchronization so new folders are discovered. Check a known variant/recipe cost, reopen Opportunities warm, and open one history chart. Report any hitch for real-client follow-up.

No PC update, real-game installation or public TwichUI release was performed by this session. Real-client frame stalls and tray behavior remain the explicit remaining uncertainties, not hidden release passes.

## Supported rollback retained

[API rollback](../deploy/prepared-market-20261123/rollback-api.sh) and [private-pointer rollback](../deploy/prepared-market-20261123/rollback-private-release.sh) pass check mode. API rollback preserves the collector overlay and replaces only the two APIs with retained `a3f822…`; private rollback atomically selects retained signed beta.11 without deleting anything. Neither was executed. A pointer rollback cannot force an installed SemVer downgrade. Preserve complete owned legacy/A/B recovery and use the existing Companion recovery flow before downgrading consumer support; never splice banks or improvise a database downgrade.

Keep the worktrees referenced by the live Compose overlays and these operators. Previous images, signed releases, protected archives, key recovery and generation recovery remain available. [Final version combination](evidence/market-regression-cleanup/final-release-combination.json).
