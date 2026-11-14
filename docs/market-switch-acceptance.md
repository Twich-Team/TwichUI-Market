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
