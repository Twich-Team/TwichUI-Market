# Companion v2: Windows tray acceptance

**Status: tray actions UNVERIFIED.** A real notification-area menu has been captured and inspected. Its actions have not yet been accepted. This checklist closes that gap on the owner's Windows PC; a green build or a screenshot alone does not close it.

## What the runner established

The earlier screenshots show Windows' taskbar Pin/Close menu, because the harness selected the application's taskbar button. Those failures do not establish an application defect.

The focused corrected attempt at source **2d66026**, Windows run **43647891422**, selects the real notification icon: automation ID `NotifyItemIcon`, class `SystemTray.NormalButton`, inside `TopLevelWindowForOverflowXamlIsland`. Its screenshot visibly contains the actual companion menu: status, Open companion, Sync now, Resume automatic sync, Settings and Quit. The popup belongs to the companion process and is class `#32768`.

However, that runner exposes the popup to UI Automation as `ControlType.Pane` with no `MenuItem` descendants. Automated menu selection cannot proceed reliably. The observed limitation concerns automation discovery; whether every action works on a normal Windows desktop remains unresolved. The strict optional tray test is retained, and its assertions are not relaxed. Default Windows checks continue independent restart, minimize/close, startup, sync, upgrade and uninstall coverage, while recording tray acceptance separately as unverified. Stable release acceptance still requires a real tray action result.

Evidence: [focused Windows run](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43647891422), acceptance artifact **14134754188**, ZIP SHA-256 **59415e78e3cf366d53b199dc38f67deda4baf15f1bf72f6c099a6f689f75cfb8**. Locally verified files are `artifacts/companion-v2/windows-43647891422/native-tray-attempt.png` and `tray-discovery.json`. These contain explicitly synthetic account/market data. No mock tray image is substituted.

## Prepare the test

Use the exact candidate installer recorded in [acceptance](companion-v2-acceptance.md): sourcee55807c, Windows43652127596, [engineering artifact14136930503](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43652127596/artifacts/14136930503). The raw2.0.0-beta.1 installer is4,404,245bytes, SHA-256 `da9dc6d9a00ec716211d5a716a2a5bc5902373b5b938c3576e0c8482732c5f00`. Check the downloaded installer with Windows Properties or PowerShell `Get-FileHash` before use. This owner test artifact requires GitHub access and expires; it is never the ordinary-user download path. This older unkeyed candidate is retained as historical evidence only. The final Tauri-signed candidate needs its own exact installer hash and PC acceptance. The eight-screen design is approved; final publication/deployment approval remains separate. Commercial Windows signing is not required. Prefer a separate Windows test account if an older companion is already installed. Keep any existing companion data; do not reset its cache to perform this test.

Record the installer version/hash, Windows version, display scaling and whether you use more than one monitor. The installer intentionally has no commercial Windows publisher certificate. Download only from the exact HTTPS market.twich.gg account page once approved, and compare the recorded SHA-256. If SmartScreen offers More info, inspect the app and choose Run anyway only if you trust that exact download. If Windows policy, Smart App Control or Defender blocks it without that option, stop and report the exact message. Keep every Windows security protection enabled; do not add root certificates or global exclusions. Tauri updater signatures verify package integrity and signed version; they do not remove Windows reputation/publisher warnings.

Production is still on the approved website/API release. Browser pairing and synchronization with v2 require the compatible approved candidate API; they must not be inferred from the existing production login page. The disconnected checks below can be completed first. Complete connected checks once a compatible approved endpoint is supplied. This checklist never changes server collection settings.

## Disconnected checks

1. Install for your Windows account and open the companion. Its first window should be visible; launch at Windows sign-in should start off.
2. Find the small companion icon beside the clock. Open the **^** hidden-icons area if necessary. Use that notification icon, not the larger taskbar application button.
3. Right-click the notification icon. Capture the full real menu with **Win + Shift + S**. It should show a status, **Open companion**, **Sync now**, **Pause/Resume automatic sync**, **Settings…**, and **Quit**. Sync should be unavailable while disconnected.
4. Choose **Settings…**. The existing window should open directly to Settings. Change no collection settings; these are local preferences.
5. Return to the dashboard, then click and double-click the notification icon. Confirm the existing window opens without creating a second companion process. Several WebView2 helper processes are normal.
6. Choose **Quit** from the notification menu. The companion window and notification icon should disappear, and its main process should exit. Launch it normally again.

## Connected checks

1. Sign in using the supplied compatible candidate endpoint, approve the named PC in the browser and finish its first sync. Confirm US Normal — Horde and a completed offline cache. Do not copy a token for a new installation.
2. Right-click the notification icon. Confirm its status agrees with the dashboard. Choose **Sync now** and confirm a new desktop-check time. An unchanged upstream-data time is valid.
3. Choose **Pause automatic sync**. Confirm the dashboard and menu say paused. Manual **Sync now** should remain usable. Choose **Resume automatic sync** and confirm automatic checking resumes without duplicate work.
4. Enable **Keep running when I close the window**, close it with **X**, then reopen it using **Open companion** in the notification menu. The same cache and account should remain.
5. Enable **Hide to the tray when minimized**, minimize the window and restore it from the notification icon. Repeat with a single click and double-click. Note any missing window, duplicate process or unexpected focus behavior.
6. Start a sync, hide the window and wait for completion. Reopen from the tray and confirm the desktop-check time advanced. Saved prices must remain available if the network is temporarily unavailable.
7. Enable **Launch when I sign in to Windows** and **Start quietly in the tray**. Quit normally, then sign out/in to Windows when convenient. The configured companion should start in the notification area, retain its account/cache and open from its icon. Disable launch at sign-in and verify that reversal on a later sign-in.
8. Open the companion shortcut several times. It should restore the existing process. Finally choose tray **Quit**, verify exit and reopen normally. Record whether window size/position and preferences persisted.

## Record the result

Return the exact version/hash, Windows/display details, one actual tray-menu screenshot and pass/fail for each numbered check. For a failure, record the clicked control, what appeared and whether the companion still runs. Do not send passwords, tokens or Credential Manager contents.

The acceptance record remains **unverified** until those observations are reviewed. A confirmed failure on the owner's desktop becomes an application issue to fix; inability of the GitHub runner to expose menu children is recorded separately. New desktop/web visual approval and signing/publication decisions remain distinct gates.
