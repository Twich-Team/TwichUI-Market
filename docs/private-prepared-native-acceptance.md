# Private Forever acceptance: frozen real generation, 16 versus 32

No production deployment, signing or release is needed. Use the existing unsigned
DEV application and isolated tools, never the normal Companion or installation.
The game and all tools run inside a disposable Windows VM with its own user and an
independent Forever installation. Do not mount production folders/drives, copy normal
WTF/AppData/keyrings, use junctions, or install the normal Companion in this VM.
This VM boundary is what prevents DEV discovery from accessing production directories.
The offline publisher additionally requires a confirmed DEV destination and private marker.

## Source and artifacts

The DEV workflow produces an exact-source artifact named
`TwichUI-Market-Companion-DEV-<first seven source characters>`, with:

- `build.json`: full Market source commit, run/attempt, `team.twich.market.dev`, unsigned,
  private-test status and disabled updates.
- DEV installer and `SHA256SUMS.txt`; separate native helper/scripts/docs and
  `PRIVATE-TOOLS-SHA256SUMS.txt`. Check every file with `Get-FileHash -Algorithm SHA256`.
- `prepared_private_publish.exe`: **private-dev Windows only**, no network, credential
  access, discovery or SavedVariables access. It invokes the existing full validator,
  destination checks, readback, root-last publication and retained last-good banks.

Installer app ID/storage are `team.twich.market.dev`; Credential Manager namespace is
`TwichUI-Market-DEV`; executable is `twichui-market-companion-dev.exe`. The window visibly
says DEV/unsigned; version shows `2.0.0-beta.11 DEV <full source SHA>`. Updates are disabled.
Do not follow the old beta.8 reference in the workflow's historical README as an instruction
to downgrade. No signed-updater or production installation replacement is part of this kit.

Use addon `1e034c025613a245f6238866fb2a57d76690c596` (prepared reader plus current main).
Market source must equal `build.json.source_commit`; clone/check out that exact source
for the local endpoint adapter. The public/private repository source contains no real
snapshot or credentials. Never commit or upload real Market snapshots/VM checkpoints.

## Install and obtain a source generation

1. In the VM, install a supported actual Forever client with a **fresh private WTF**.
   From the pinned addon checkout, copy these complete folders into its `Interface\AddOns`:
   `!!!TwichUI`, `TwichUI_Settings`, `TwichUI_NavData`, `TwichUI_Diagnostics`,
   `TwichUI_Layouts`, `TwichUI_LayoutWizard`, `TwichUI_Workshop`. No outer repository folder.
   Chart UX #117 is separate and is not included by this procedure.
2. Install the checksummed DEV installer in the VM. Sign in using the existing Companion
   browser/device approval flow to **https://market.twich.gg/**. Approve this distinct
   DEV connection normally; never paste/extract tokens or reuse the normal app's keyring.
   Choose **US Normal — Horde, market 2 / house 114**. Keep launch-at-login disabled.
3. Choose **Connect Workshop** and confirm ONLY the exact independent VM game folder
   and market. Cancel any unexpected destination. Complete synchronization with game
   closed. The source is the existing authenticated
   `/api/v1/workshop/markets/2/summary?contract_version=3` and its generation-specific
   64 current + 64 history paths. Its preparation/cache writes are the owner-authorized
   existing API behavior; no production configuration or prepared endpoint is activated.
4. Pause and **fully exit** DEV; verify its process is absent (window close can hide to
   tray). The current production prepared endpoint may be absent: validated legacy
   Contract 3 delivery is fine for this SOURCE download. A Contract 2 source is not enough;
   stop on that condition rather than relabeling it.
5. Log into the private game normally, open the desired professions, and exit. Keep a
   common fresh PRIVATE WTF seed for both layouts; do not perform AH scans. Keep the
   same character, recipes, prices/settings, filters, sort and viewport across trials.

## Freeze a copy, exercise the isolated proposed endpoint

Run only inside the VM. Set `$Kit` to a NEW private working directory outside Git,
`$MarketSource` to the exact Market checkout, and `$PrivateGame` to the confirmed private
game path. Do not substitute a normal installation. PowerShell:

```powershell
$ErrorActionPreference='Stop'
$Kit = (Resolve-Path (Read-Host 'Extracted PRIVATE test kit directory')).Path
$MarketSource = (Resolve-Path (Read-Host 'Exact Market source checkout directory')).Path
$PrivateGame = (Resolve-Path (Read-Host 'Confirmed independent VM Forever directory')).Path
$build = Get-Content -LiteralPath (Join-Path $Kit 'build.json') -Raw | ConvertFrom-Json
$actual = (git -C $MarketSource rev-parse HEAD).Trim()
if ($actual -ne $build.source_commit -or $build.application_id -ne 'team.twich.market.dev') { throw 'Wrong private source/artifact' }
$Dev = Join-Path $env:APPDATA 'team.twich.market.dev'
$Configuration = Join-Path $Dev 'workshop-delivery-v1.json'
$c = Get-Content -LiteralPath $Configuration -Raw | ConvertFrom-Json
if ($c.version -ne 2 -or $c.scope.market_id -ne 2 -or $c.scope.server -ne 'https://market.twich.gg/' -or
    (Resolve-Path -LiteralPath $c.installation).Path -ne (Resolve-Path -LiteralPath $PrivateGame).Path) {
    throw 'Wrong DEV connection or private installation'
}
$caches = @(Get-ChildItem -LiteralPath $Dev -Directory -Filter 'workshop-summary-*' |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'current.json') })
if ($caches.Count -ne 1) { throw 'Choose the exact matching completed cache; do not guess or copy all AppData' }
$Copy = Join-Path $Kit 'private-market-source-frozen'
if (Test-Path -LiteralPath $Copy) { throw 'Preserve previous source copy; use a new kit directory' }
Copy-Item -LiteralPath $caches[0].FullName -Destination $Copy -Recurse
Copy-Item -LiteralPath $Configuration -Destination (Join-Path $Kit 'private-delivery-configuration.json')
```

Only the completed summary bank/configuration copy is needed. Do not copy profiles,
credential stores, authorization/session data or the whole AppData directory.
Install the locked backend dependencies into a new VM-local Python environment:

```powershell
python -m venv (Join-Path $Kit 'python')
$Python = Join-Path $Kit 'python\Scripts\python.exe'
& $Python -m pip install -r (Join-Path $MarketSource 'backend\requirements.lock')
$Frozen = Join-Path $Kit 'frozen-prepared-source'
& $Python (Join-Path $MarketSource 'scripts\prepare-private-current-snapshot.py') `
    --cache-copy $Copy --configuration-copy (Join-Path $Kit 'private-delivery-configuration.json') `
    --out $Frozen
if ($LASTEXITCODE -ne 0) { throw 'Frozen source preparation failed; do not install partial output' }
```

This invokes the **actual proposed prepared API route** in-process against an isolated
temporary SQLite database. It verifies authentication (401), both authoritative 16/32
responses (200), conditional integrity (304), all source hashes and exact current/history
binding. Its private test user/device/token exist only in that disposable database.
It never contacts production, opens a listener, changes owner accounts, collects data or
deploys a service. Thus no publicly reachable new endpoint is needed for this test.
Output contains the original manifest/128 parts, both attestations, scope and a hash
receipt—no credentials. `source_synthetic=false` is a manifest declaration, not independent
proof of genuine provenance; retain the DEV download/source record. CI uses fabricated
vectors with ordinary admission flags and labels them as fabricated.

For a strictly read-only production session, substitute an already completed compatible
cache/export obtained by an approved method. Do not start summary preparation in that case.
The new prepared endpoint remains unactivated on production throughout either procedure.

## Select, publish and preserve each layout

Exit game and DEV. Create the marker only in the independent VM game root after reviewing
the exact path. This marker never belongs in a production installation:

```powershell
[IO.File]::WriteAllText((Join-Path $PrivateGame '.twichui-private-native-test'), "PRIVATE VM ONLY`n", [Text.UTF8Encoding]::new($false))
& (Join-Path $Kit 'select-private-current-layout.ps1') -Layout 16 -PrivateGameRoot $PrivateGame -DevAppData $Dev
if ($LASTEXITCODE -ne 0) { throw 'Layout selection failed' }
& (Join-Path $Kit 'prepared_private_publish.exe') $Dev $Frozen 16
if ($LASTEXITCODE -ne 0) { throw 'Native publication refused; preserve previous working files' }
```

Save a complete private snapshot S16: AddOns (root, both banks, ownership/rollback files,
capability) and the private WTF seed. Do not move ownership markers to a different game
path. Preserve the original snapshot, then repeat the two commands with **32** and capture
S32. Keep DEV exited: offline publication uses frozen G and never asks production for a
newer generation. Each publication independently validates every original source partition
and the selected attestation before changing the active root. A valid same-layout repeat
reports `changed:false`. Never hand-edit generated data, source flags, prices or clocks.

Read-only comparison of the two snapshot AddOns directories:

```powershell
$S16AddOns = (Resolve-Path (Read-Host 'S16 snapshot AddOns directory')).Path
$S32AddOns = (Resolve-Path (Read-Host 'S32 snapshot AddOns directory')).Path
& $Python (Join-Path $Kit 'verify-prepared-layout-pair.py') $S16AddOns $S32AddOns
if ($LASTEXITCODE -ne 0) { throw 'Refuse comparison: generations/data/history do not match' }
```

Require `pair_matches:true`, one original source generation G, all 64 identical histories
and identical sorted current tuples (including exact variants and missing values).
Attestation IDs/layouts differ; economic data must not. This supplements native integrity
validation, not a replacement parser for admitting data.

Restore an entire S16 or S32 to the **same original private game path** only with game/DEV
closed, including matching capability, banks and the same private WTF seed. Never combine
root/parts from snapshots, delete rollback folders, or restore these into production.
Existing legacy/other-bank folders are deliberately retained; record that upgrade footprint.
Undo the experiment by restoring the complete original private snapshot. Do not downgrade
an old addon/Companion onto prepared root v2; first restore a complete compatible legacy
snapshot. Uninstalling DEV is independent of the normal application and preserves caches.

## Three paired cold trials, warm reuse and history

Alternate 16/32 order. Fresh Lua/login for each cold trial; finish while G is fresh under
normal reader rules. Do not open pricing pages before capture or change the clock.

```text
/tui perf start workshop 3
/tui perf mark opportunities-open
```

Open Opportunities, keep the initial viewport fixed until settlement, then:

```text
/tui perf stop
```

Export Quick summary + JSON outside the restored tree after combat. Check G/layout after
the timing capture (or reload afterward to avoid contaminating cold measurements):

```text
/run local s=TwichUI.Workshop.Summary.Status(); print(s.generation,s.prepared_version,s.parts,s.error)
```

Require G / version 1 / count 16 or 32. For the fixed 120-recipe scenario, existing native
goals are first visible ≤2 s, visible settlement ≤3 s, all settlement ≤10 s, current work
CPU ≤2 s. Warm reopen target ≤10 ms calculation settlement with no new current loads/hashes
or compatible craft recomputation. Report first-ten only with ten priced visible rows.
Keep the ~2 ms cooperative budget; target current-load p95 <8 ms and inspect every callback
>16.7 ms. Provisional sampled incremental-memory goal 16 MiB is NOT an established pass:
offline prepared peaks were 19.50/17.23 MiB (16/32). Sampled heap/FPS estimates are not exact
peak heap/frame CPU. Lua globals/previous banks cannot be unloaded before a fresh session.

Compare exact costs/selling values/profits, unknowns, variants, sort/filter, scroll and
warm reopening. Separately mark `history-open`, select recipes, hover/zoom, rapidly switch
and hide/reopen while pending; all 64 histories remain lazy and provenance stays intact.
Chart #117's separate loading-state UX is not part of this reader candidate.

For generation replacement, finish the matched comparison first, preserve both snapshots,
then allow DEV to obtain a genuine next completed source and freeze it separately. Repeat
native publication, check no mixed generations/stale completion, and reload normally.
Cancellation/interrupted publication must retain the existing root/last good; exercise
corrupt/interruption boundaries in the existing disposable native tests, not by damaging
production or editing loaded game files. No automated gameplay, AH purchases or reloads.

Return source/installer hashes, pair receipt, hardware/client build, recipe count, fixed
viewport/settings and six cold + warm/history exports. Passing private acceptance does not
authorize merge, backend deployment, signing, updater publication or addon release.
