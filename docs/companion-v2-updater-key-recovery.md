# Owner updater key backup and recovery

This key authenticates TwichUI Market Companion updates. It is separate from Windows commercial code signing and has no certificate/subscription fee. The owner explicitly chose this zero-cost approach. No installer/publication/deployment is approved by generating the key.

The actual encrypted private key is stored outside the repository at:

`/home/marketdev/.local/share/twichui-market-companion/signing/updater.key`

Its public key is `updater.key.pub` in that folder and is copied to `desktop/src-tauri/updater-public-key.txt`. The separate generated passphrase is stored at:

`/home/marketdev/.local/state/twichui-market-companion/updater-key.passphrase`

Both project directories are owner-only0700 and key/passphrase files0600. They are outside Git, PostgreSQL archives and application/Docker build contexts. The private key is encrypted by supported Tauri tooling; its passphrase is never placed in process arguments or logs. Do not paste either private file into chat, issues or CI logs.

## Back up

The dedicated key archive is:

`/home/marketdev/.local/share/twichui-market-companion/signing/twichui-market-updater-key-20261115.tar.gz`

It contains the **encrypted** private key, public key and public metadata; it excludes the passphrase. This on-host archive is a recovery source, not protection against loss of the whole server. Copy it through your normal secure file-transfer method to at least two owner-controlled safe locations, with one offline. Save the passphrase separately in your password manager or another protected location. Do not put the passphrase in the same archive. Do not add either to the project database backups or application installer.

Retain the public-key fingerprint with those copies:

`5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`

## Recover

1. Restore the encrypted key archive into a new empty owner-only folder, retaining0700/0600 permissions. Restore the passphrase from its separate protected copy. Do not overwrite a working key or run key generation as a recovery action.
2. Check the normalized public key's SHA256 against the fingerprint above and the public key compiled into the installed app. A different key will not authenticate updates for existing installations.
3. Use the pinned Tauri signer to sign a non-executable test file with its version bound. Supply the passphrase through the private signing wrapper/in-process API or a protected input, never as visible command text. Verify it with the independent public-key verifier before signing an installer.
4. Sign only an exact-source Windows candidate that has passed the required checks. Preserve its raw bytes, detached signature, digest/version and owner approval receipt. The publication tool must independently re-verify them; a successful sign command alone does not approve release.

An actual archive extraction, signing and independent verification rehearsal passed on2026-11-15UTC. Temporary recovered copies were removed; the original encrypted key/passphrase and dedicated archive remain intact. No private bytes were placed in Git or logs. [Public verification evidence](evidence/companion-v2-updater-key-verification.json) records the result.

If the private key or passphrase is lost, do not disable updater signature checks. Recovery needs both protected materials; otherwise existing users need an explicitly verified manual installer that establishes a new public key. If compromise is suspected, stop publication and review a deliberate key-transition/manual recovery procedure before releasing anything.

## Local signing isolation

`prepare-companion-signing-input.py` first queries canonical passed exact-source CI and validates the original installer/installed public-key/executable/upgrade/performance receipts, without opening private material. Its output contains only public candidate metadata and installer bytes. `sign-companion-update.cjs` then rechecks bounded bytes, source/version, all three recorded CI identities and the actual owner public key, signs a copy using pinned Tauri2.12.4, and writes public detached proof. Existing signed version directories are never overwritten.

Run that wrapper only in the approved **rootless** Node container with no network, Docker logging disabled, read-only root/source/input/key/passphrase mounts, bounded temporary/output storage and CPU/memory. Redirect both output streams to `/dev/null` **inside** the container; the supported CLI may otherwise print key/signature details. Set only the nonsecret `TWICHUI_OWNER_SIGNING=authorized` flag. Mount the encrypted key folder at `/keys` and the separate passphrase folder at `/recovery`, both read-only; never copy them into the build context or pass password values in command text/environment. The wrapper supplies the passphrase to Tauri's supported in-process API, so it is absent from operating-system process arguments. Independently verify the resulting bytes/signature/version before accepting any proof. Windows CI receives only the public proof and exact installer.
