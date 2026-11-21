# Companion 2.0.0-beta.8 — publication acceptance

**Published and verified:** [website download page](https://market.twich.gg/companion), [immutable authenticated installer](https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.8/windows-x64). The owner explicitly authorized the Workshop repair release, existing-key signing, Windows verification and private-beta pointer update. No further publication approval was inferred from CI. [Exact owner record](evidence/companion-beta8/owner-release-approval.json).

- Version: **2.0.0-beta.8**; original Windows installer **4,849,411 bytes**.
- Installer SHA-256: **`60ed1c13b96fe5cc8601343ce7efb1d1730891bedaeb5a30eb060b31fe3dc9d1`**.
- Installed executable SHA-256: `faad54c5183014aaec07dee65023f1d489c372bfbc99f36dd1ab9b83187edd92`.
- Frozen payload source: `36dc204d5975f57629ca1c830d41d8b95d2ac508`.
- Verified repair: `a85c0fb78c4d4aaa038b2364079e7b739006c85c`; PR37 merged as `814ffd250251baa9f6d8e62a3cbae617375c778f`.
- Existing updater public-key SHA-256: `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`; no key generation/rotation.
- Tauri updater signature verified; Windows Authenticode remains **NotSigned**.

## Exact repair and Windows source

The native core, Tauri runtime and UI Git objects are identical to the verified repair. Only committed desktop manifests/lockfiles move the release from beta.7 to beta.8. The installed-test gate now exercises Workshop on beta.8 and later beta versions while retaining older beta.5/beta.6 SDK coverage. The repair recognizes bounded native World of Warcraft product metadata in the supported 1.60 family without pinning patch/build/revision, and separates read-only game/addon input validation from strict output ownership. Unsupported-client refusal, junction/access/integrity controls, account/market isolation and actionable sanitized setup errors are preserved. [Source object proof](evidence/companion-beta8/source-preservation.json).

All canonical frozen-payload checks pass: [Windows 44341487381](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44341487381), [backend 44341487229](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44341487229), [website 44341487210](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44341487210). Windows includes all four jobs, actual installed Workshop setup/publication/recovery and old-release upgrade/uninstall retention; both small and 45,125-variant Windows-produced artifacts pass the production Lua consumer. Backend source passes 730 tests; frontend 132 tests plus browser/WebKit checks pass. Installer artifact14444802753, original acceptance14445985633, NTFS14445090083 and Lua14445841185 are independently ZIP-SHA checked against GitHub metadata before extraction. Original receipts/bytes are retained under task artifacts; no rebuilt executable was substituted.

## Signing and exact signed SDK verification

Pinned Tauri CLI2.12.4 signed the original installer bytes on this owner host, in a bounded rootless no-network container with read-only key/passphrase inputs and disabled signing logs. No private material entered GitHub, source, build contexts or logs. An independent offline Rust verifier confirms digest/signature/authenticated beta.8 version, and independently verifies the actual HTTPS-downloaded file again. [First verification](evidence/companion-beta8/independent-signature.json), [downloaded bytes](evidence/companion-beta8/downloaded-signature.json).

The [actual signed SDK job](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44345199307/job/134945589542), harness `3ebd8b3c8b613ca8ed42a85614679a824ff85033`, downloads this exact original installer. It verifies signature/version, rejects corrupted payload and wrong signed version, installs through the supported Tauri updater SDK, verifies the exact installed executable, reconnects/syncs/exports, and preserves credentials/cache/settings/connection plus uninstall data. Installer-process exit was not directly observed; the final installed bytes/state were independently verified. Engineering receipt publication flags remain false; the separate owner record supplies actual authorization. [Source-bound SDK receipt](evidence/companion-beta8/signed-update-acceptance.json), [original artifact identity](evidence/companion-beta8/signed-sdk-artifact.json).

## Live download, update and immutable preservation

Audited private publisher transition beta.7 → beta.8 uses **00000007.json / 00000007.complete.json**. The operator container is bounded, rootless, offline and has access only to the prepared public bundle and the existing dedicated release volume. Existing APIs keep their read-only release mount; publication does not replace production frontend/API images. [Publisher receipt](evidence/companion-beta8/publication.json).

Actual trusted authenticated HTTPS verifies the website link and version, exact browser/native installer bytes/hash, and updater manifests for **beta.5, beta.6 and beta.7 → beta.8** with the original signature/digest/version. Beta.8, beta.9 and stable2.0.0 receive204, so no downgrade is offered. Anonymous download remains401. Prior beta.5/beta.6/beta.7 downloads retain their original hashes. Every one of the **66 original immutable store files** is byte-identical; only existing current.json changes, with new version/audit files added. [HTTPS proof](evidence/companion-beta8/publication-https.json), [store comparison](evidence/companion-beta8/store-preservation.json), [genuine page screenshot](evidence/companion-beta8/website-beta8.png).

The separate owner-approved retention exception changed only two Python modules in API/local API/monitor/retention, preserving all other runtime modules and current frontend, data, collector, provider, backup and release state. [Retention activation acceptance](retention-activation-acceptance.md). No Workshop summary API or addon rollout occurred; prior separate rollout and genuine owner-game acceptance gates remain. Do not infer live Workshop data delivery from the Windows fixture-backed tests.

Both temporary browser/native verification credentials used the existing owner and existing device, then were revoked. Real HTTPS independently returns401 for both, and the private token file is deleted. No password reset, account/device creation, allowlist expansion or recurring-backup enablement. [Cleanup](evidence/companion-beta8/verification-cleanup.json).

## Remaining actual PC/game acceptance and rollback

The permission matrix passes11 real NTFS cases with Administrators disabled and an administrator-only read denied. TokenElevation remains true on the runner; a genuine normal-UAC owner login is not established. CI executables reproduce the owner's reported version metadata and are generated fixtures, not genuine Forever bytes. The owner's first failing native stage, real Forever recognition/one authorization, game-loaded generation and actual PC tray behavior remain unverified. Run beta.8 unelevated on the real installation, export sanitized diagnostics if it refuses, and verify game-loaded updates after WoW closes. These limits are preserved in owner/SDK evidence; no physical-PC acceptance is fabricated.

For rollback, use the existing audited private publisher to switch the pointer to immutable beta.7; retain beta.8, all previous assets/receipts/audits and the trust key. SemVer prevents clients already on beta.8 from being forced to downgrade; a new corrective update needs a newer signed version and its own publication authorization. Do not overwrite beta.7 or restore a database as release rollback. Keep this worktree/configuration available because the live retention overlay references it.

Final integration [PR39](https://github.com/Twich-Team/TwichUI-Market/pull/39) reconciles the approved release lineages. All application/contract/workflow trees equal fully passed integration source3ebd8b3; frozen published payload remains36dc204. [Tree equivalence](evidence/companion-beta8/final-source-equivalence.json), [complete integration CI](evidence/retention-activation/ci.json).

PR39 merged as `a0f614be8b1b2aeea4dae6b1474f7ad8e16d7589`. All six application/contract/workflow trees match tested source3ebd8b3; [actual merge receipt](evidence/companion-beta8/integration.json). No additional deployment or release-pointer change was needed.
