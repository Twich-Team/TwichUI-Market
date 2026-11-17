# M2 automatic Market delivery

Market baseline: integrated `6cef35797f28d562c7ee3db3aa290cfe876f418d`.
Market retains its existing integration/release conventions. TwichUI baseline: protected main
`3a33269fc75d9daa5c24525c4e66f0095e2a194f`. One-time synchronization:
[TwichUI #41](https://github.com/Twich-Team/TwichUI/pull/41), merged at
`0f25a23ddd1b0acf8ea269c508417ae8717b3629`, tree exactly equal to main.
Neither old TwichUI branch is deleted. All subsequent TwichUI feature PRs target main.

## Architecture

| Stage | Component and behavior |
|---|---|
| Schedule | Existing native Worker / NativeTask; startup/manual/interval, pause/cancel/backoff preserved |
| Authentication | Same authenticated client after scalar sync; account/origin/market configuration; archive rechecks bootstrap |
| Archive | Existing download_archive / ArchiveStore, resumable pages, transactional complete active/previous checkpoint promotion |
| Selection | Existing SQLite exact selection copied into confirmed configuration; 1–10 variants, rolling 1–60 UTC days |
| Projection | Existing schema-3 projector/validators, full selected history; 2 MiB canonical / 3 MiB Lua |
| No-op | Checkpoint/selection/window/budget identity and installed generation skip projection/writes; receipt-only differences do not rewrite files |
| Publication | One confirmed installation; compatible consumer capability; fixed TOC and one Data.lua replacement commit point |
| WoW | Data addon loads on demand, login/player reload reads files; no IPC/automatic reload |
| Workshop | Validated in-memory observation, generation, scope and age; never infers delivery/pending files |
| Recovery | Prior completed archive and Previous.lua; disable retains files; explicit closed-game rollback; no SavedVariables access |

`workshop-delivery-v1.json` is separate nonsecret configuration; absence means off. Each scope has a
bounded status record. Archive checkpoint, validated generation, published generation, delivery attempt
and last successful file write are distinct. Loaded game generation remains unknown. Scalar sync success
never implies delivery succeeded. Delivery errors preserve previous artifacts and retry on the existing
schedule. No collection, metadata requests or provider allowance changes are introduced.

## Filesystem policy

Preflight validates `Wow.exe`, owned `Interface/AddOns`, and compatible installed Workshop
`MarketDelivery.json`. Checks cover absolute local paths, ownership/ACLs, permissions, links,
junction/reparse points, parent components, existing files and available disk space. Unknown folders
are refused and preserved. Compatible manual exports are validated and shown for explicit adoption; their original account/installation cannot be inferred. An account/market/issuer/installation marker
prevents cross-scope reuse. Existing owned generations are validated and shown during review.

Windows defers writes if any process is named `wow*.exe`; enumeration failure refuses publication.
This conservative process-name policy does not certify native Forever behavior or renamed executables.
Keep WoW closed during pilot delivery. No security exclusions, game control or automatic reloads.

The TOC must match the existing publisher's exact invariant bytes. First installation writes valid data
before activating the TOC. Updates never change the TOC. Same-volume temporary-file replacement commits
only Data.lua, with flushed Previous.lua and final hash/readback checks. Previous.lua is never loaded.
No atomic-directory or universal power-loss/antivirus guarantee is claimed. An interrupted first install
can resume from its owned marker/data. Unknown crash debris refuses further writes for manual inspection
rather than deleting files. Locked, denied and full-disk failures retain recoverable previous artifacts.

## Compatibility

| Component | Requirement |
|---|---|
| Server | L2 archive protocol 1 / evidence revision 1; bridge contract 1 |
| Companion | M2 2.0.0-beta.4 candidate; existing device credentials/updater trust retained |
| Workshop | M2 installed consumer capability 1, schema 3, transport 1, 2/3 MiB limits |
| Payload | Unchanged generation schema 3, selection contract 1, receipt schema 1 |

Workshop preserves legacy schemas 1/2. The installed capability is a compatibility declaration, not an
authentication signature; payload validation still applies. Older public Workshop releases without it
are refused. No public addon release, valuation-default change or live AH transactions are included.

## Owner pilot setup and acceptance

1. On the authorized operator host, verify actual production image/commit/schema and collector health
   using `foreverdb-release-acceptance.md`. Last recorded production is `6bb71a6`, schema `fdb_20261116`;
   L2's merge is not deployment evidence. Before required server update, checksum a fresh backup and
   complete isolated restoration; preserve previous images, collector, quotas, credentials and history.
   Use the established deployment process only; never reset the production database.
2. Build the exact verified M2 Windows commit through existing CI. Retain installer/SHA256/key identity
   and native upgrade evidence. Use the owner's Tauri signing host/private updater procedure in
   `companion-v2-release-operations.md`. Never substitute unsigned bytes or reuse an old signature.
3. Install verified M2 Workshop source for this private pilot, preserving the previous addon copy.
   Do not publish a general addon release or modify real SavedVariables.
4. Connect the companion; choose the intended market. Open **Workshop history and automatic delivery**,
   download history, explicitly enter ten item-ID/full-variant-key pairs and check selection sizes.
5. Paste the one folder containing `Wow.exe`; choose a conservative rolling history window (30 days).
   Review exact destination, region/ruleset/house, then confirm and enable. A validated manual export requires explicit adoption; preserve an unknown/incompatible folder outside AddOns before retrying.
6. Close WoW; use Sync now or wait for its ordinary schedule. Verify archive, validated and published
   identities, file size and last write. Resolve errors without deleting last-good files.
7. Log in, enable Workshop — Experimental, open AH Market and select Market server history. Compare
   selected variants, exact copper and UTC dates. Hover the status chip for loaded generation, source,
   observation time, scope and validation. The Reload action first warns about unsaved interactions and
   cannot assert a newer file exists; acceptance rechecks combat and experimental consent.
8. Capture Diagnostics: game build, companion/addon versions and commits, source timestamps,
   canonical/Lua bytes, loaded generation, validation/worst slice, worst frame/callback, memory,
   errors/stutters. Verify local scans/history remain unchanged without editing them directly.
9. Exercise another scheduled update with WoW closed, then confirm consumption on login/reload.
   Deliberately refuse an update and verify last-good recovery. Disable delivery on corrupt identity,
   unsafe replacement, changed local history, severe freezes or unexpected automatic behavior.

Rollback: disable first; with WoW closed, **Disable and restore previous** restores validated
Previous.lua. Preserve configuration and archive. Login reads restored files. Server rollback uses
the existing image/backup procedure. Signed updater rollback cannot force a SemVer downgrade; use a
newer corrective signed version if necessary.

## Evidence categories and open gates

Local core tests, authenticated synthetic HTTP → Rust → SQLite → automatic publication → production
Lua reader, mocked IPC Chromium, exact-source CI, native installed Windows, owner hardware, production
deployment and real Forever acceptance are separate claims. See the evidence ledger added after checks.

This Cloud workspace has no owner-PC access or marketdev Docker context. Its production HTTPS health
attempt returned 403. No current production commit/database/backup is claimed verified here, no private
signing key is accessed, and no deployment/game installation is claimed. The pilot remains off by default.
Formal L4, actual game-running behavior, antivirus/power/crash/restart and signed owner upgrade evidence
remain open. Next Advisor milestone: a separate source-qualified lightweight summary index with its
competition safeguards; no universal summary runtime is implemented in M2.
