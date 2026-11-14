# Approved US Normal Horde collection switch — 2026-11-14

The owner explicitly approved replacing US house 110 with verified US Normal — Horde house 114 / market 2 at a five-minute interval, preserving history, receipts and backups. The existing audited transition handler executed at **15:15:50 UTC / 08:15:50 MST**, as the active owner through the privileged operator boundary. Security event **233**, `market.transition.confirmed`, records `from=1 to=2`. No direct schedule SQL or additional feed activation was used.

[Full acceptance evidence](evidence/forever-us-normal-horde-switch.json) includes CI results, backup manifest/restoration, transaction output, exact history fingerprints, collection runs, browser observations and resource samples. The [original plan](evidence/forever-us-normal-horde-transition.json) is marked executed while preserving its pre-switch proposal entries. [Mapping research and uncertainty](market-identity-findings.md) remain separate from operational acceptance.

## Prerequisites satisfied before execution

The then-latest clean commit, **85e74a8ff32442de67761fa9f93857a9679d77a1**, passed all three required CI workflows:

- [Backend 43607856297](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43607856297).
- [Private website 43607856227](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43607856227).
- [Windows companion 43607856252](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43607856252).

Fresh backup `market-development-20261114T151409719774Z.dump` completed at 15:14:16 UTC, SHA-256 `564bdfbd736f5570da43f96dde25515ea5aae88fd1ec8cb4ea0adf01614dfbd5`, 77,159,054 bytes. Checksum/size validation and isolated `market_restore` restoration passed at 15:14:29 UTC, before switching. Restored schema 0011 includes both configured markets, both verification receipts, 144 observations, 1,324,933 listings and 320,105 statistics, with zero synthetic observations. The current backup gate was true at execution. Backup rotation was avoided; all seven previous development archives and all other existing archives remain present. All **14** resulting project archives pass their recorded checksums. The restore database was removed afterward; production was never overwritten.

## Live acceptance

| Requirement | Observed result |
|---|---|
| Exactly one enabled collector | Market 2, US Normal — Horde, house 114 auctions; verified identity and feed; interval 300 seconds |
| Previous market disabled with history intact | House 110 / market 1 disabled; exact fingerprints unchanged immediately and after the next collection |
| First genuine snapshot | Observation 146 / snapshot 14: 89,533 physical listings, 8,668,422 response bytes, HTTP 200, synthetic false; nine-second ingestion |
| Next scheduled collection | Observation 147 / snapshot 15: 89,692 physical listings, 8,637,901 response bytes, HTTP 200; nine seconds; new upstream generation at 15:17:46 UTC |
| Market Explorer | Production localhost:18443 and read-only preview localhost:18444 show selected US Normal — Horde with real item, supply, prices, listings and history; trusted TLS; no page errors |
| Collection health | Both runs successful; zero market failures; no collector restart or OOM; original 384 MiB / 0.5 CPU caps retained |
| Database/storage | Allocation 468,571,827 → 529,323,699 bytes; total growth 60,751,872 bytes including concurrent background work; 9.86% of the configured 5 GiB limit; over 20 billion filesystem bytes free |
| Isolation | Original project container identities/images/start times/restart counts unchanged; host listening ports unchanged; no AMP, unrelated container, host networking, firewall, SSH or proxy operations |

The two checks began at 15:15:53 and 15:21:04 UTC. The 300-second schedule plus worker polling accounts for the observed 311.5-second spacing. No house 110 observation or collection run was added after disabling it. No commodities, other region, PvP market, extra worker or duplicate feed was activated.

Exact whole-row COPY/SHA-256 fingerprints cover **145 old observations, 13 old snapshots, 1,324,933 old listings, 320,105 old statistics, one daily reference, both verification receipts and the registered identity**. They match before/after the transition and at the final check. No previous history was renamed or attributed to house 114. Historical retention batch count remains zero, and no historical policy was authorized.

Browser evidence uses an item actually present in house 114, Bent Staff (35), preserving its exact variant. After the second generation, both interfaces show **9 units / 9 listings / recent price 427 copper**, matching snapshot 15's listing IDs, quantities and rounded 3,847-copper buyout total. House 110 remains independently queryable. Screenshots were visually inspected; preview charts finished rendering. Temporary members were disabled and their sessions revoked; owner credentials were not changed.

## Resource evidence and limits

After two collections, worker memory is about 124 MiB, with a measured lifetime peak **222 MiB / 384 MiB**, zero cgroup limit events and zero OOMs. API is about 103 MiB / 384 MiB; database current usage is about 612 MiB / 768 MiB. Database lifetime peak is 805,326,848 bytes, including a 20 KiB kernel accounting overshoot above its 805,306,368-byte limit; limit/reclaim events are recorded, with zero OOMs or restarts. No limit was raised. These are bounded observations across two cycles, not a long-run capacity guarantee. AMP isolation is established by operation scope and unchanged listeners; no gameplay health probe was performed.

Reproduce the browser check with `python3 scripts/verify-live-market.py --script verify-market-switch-browser.cjs`. It uses the existing audited temporary-member lifecycle and trusts the project CA only inside its disposable browser. Screenshots remain in ignored `artifacts/market-switch/production-normal-horde.png` and `preview-normal-horde.png`; public JSON acceptance is committed. The first verifier attempts caught an old-market item assumption and a lazy-chart timing race; the final verifier uses actual destination listings and waits for rendered charts.

Production frontend assets, existing services, backups and historical data were retained. No frontend promotion or retention change was part of this approval. The collection switch is complete.

## Follow-up verification at 16:16 UTC

The repeated owner instruction was reconciled against the existing transition audit before any schedule mutation. Event 233 remains the only `market.transition.confirmed` event; the completed transition was not replayed. [Fresh acceptance evidence](evidence/forever-us-normal-horde-recheck.json) records the current database, browser, backup and resource checks.

- Market 2 / US Normal — Horde / house 114 remains the only enabled collector at 300 seconds. House 110 remains disabled, with no post-switch observations.
- All 12 destination collection checks through 16:11:37 UTC succeeded: two HTTP 200 ingestions followed by ten conditional HTTP 304 checks. First genuine observation 146 / snapshot 14 still contains 89,533 listings. All seven original whole-row history, mapping and receipt fingerprints match the pre-switch evidence exactly.
- Certificate-validated Chromium checks pass again on production and preview. Both show the correct market identity, Bent Staff supply of nine units across nine listings, a recent price of 427 copper, genuine history, and independently queryable house 110 history. No page errors occurred. Temporary browser members are disabled and their credentials revoked.
- Fresh backup `market-development-20261114T161622641394Z.dump` (86,711,170 bytes; SHA-256 `08d66ae9ed72dd567ff07170dc2296a47970ee17a0650f3f47c0d8d8a76efbc9`) restored into isolated `market_restore` at 16:16:46 UTC. It preserves 157 observations, 1,504,158 listings, 361,377 statistics, two receipts and the current schema 0012. The separate preferences project had already added that schema; this verification changed no schema. All 15 preceding archives remain present and all 16 archive checksums pass.
- Worker memory is 127,684,608 / 402,653,184 bytes; lifetime peak remains 232,771,584 bytes. Database allocation is 530,183,859 / 5,368,709,120 bytes (9.88%). Current memory for all eight inspected production services is below its configured limit, with zero OOM events or restarts. The previously documented database lifetime accounting peak and reclaim events remain visible; no limits were increased.
- All eight production container IDs, images, start times, restart counts and configured resource limits match their pre-switch values. Rootless operation remains verified. AMP and unrelated services were outside all operations; gameplay health was not probed.

The latest committed code at this check, `3e794ad880cabadb96ca9274248ac521dc6fc471`, passes [Backend 43613615604](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43613615604), [Private website 43613615581](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43613615581), and [Windows companion 43613615678](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43613615678). The original pre-switch CI/backup evidence above is retained. This follow-up only adds documentation and acceptance evidence; uncommitted preferences work remains separate and no additional market is activated.
