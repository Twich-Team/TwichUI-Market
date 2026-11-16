# M1.5 manual Forever acceptance

**Delivery is held.** The genuine house-114 history contains 45,125 exact variants. Its authenticated canonical manifest request returned HTTP 413 after crossing the server's 64 MiB build bound. No complete generation or genuine `Data.lua` was produced. Do not install a fixture, an empty substitute, selected records from this generation, or a shortened history to bypass this result. A separately reviewed bounded-scope mechanism is needed before delivery.

The initial limits apply together: canonical input at most 2,097,152 bytes, at most 1,000 exact-variant records, and generated Lua at most 3,145,728 bytes. These are test budgets, not established Forever capacity. Contract completeness and last-good retention remain unchanged.

## Prepare on the owner's Windows computer

1. Use the actual Forever launcher to identify its installation directory. Verify that directory contains the executable used to launch **Forever** and the corresponding `Interface` and `WTF` directories. The owner's absolute installation path has not been verified. Do not substitute a Retail or Classic installation or assume a `_retail_` subdirectory.
2. Exit the game completely. Copy the entire `<Forever installation>\WTF` directory to a dated backup outside the installation. This preserves account and character settings, including account `SavedVariables\TwichUI_Workshop.lua`, its `.bak`, and `!!!TwichUI.lua` and its `.bak`. Do not reset or edit these files. Copy the current TwichUI addon folders and any existing `TwichUI_MarketData` folder to the same backup. Record hashes if comparing SavedVariables across sessions.
3. Back up the companion's existing `%APPDATA%\team.twich.market` directory while the companion is closed. Preserve its settings, `market-v1.sqlite`, `bridge-v1.sqlite`, and SQLite WAL/SHM files where present. Keep Windows credential storage intact. Do not clear caches or unpair the working device for this test.
4. Use a reviewed TwichUI build containing merged Workshop commit `732ccf87b825c7f93d7dbb73cae9fa9bfb001fd8`. The repository merge does not install the addon on the owner's computer. Do not mix unknown installed addon versions with isolated replacement files.
5. Install the approved companion through the existing account-controlled download/update process. Preserve the existing data and connection. The intended M1.5 candidate is `2.0.0-beta.3`, installer SHA-256 `d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183`, 4,515,855 bytes. Compare with `Get-FileHash -Algorithm SHA256`. Its Tauri updater signature authenticates bytes/version; its Windows publisher status is `NotSigned`, so Windows reputation warnings can remain. Do not disable Windows protections.

## Stage and install only after the delivery hold is resolved

1. Confirm the server is `https://market.twich.gg`, the existing account is connected, and the selected market is the intended exact house. Current retained source identity is US, transport ruleset ID 2, house 114, auctions, server market ID 2. Player-ruleset mapping is unverified; the display label is not independent proof of that mapping.
2. Use **Export for Workshop testing** explicitly. Select the documented algorithm; provisional asking means and `twichui-pricing-v1` canonical calculations are different. Do not change production pricing defaults. Record generation ID, source identity, algorithm, UTC dates, coverage, integrity and all three size measurements before delivery. A failed export must leave the preceding cache/output usable.
3. Export only to the companion's displayed owned staging directory outside the game. The scope-specific path is under `%APPDATA%\team.twich.market\workshop-testing\<scope hash>\TwichUI_MarketData`. Never point the exporter at `Interface`, `AddOns`, `WTF` or SavedVariables. Inspect its two files; the TOC must be load-on-demand with no SavedVariables declaration, and `Data.lua` must match the verified generation. Retain any `Previous.lua` in staging as recovery evidence; it is not listed in the TOC.
4. With the game still closed, manually copy the verified pair to exactly:

   - `<Forever installation>\Interface\AddOns\TwichUI_MarketData\TwichUI_MarketData.toc`
   - `<Forever installation>\Interface\AddOns\TwichUI_MarketData\Data.lua`

   The folder must not contain a second nested `TwichUI_MarketData` directory. Install both files as one controlled pair; keep the previous folder backup. No delivery tool should write to the installation automatically.
5. Restart the client so it discovers the new addon directory. Enable TwichUI, Workshop and the data addon in the addon's list as appropriate. If only replacing an already discovered addon, a player-initiated `/reload` is an alternative; nothing in this procedure triggers it automatically. Start out of combat.

## Load and compare explicitly

Open Workshop with `/tui workshop`. Use **Server history** beside an item's Price history to open the separate Auction House Market view, or open that Market view and choose **Market server (external)** in its market selector. Selecting this source explicitly calls the guarded bridge loader. Loading the data addon alone must not open Workshop or start a scan. Choose an exact server variant, then the price/supply metric and history range.

Do not run scans, posting, buying or cancellation as part of acceptance. External research must retain disabled trading shortcuts and must not feed local trading confidence.

For a future approved generation containing the same retained sample, item 647 (Destiny), exact variant `bd06e80e4090c7ea5e683c4997f73a753ad0b57d9f9d30379d991531ddff63ef`, has provisional daily Recent Price **1,499,999 copper on November 15 UTC** and **1,699,900 copper on November 16 UTC**. The November 14 observation has no listing for this variant; that is observed absence, not a missing market observation. Its provisional Market and Historical Values are **1,599,950 copper** over the two priced days. These are asking-listing observations, not sales.

Variant `cdd8fb2e3934817e43af42f8b230fa6900254eb50149bbed7219c325acc46a6c` for the same item has 2,300,000 and 1,699,900 copper on November 14/15, and no current listing on November 16. Its current Recent Price must remain unavailable, while the provisional reference is 1,999,950 copper. Do not combine the two variants. Compare against a newly authenticated export if observations have advanced. A canonical generation needs its own independently verified expected values; do not reuse these provisional expectations.

Only November 14, 15 and 16 UTC were genuinely available during rollout. Earlier dates within a requested 60-day range are unobserved. Three dates do not establish a mature 14-day or 60-day empirical model. Record exact observed timestamps and distinguish absent items, missing dates, omitted history and unsupported arithmetic.

Measure the actual client: compilation/load pause, time until ready, longest validation slice, responsiveness while loading, repeated navigation, and memory before/after replacing a generation. Use existing Diagnostics scopes `workshop.bridgeLoad`, `workshop.bridgeValidate`, `workshop.bridgeRecord`, and `workshop.bridgeHistory`, and the record/byte/cache gauges where available. Record hardware, client version, addon/installer hashes and whether any errors, freezes or combat/taint issues occur. Cloud CPU measurements do not qualify real frame timing.

Check source generation time, last successful server check, actual observed time and upstream modification time separately. A recent server check can refer to older source data. Recognize `loading`, `absent`, `invalid`, unsupported versions/algorithms/arithmetic, stale timestamps and incomplete coverage. A rejected candidate must not become the current snapshot. Re-enter the local source and verify local Prices, History2, distributions and profile/history data remain intact. The data addon declares no SavedVariables.

## Roll back the manual test

Exit Forever. Restore the entire previous `TwichUI_MarketData` folder from the backup, or remove only the newly installed data-addon folder if none existed before. Restore the previous TwichUI addon version if it was replaced. Restart and select the original local market source. Preserve all current `WTF` files for diagnosis; the bridge should not require replacing them. Restore SavedVariables from the verified backup only as a separate owner-controlled recovery step with the game closed, after preserving any newer local history.

Keep the previous companion build/data backup. A release-pointer rollback does not force an installed companion to downgrade; use a newer corrective signed release for normal updater recovery. Owner Windows filesystem/interruption/antivirus behavior, tray actions and actual Forever acceptance remain untested until exercised on that installation.
