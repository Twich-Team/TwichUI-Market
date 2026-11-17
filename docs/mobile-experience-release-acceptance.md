# Mobile Experience Modernization production release

Owner explicitly approved PR #23 for controlled merge and frontend-only deployment on 2026-11-17. Physical iPhone acceptance follows deployment and does not block this approved test release. Earlier review-only holds are superseded for this exact scope.

## Frozen source and preflight

PR #23 merged into `integration/companion-v2-metadata-recovery` at **fa089a2660e745d6f77f5c2b0b7bbcb9109d6ae8** from approved review head `b9db6b76bb874e800fccae8a1c39176d620c7492`. The merge tree equals the reviewed head; application source equals verified `9fbd10efa3d747d322ddeefc5d21cd57465f4b14`. No integration conflict, force push or unrelated change.

Production preflight retains API/collector application `2920f366f7b5cd32178ae06ae94cea84701ff87f`, schema `usability_20261117`, enrichment `6bb71a6`, and already published signed Companion beta.5. Backend/contracts have no diff from the retained API source. No database migration, provider campaign, pricing change or Companion publication is part of this release.

Fresh [backup](evidence/mobile-release/backup.json) is retained privately under `.worktrees/mobile-release/artifacts/mobile-release/`: 537,544,711 bytes, SHA-256 `02484c55eea3c72d1a2ae3cc8670944b87c3fb73f1187f4ae9928b39db3c5346`. A bounded, network-isolated `market_test` restore preserves all 982 original observations, 87 snapshots and 10,163,661 listing rows; [original-column fingerprints](evidence/mobile-release/restore-preservation.json) match. The first isolated fingerprint query exhausted its 5 GiB temporary filesystem while sorting; using the existing ordered indexes completed the identical check without increasing its limits. The isolated database is retired. All previous scheduled archives pass hashes and remain intact. The pre-existing full scheduled-backup budget remains unchanged; no archive was pruned or storage policy expanded. Off-host recovery copies remain unverified.

[Compose preflight](evidence/mobile-release/compose-preflight.json) proves only the `proxy` image changes, and rollback restores its exact prior configuration. New image **sha256:f2c101081b74615f4220062d91975d80d1de2e53c269acfabbba57797e7f13bb**, built from the merged frontend and previous production Caddy runtime. Previous **sha256:197b01f4f4b9e7cf35d574e4c3e6f60f94a462e3dd5b9dccd488fb128d3743d9** remains tagged `twichui-market-web:mobile-rollback-197b01f`.

## Released and verified

**Live at https://market.twich.gg**, deployed **2026-11-17 16:55:15 UTC**. The merge and final integrated application are both **fa089a2660e745d6f77f5c2b0b7bbcb9109d6ae8**. Release evidence lives on `release/mobile-experience-production`; its closing commits change only operational acceptance/docs and the inert public test harness. The deployed application remains the exact verified merge, not a later feature build.

### Exact merged-source CI

| Workflow | Exact result |
|---|---|
| [Backend 44128324202](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44128324202) | Success, attempt 1: **605 PostgreSQL tests**, dependency audit, schema parity, populated preservation and migration/contract/operational checks |
| [Private website 44128324249](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44128324249) | Success, attempt 2: **129 frontend tests**, TypeScript/Vite, dependency audit; **47 Chromium workflows** (including six new responsive workflows), **six Linux WebKit mobile workflows**, one ForeverDB, one provider-rate and five usability workflows: **60 browser workflows total**; existing mocked IPC checks pass |
| [Windows 44128324256](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44128324256) | Success, attempt 1: **98 workspace + one Tauri tests**, two documented ignored checks, native HTTP/PKCE/archive/provisional protocols, actual legacy upgrade and installed UI/uninstall retention; separate signed-update SDK job succeeds |

[Exact CI identities](evidence/mobile-release/integrated-ci.json), [log-derived counts](evidence/mobile-release/test-summary.json). Website attempt 1 passed 46 workflows but a test-side `route.fetch()` handler encountered a disposed Playwright response during teardown. The entire failed job reran with **identical source and assertions**, then passed all ordinary and WebKit workflows plus existing specialist checks. No product code, assertions, retries or thresholds were weakened. Earlier application evidence remains valid because runtime source is unchanged.

### Actual public HTTPS acceptance

[Sanitized receipt](evidence/mobile-release/acceptance.json), [15-scene production gallery](evidence/mobile-release/review.html), [predeployment session continuity](evidence/mobile-release/session-continuity.json), [public asset hashes](evidence/mobile-release/public-assets.json), [desktop/credit comparison](evidence/mobile-release/desktop-and-credits.json), [CSRF/logout](evidence/mobile-release/logout.json).

- Certificate-validated public HTTPS and all **19 served application asset hashes** match the release package. No fixture API responses were substituted. Existing authenticated public session, account ID and exact saved preference values/revision survived proxy replacement.
- Explorer at **320, 344, 360, 375, 390, 430, 600, 768, 1024 and 1440px** has no document overflow. Search and market selector do not overlap. Narrow catalogue uses item records with visible unit prices, reference ranges and current total supply. Compact menu exposes every navigation action and Escape returns focus. URL-selected sorting reflected by the mobile control, actual Linen search, narrow Next/Previous pagination, variant expansion, exact variant Item Details links, chart canvas and browser Back restoration pass.
- Deal Finder, Account/connected devices, Companion and all **nine administration sections** pass 320/344/390/768/1440px containment checks. Real provider settings, budgets and metadata controls render without invoking saves, tests, recovery campaigns, collection or retention. Current dense administration/listing tables retain intentional labelled inner scrolling. Linked provider attribution remains visible and compact.
- Actual pending device-consent screen has reachable **Approve/Deny** at 320px. Acceptance clicked **Deny**, independently confirmed denied state, and admitted no device. Actual approval mechanics remain covered by isolated exact-source Chromium/Windows CI. A first public harness attempt tried reading the decision response after the normal loopback redirect disposed it; the denial itself succeeded. The harness now verifies the public authorization status independently, and the full public checks pass. No product correction or rollback was needed.
- Existing private beta.5 download remains **4,762,861 bytes**, SHA-256 `6124b9472b03c1ee53a83e3a8e7570a9f3621834c77624cd9aa48bc005465de1`. No new Companion was built for distribution or published by this task. Original device/authorization credentials are unchanged.
- Login inputs/submit remain reachable at 320px and anonymous protected requests return 401. The operator's stored bootstrap password was **already rejected before deployment**; no account password was changed. Authenticated checks use a short-lived audited session on the existing owner account. Actual current-password entry remains an owner phone check. Missing-CSRF logout returns 403; valid UI logout succeeds and the same temporary grant then returns 401. Only that grant was revoked; private verification copies were removed.

### Production preservation

[Original-row fingerprints](evidence/mobile-release/preservation-after.json) preserve all **982 baseline observations, 87 snapshots, 10,163,661 listings**, their statistics, original users, all **259 baseline credentials**, preferences, market mappings and retention state. New ordinary scheduled observations may continue. [Runtime comparison](evidence/mobile-release/runtime-after.json) proves only proxy was replaced: API, local API, worker, enrichment, database, monitor and backup IDs/start times, environment hashes, mounts and resource limits remain unchanged. The proxy retains its original listener restrictions, mounts and resource limits.

[Provider guard](evidence/mobile-release/provider-after.json) confirms original enabled/automatic settings, quotas/rate configuration and encrypted credentials match exactly; normal shared usage/accounting is retained, never reset. Existing metadata-priority requests can continue through the unchanged worker; no new manual provider campaign was started. [Original Companion device fingerprints](evidence/mobile-release/devices-after.json) match. [Collection/database receipt](evidence/mobile-release/production-after.json) confirms **house 114 alone / 300 seconds**, a successful scheduled check after deployment, **zero new collection failures** (two older failures remain honestly recorded), schema **usability_20261117**, zero retention batches and no destructive approval. Bridge/pricing contracts and beta.5 distribution remain unchanged. No host, AMP, Traefik, Komodo or unrelated container/network operation occurred.

### Deployment and immediate rollback

Continue using the original project/environment and full existing overlay chain. Append the mobile overlay **last**, and replace **only proxy**. The exact tested commands are reconstructed below; do not run an unscoped `up`, restart workers, downgrade schema or restore the dump over production.

```bash
mobile_release=(
  docker
  --context
  rootless
  compose
  -p
  twichui-market
  --project-directory
  /home/marketdev/projects/TwichUI-Market
  --env-file
  /home/marketdev/projects/TwichUI-Market/.env
  --env-file
  /home/marketdev/projects/TwichUI-Market/.env.combined-release
  -f
  /home/marketdev/projects/TwichUI-Market/compose.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.tls.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.traefik.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.companion-private-beta.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.combined-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.admin-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.explorer-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.polish-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.foreverdb-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/usability-release/compose.usability-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/mobile-release/compose.mobile-release.yaml
)
"${mobile_release[@]}" up -d --no-deps --no-build --pull never --wait proxy
```

For immediate frontend rollback, append `-f /home/marketdev/projects/TwichUI-Market/.worktrees/mobile-release/compose.mobile-rollback.yaml` to the same array, then run `up -d --no-deps --no-build --pull never --wait proxy`. This restores the prior pinned frontend image; APIs/schema/data/Companion stay current. The image is locally retained and rollback configuration was compared byte-for-byte to the prior effective service configuration. An actual production rollback was unnecessary and was not performed.

### Physical-phone checklist and limits

1. Open **https://market.twich.gg** on your iPhone; reload if an old tab retains the previous shell, then sign in with your current password.
2. Open Menu; reach Explorer, Deal Finder, Administration, Account and Companion. Rotate portrait/landscape and try increased text/zoom, notch spacing, browser toolbars and keyboard.
3. Search Linen beside the market selector. Read prices/supply, change sorting, use Next/Previous and expand variants. Open an exact Item Details link, interact with its chart, then use Back.
4. Inspect metadata/provider sections without saving quotas or launching recovery. Check connected devices and the existing beta.5 download/approval screen; approve only a request you initiated.
5. Record device, iOS/browser version, viewport/orientation and a screenshot for any clipping, missing control or awkward touch interaction. Repeat on another phone/tablet if available.

Physical iPhone/Safari, actual touch/keyboard/browser toolbar behavior and owner current-password entry remain **post-deployment acceptance**, not claimed from emulation or Linux WebKit. Existing measured initial layout shift remains a performance limitation; no Core Web Vitals pass is claimed. Dense secondary tables intentionally retain contained scrolling; Explorer does not require a desktop-table swipe. Existing scheduled-backup capacity and off-host recovery limits remain as recorded above. No release-blocking product regression was found. Stop at this completed release; no further milestone, provider investigation, Companion publication or infrastructure work is authorized here.
