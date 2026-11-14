# Forever player-facing market identities — 2026-11-14

**US Normal Horde is house 114 with high mapping confidence.** It is registered as market 2, verified and **disabled**. Only market 1 / house 110 remains scheduled at 300 seconds. Owner confirmation of the collection switch is pending. This finding supersedes the earlier unresolved numeric correspondence; the in-game verification workflow remains available for stronger first-hand evidence.

## Evidence and applicability

Reviewed 2026-11-14, with authenticated US probes at 14:52:39–14:52:50 UTC (07:52 Mountain Standard Time). [Public-source review, exact requests, timestamps, hashes and uncertainty](evidence/forever-us-normal-horde-review.json).

[Saddlebag Exchange](https://saddlebagexchange.com/wow-forever/upload-timers) explicitly labels 110 PvP Alliance, 111 Normal Alliance, 113 PvP Horde, 114 Normal Horde and 116 PvP Neutral. The rendered paginated label rows are EU; its NA overview has the exact same-generation US counts measured directly below. This alone would not prove US routing.

[Forever Mastery's US Normal Horde page](https://forevermastery.com/en/prices/us-normal-horde) describes identifying Normal from an in-game scan and PvP from comparison with KR/TW availability. The original scan receipt is not public. Current prices come mainly from Blizzard, so price agreement independently corroborates the publisher's **market labeling**, not a second independent measurement of prices. Editorial independence between publishers was not established.

Its individual item pages expose both Americas Horde markets at 14:17 UTC, resolving the missing numeric correspondence by exact supply and minimum-price fingerprints. Prices below are copper per unit. Each API observation matches the corresponding publisher observation on both fields:

| Item/source | Normal Horde / API 114: supply, minimum | PvP Horde / API 113: supply, minimum |
|---|---:|---:|
| [Linen Cloth 2589](https://forevermastery.com/en/items/2589-linen-cloth) | 20,848; 21 | 8,736; 21 |
| [Wool Cloth 2592](https://forevermastery.com/en/items/2592-wool-cloth) | 6,553; 145 | 6,940; 129 |
| [Light Leather 2318](https://forevermastery.com/en/items/2318-light-leather) | 13,989; 28 | 9,963; 48 |
| [Copper Ore 2770](https://forevermastery.com/en/items/2770-copper-ore) | 6,077; 117 | 1,738; 194 |

The main [PvP Horde page](https://forevermastery.com/en/prices/us-pvp-horde) was one generation older (13:17 UTC); its figures were excluded from same-generation matching. A trailing-slash research result was even older and also excluded. Commodity endpoints supply the four stackable-item fingerprints; these are read-only evidence, not additional configured feeds.

## Direct authenticated US evidence

All six fresh requests returned HTTP 200, `Battlenet-Namespace: dynamic-forever-us`, and Last-Modified `Sat, 14 Nov 2026 14:17:45 GMT`.

| House | Auction listings | Commodity listings | Auction-array SHA-256 |
|---|---:|---:|---|
| 113 | 95,545 | 73,420 | `fb2e9c92fcd2d4af50137961b9058911724c9d75caca6a74e69a1b47d25aa749` |
| 114 | 89,533 | 64,041 | `7452c6d389b9e782be5e2bf85043a925b11c3085d7ab3000d549bd36ead0994f` |

The auction ID sets have zero overlap. For **each** house, ruleset URL 1 and 2 return identical auction arrays. Embedded ruleset links echo the requested URL. These links establish transport only; they are not proof of PvP/Normal identity. Fresh index membership, house identity and successful normalization were separately checked by the existing verifier when creating live receipt 2 at 14:58 UTC.

## Client ruleset semantics

[Daybreak's extracted client evidence](https://daybreakforever.com/discoveries/systems), reported build `1.60.1.70888`, distinguishes `AvailableSuperDistrict.ID` from its `SuperDistrictID`: picker row **2** is **PvP**, pointing to district 1; row **3** is **Normal**, pointing to district 2. API ruleset IDs are 1 PvP and 2 Normal. Treating a redirect selector of 2 as API Normal would reverse this evidence.

Published `AuctionHouseRedirect` rows route source house 2 with selector 2 to 110 and selector 3 to 111. This supports the Saddlebag Alliance labels when interpreted through picker row IDs. It is a supported interpretation, not a proven foreign key. The published Horde examples have target 0, so they do not independently prove 113/114. The [schema definition](https://raw.githubusercontent.com/wowdev/WoWDBDefs/master/definitions/AuctionHouseRedirect.dbd) has **four unnamed integer fields**, including a fourth house reference; do not reduce it to a complete three-column routing rule. [AvailableSuperDistrict's schema](https://raw.githubusercontent.com/wowdev/WoWDBDefs/master/definitions/AvailableSuperDistrict.dbd) confirms the separate identifiers.

The rendered research page omits expandable table evidence; the publisher's indexed excerpts expose the cited rows. Direct Wago CSV retrieval was inaccessible, and no local client extraction or first-hand live routing was obtained. The beta data also includes Hardcore and other historical groups; no RP/RPPvP assignment follows from it. Client data is corroboration only. No access restrictions, DNS, SSH, proxy, firewall or host settings were changed.

## Registration and switch gate

[Registration receipt](evidence/forever-us-normal-horde-registration.json): market 2, mapping 1, live verification 2, actor owner. The reviewed research file hash is `e1ec0c93d2efc1e5bf96b7dfa353f92ca985c1dcdac1bca5548b040999aa3a37`; the database registry hash is `9b638e0a304e77792d053750d8a2a20e70712a7ea92cb73bea724ba0ac800e2b`. Confidence is stored as `verified` for the existing registry gate; underlying research confidence is **high, corroborated, not first-hand in-game certainty**.

The privileged registration command validates the exact reviewed file, scope, freshness and four paired observations, performs fresh authenticated verification itself, refuses an upstream generation change or duplicate/alias destination, then atomically adds the disabled destination, registry, live receipt and audit events. It cannot activate any market. All previous 141 observations and 13 snapshots were compared before/after and remained identical, with identical hashes. No old history is relabeled as Normal Horde.

[Prepared atomic transition](evidence/forever-us-normal-horde-transition.json) names market 1 → market 2 and the existing authenticated `/api/v1/admin/market-transition` request. It requires explicit owner confirmation, fresh intact receipts and no third active feed. The existing transaction locks serialize it with collection; it disables 110 and enables only 114 at 300 seconds in one commit. All prior market history remains under house 110. No commodity, PvP, regional or duplicate feed is configured. No transition has been executed.

Reproduce read-only API comparison in the bounded worker environment:

```sh
docker --context rootless compose -f compose.yaml -f compose.tls.yaml run --rm -T --no-deps worker python - < scripts/research-forever-horde.py
```

The registration is already applied; do not rerun it to activate collection. After owner confirmation, recheck the prepared transition and latest database state. Refresh an expired upstream receipt using `python -m market.verification` before switching. Retain the wizard for a character-associated auction/listing match if stronger evidence is desired; this research does not claim that in-game step occurred.
