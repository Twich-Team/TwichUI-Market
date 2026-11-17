# Usability & reliability — production release acceptance

The owner approved PR #17's implementation/visuals and explicitly authorized integration, deployment and publication of the next compatible signed Windows Companion. These actions are complete at **https://market.twich.gg**. The previous review-only hold is superseded for this release. No addon modification/publication, destructive history maintenance, permanent identity cleanup, quota increase or infrastructure change occurred.

## Exact identities

- Approved application `df4d974bec1adb157fbca8b0eabb99f5190c6286`; review `ea90a98138221bc569d882577a1720fba1298457`.
- [PR #17](https://github.com/Twich-Team/TwichUI-Market/pull/17) merged as **`6d573c49d929dc63e2cb2115cb9f312787d086fe`**, onto the unchanged integration baseline `6cef35797f28d562c7ee3db3aa290cfe876f418d`. Scoped L2 work remains included, with its existing limits and delivery hold.
- Exact released application / beta.4 payload source: **`2920f366f7b5cd32178ae06ae94cea84701ff87f`**. Only explicit desktop versioning and necessary release-helper inputs were added to the approved application. The strict visual check now takes the actual approved visual commit instead of a hardcoded historical receipt; no check was removed.
- Signed-original-byte verification harness: **`b3ef86411ef23331a059aea113485abbcd3e0019`**. Its application code is identical; the detached public signature/provenance changed. The later closing commit contains only deployment pins/docs/evidence, not a rebuilt installer or application.
- Live API/local API/collector image: **`sha256:fa5d8f4c18e0421da98a9bd275789d022924000e8d513e2aa50157e000e39f5f`**.
- Live frontend image: **`sha256:197b01f4f4b9e7cf35d574e4c3e6f60f94a462e3dd5b9dccd488fb128d3743d9`**.
- Database: **`usability_20261117`**, safely advanced `fdb_20261116 → archive_20261116 → usability_20261117`.
- Enrichment remains the original `6bb71a6` image; database, enrichment, monitor and backup container IDs/start times are unchanged. No ingress, AMP, Traefik, Komodo, host networking, key or provider setting changed.

The collector needed one controlled replacement because its original daily-maintenance image did not even contain the Companion authorization model. Leaving it unchanged would leave the referenced-credential safety repair inactive. Its collection-loop and ingest source bytes are unchanged; asking-v1-provisional stays the default. Replacement waited for a quiet interval, retained the persisted next check and global collector lock, and never started a duplicate. House **114 alone**, **300 seconds**, **zero failures**, continued successful collection after promotion. [Runtime identities](evidence/usability-release/runtime-after.json).

## Exact-source verification

[Machine CI identities](evidence/usability-release/integrated-ci.json), [actual log summaries](evidence/usability-release/test-summary.json).

| Application-source workflow | Result |
|---|---|
| [Backend 44007355463](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44007355463) | 605 PostgreSQL tests; migrations, preservation/round trips, dependency audit; 44 operational and 16 scoped-contract checks pass |
| [Website 44007355538](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44007355538) | 129 frontend tests, build/audit, 41 ordinary + one ForeverDB + one provider-rate + five owner-observation browser workflows pass; mocked Companion update/archive UI checks pass |
| [Windows 44007355418](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44007355418) | 94 workspace + one Tauri tests pass; native HTTP/auth/sync/export/renewal/revocation, real installed UI/hidden synchronization, settings/cache, legacy upgrade and NSIS uninstall retention pass. Two documented opt-in tests are ignored; signed SDK acceptance runs separately |

The signature harness also passed Backend **44008432469**, website **44008432422** and Windows/signed SDK **44008432442**. The harness website's first attempt failed an immediate mobile-width assertion; the failed workflow alone was rerun without changing source or assertions and passed. No product defect was demonstrated by this intermittent check, and its failed attempt remains available. These are exact push-source runs, not PR-preview substitutes.

## Backup, migration and preservation

All **29 previous database archives** passed their stored SHA-256/length checks and remain intact. The unchanged 3 GiB scheduled-backup budget was already nearly full, so a separate owner-only release directory received a bounded archive; no backup was rotated/deleted and no retention/budget was increased.

Fresh archive **`market-usability-20261117T030531Z.dump`**, **453,697,171 bytes**, SHA-256 **`1f431684d4b1a3e52b14ed186e29fa3b35ed546e29b04d5d3ef4b08aca52a7ea`**, retained under the release worktree's ignored `artifacts/usability-release/`. It restored into isolated **market_test** with bounded memory/CPU/tmpfs and no workers. All **35 original tables/columns** retained identical fingerprints through upgrade/check/downgrade/re-upgrade; the restored population contained **825 observations and 8,573,753 listings**. pg_trgm and index validity passed. Both retained encrypted provider envelopes decrypted using the original keyring, and the previous production API could read the upgraded additive schema. The encrypted keyring recovery archive also decrypted in memory and matched runtime; no plaintext key file was created. The isolated database/network are retired.

[Backup receipt](evidence/usability-release/backup.json), [full isolated proof](evidence/usability-release/restore-proof.json), [production preservation](evidence/usability-release/preservation-final.json), [provider configuration fingerprint](evidence/usability-release/provider-configuration-sha256.json).

Production original-column fingerprints preserve all pre-existing observations, snapshots, listings/statistics, users, credentials, preferences and mapping records. The probe repeated a 7D chart choice, which advanced the preference revision/timestamp without changing values. This was detected, then the exact original row was restored with backup-digest, value-equality and concurrent-revision guards and an audit event. No unrelated preference was reset.

During acceptance the owner independently saved the same non-destructive retention proposal twice from another client. The initial strict table-wide audit correctly noticed that a previously empty policy table now had a row. That concurrent owner action was preserved, not overwritten or hidden; both audit/change receipts remain in the final proof. Policy remains **unauthorized**, compaction **false**, and retention batches **zero**. No production account/device was archived or deleted. No new account/device entry was created; only three audited temporary browser/native credentials were issued, revoked, verified as 401 over HTTPS and their private files removed. Native acceptance used a temporary narrow grant on the existing device, without rotating its real credentials.

## Actual public HTTPS acceptance

[17-scene actual production gallery](evidence/usability-release/review.html), [sanitized public acceptance](evidence/usability-release/public-acceptance.json). These are real stored observations and measurements, not synthetic fixtures. Screenshots were inspected. Dates use **America/Denver**. Each screenshot/query retains its own market/snapshot scope and capture time; they are not a fixed-population coverage-gain experiment.

Verified Explorer/navigation, removal of redundant notices, existing variant/quality presentation, metric explanations, actual 24H/48H intraday samples/local timestamps, honest gaps/unavailable values, Current Listings' own observation timestamp and existing 7D chart. Actual Deal Finder cards loaded local same-origin icons without hover, including narrow layout. Administration Overview, device counts and owned records, metadata summaries/charts, provider field/provenance tables, measured database growth/GiB formatting, member/device archive controls, security events and disabled destructive controls passed. The real authenticated retention dry-run preview passed with application authorization false; its confirmation token was discarded. Public logout without CSRF was refused (403), valid logout returned 204, and that final temporary session then returned 401. [Preview/CSRF/logout evidence](evidence/usability-release/retention-preview-logout.json). No destructive controls or provider test/campaign buttons were exercised. Public details/Overview axe checks passed; browser JavaScript errors and direct third-party browser requests were zero.

Measured metadata administration latency was about **5 seconds** for one public request, not a latency guarantee. The public probe's initial five-second readiness assumption was corrected to wait for the actual response; no API assertion or product behavior was weakened. Tooling selector/path mistakes were corrected separately from the application. Public native bootstrap and a real **50-change sync-v1 page** passed with asking-v1-provisional unchanged. Full installed native sync/export and unchanged bridge contracts passed Windows CI; the previous genuine-history delivery hold was not bypassed by launching another live bridge campaign.

## Signed Companion beta.4 publication

**Version `2.0.0-beta.4`**, private account-controlled Windows x64 NSIS channel. [Get Desktop Companion](https://market.twich.gg/companion); [authenticated exact installer](https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.4/windows-x64).

- Exact installer: **4,715,921 bytes**, SHA-256 **`6a64493b795577b23503af86a1ff8d79181a157f233272a2247703c2059689af`**.
- Installed executable SHA-256: **`6acb8f7cd1e10b1291c7eee09040b8662b3212cc648b6e3c576060178c771916`**.
- Original installer artifact **14294729360**, canonical Windows run **44007355418**, payload source **2920f366…**. The later harness rebuild was not substituted.
- Existing updater public-key fingerprint **`5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`**; no rotation or private material in Git/CI/API/build context. Signing used the pinned free Tauri CLI in the documented no-network rootless wrapper with logging disabled.
- [Actual signed SDK acceptance](evidence/usability-release/signed-update-acceptance.json), run **44008432442**: exact signature/version, tampered payload and wrong signed version rejection, actual installation, installed executable hash, retained credentials/cache/connection, reconnect/sync/export and uninstall retention. Detached installer exit was not directly observed; successful installed state and executable bytes were independently verified.
- The immutable publisher independently verified the complete bundle and signature, imported beta.4 and atomically moved the pointer from beta.3. Previous releases/evidence remain available. Private admission remains owner-only; no new account was admitted. Stable remains unpublished.

[Real HTTPS update/download proof](evidence/usability-release/published-beta-acceptance.json), [independent signature verification of the downloaded bytes](evidence/usability-release/public-signature-verification.json): an authorized beta.3 request receives beta.4 and its exact original asset/signature; beta.4 and a newer client receive **204**, unauthenticated access receives **401**. Publicly downloaded beta.4 bytes match the signed installer and verify offline. Beta.3's original SHA-256 `d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183` still downloads unchanged for recovery. No silent installation occurred. Windows publisher is honestly **NotSigned**; free Tauri update authentication does not remove SmartScreen or replace Authenticode trust.

Beta.4 includes the dashboard update banner, tray indication, hidden/minimized Windows notification, persistent deduplication, automatic checks and explicit install confirmation. The new notification experience runs after beta.4 is installed. Physical Windows toast/tray behavior and the owner's beta.3→beta.4 PC upgrade remain manual owner acceptance, distinct from actual CI-installed upgrade and public server checks.

No unpublished addon change is required. Existing validated data-only exports, transport/schema identifiers, receipt, hashing, pricing identity and atomic generation semantics remain. [Addon PR #42](https://github.com/Twich-Team/TwichUI/pull/42) was neither changed, merged nor published. Its missing simulator and in-game provenance/refusal acceptance remain separate development work; no unsupported reader was silently activated.

## Deployment and immediate compatible rollback

Use the **original production project directory/environment files**. Append the new overlay last; never issue an unscoped `up`. This preserves existing keyring/store/configuration mounts and listener restrictions.

```bash
market_release=(docker --context rootless compose -p twichui-market
  --project-directory /home/marketdev/projects/TwichUI-Market
  --env-file /home/marketdev/projects/TwichUI-Market/.env
  --env-file /home/marketdev/projects/TwichUI-Market/.env.combined-release
  -f /home/marketdev/projects/TwichUI-Market/compose.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.tls.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.traefik.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.companion-private-beta.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.combined-release.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.admin-release.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.explorer-release.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.polish-release.yaml
  -f /home/marketdev/projects/TwichUI-Market/compose.foreverdb-release.yaml
  -f /home/marketdev/projects/TwichUI-Market/.worktrees/usability-release/compose.usability-release.yaml)
"${market_release[@]}" up -d --no-deps --wait api local-api proxy
```

The necessary collector replacement is already complete; future API/frontend restarts do not need another collector restart. [Pinned rollback overlay](../compose.usability-rollback.yaml) appended last restores the predecessor API/frontend and, only if needed, original collector. Retain `usability_20261117` and all newer rows; do not downgrade/drop tables or restore a dump over live data. Additive archives block schema downgrade once populated. Enrichment stays compatible and untouched. Private release rollback uses the existing no-network immutable publisher's `rollback 2.0.0-beta.3 --actor …` with the same original environment/store mounts; verify first, retain all versions, and never force a client downgrade. A corrective client update needs a newer signed version.

## Known limits and stop boundary

Scheduled database backups still report the pre-existing **full archive budget** failure. All old backups and a new checked/restored release archive are retained, but future scheduled backup capacity requires an owner storage/archival decision. No backup policy/budget or host storage was changed to conceal that warning. Off-host database/keyring/updater-key copies remain unverified.

Actual Windows toast/native tray actions and the owner's physical upgrade remain manual checks; there is no claim of physical PC verification. Addon PR #42 remains separate. No release-blocking defect is outstanding in completed checks. Stop here: no additional development campaign, provider campaign, pruning, identity cleanup, addon publication or infrastructure change is authorized by this completion record.
