# TwichUI Market Companion 2.0.0-beta.2

Frozen owner-review candidate. No stable publication or production deployment is approved.

## What is ready

- Compact Windows companion with system-browser account approval, secure native credential storage, saved market choice and offline prices.
- Native background synchronization, manual sync, pause/cancel/retry, configurable intervals, single-instance restoration and optional Windows startup.
- Account/device management and a website setup wizard prepared for a separately approved compatible API rollout.
- Free Tauri-signed automatic updates: a dedicated embedded public key, exact package/signature/version validation, no forced downgrade, immutable release/audit handling and explicit installation consent.
- Actual signed SDK installation, reconnect, synchronization, export, legacy upgrade and uninstall retention verified on disposable Windows runners. Installer/source hashes and exact CI are in the owner-review packet.

## Known limitations

Tray menu rendering is independently verified; tray actions remain **unverified** pending the owner's PC checklist. GitHub's UI Automation cannot reliably select that menu. No additional tray retry is planned. The optional installer-exit observer missed its process; successful installed bytes and the complete application lifecycle are verified independently.

Windows Authenticode status is **NotSigned**, by the owner's zero-cost decision. Unknown Publisher/SmartScreen warnings may appear. After checking the exact HTTPS source and installer SHA256, use the normal **More info → Run anyway** option only if it is offered and you trust the file. If Windows policy blocks installation, stop and report the message. Never disable Windows security protections.

The current production website/API has not been changed to expose Companion v2 pairing or downloads. Connected owner-PC testing requires a separately approved compatible endpoint. Screenshots and sync timing use explicitly synthetic fixture data; they do not establish full-market live throughput. No game/addon/SavedVariables files are changed.

No paid Windows certificate, signing service or Microsoft Store registration is required. [Owner review](companion-v2-owner-review.md), [manual Windows checklist](companion-v2-windows-manual-acceptance.md), [key backup/recovery](companion-v2-updater-key-recovery.md).
