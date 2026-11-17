# Universal Item Advisor U2 — verified identity foundation

U2 implements a pure, bounded resolver with explicit trust inputs, a provenance
corpus, adversarial tests and a test-only U1 adapter. It is production-inactive.
It proves descriptor hashing and resolution mechanics; **no real Forever link to
upstream variant equivalence has been established** from the available material.
Returning uncertainty is the intended result for those unproven identities.

U1 [draft #21](https://github.com/Twich-Team/TwichUI-Market/pull/21) was open,
draft and unmerged at inspection, head
`230465e1adf7c13f40344cc073383031d4a55f8d`. U2 starts from that exact head in
isolated `feature/advisor-identity-u2` and targets `feature/advisor-summary-u1`,
not the older integration baseline. Preserve both U1 commits. Neither PR may be
merged automatically. Read-only addon analysis uses current protected main
`36cdb04b35ca132650673463ecc09a0bbeadb6dc`; its workspace is unchanged.

## Source-verified identity trace

Source references/fingerprints and exact fixture provenance are in
[corpus.json](../contracts/market-summary-index-proposal/u2/corpus.json).

| Stage | Authoritative source / established behavior | Limit |
| --- | --- | --- |
| Bag observation | Forever ContainerDocumentation: `C_Container.GetContainerItemInfo` returns itemID and hyperlink; AdvisorData reads these | Cached availability and real event timing need native acceptance |
| Link extraction | Forever SharedXML/LinkUtil `GetItemInfoFromHyperlink` extracts item ID and item body | Does not define complete variant layout or upstream mapping |
| Variant warning | Workshop Worth.LinkVariant checks field 7 for suffix-like values, field 13 for bonus count; existing Worth fixtures exercise it | A conservative warning, **not proof of exact identity or plainness** |
| Native auction key | Forever AuctionHouseDocumentation `GetItemKeyFromItem` / ItemKey has itemID, itemLevel, itemSuffix, battlePetSpeciesID | No bonus/modifier payload or upstream-descriptor relation |
| Existing local safety | auction/SellData refuses bonus-key comparability; ReadRequests.Key validates four fields | ReadRequests fills omitted members with zero and rejects negative suffixes; U2 must preserve missing/raw evidence instead |
| Upstream identity | Market `ingest.normalize`: entire auction `item` object, sorted-key compact ensure-ASCII JSON, SHA-256 UTF-8 | Every unknown field and array order affect identity; absence is not zero/empty |
| Bridge identity | `contracts/bridge/v1/validate.py`: exact_upstream requires canonical descriptor/id/hash agreement, hash_only requires null descriptor | A hash-only key is not reversible |
| Market selection | market_configuration.valid_mapping / mapping_for, bridge_api.market_identity; source maps and upstream receipts are separate | Region/transport alias, labels or local realm names alone do not prove player economy |
| Summary lookup | U1 `(item_id, variant_key)` lookup in bucket `item_id % 64` | The tuple carries no descriptor; identity metadata must remain separate |

The read-only native UI source is branch `forever`, commit
`bebcb6bf309cf41b41bd74f8ca651e6a105b2676`, version `1.60.1.70938`.
Inspected ItemDocumentation (`GetItemInfo`, `GetItemInfoInstant`, `GetItemID`,
`GetItemLink`), ContainerDocumentation, AuctionHouseDocumentation and LinkUtil.
These establish API/source shapes, not observed game values or cross-source
semantic equivalence. The core/Workshop `.toc`, repository engineering/architecture,
feature safety and verification policies were read. No native source was copied.

## Implementation and supported mapping boundary

- [scripts/advisor_identity.py](../scripts/advisor_identity.py): raw link/normalized
  identity validation, pinned source/candidate validation, approved exact-vector
  mapping and structured refusal outcomes. No database/network/UI/game calls.
- [U2 contract](../contracts/market-summary-index-proposal/u2/README.md): exact
  inputs/outcomes, trust boundaries, bounds and conservative matching rules.
- [fixture corpus](../contracts/market-summary-index-proposal/u2/corpus.json):
  source facts, existing synthetic links and literal canonical hash vectors.
- [tests](../scripts/tests/test_advisor_identity.py) and
  [test-only U1 adapter/helpers](../scripts/tests/advisor_identity_support.py).
- [focused measurement](../scripts/measure_advisor_identity.py),
  [machine results](evidence/advisor-identity-u2/resolver.json).

Canonical game input is `{item_id, attributes}`. Attributes explicitly retain raw
link fields, complete native item_key and/or separately observed suffix/property,
bonus and modifier facts. Unknown/null/missing differs from zero. The parser
preserves every token without interpreting Retail-style positions. Unknown fields
are unsupported, not discarded. Full market representation is reused unchanged.

An exact result needs independently trusted source context, a pinned complete
candidate bundle, and an independently approved **whole game descriptor ↔ whole
upstream descriptor equivalence**. Evidence is bound to full market and issuer;
candidate data is additionally bound to the exact U1 generation and source policy.
All available observed attributes must match exactly. No hash is invented from a
link. This is an exact-vector implementation, not a generic field translator.

**Source-verified:** canonical descriptor-to-hash derivation, structural descriptor
validation, existing market identity rules and native API shapes.
**Fixture-tested:** literal existing upstream contract hash vectors and raw
extraction/refusal for existing addon fixture links.
**Synthetic-only:** exact positives for base, suffix/random-property and bonus/
modifier cases with explicit test-approved equivalences. These exercise mechanics
and do not authorize the corresponding native mappings.

**Unsupported/unresolved:** item ID alone, unapproved link equivalence, omitted/
contradictory fields, unknown modifiers, hash-only targets, incomplete sets,
historical-only/unavailable/unsupported candidates, unverified/mismatched markets,
and mixed source generations. Multiple possibilities/conflicting approved mappings
are ambiguous. A failed lookup/not_found never establishes absence or zero supply.
No production/native equivalence is bundled; default trust registry is empty.
Even U1's synthetic market mapping was explicitly unverified, so it cannot be
used unchanged as a trusted native market selection.

## Actual fixture provenance and missing evidence

Corpus includes four **existing repository fixture** links (plain-looking,
suffix-like, bonus-like and truncated ID-only) from addon test_workshop_worth.lua.
They were originally synthetic and remain labelled as such. Two literal canonical
upstream descriptor/hash vectors come from the existing synthetic bridge fixture
(items 2 and 2589). Other suffix/bonus/modifier positives and all mutations are
explicit **synthetic negative/positive controls**, constructed by test helpers.
Source fingerprints establish which implementations were inspected.

Available fixture coverage: **zero source-verified native item-link recordings,
zero recorded upstream item examples in this corpus, zero paired native/upstream
equivalences, zero production-approved mappings**. Searches covered native UI
source, addon tests/fixture directories, approved local test resources and Market
contract fixtures. No live account, production DB, player SavedVariables or auction
transaction was used to fill the gap.

The exact missing input is an independently attributable pair: actual Forever bag
itemID + full hyperlink + raw ItemKey/edition/realm context, and the corresponding
complete upstream auction item descriptor/variant hash with source market,
observation and provenance. Matching item names, incidental identical IDs or four
zeros do not establish that pair. Approval also needs evidence about every
price-relevant modifier omitted from either representation.

## Focused verification

**32 new U2 tests pass**, including five U1 integration tests. Together with
28 unchanged Advisor/U1/proposal checks, 16 existing schema-3 scoped conformance
checks and one frozen compatibility-policy check: **77 passing tests**.
Python compilation, corpus/source fingerprints, report links, measured source
fingerprints, whitespace and final isolation diff checks also pass.

Positive tests: trusted synthetic exact base/suffix/property/bonus/modifier mapping,
maximum signed-32-bit item ID, canonical hash vectors, exact U1 tuple retrieval,
determinism across 20 seeded candidate permutations and input snapshot isolation.
Negative tests: missing/truncated/malformed links/identities, unknown extra fields,
contradictions, nulls, distinct IDs with similar names, unsupported hashes, duplicate
candidates/modifiers, partial/noncanonical/oversized descriptors, hash-only and
historical-only data, every market identity field, forged verification/confidence,
corrupt bundle/equivalence pins, wrong generation, bounds/depth and ambiguity.

The adapter requests only the target item's metadata at its existing U1 bucket.
Unresolved input never calls U1.lookup; it cannot fall back to the base variant.
Exact identity preserves U1 unknown/absent/unavailable/confidence states. Missing
summaries remain unavailable. Mixed generations/markets fail before part loading;
an unrelated corrupt part is not read, while corruption in the requested part
raises U1's validation error and never becomes a zero-value row.

Reproduction (existing JSON Schema dependency only):

```sh
python3 -m unittest discover -s scripts/tests -p 'test_advisor*.py' -v
python3 -m unittest discover -s contracts/bridge/scoped-l1 -v
python3 -m unittest discover -s scripts/tests -p test_bridge_compatibility_policy.py -v
python3 -m py_compile scripts/advisor_identity.py scripts/measure_advisor_identity.py scripts/tests/advisor_identity_support.py scripts/tests/test_advisor_identity.py
python3 scripts/measure_advisor_identity.py --report /tmp/advisor-identity-u2.json
git diff --check
```

No complete backend/website/Windows/M2/simulator campaigns ran. Commits use
`[skip ci]` to avoid automatically repeating those unrelated PR workflows. No U1
schema/library change was necessary; existing assertions/negative controls remain.
No addon-side fixture PR or new runtime diagnostics is needed for this offline
component. Future U3 runtime scopes/gauges belong in the existing diagnostics.

## Measured lookup / allocation behavior

Synthetic-only Python 3.12.14/Linux, one item, 128 exact candidates, one approved
synthetic equivalence; 26,704-byte bundle and 678-byte proof. Three timing passes:
construction **5.06–5.43 ms**, 10,000 complete resolver lookups **233.84–245.32 ms**
(about **23–25 microseconds per lookup**). Lookup includes validation, small input
snapshot/serialization and result allocation; excludes disk/partition loading.

Separate tracemalloc pass: construction retained **61,158 B**, peak **110,265 B**;
after 10,000 lookups retained **61,254 B**, lookup-pass peak **62,986 B**. These
figures exclude caller-owned pre-existing input objects, imports, native allocator
and RSS; they are approximate Python allocations, not an addon heap budget or a
proof about indefinite retention. Resident state is bounded to 128 candidates and
32 proofs; no cross-market cache, whole-market index or partition scan exists.
Timings vary; implementation fingerprints and exact shape are committed. Python
performance does not predict Lua 5.1 or actual Forever frame behavior.

## Proposed U3 interface and required native acceptance

U3 should own a separate normalized identity service near AdvisorData/Worth, while
Bridge owns generation/integrity and ServerMarket exposes a separate external
research-evidence tier. Keep Lua 5.1 semantics and explicit null handling. Do not
reuse ReadRequests.Key's default-zero output as a complete observed identity.
Capture guarded plain values from actual bag ItemLocation, C_Container, C_Item and
C_AuctionHouse APIs; preserve cache failures/restricted values as unknown. Binding
and eligibility remain separate gameplay facts.

Before a real equivalence can be approved, capture native fixtures for base and
same-item variants, positive/negative suffix/property cases, bonus/modifier/context
order, absent versus empty members, enchantments/gems, item levels, battle pets,
truncated/cached links and GUID/unique-field differences. Determine whether some
link fields are display/player-specific and can safely normalize only after proof.
Confirm API availability/event timing/combat behavior and actual realm/region/
ruleset/faction-to-house mapping; no API inspected here supplies a verified server
market ID or transport ruleset mapping by itself.

U1 tuples intentionally omit descriptors. The smallest compatible proposal is a
**separate, inactive identity-metadata sidecar**, with closed per-item bundles as
exercised here, bound to the same issuer/full market/U1 generation. The future
publisher must provide trusted per-item content pins through a bounded,
independently pinned sidecar directory/manifest and expose only the requested
item/bucket to the consumer. This is proposed, not delivered by U2: U1's closed
manifest cannot silently acquire fields, and no global descriptor table should be
appended to every tuple or eagerly loaded at startup. Actual packaging/discovery,
root-to-item integrity, atomic generation switching, per-bucket refusal and native
loading budgets require a separately authorized design/implementation.

U3 must obtain all three trust inputs independently, request one item/bucket,
validate source binding, resolve or return Insufficient Evidence, and only then
read its exact summary. Keep a bounded resident-item/part budget, deduplicate work,
slice hashing/validation outside hot callbacks and stop rather than prune on
128-candidate/byte overflow. U2's synchronous Python construction is not a safe
client callback budget. Test Lua numeric bounds, canonical JSON/hash agreement,
transient memory, native compile/load/GC/frame tails and repeated-use residency.

A resolved identity alone must not produce an Auction recommendation. Preserve
Advisor.Decide's crafting reservations/pending plans, eligibility/bound checks,
vendor 1.5x/gain thresholds, unsupported-variant refusal and disenchant safeguards.
Keep MarketFacts/local history ownership, source freshness/confidence and
Sell.Suggest/Sell.Observation local competition predicates. Summary evidence is
asking-price evidence, never a completed sale, vendor value, DE return or promise
of proceeds. Do not connect U2 to active policy. Native acceptance and explicit
activation authorization remain future gates; this task stops before U3.

M2/beta.5 isolation: no backend/API/database, desktop/updater, signing/publication,
release-source/artifact/store, detailed schema-3, SQLite retention, working-set,
scheduler, pricing, addon runtime/default, installed addon, SavedVariables or
TwichUI_MarketData changes. U1 commits and files remain intact. U2 stops at its
pushed stacked draft PR; nothing is merged, deployed or published to players.
