# Companion 2.0.0-beta.5 release acceptance

**Complete:** the owner-authorized private beta.5 is Tauri-signed, published and actually offered by the production website/updater. Atomic promotion completed **2026-11-17 13:02:48 UTC**, store audit **00000004.json / 00000004.complete.json**, actor `owner-authorized-M2-beta5-publication`. Beta.4 remains recoverable. The approved source/candidate was reused; only release test harnesses and documentation changed on `release/companion-beta5-publication`.

## Frozen release identity

The approved remote `integration/companion-v2-metadata-recovery` HEAD is **8c52b70afe8db4d514a46daf7dd13f27cccc8014**, including merged Market #19 (`25e6131b646f94afdb72a5d69b276cd6251e9ab1`) and #20's help correction. The source and embedded installed version are **2.0.0-beta.5**. No candidate rebuild or product change was made during this task.

The supplied `/workspace/TwichUI-Market/artifacts/market-m2-pilot/README.txt` and its equivalent in this checkout were absent. Release inputs were recovered from repository operations, the actual production store, and original exact-HEAD Windows Actions artifacts. The original installer ZIP digest was checked before extraction. [Release identity](evidence/companion-beta5/release-identity.json), [source CI](evidence/companion-beta5/source-ci.json), [public signed proof](evidence/companion-beta5/signed-candidate.json).

| Asset | Identity |
|---|---|
| Installer and raw updater | `TwichUI-Market-Companion-2.0.0-beta.5-windows-x64.exe` |
| Bytes / SHA-256 | 4,762,861 / `6124b9472b03c1ee53a83e3a8e7570a9f3621834c77624cd9aa48bc005465de1` |
| Detached signature | `TwichUI-Market-Companion-2.0.0-beta.5-windows-x64.exe.sig` |
| Signature file SHA-256 | `7b4091a65201955c336022fa3ccc7c12ee1e44adf1e0a03f9d900b6e61ab3863` |
| Actual installed executable SHA-256 | `ea0aefbcc4e62c286f9ab7e2a963947c2c99e3730446565986578f23f77a1b1f` |
| Original Windows candidate | run 44015042019, artifact 14298178148 |
| Target / installer | `x86_64-pc-windows-msvc`, ordinary release NSIS current-user install |

Signing used the existing encrypted owner Tauri key and pinned CLI **2.12.4** in the documented bounded no-network rootless wrapper with read-only key/passphrase/input mounts and disabled signing logs. No new identity or rotation. The normalized public-key SHA-256 remains **5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf**. Detached signing preserves the original installer bytes. **Windows Authenticode remains NotSigned**; Tauri updater verification is separate from OS publisher signing.

## Production distribution

The existing private store is `twichui-market_companion-private-beta`, mounted read-only at `/private-beta` in the production APIs. Beta.5 is an immutable version directory; the established publisher stages and independently verifies all assets/receipts, writes audit intent, atomically promotes `current.json`, then writes completion. The signature is stored in `manifest.json` and returned in authenticated updater metadata; the raw NSIS installer is also the updater artifact. There is no separate updater ZIP or newly invented public signature route.

- Website: https://market.twich.gg/companion
- Installer: https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.5/windows-x64
- Beta.4 updater request: https://market.twich.gg/api/v1/companion/private-beta/update/windows-x86_64/2.0.0-beta.4
- Current website metadata: https://market.twich.gg/api/v1/companion/private-beta/current

These remain authenticated, owner-allowlisted private routes. Stable distribution remains unpublished. The website reads the current release dynamically; no frontend/API/collector image replacement or schema migration is required.

Production retains API application **2920f366f7b5cd32178ae06ae94cea84701ff87f**, schema **usability_20261117**, API image **fa5d8f4c18e0421da98a9bd275789d022924000e8d513e2aa50157e000e39f5f** and frontend image **197b01f4f4b9e7cf35d574e4c3e6f60f94a462e3dd5b9dccd488fb128d3743d9**. All required backend/contracts files are identical to beta.5's source. [Compatibility](evidence/companion-beta5/compatibility.json).

## Actual public acceptance

[Authenticated public HTTPS receipt](evidence/companion-beta5/public-distribution.json), [downloaded-byte signature proof](evidence/companion-beta5/public-signature.json), [rendered website receipt](evidence/companion-beta5/website.json), [actual production screenshot](evidence/companion-beta5/website-beta5.png), [publication audit](evidence/companion-beta5/publication.json). Chromium displays beta.5 and its correct immutable download link without page errors. Browser and native authorization return identical complete **4,762,861-byte** installers, matching the approved SHA-256 and signature. A beta.4 updater request returns **200 / beta.5**; beta.5, beta.6 and stable 2.0.0 receive **204**, and unauthenticated requests receive **401**. The unchanged beta.4 asset remains downloadable. Existing-device production bootstrap and a bounded real sync-v1 page succeed over public HTTPS. This is protocol acceptance from the operator host, not native Windows-to-production or owner-PC acceptance.

## Windows release-path evidence

The existing exact-signed-byte SDK workflow passed in **44085832476**, harness **97395db4723f972d45bcbb420682ead3a7097357**: supported SDK **2.14.1** signature and authenticated version, corrupt-byte and wrong-version refusal, actual installed executable digest, legacy credential/cache/connection retention, reconnect/sync/export and uninstall retention. [Receipt](evidence/companion-beta5/signed-update-acceptance.json).

The additional beta.4 workflow installs the exact original beta.4 installer, authenticates an isolated fixture through native Windows Credential Manager, seeds scalar SQLite and a history archive/exact working set, closes it, runs the signed SDK installation, compares retained file hashes, restarts beta.5 and checks account/device, selected market, settings, archive/projection, sync/export and uninstall retention. It configures no game path and requires delivery to stay off. The first run installed beta.5 and passed retained hashes but queried the WebView during navigation; the focused harness was corrected to wait for its real version element. A retained-checkpoint inspection also avoids requesting a new server checkpoint before comparing the original header. No release bytes or product assertions were weakened; the successful original SDK job was reused.

The corrected focused check passed [Windows run 44087256780](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44087256780), harness **fc1f435dd31e569e3bf986a178fc966e73fcec76**, original-byte artifact **14330516361**. [Beta.4 upgrade/retention receipt](evidence/companion-beta5/beta4-upgrade.json) records successful signed SDK installation, exact installer retention hashes for both SQLite files, settings and connection metadata, retained account/device/selection, reconnect/sync/export, delivery remaining opt-in and uninstall retention. The successful original signed-byte job in the earlier overall failed run is explicitly separate and was not repeated.

All runner market/game data is synthetic. These are actual installed Windows CI checks, not owner-PC or real WoW observations. The detached installer exit was not directly observed in the original SDK receipt; final executable/data/reconnect state was verified independently.

## Preservation and rollback

The full prior store, immutable metadata and signatures were copied before publication into ignored `artifacts/market-m2-pilot/store-before`; every original file was hashed. Beta.4 is **4,715,921 bytes**, SHA-256 **6a64493b795577b23503af86a1ff8d79181a157f233272a2247703c2059689af**. Its immutable URL remains https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.4/windows-x64. Earlier releases remain retained. [Baseline](evidence/companion-beta5/store-before.json), [actual prepublication download](evidence/companion-beta5/public-before.json).

The 128 MiB store used 13,691,204 bytes before beta.5. Isolated rollback rehearsals used the actual pinned publisher **3f757981f846016e3578f78998f4a8e2cb277705771f9bd83bb8daf6468c5b6f** and existing key, including exact beta.5 admission followed by beta.4 pointer recovery. [Rehearsal](evidence/companion-beta5/rollback-rehearsal.json), [bounded operator configuration](evidence/companion-beta5/publication-preflight.json).

For recovery, use the complete existing Compose/environment command in [production operations](usability-release-acceptance.md#deployment-and-immediate-compatible-rollback), retain its usability overlay last, supply the retained beta.5 incoming directory, and run only `--profile private-beta-tools run --rm --no-deps private-beta-publisher rollback 2.0.0-beta.4 --actor owner-authorized-beta5-recovery`. Re-verify public metadata and both immutable installers. Do not run `up`, restore a dump over production, remove assets, alter signatures or downgrade the schema. Pointer rollback cannot force an installed beta.5 client to downgrade; a corrective automatic update needs a newer signed version.

[Postpublication store](evidence/companion-beta5/store-after.json) proves **every previous asset, manifest, signature, receipt and audit file** is unchanged; only the active pointer and new beta.5/audit files were added. [Runtime comparison](evidence/companion-beta5/runtime-after.json) proves every production container/image/start/environment/resource identity is unchanged. [Protected rows](evidence/companion-beta5/protected-after.json) match original users, all 257 original credential rows and preferences; [provider guard](evidence/companion-beta5/provider-guard.json) matches encrypted credentials, quotas and configuration. The authenticated bootstrap deliberately advances existing device `last_connection_at`; a fully identical device-table fingerprint is not claimed and that telemetry is retained. [Production state](evidence/companion-beta5/production-state-after.json) confirms all 937 baseline observations remain, collection continues and the owner device is still authorized on beta.4; publication does not claim its physical installation. [Cleanup](evidence/companion-beta5/verification-cleanup.json) confirms both temporary verification grants return 401 after revocation and their private file was removed.

Database data/backups/keyring, original account/device grants, preferences and provider quotas are preserved. Verification uses two audited short-lived grants on existing owner device 3, then revokes only those grants. No new account/device is admitted. House 114 alone remains at 300 seconds; no provider campaign, pricing-default activation, collector reconfiguration or destructive retention. The prior scheduled database backup capacity limitation remains recorded in the usability acceptance; this artifact-only publication does not change that policy or require a database restore/migration.

## M2 pilot and owner steps

Exact-source installed evidence confirms scheduled archive synchronization, transactional history storage, exact selection, bounded schema-3 projection/publication, no-op writes and opt-out. Policy remains **1–10 variants**, **2 MiB canonical / 3 MiB Lua**, explicit owned installation, compatible consumer, conservative closed-game deferral and recoverable previous generation. Archive, generated, published and loaded-game status remain distinct. [Original installed M2 fixture receipt](evidence/companion-beta5/installed-m2-delivery.json), [full pilot procedure](market-auto-delivery-m2.md).

TwichUI #42/#43 are merged; main **36cdb04b35ca132650673463ecc09a0bbeadb6dc** has `TwichUI_Workshop/MarketDelivery.json`, capability/contract/transport 1, schema 3 and the exact size limits. No public addon release is published here.

1. Accept beta.5's update in the existing Companion, or download the private installer from the signed-in website. Existing credentials/configuration/history remain; automatic data delivery stays off.
2. With WoW closed, back up the existing addon folders and install the compatible `TwichUI` and `TwichUI_Workshop` folders from that pinned main source into the intended existing `Interface/AddOns`; preserve SavedVariables. This is owner-side private pilot installation, not a public addon release.
3. Confirm the selected market; download Workshop history and choose 1–10 exact item-ID/full-variant-key pairs. Start conservatively with a 30-day window. Do not invent bonus-name mappings.
4. Enter the one confirmed folder containing `Wow.exe`, review the exact destination and scope, then explicitly confirm/enable delivery. Keep WoW closed for writes; inspect archive/generated/published statuses and last successful write.
5. On login, enable Workshop — Experimental and inspect AH Market → Market server history, loaded generation, scope and dates. Reload only through the player's explicit safe confirmation. Capture real Forever diagnostics, performance, subsequent update and previous-generation recovery acceptance.

Built, Tauri-signed, published and publicly downloaded/verified are separate receipts. Installed Windows CI acceptance is separate from the owner's physical Windows installation, toast/tray actions, actual game-running behavior, native Forever performance/L4, antivirus/power-loss behavior and in-game acceptance; those owner-machine checks remain outstanding. No delivery was activated on any existing owner installation.
