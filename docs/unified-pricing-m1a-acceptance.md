# M1a acceptance and remaining gates

M1a implements the owner-approved M0.5 model as an isolated shadow calculation and freezes bridge contract v1. It does not activate pricing, export history, deliver an addon, change the tray scheduler, migrate data or deploy anything. Draft implementation PRs: [Market #7](https://github.com/Twich-Team/TwichUI-Market/pull/7), then dependent [TwichUI #21](https://github.com/Twich-Team/TwichUI/pull/21). Owner review precedes either implementation merge.

## Approved specification integration

| Research PR | Target | Merge commit |
|---|---|---|
| Market #6 | `integration/companion-v2-metadata-recovery` | `4cb4d86f4402cd3c6508914549f697507d69c0c6` |
| TwichUI #20 | `feature/workshop` | `5b6e4e9f4dd3908042831bf6496133fbd8154960` |

Targets, diffs, repository merge permissions and the five shared fixture hashes were reviewed. Market research Backend, website and Windows runs all passed (43728045187, 43728045169, 43728045215); addon had no PR workflow runs. Normal expected-head merge commits were used without bypass or force. The original research files remain unchanged. Addon contract mirror pins final Market source checkpoint `941f0f2d80019665f7caa2a3c4d76cfb6910c91c`; its four schema/generation/checksum bytes are unchanged from initial checkpoint `7823197ca5537467762ed62115f8df0204e3038e`. Addon implementation checkpoint is `f8e4844f21617e72b4ab724315ea8a780a5e6f97`.

## Implemented and verified

Python provides pure snapshot/coverage/quality functions and complete-scope daily history under `twichui-pricing-v1`. Minimum is ceiling unit copper; Recent Price uses the approved strict-quarter anchor, half-anchor eligibility and cheapest 30% eligible quantity mean. Market Value uses the 4/2/1 lower weighted median over UTC ages 0..13; Historical Value uses the lower median over exact UTC ages 0..59 with at least three priced dates. Last complete daily scope wins, including absence; partial observations cannot replace it. Today is provisional and missing days are not filled.

Rust supplies strict money/tier validation, checked-u128 Recent Price and daily history conformance. Lua supplies the dormant equivalent for supported exact-double arithmetic, rejecting unsafe intermediates before reporting a result. Lua history conformance currently accepts integral UTC epoch seconds through 2100-01-01 and observation IDs through 2^53-1; it rejects fractional seconds. It must not be used by truncating a contract timestamp: M1b must preserve full source timestamp precision and select validated precomputed closes, or extend the arithmetic interface with exact timestamp comparison. Rust/Lua header checks are capability checks only, not full contract acceptance. Neither application selects these paths for live results. Legacy `asking-v1-provisional` APIs, protocol defaults, persisted generations and Workshop local history remain intact; no Advisor/Sell consumer changes.

| Evidence | Result and scope |
|---|---|
| Independent research verifier | PASS: 23 snapshots, 8 temporal, 30 boundary cases |
| Python focused + legacy ingest compatibility | 119 passed; includes 250 seeded Fraction-oracle/permutation trials and 7 isolated critical mutations |
| Python/Rust/Lua shared calculations | All agree on 19 supported priced snapshots and 8 temporal calendars; empty/bid-only and unsupported money explicitly checked |
| Lua quality and header conformance | 11 quality cases; both bridge algorithms accepted only with compatible versions/bases |
| Rust full core workspace, locked | 71 passed, including 4 new pricing/conformance tests; no dependency changes |
| Addon fast market | 14 modules/files passed; 71 selected Lua files syntax-checked |
| Addon market mutation campaign | 201/201 applied mutations killed; no survivors, invalid, timeout or infrastructure cases; 602.2 seconds |
| Addon full Cloud milestone | PASS: 239 offline modules/files, 702 Lua syntax files, all 10 simulator suites; 2,370.634 seconds; known simulator limitations retained |
| Bridge offline validation | Both synthetic golden generations valid; corruption, rehashed semantic errors, duplicate JSON keys, bounds, unknown fields/versions, identity, absence and history coverage rejected |
| Fixture preservation | Five original pricing files and four bridge mirror files byte-identical across repositories; manifest hashes verified |

Commands were the existing addon `tests/run.sh` tiers and `tools/mutate.sh --group market`; backend pytest; locked Rust workspace tests; and the contract/research validators. Initial full Cloud run passed all 239 offline modules and syntax, but all nine actual simulator catalogs could not launch (`bwrap: setting up uid map: Read-only file system`); simulator lab guard passed. Retried via the repository-documented elevated execution path without altering the simulator, fixtures, assertions or test selection. Cloud results never satisfy the separate local milestone gate. Workshop reports PASS WITH KNOWN SIMULATOR LIMITATIONS: its established voice-settings unsupported API and invalid-UTF8 addon-message rule remain classified runtime errors in the logs; this is not a runtime-error-free or real messaging run. No real-client testing or visual acceptance is claimed.

Market checkpoint `7823197` passed Backend/PostgreSQL run [43732236108](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43732236108) (490 pytest and 34 operational tests), website [43732236017](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43732236017), and Windows [43732236050](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43732236050). Workflows validated combined PR preview `7306977b29648abd7058c32d0186e37223b42c9a`; this is integration evidence, not release-admissible exact production CI. Final source-changing checkpoint `941f0f2d80019665f7caa2a3c4d76cfb6910c91c` also passed all three workflows: [Backend 43733440464](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43733440464) (491 pytest, 34 operational), [website 43733440468](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43733440468), [Windows 43733440440](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43733440440). Backend tested preview `05dbfd760ec8fe24efaf499719b05c412f4a8da9`. The final evidence checkpoint changes documentation/reports only; its automatically repeated CI is visible on the draft PR. No release admissibility is inferred.

## Offline shadow findings

[Machine-readable comparison](evidence/pricing-m1a-shadow.json) records source hashes, identity, provenance, scope and both results for all 23 cases. Reproduce with `python scripts/compare-pricing-shadow.py --fixtures contracts/pricing/v1/snapshots.json`. An explicit local original snapshot can instead be supplied through `--snapshot`; the tool has no network, database, app or persistence path.

Four genuine November 14 listing excerpts retain their original house-110/commodity provenance and timestamps. Both formulas agree at 4,099, 32,500, 948 and 50 copper on these single-tier excerpts. They are not complete variant books, current house-114 data or a history validation. The Cloud route to the service is proxy-blocked; the owner confirmed no alternate authorized snapshot export. Representative full production comparison remains open.

| Explicitly synthetic case | Legacy Recent copper | Canonical Recent copper | Interpretation |
|---|---:|---:|---|
| Healthy material | 110 | 100 | Lower available quantity band differs intentionally from all-listing mean |
| High outlier | 912727 | 5000 | Representative value resists the high ask |
| Cheap outlier | 4941 | 5000 | Sub-half-anchor listing removed from representative band, preserved in observed minimum |
| Thin cheap third | 6167 | 1 | Cheap supply exceeds quarter boundary; canonical value alone is insufficient selling evidence |
| Unequal stacks | 180 | 134 | Quantity-aware band differs from descriptive mean |
| Fractional unit minimum | 100 | 101 | Ceiling preserves the approved observed unit rule |

These examples validate specified arithmetic, not the real economy or sale proceeds. Full-horizon 14/60-day behavior is tested using synthetic calendars only. Two actual available service dates cannot validate those horizons. Quality, minimum and supply stay separate; no result overrides existing selling safeguards.

## Bounded performance probe

[Raw measurements](evidence/pricing-m1a-performance.json) come from `python scripts/benchmark-pricing-shadow.py`: 150,000 synthetic auctions, one exact variant, 32 tiers, quantities 1..20, three interleaved rounds, input allocation excluded, other verification processes active. Canonical source hash is recorded.

Legacy prevalidated summary median wall/CPU was **47.765 / 47.780 ms**; canonical validation plus summary **253.950 / 253.893 ms**. Wall spread was 2.72% / 2.74%. Peak auxiliary traced Python allocations were 18,166,732 / 8,309 bytes; these exclude already-created input rows and do not measure retained process RSS, export serialization, network, Rust, Lua, desktop or real-client costs. Canonical is slower in this differing-scope probe; no speedup or operational latency guarantee is claimed. The results establish only a bounded synthetic offline baseline. Both descriptive means were 5,016 copper; canonical Recent was 5,004.

No addon runtime diagnostics scope/gauge is added because PricingV1 is outside every TOC and does no runtime work. M1b parsing/import/loading must add registered timing scopes and bounded retained-data gauges before being judged in client diagnostics.

## Frozen contract and required M1b work

[Bridge contract v1](../contracts/bridge/v1/README.md) freezes format/contract/schema/transport versions, exact market and variant identity, canonical/provisional algorithm-basis pairs, current and daily records including historical-only variants, supply/distributions, UTC source freshness, coverage/synthetic provenance, exact money strings, canonical hashes and hard size limits. Its Python offline validator checks schema plus semantics/integrity. The two synthetic golden generations are reproducible test data, not actual exports. The companion and Workshop do not yet fully validate/import this format.

Recommended order after separately approved M1a merges:

1. Server: bounded authenticated watermark-pinned history export; derive canonical values only from retained sufficient original inputs; preserve old APIs/generations. Add cursor/consistency tests and authorized representative full-snapshot shadow comparisons.
2. Desktop: separate algorithm-qualified cache, full schema/semantic/integrity validation and manual sandbox bridge generation. Add safe fixed string/chunk serialization and atomic same-filesystem replacement with readback/rollback. Preserve account/market isolation and the existing scheduler.
3. Workshop: bounded non-executing reader for `TwichUI_MarketData`, separate imported evidence/local scans, source-aware displays and existing Advisor/Sell gates. Reject unsupported versions/ranges atomically and preserve prior valid data. Add diagnostics scopes/gauges.
4. Acceptance: Windows replacement/failure/caching and Forever addon discovery, load/reload, size/memory, saved local history, corrupt/newer/absent bridge and selling-confidence checks. Complete real-data shadow and local/client gates. Any production activation, deployment or automatic delivery needs separate authorization.

Stop at M1a. No implementation PR is automatically merged and no M1b export, delivery or reader is implemented here.
