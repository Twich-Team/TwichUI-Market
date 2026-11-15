# Desktop Companion v2 — frozen owner-review checkpoint

**2.0.0-beta.2 is ready for owner review and controlled integration preparation.** No demonstrated security/functionality defect blocks this candidate review. The complete original deployment goal is not claimed finished: PC tray actions, combined PR #2 acceptance and explicit publication/deployment approval remain separate. Work stops here under the owner's convergence instruction; no next beta, pipeline redesign, additional infrastructure or production change is planned.

## Exact frozen identity

| Item | Identity |
| --- | --- |
| Frozen implementation/release checkpoint | `d9d5ae354931bfe9276c30fde6f83da8d661e457` |
| Immutable installer build source | `c7bad2f5e84213e1c69e3eb66e8daa6540f05bc9` |
| Version / package | `2.0.0-beta.2` / Windows x64 NSIS |
| Installer | `TwichUI-Market-Companion-2.0.0-beta.2-windows-x64.exe` |
| Installer bytes | 4,426,483 |
| Raw EXE SHA256 | `0fbc53603c218ffa85c8ee7b4e54f25e53c52a6fc3b2330ae914337714d41869` |
| Actual installed EXE SHA256 | `fc11b4428f712779e8ac0f954847c8089f869a30567e71c67a422b1ce057d46f` |
| Windows publisher | NotSigned; commercial signing deliberately not required |
| Tauri verification key SHA256 | `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf` |

The installer source and later verification source are distinct on purpose: the SDK test consumes the original exact bytes, never a timestamp-different rebuild. The installed-file reference is measured from the actual installed application, separately from a build-directory file. Earlier beta1/reference-error records remain preserved. [Machine-readable freeze](evidence/companion-v2-frozen-candidate.json).

## Exact CI and updater evidence

Every listed workflow completed successfully:

| Scope | Backend | Website | Windows |
| --- | --- | --- | --- |
| Installer source c7bad2f | [43664574952](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43664574952) | [43664574886](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43664574886) | [43664574901](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43664574901) |
| Frozen verification d9d5ae3 | [43665403724](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43665403724) | [43665403722](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43665403722) | [43665403770](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43665403770) |

Essential evidence is reused for unchanged code: 327 PostgreSQL tests, 16 operational/release gates, migration preservation/round trips and dependency audit; 60 frontend units and 21 actual browser workflows; Windows core/vault/SDK/HTTP/auth plus real installed native startup, hidden sync, restart, preferences, legacy upgrade and uninstall retention. The final separate signed-updater job proves signature/tamper/authenticated-version checks, actual beta2 installation, exact installed EXE, preserved legacy grant/cache/connection, reconnect/sync/export and uninstall retention. [Actual signed SDK receipt](evidence/companion-v2-signed-update-acceptance.json), [public signature/provenance](evidence/companion-v2-signed-candidate.json), [independent crypto verification](evidence/companion-v2-signed-candidate-crypto.json).

The dedicated encrypted private key stays outside Git, CI, application bundles and PostgreSQL backups. Actual encrypted-key recovery and wrong-passphrase rejection are already verified. [Backup/recovery instructions](companion-v2-updater-key-recovery.md). No private signing material is needed on your Windows PC.

## Installer, screenshots and measurements

The local owner bundle is `artifacts/companion-v2/owner-review-2.0.0-beta.2.zip`. It includes the exact installer, detached signature, public key, SHA256SUMS, source/CI/signature receipts, release notes, rollback instructions and eight actual screenshots. The original [CI installer artifact14141637538](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43664574901/artifacts/14141637538) is another owner engineering download; it expires and is not the future ordinary-user distribution path. Permanent account-controlled market.twich.gg publication remains unexecuted.

[Open the eight-image gallery](evidence/companion-v2-keyed-screenshots/index.html). Seven captures are from the frozen beta2 source; the tray capture retains its earlier independent source and explicit unverified-action status. The original owner-approved gallery/approval receipt is unchanged. All market/account screenshots are synthetic fixtures.

Actual frozen-installer sample: native window717.4204ms at50ms polling; second-launch restore92.4051ms;132,497,408 private bytes across7owned native/WebView processes;10.06448s idle0.4657%one-core/.1164%host CPU with zero additional Market API requests. Summed working set386,936,832bytes may count shared pages repeatedly. Desktop frontend28,603bytes. Initial1813.866ms/no-op907.0153ms sync use two variants with500ms/page injected delay; they are not a full live-market benchmark. Original JSON is retained beside the screenshots.

## Remaining-item classification

| Classification | Remaining item / decision |
| --- | --- |
| Release-blocking security/functionality defect | **None demonstrated for this frozen review candidate.** A confirmed owner-PC or combined-integration failure would be handled as a specific defect, without speculative pipeline work. |
| Owner approval required | Review this exact installer, release notes and screenshots. Run the disconnected PC checklist; tray actions remain unverified until observed. Connected PC acceptance needs an approved compatible API. No full stable tray acceptance is claimed. |
| Owner approval required | Explicitly authorize controlled integration with PR #2. Its new metadata designs/provider setup retain their own owner gates. |
| Owner approval required | Separately authorize installer publication and production rollout after the actual combined source is accepted. Neither the prior design approval nor free-signing decision grants this. |
| Nonblocking limitation / future enhancement | GitHub tray UIA exposes the rendered popup as a Pane with zero MenuItem children. No further repeated automation. The optional installer-exit observer did not capture a direct exit code; actual bytes and complete lifecycle are verified. |
| Nonblocking limitation / future enhancement | Expected Windows unknown-publisher/reputation warnings; owner-PC policy may require reporting a block. No security disabling. Fixture-limited performance and genuine production desktop end-to-end checks remain explicitly distinguished. Brother/friend account invitations can follow later; no additional account access was activated. |

## Your review steps

1. Transfer `artifacts/companion-v2/owner-review-2.0.0-beta.2.zip` to your Windows PC and extract it. Open `START-HERE.txt`, then the included screenshot gallery and release notes.
2. Compare the installer's PowerShell `Get-FileHash -Algorithm SHA256` result with the raw EXE digest above. Use this exact installer, not a rebuild or an older beta.
3. Follow the included Windows manual checklist. Disconnected installation/tray checks can run now; stop before connected checks until a compatible approved API is available. Record Windows version, installer hash, menu screenshot and each observed result, without credentials.
4. Review the limitations and rollback notes. If acceptable, explicitly authorize controlled PR #2 integration as the next bounded step. Final publication and production deployment remain separate decisions after combined acceptance.

## Item Metadata Recovery PR #2

**Ready as the frozen input for controlled integration; not yet merge/deploy certified.** Read-only assessment inspected [PR #2](https://github.com/Twich-Team/TwichUI-Market/pull/2), head `b18927ac867d3421f59cde163d3750af3ab17950`. Its prior green combined preview targets an older Companion checkpoint, so it cannot certify this freeze. GitHub reported nonmergeable at inspection; no merge simulation, branch integration or new combined test campaign was started here.

Use frozen `d9d5ae3` for a separately authorized integration candidate. Reconcile the overlapping native authorization allowlist so both the private updater and additive metadata read route remain; preserve signed-updater/exact-source CI and both browser fixture environments. Migration order remains `0012 → 0013 → meta_20261114`; no new Companion migration was added. Keep v1 pricing/sync/export contracts, the sole house114 collector, accounts/history and all key boundaries. The metadata provider keyring must remain separate from the updater signing key. Run combined exact-commit CI before any release use; do not rebuild the frozen installer unless a demonstrated incompatibility requires it. This readiness assessment is not merge or deployment authorization.

## Rollback and production preservation

Nothing was deployed or published. Production stays on the previously approved c8f03c2/schema0012 release, with house114/market2 alone enabled at300seconds. The final read-only check at 02:14 UTC confirms HTTPS health, unchanged worker/API/frontend start times, zero restarts/OOM and last collection success at 02:12:44 UTC. House110 retains all145 observations; the database is908,711,603bytes below5GiB and pruning is off. Worker memory101.1MiB/384MiB; PostgreSQL660.9MiB/768MiB. [Final health receipt](evidence/companion-v2-owner-review-health.json). [Read-only preservation fingerprints](evidence/companion-v2-free-signing-preservation.json), [backup/rollback evidence](evidence/companion-v2-free-release-preflight.json). That older image-build record is historical preparation, not beta2 deployment authorization.

Previous production API `sha256:17d2c17591bd0ddea617fcf9018d0235a9100bd00813ea0faa025f3b83e679f2` and frontend `sha256:fb5f20db59d6a5ed92c1ea4d490e1d6af86772065b9d5be88f1096cf00cc6d0c` are retained, including pre-v2 rollback tags. The latest rehearsed archive is `market-development-20261115T010501853878Z.dump`, SHA256 `6e90a5339526b910314d4128f3166e734fdf5eb3b99be3ac29ab1dc64bdf3c11`; actual isolated restore passed and all17earlier archives were preserved. Refresh that preflight only for a later authorized rollout.

No earlier approved Companion updater release is live, so there is no previous published desktop version to roll back to. Preserve the frozen repair installer and all offline data; do not force an older installer or delete AppData/Credential Manager entries. Future audited pointer rollback retains all versions and never forces client downgrades; a corrective client build needs a newer signed version and owner approval.

Review/install first; report PC tray observations without credentials. If acceptable, authorize controlled PR #2 integration as the next bounded step. Publication and production approval remain separate. Work is stopped at this owner-review boundary.
