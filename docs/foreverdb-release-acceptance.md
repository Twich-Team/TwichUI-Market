# ForeverDB metadata production acceptance — 2026-11-16

The owner-authorized implementation is merged in [PR #14](https://github.com/Twich-Team/TwichUI-Market/pull/14) and deployed at **https://market.twich.gg**, exact application/merge commit **`6bb71a61fa3493da3f418288c3af1841fabfb0fc`**, schema **`fdb_20261116`**. API, local API, frontend and metadata worker use the verified release images. The collector, database, monitor and backup services retain their original container identities, images, starts and settings.

**External account gate remains:** the public ownership proof is ready, but ForeverDB's account-side website verification and the configured key's Website purpose have not been confirmed. No authorized signed-in ForeverDB account browser was available. Open [ForeverDB Developers](https://foreverdb.net/developers), confirm the key is a **Website** key for `https://market.twich.gg`, and click **Verify** for that website. Developer ID is `dev-0255`. A plugin/personal key requires the provider's proper website-key issuance process; do not bypass its restrictions. API success and `meta.client` are not verification of either key scope or account status.

[Sanitized machine acceptance](evidence/foreverdb/production-acceptance.json), [seven-scene genuine production gallery](evidence/foreverdb/review.html), [verified capability/coverage inventory](foreverdb-capabilities.md), [captured property/type inventory](evidence/foreverdb/capabilities.json).

## Root cause, mapping and source compatibility

The HTTP adapter already called `/api/v1/items/{id}`. `parse_foreverdb()` intentionally constructed only `{'name': ...}` from its response. The catalog whitelist also lacked structured relationships. Production's initial 496 available ForeverDB records retained names/build hashes but discarded richer response fields; this was not a list-versus-detail or provider-availability failure.

The new adapter uses ForeverDB's actual camelCase schema. It preserves quality, category labels/IDs, levels, bonding, uniqueness, exact integer copper sell value, signed stat IDs/labels/values, weapon damage and speed in seconds, effect triggers/text/spell IDs, and source-qualified disenchant data. Original item records are retained once in versioned source evidence; raw records are excluded from every individual field origin to avoid multiplying their storage. Unknown optional fields remain in source evidence. Null/absent fields and empty partial arrays do not erase previously valid metadata.

Existing field precedence stays Blizzard → Everloot → ForeverDB → TheWoWDB. Alternate values and source versions remain available; a provider's omitted field cannot replace richer known data. TheWoWDB's live item-25 detail path returned 200, parsed and persisted successfully after deployment, retaining its `wow_classic_beta-1.60.1.70532` identity and attribution. Its existing parser remains unchanged. The comparison in the capability inventory describes tested adapter coverage, not an assertion that untested provider fields are unavailable.

Each new source retains provider/resource identity, game edition, exact client build, retrieval timestamp, payload hash, attribution and field origins. Core item build identity is separate from related-resource build identity: a newer recipe/vendor response cannot silently renew older item stats. Historical/speculative/beta qualifiers stay with fields, and mixed retained ForeverDB builds receive a visible notice. Actual `dataFromBuild`/`liveClient` item examples were not returned in this bounded campaign; their defensive tests are explicitly synthetic and do not establish live current-field coverage.

## Official capabilities investigated

Twenty-three authenticated successful capability responses cover `/api/v1/meta`, item list and eight item-detail examples, spell list/detail, profession list/detail (including a second page), vendor list/detail, item-set list/detail, disenchant tables, build list/latest detail, mining gathering and changes-seen. Each call used existing server-side encrypted credentials, a descriptive application User-Agent and persistent shared reservations. Complete observed property paths/types and nullable examples are linked above; list pagination is `meta.total/limit/offset/next`.

Current sampled Forever client identity is **`1.60.1.70938`**. Item stats, effects, damage, speed, categories, prices and Classic-reference disenchant results are directly sample-confirmed. Profession recipes retain reagents/quantities, output count or random min/max, skill colors and source, category, learning sources, hidden-recipe qualifiers and Forever changes. Vendor offers retain purchase prices/stacks, limited stock, reputation, location and source evidence; copper display uses exact strings. Sets retain pieces, bonuses and availability warnings.

Spells improve item effects through exact spell references and source links. Bounded profession/vendor/set imports project directly onto related item records; raw resource caches retain ranks/trainers and the complete returned source structure. These are explicit administrator jobs, 1–10 reserved requests, 20 recipes per page, with no arbitrary endpoint/next-URL following. No general quest planner, spell encyclopedia, gathering-location database or whole-build crawler was introduced.

## Real production enrichment and completeness

All eleven acceptance jobs completed with one request each: eight item details (`25`, `19019`, `2589`, `8188`, `2235`, `10098`, `2553`, `4306`), one Alchemy page, vendor `54` and set `1`. All returned **HTTP 200** and persisted. Alchemy's 20 recipes produced **45 related item records**; the vendor produced **8**, and the set **6** (resource record counts can overlap and are not a sum of unique items).

The eight-item target set went from **zero detailed ForeverDB records to eight**. Two targets previously had ForeverDB names; six had no ForeverDB source fields. This includes equipment, stats/effects, materials, a recipe and Classic-qualified disenchant data. A real 1,400-byte WebP icon was downloaded and validated through the shared ForeverDB budget without forwarding any credential or replacing existing artwork.

The before/after comparison pins the **same 5,076 observed item IDs from snapshot 53**, rather than changing the denominator during collection:

| Retained ForeverDB field | Before | After |
|---|---:|---:|
| Names | 486 | 488 |
| Core quality / levels / categories | 0 | 4 |
| Structured stats / weapon facts | 0 | 2 |
| Binding / disenchant reference | 0 | 3 |
| Effects | 0 | 1 |
| Crafting relationships | 0 | 8 |
| Vendor relationships | 0 | 5 |

Administration reports **484 name-only and 16 detailed-or-related ForeverDB records** in that observed population. Four are core item details; relationship-only records count separately from complete base-item metadata. The eight-item target set includes items outside that snapshot, so its eight detailed records must not be confused with four current-snapshot core details. No full-catalog enrichment or overall market-name coverage improvement beyond these measurements is claimed.

Real public-browser verification confirms Explorer search/navigation, item detail stats/damage/speed/vendor sell, visibly Classic-qualified disenchant references, crafting/vendor/set presentation, source attribution, mobile width, administration and unchanged owner preferences. Browser JavaScript errors and direct browser requests to provider APIs were both zero. The original auction history, prices, supply and bridge generation behavior were not changed.

## Quotas, recovery and credentials

The owner explicitly authorized a temporary bounded exception after the original application budget was exhausted. The initial allowance was 500→540/day; actual use was **35 ForeverDB reserved attempts** (23 authenticated research + 11 authenticated production API calls + one conservatively charged public icon). One separate TheWoWDB request used its own unchanged pool. All calls use the shared reservation/pacing/cooldown system; concurrency remains one. No catalog crawl ran.

Original settings are restored exactly: **150/hour, 500/day, 30/minute, minimum 3 seconds**, automatic/enabled state unchanged. Credentials, key IDs, validation/expiry, other provider grants and full configuration fingerprints match before deployment. Usage was not reset: 535 reserved attempts remain conservatively charged, estimated remaining allowance is zero, and the recorded next eligibility is `2026-11-16T21:51:43.401674+00:00`. Actual account plan, other-key usage and provider-side remaining quotas remain unknown; successful requests do not prove a paid entitlement.

Name-only/outdated source mappings, viewed observed items and newly observed build identities become eligible through existing recovery. Related cache/job identities survive restarts. HTTP 401/402/403/404/429/5xx retain different outcomes; authorization/subscription/forbidden failures stop automatic attempts pending administrator validation, missing results complete with a negative cache, and temporary failures obey bounded attempts/campaign budgets and Retry-After. Failed refreshes retain good data. Existing pending jobs and usage survive the release.

No API secret enters source, screenshots, fixtures, logs, browser assets, desktop or addon. Exact release-bundle and source-diff scans against all current encrypted provider credentials passed without emitting values. A temporary acceptance browser session was revoked, verified to return 401, and its private local token file removed. Existing credentials were not rotated.

## Website ownership and attribution

`GET https://market.twich.gg/.well-known/foreverdb.txt` returns **200**, `text/plain; charset=utf-8`, exactly **8 UTF-8 bytes: `dev-0255`**. Public HTTPS requests and a fresh unauthenticated browser context both passed, with redirects disabled. This is the actual production asset, served through an explicit static route without SPA fallback or authentication. Only the file method is implemented.

Visible ForeverDB.net links remain next to Explorer identities and item facts wherever its data contributes; TheWoWDB credits remain. Account-side **Verify is not confirmed**. The owner action in the opening paragraph is required before calling website verification complete. The API does not expose a sampled website-verification or key-purpose status; administration truthfully shows unknown/manual confirmation.

## Verification, schema and backup

Exact merged-source CI passed:

- [Backend 43812904753](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43812904753): **575 PostgreSQL tests**, **39 operational checks**, dependency audit, upgrade/check/downgrade/re-upgrade and metadata/provider/ForeverDB/Companion migration verification.
- [Website 43812904735](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43812904735): **123 unit tests**, TypeScript/Vite build, dependency audit, **41 ordinary + one ForeverDB + one provider-rate Chromium workflows**. Fixture mobile/axe checks passed with zero violations; fixture observations exist only in isolated `market_test`.
- [Windows 43812904734](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43812904734): native compatibility, HTTP/authentication, install/upgrade and actual signed SDK lifecycle checks. No new desktop release was published. Existing beta.3 exact download SHA-256 remains `d31efbb8a6611cad107f8b368eb8c16585125e269fae180bfabdd9ae6c287183`.

The additive migration adds a nullable task resource and bounded related-response cache. Production advanced only `rates_20261115 → fdb_20261116`, with unchanged original provider columns and a clean Alembic check. All original-column market/provider/credential/counter/job/source fingerprints survived actual isolated restore and upgrade/check/downgrade/re-upgrade. Populated resource/cache downgrade is refused. Fourteen selected item/cache field hashes remained identical across a production API restart; subsequent real HTTPS item-profile and legacy sync-cursor reads passed.

Fresh production archive: `market-development-20261116T053407650838Z.dump`, **329,130,127 bytes**, SHA-256 **`0cde5d55eb4596d7d33bcd5ea284b31030ebfb49200a19cc723c8b52c4a3d254`**. Actual restoration verified at **2026-11-16 05:38:06 UTC** into isolated `market_restore`: **593 observations, 6,238,090 listings, zero synthetic observations**, all constraints restored. Existing encrypted keyring backup was decrypted in memory and compared with the current runtime keyring; both protected provider envelopes also decrypted in the restored-schema rehearsal. No plaintext key file was created and no secret was rotated. An off-host copy remains unverified.

All pre-existing original-row fingerprints remain identical after deployment, including accounts, original credentials, preferences, original auction observations/listings/statistics, verification mappings and retention policy. Final smoke recorded **600 observations**, **6,238,090 listings**, zero synthetic observations, zero retention batches. House **114 alone**, **300 seconds**, **zero failures**; scheduled HTTP 304 checks continued through and after deployment. No collector, pricing, scoped bridge, bridge-v1, addon, automatic delivery/reload or M2 change was made.

All 28 previous archives were preserved alongside the new archive, within the existing 3 GiB budget. Only about **64 MiB archive headroom** remains, insufficient for another comparable dump. Review/offload archives through the owner's normal backup process; this release changes neither retention nor budget. Resource samples and all application containers show no OOM; point-in-time samples are not peak guarantees. Isolated test/restore containers and networks are retired.

## Current deployment and rollback

[Release image pins](../compose.foreverdb-release.yaml), [immediate predecessor rollback pins](../compose.foreverdb-rollback.yaml). The tracked-only command below was compared against the actual full predecessor-overlay command and produces identical service configurations. Existing untracked M1.5/provider-repair overlays remain untouched and are not needed by this portable command.

```bash
market_release=(docker --context rootless compose -p twichui-market
  --env-file .env --env-file .env.combined-release
  -f compose.yaml -f compose.tls.yaml -f compose.traefik.yaml
  -f compose.companion-private-beta.yaml -f compose.combined-release.yaml
  -f compose.admin-release.yaml -f compose.explorer-release.yaml
  -f compose.polish-release.yaml -f compose.foreverdb-release.yaml)
"${market_release[@]}" --profile metadata up -d --no-deps --wait api local-api proxy enrichment
```

Before a future rollback, pause active related jobs through authenticated administration and stop only metadata enrichment. Keep `fdb_20261116`, the cache, source versions, queued tasks, quota history and all auction data. Append the rollback overlay last:

```bash
"${market_release[@]}" --profile metadata stop -t 45 enrichment
"${market_release[@]}" -f compose.foreverdb-rollback.yaml \
  up -d --no-deps --wait api local-api proxy
```

This restores the predecessor application source `73617a9` while leaving the collector/database/monitor/backup alone. Keep enrichment drained until a compatible forward worker is restored or related-job compatibility is reviewed; the predecessor worker does not understand new related tasks. Do not downgrade populated schema, clear metadata, restore over production, change quotas/credentials, or prune historical observations to facilitate rollback.

## Unsupported, unverified and follow-up work

Armor values, richer equip requirements and appearance/display IDs were not returned in sampled item detail records and are not guessed. `liveClient`/retained-build item examples and alternate-currency/extra reputation conditions were not live-confirmed in the selected items/vendor; original optional data is preserved where returned, with no fabricated units/probabilities. No player-observed Forever disenchant bucket was returned in the sampled table; Classic reference chances must not become verified Forever yields.

Future work can use explicit budgeted profession pages and targeted item recovery, add a verified observed-disenchant fixture when genuinely available, and evaluate gathering or broader build-change discovery only when an existing Market consumer warrants that architecture. Increase application allowances only from the owner's actual provider grant. Confirm the Website key scope and complete ForeverDB's account Verify action first; no further manual provider campaign, desktop release, pricing/bridge activation or infrastructure change is authorized by this acceptance record.
