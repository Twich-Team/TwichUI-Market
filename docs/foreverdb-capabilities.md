# ForeverDB capability and coverage inventory

Evidence date: 2026-11-16 UTC. Primary source: [official live developer documentation](https://foreverdb.net/developers), successfully retrieved by project-host HTTPS. Twenty-three authenticated successful samples were captured through shared persistent reservations after the owner authorized a bounded temporary application-budget exception. Fixtures retain attribution and provider watermark text; the secret never enters evidence. The documentation is descriptive rather than a complete typed schema.

All endpoints below are documented read-only GET under `https://foreverdb.net`. Responses have `data` and `meta`; `meta` carries build identity and `meta.client` the approved developer ID. Lists carry total/next-page metadata; precise key names/types and nullable detail shapes are captured in the fixture-backed inventory below. Query pagination uses integer `limit` 1–100 (default 25), integer `offset`, except unpaginated resources noted below. Never follow arbitrary response URLs. Treat each HTTP call, including diagnostics and related resources, as one shared reserved attempt; documentation does not describe differentiated endpoint costs.

| Resource | Documented endpoint(s) | Documented fields/concepts and qualifiers | Pagination/filter | Market relevance / implementation |
|---|---|---|---|---|
| Data identity | `/api/v1/meta` | Client build, level cap, resource counts. Complete schema unknown. | None documented | Validate identity; expose observed build, never infer key scope/plan/verification |
| Items | `/api/v1/items`, `/api/v1/items/{id}` | List identity/name; detail stats, damage, speed, binding, sell price, effects, `disenchant`. `betaEvent`, `speculation`, `speculationReasons` on both. `liveClient` field beta/live changes; `dataFromBuild` retained older record. | q, quality 0–5, class, slot, minLevel, maxLevel; limit/offset | Detail-first for observed/requested IDs; no full crawl. Exact mappings gated on samples |
| Spells | `/api/v1/spells`, `/api/v1/spells/{id}` | Name/rank/description/icon/school/cast time/range/cooldown/required level/base costs. `liveClient` added/removed/changed, beta/live values | q; limit/offset | Direct item-effect references only; no spell encyclopedia |
| Professions | `/api/v1/professions`, `/api/v1/professions/{slug}` | Twelve identities; counts, ranks/caps, trainers, recipes, reagents, outputs `count`/`min`/`max`; skill orange/yellow/green/grey; `skill.orangeSource`, `orangeClassic`; `learnedFrom.sources`, category/parent, `trainerCostSource`, `recipeItemsHidden` / legacy alias `recipeItemsNotInClient`; Forever changes | Detail q/new/changed; limit/offset. List no pagination documented | Related recipe inputs/output acquisition; no Workshop pricing/formula changes |
| Vendors | `/api/v1/vendors`, `/api/v1/vendors/{id}` | Locations; `reputationFaction` controls discounts; details sold items, copper prices and `costs` currencies/items; Classic vs seen-in-Forever | q/zone/seen; limit/offset | Direct acquisition, preserve stock/cost/source semantics; never AH price |
| Disenchant | `/api/v1/disenchant` plus item detail `disenchant` | Uncommon/rare/epic weapons/armor by item level; player-observed Forever results with observation/player counts, separate Classic table | None documented | Preserve distinct populations; no fabricated yield probabilities |
| Sets | `/api/v1/itemsets`, `/api/v1/itemsets/{id}` | Pieces; detail bonuses; `betaEvent`, `speculation`, `speculationReasons` | q; limit/offset | Direct item membership/bonuses if references are present |
| Builds | `/api/v1/builds`, `/api/v1/builds/{build}` (`latest` allowed) | Dates/previous build/resource totals and counts; added/removed/changed rows with before/after; `dataOnly` distinguishes invisible data changes | type/class/change/q; limit/offset | Build provenance and targeted future invalidation; no per-cycle all-record refresh |
| Gathering | `/api/v1/gathering/{slug}` | herbalism/mining nodes/skill/zones/counts; skinning beasts/outputs; fishing skill/catches/pools. Spawn counts Classic until observed Forever | zone ID/name; no pagination documented | Follow-up: substantial location model beyond existing item details |
| Changes seen | `/api/v1/changes-seen` | Item/NPC/vendor/trainer/quest differences, Verified (2+ players or client check) vs Not confirmed; counts, no identities | kind/verified; limit/offset | Direct item uncertainty; no automatic override without source evidence |
| Quests | `/api/v1/quests`, `/api/v1/quests/{id}` | Levels/side/zone; starts/ends type/id/name/location/map percentages/instance/source; previous/next/questLine; player vs Classic evidence | q/zone/minLevel/maxLevel/side; limit/offset | Recipe acquisition references only; no quest planner |
| Dungeons | `/api/v1/dungeons`, `/api/v1/dungeons/{id}` | Levels; detail bosses/notable loot | limit/offset | Acquisition follow-up only |
| Other | `/api/v1/zones`, `/api/v1/classes`, `/api/v1/classes/{name}`, `/api/v1/poisons`, `/api/v1/battlegrounds`, `/api/v1/buffs-nerfs`, `/api/v1/merchants-favor`, `/api/v1/articles`, `/api/v1/articles/{slug}`, `/api/v1/posts` | Public docs cover these separately; not required for core item ingestion | Endpoint-specific; no probes/crawls planned | Out of scope except direct recipe/item currency references |

Optional/null fields remain unknown until observed. Absence of a field in one sample is not evidence of global unavailability. Build validation must enforce Forever's exact 1.60 family and retain older `dataFromBuild` identity rather than silently labelling retained fields current.

## Authentication, quotas and use

Official docs allow `X-API-Key` or `Authorization: Bearer`, require descriptive server User-Agent (Cloudflare can reject default urllib with 403/1010), and aggregate all keys per account. Free 5,000/day, 30/minute; paid 10,000/day, 60/minute. Daily accounting is UTC. The docs describe both 402 `subscription_required` and 429 with Retry-After; preserve their different meanings. Account deletion/suspension invalidates keys. Existing application limits remain authoritative if tighter.

Website keys are for one owned verified website; plugin/personal keys cannot serve websites. Keys must stay server-side and must not ship in desktop/addon/browser artifacts. A successful API call alone does not prove correct key scope. Account plan, other-key usage, website-key scope and provider website verification status are currently unknown unless observed in an authorized account workflow or returned explicitly by the API.

Visible credit/link to ForeverDB.net is required wherever free-tier data appears; retain attribution even when paid plan status is unknown. No resale or claim of ownership; Blizzard client, player observations and Classic-derived data remain distinguished. Provider notes response watermarking and 90-day aggregate endpoint/resource/client-family/country/origin usage logs; do not strip attribution or republish the entire API as an unrelated service.

## Existing application coverage, before change

`D` = documented by ForeverDB; `A` = confirmed authenticated current response; `I/S/V` = ingested/stored/visible. `pending` is an evidence gate, not an unsupported-field claim.

| Field | ForeverDB docs | ForeverDB A | ForeverDB I/S/V before | TheWoWDB existing mapping |
|---|---|---|---|---|
| Name | D | Persisted name/build provenance; raw sample pending | yes/yes/yes | name; sample-backed |
| Quality | List filter and rich item concept; exact property pending | pending | no/no/no | quality enum; sample-backed |
| Class/subclass, inventory slot | List class/slot filters; detail schema pending | pending | no/no/no | slot/item_subtype display lines |
| Required level, item level | Required-level list filters; detail schema pending | pending | no/no/no | required_level/item_level |
| Equip requirements | Exact schema pending | pending | no/no/no | verified non-null detail fields only |
| Damage/speed, armor | Damage/speed documented; armor exact schema pending | pending | no/no/no | only fields represented by existing community parser |
| Stats | D | pending | no/no/no | stats label/value converted to lines |
| Binding | D | pending | no/no/no | binding |
| Vendor sell copper | D | pending | no/no/no | vendor_sell as exact copper string |
| Effects/spell references | D | pending | no/no/no | current community parser coverage only |
| Sets | Separate endpoint D | pending | no/no/no | no structured set mapping |
| Icon/appearance references | Spell icon D; item schema pending | pending | no/no/no | allowlisted attributed icon via local media |
| Disenchant | D, Classic vs observed Forever | pending | no/no/no | no structured mapping |
| Recipes/reagents/output quantities | Profession detail D | pending | no/no/no | no structured mapping |
| Vendor/trainer/quest/drop acquisition | Profession/vendor detail D | pending | no/no/no | no structured mapping |
| Availability qualifiers | D | pending | no/no/no | community-beta warning |
| Game build | D | Persisted 1.60.1.70938 source identity | yes/yes/yes | exact wow_classic_beta-1.60.1.70532 sample identity |

Root cause: HTTP detail selection is already correct; `parse_foreverdb` discards every item field except `name`. Catalog's supported-field set lacks structured relationships; existing frontend displays only selected attributes and tooltip lines. Source precedence is field-level and non-destructive, so it can preserve TheWoWDB/Blizzard fields when ForeverDB omits them. No new source ranking is justified merely by richer API responses.

## Authenticated capabilities and implemented coverage

[Captured schema/type inventory](evidence/foreverdb/capabilities.json) links each documented route to its actual successful sample, response field paths/types, meta pagination and build. Sanitized successful response fixtures are in `backend/tests/fixtures/foreverdb`; error/old-build tests are explicitly synthetic mutations. No live armor, equip-requirement, appearance, liveClient or dataFromBuild example was observed in this bounded set; these fields are not declared globally unavailable. Optional unknown fields remain in the original record/resource evidence.

| Field | Authenticated sample | New ingestion/storage | Existing application presentation |
|---|---|---|---|
| Name / quality | id/name/quality/qualityId | Name, enum quality and exact category ID | Existing Explorer identity/colors and facts |
| Categories / slot | class/classId/subclass/subclassId/inventoryType/inventoryTypeId | Labels plus integer category_ids | Type/subtype/slot, exact IDs in source evidence |
| Levels | itemLevel/requiredLevel integer, including zero | level/required_level; null omitted | Item Level / Requires Level |
| Weapon | damage.min/max/school, speed | weapon; speed_seconds and decimal number strings | Damage and speed in seconds |
| Attributes | stats[].statId/stat/value integers | stats with exact IDs/labels/signed values | Signed stat values; existing primary stat lines take display priority |
| Binding / uniqueness | bonding nullable, unique boolean | binding and unique | Binding and Unique |
| Vendor sell | sellPrice integer | vendor_sell exact copper string | Explicit vendor sell label/currency, never AH pricing |
| Effects | trigger/triggerId/spellId/text, including empty text | effects, exact spell identity and original text | Trigger/text or unavailable description, fixed ForeverDB spell link |
| Disenchant | disenchantable boolean; disenchant.source/skill/results or null | Separate qualified structured data; original numeric chances retained | Classic/reference warning, ranges and reference chances; no guaranteed yields |
| Availability | betaEvent/speculation/speculationReasons | availability and field-source qualifiers | Visible warnings; earlier-build field provenance stays visible after partial refresh |
| Retained/live-client details | Documented; not returned in sampled items | Retained build accepted only as validated Forever identity; structured live changes retained; tests are synthetic | Historical/source-qualified notice and expandable changes |
| Artwork | exact https://foreverdb.net/icons/{integer}.webp | Allowlisted source reference; bounded locally cached WebP fallback, no credential forwarded; original Blizzard/TheWoWDB preference retained | Existing private local icon surface and source credit |
| Crafting | profession slug/name/kind/ranks/trainers/recipes; recipes spellId/name/skill/makes/reagents/learnedFrom/changes | Bounded cached profession pages; per-item crafting relationships on outputs, reagents and recipe items; exact quantities and original learning sources retained | Crafting detail, quantities, skill colors/source, learning sources and uncertainty |
| Vendors | id/location/reputationFaction/source/seenInForever and sells | Item relationships retain offer price/stack/limited/source; price_copper string for exact display; full costs and location evidence | Purchase-price label, stock/reputation, source-qualified acquisition |
| Sets | id/name/items/bonuses and availability | Per-piece item_sets relationship and source | Set name/bonuses/qualifiers |
| Build | meta.build = 1.60.1.70938; build list/detail sampled | Every source/resource retains current build; older field origins survive partial records. New observed builds make older available details eligible under existing quotas | Field provenance, build coverage and retained-field notices |

Related imports are explicit bounded administrator jobs (1–10 requests, 20 recipes/page). They reuse durable task leases, quota reservations, cooldowns, Retry-After and caches. No unrelated encyclopedia, pricing formula, bridge contract or unrestricted catalog backfill is introduced. Individual spell text/identity already enriches item effects; a separate spell encyclopedia/cache is unnecessary. Gathering/build-change discovery is sampled and documented; bulk location and whole-build invalidation feeds remain follow-ups.

Actual provider plan, key type, other-key account consumption and website verification state are not exposed by sampled meta. API `meta.client=dev-0255` confirms developer identity only. Application diagnostics show explicit unknown/manual-account verification, never a fabricated verified badge. The owner has not yet confirmed key type or an authenticated browser session.
