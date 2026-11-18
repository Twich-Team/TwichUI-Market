# Universal Item Advisor U1 — inactive broad-summary foundation

U1 implements an offline summary projector, bounded deterministic partition
writer, strict manifest/partition validator and one-part reference reader.
It does not activate a production protocol or implement an addon consumer.

Base: approved `integration/companion-v2-metadata-recovery` at
`8c52b70afe8db4d514a46daf7dd13f27cccc8014` (verified M2 merge `25e6131` and
manual-export help `95e6636`). Work is isolated on short-lived
`feature/advisor-summary-u1`. The separate beta.5 publication branch/store and
existing TwichUI workspace are untouched. Nothing is merged, deployed, installed
or delivered to players.

## Components and research reuse

- [scripts/advisor_summary.py](../scripts/advisor_summary.py): executable pure
  projection/export/read library; no application dependencies beyond the existing
  JSON Schema tooling. No database, network, scheduler or addon hooks.
- [manifest schema](../contracts/market-summary-index-proposal/u1/manifest.schema.json)
  and [exact contract / API](../contracts/market-summary-index-proposal/u1/README.md):
  closed experimental envelope referencing existing proposal definitions.
- [focused adversarial tests](../scripts/tests/test_advisor_summary.py): identity,
  projection, availability, limits, integrity and failure behavior.
- [benchmark CLI](../scripts/benchmark_advisor_summary.py) and
  [machine evidence](evidence/advisor-summary-u1/synthetic.json): fresh-process
  synthetic generation, validation, lookup, deterministic rebuild and change cost.

Read/reused L2's [summary proposal](../contracts/market-summary-index-proposal/README.md),
[feasibility code](../scripts/advisor_index_feasibility.py),
[L2 delivery findings](scoped-market-delivery-l2.md),
[large-market investigation](workshop-bridge-large-market-investigation.md), actual
`bridge_api.assemble_record`, archive stream architecture and canonical pricing
bounds. Retain the exact nine columns, five availability codes, two confidence
codes, market/issuer/source semantics and canonical serializer. The original
monolithic proposal, pricing implementation and frozen fixtures stay unchanged.

Projection copies already-derived canonical metrics from current evidence. It
reuses existing field names and validates an existing canonical bridge fixture;
it does not reimplement weighted medians, daily references or pricing. A later
adapter must supply a pinned, ordered stream independently of detailed selections.
There is no active database/archive adapter in U1, and no claim of database query
performance or production export acceptance.

Current addon source was read at local commit
`36cdb04b35ca132650673463ecc09a0bbeadb6dc`: `AdvisorData` discovers
bags/tracked/recipe/local identities; `ServerMarket.Evidence` is a dormant external
research role; `Advisor.Decide` preserves crafting reservations, pending plans,
variant uncertainty, eligibility, vendor margin and disenchant safeguards;
`Sell.Suggest` / `Sell.Observation` depend on local evidence. No addon source,
fixtures, defaults or manifests changed.

## Partition choice and limitations

Fixed `item_id % 64`, ascending buckets and exact identities, hard 256 KiB per
part. Every related variant routes together. Missing records are unavailable even
with complete delivery; unknown/incomplete source observations never prove zero
supply or absence. All output binds exact market, observation time, age,
watermark, canonical algorithm/history basis and conservative confidence.
The [contract table](../contracts/market-summary-index-proposal/u1/README.md#exact-output)
lists every tuple/shared field and numeric support boundary.

A skewed bucket is refused in full with an actionable error. Deterministic
subdivision is an explicit later routing decision rather than an untested fallback.
This permits bounded discovery now without silently dropping variants. 256 KiB is
an offline refusal policy, **not a proven safe Forever load budget**.

Content-addressed partition bytes are independent of manifest generation metadata.
With the same observation/time, one changed price changes one bucket. Because the
reused tuple stores age at generation, advancing generation time changes all
nonempty buckets; U1 measures this honestly. Optimizing freshness representation
would be a reviewed experimental contract change, not an excuse to reset ages.
The exporter still reads the full supplied source stream on every rebuild.

## Measured synthetic results

Python 3.12.14, Linux x86_64; one fresh subprocess per shape on a shared host.
All-priced large shape: 45,125 exact variants / 45,124 item IDs, including a
same-item variant pair, three distinct 11-digit copper strings, supply 12, age 300.
These are synthetic capacity findings, not production distribution measurements.
Exact output sizes and IDs reproduce; timing and RSS vary.

| Shape | Total bytes (manifest included) | Parts | Largest part | Generation wall / CPU |
| --- | ---: | ---: | ---: | ---: |
| Empty | 1,378 | 0 | 0 B | 0.00222 / 0.00222 s |
| Small, 5 variants | 2,825 | 4 | 257 B | 0.00399 / 0.00398 s |
| 45,125 variants | 5,790,555 | 64 | 90,497 B | 3.41317 / 3.41131 s |
| 5,000 variants of one item | No generation published | Refused | 262,144 B cap | 0.14513 / 0.14512 s to refusal |

Large manifest is 14,491 B. Large producer peak RSS is **18,874,368 B**;
post-import baseline high-water RSS is 18,481,152 B, increase 393,216 B.
RSS is Linux `ru_maxrss` converted from KiB in a fresh subprocess and sampled
before reader/rebuild work. The delta is high-water growth, not a precise live
allocation measurement; imports contribute most of the total. The producer uses
bounded disk spools and never constructs a whole-market list.

Large reference-reader measurements: manifest open/validate **6.71 ms**;
full sequential integrity verification **3.034 s**; first part validation plus
lookup **48.28 ms**; **10,000 warm lookups 13.80 ms**. It retains one partition
(707 records for the selected bucket). Cold validation remains meaningful work;
these synchronous Python costs do not establish any game frame-time budget.

All files in a same-input rebuild were byte-identical. One price change altered
one 90,497 B partition plus manifest; the other 63 partition files were unchanged.
Advancing `generated_at` by 60 seconds altered all 64 partition files. The evidence
also records the empty/small cases and refusal text, implementation fingerprints,
manifest identities, CPU and memory methods. No generated partition data is
committed or installed.

## Verification and failure evidence

**Unit-tested:** 25 new U1 tests, three unchanged L2 proposal tests, 16 existing
schema-3 scoped conformance tests and one frozen compatibility-policy test:
**45 passing checks**. Syntax/schema checks and diff review also pass. Tests cover:

- Empty/small, exact variants and shared-item discovery; sparse/null metrics,
  missing current evidence, missing essential market/identity metadata.
- Complete absence versus incomplete current/source observations; explicit partial
  retained-universe coverage; missing rows always unavailable.
- Maximum supported copper retained exactly; above-support 53/63-bit values,
  floats, zero, malformed decimals rejected; explicit unsupported arithmetic is null.
- Skew/byte/count refusal, duplicate/unsorted input, no partial output, preservation
  of an existing generation, byte-identical rebuild and isolated price change.
- Corrupt/missing/truncated/oversized partitions, wrong expected generation,
  metadata tampering, duplicate JSON keys, noncanonical JSON, unknown schemas,
  forged provenance/confidence, unsafe file paths.
- Rehashed attacks still fail semantic checks: wrong route/order, duplicate rows
  or buckets, bad counts/age/confidence, unknown supply becoming zero, incomplete
  absence, or declared size limits. Unrelated corrupt parts are not loaded during
  an exact lookup; corrupt requested data never becomes a zero-value record.

During implementation, the original L2 generator established that supply-only
uses unavailable **price** confidence, so the projector preserves that code.
An initial refusal fixture used a single row that actually fit its tiny bound;
it now supplies two identities in the same bucket. Neither existing proposal
assertions nor schemas were weakened. Review additionally tightened exact hash
validation against trailing newlines; affected tests and measurement were repeated.

Reproduction from repository root (existing `jsonschema==4.26.0` dependency):

```sh
python3 -m unittest discover -s scripts/tests -p 'test_advisor*.py' -v
python3 -m unittest discover -s contracts/bridge/scoped-l1 -v
python3 -m unittest discover -s scripts/tests -p test_bridge_compatibility_policy.py -v
python3 -m py_compile scripts/advisor_summary.py scripts/benchmark_advisor_summary.py scripts/tests/test_advisor_summary.py
python3 scripts/benchmark_advisor_summary.py --report /tmp/advisor-summary-u1.json
git diff --check
```

Compare each `source_sha256` entry against the file, then deterministic fields
(bytes, counts, IDs, changed partition counts) against committed evidence. Benchmark
runs include explicit byte comparison of every rebuilt file. Focused code changes
are marked `[skip ci]` to avoid automatically repeating full backend, website,
Windows and M2 campaigns in the existing PR workflows, as requested for U1.
No full campaigns, simulator, live production probes or native client tests ran.

## Future consumer interface — proposed, not implemented

1. Resolve the player's actual Forever edition/region/ruleset/house/source against
   verified `market` mapping evidence. Reject unknown or competing market mappings.
   Region or item ID alone is insufficient. Issuer and generation trust must come
   from a separately authorized delivery boundary, not the untrusted manifest itself.
2. Given the item ID, route to one bucket before resolving a variant. Enumerate
   only that item's exact variants within the validated bucket. Match a verified
   normalization of the real game link/descriptor to a unique upstream hash.
   Do not guess base variants, collapse suffix/bonus variants, or hash an arbitrary
   game link and assume it uses the server normalization. Ambiguous/hash-only
   mappings return **Insufficient Evidence**. U1 intentionally omits descriptors;
   a future bounded resolver/catalogue contract must provide the missing proof.
3. Load only the small manifest at the chosen consumer initialization boundary;
   do not load all parts at startup. Request/deduplicate the needed bucket on
   explicit Advisor/bag work. A missing bucket/row yields unavailable; a corrupt
   part yields rejected/unavailable evidence. No game HTTP or filesystem parser is
   assumed. A future data-only delivery/LoD packaging contract is still required.
4. Validate pinned manifest, schema, issuer/market/algorithm and requested part
   before exposing any record. Use incremental hashing/validation and bounded
   callbacks for cancellable work. Preserve the previous complete generation while
   staging a new one; never mix part generations. Compile/load can be synchronous
   even if later validation is sliced. Establish budgets from real measurements.
5. Adapt to a distinct `external_evidence` role, tier `broad_summary`, with exact
   source/generation, state, references, observed time/age and limited/unavailable
   confidence. Do not impersonate `ServerMarket`'s detailed-history tier or local
   `Facts`, and do not write summaries into local history. Effective age must
   advance from actual observation time; a desktop receipt/reload cannot refresh it.
6. Retain local competition, crafting reservations/pending plans, eligibility,
   vendor and verified disenchant evidence as independent inputs to existing policy.
   Imported asks cannot satisfy `Sell.Suggest` / `Sell.Observation`, prove a sale,
   promise proceeds, invent vendor/DE values or justify stronger advice by themselves.
   Unknown alternatives and unresolved identities remain Insufficient Evidence.
7. Keep lookup indexes bounded to the requested bucket/item and schedule validation
   outside hot UI callbacks. Do not allocate a whole-market variant table. Lua
   addon code/global retention may prevent actual unloading: the Python one-part
   cache is only a reference. Set an explicit session resident-part/heap limit;
   stop loading new parts and return unavailable when it is reached. Never force
   global GC, reloads or unlimited part accumulation to meet a nominal cache size.

Open identity questions: exact Forever link-to-upstream normalization (including
suffix/bonus/context differences), base-only uniqueness proof, hash-only retained
identities, verified player ruleset/house mapping, commodity versus auction routing,
and descriptor provenance/versioning. No answer is inferred from shared item names.

## Native Forever acceptance and next step

Before any activation, independently authorize and test an exact resolver and
bounded consumer in a disposable native Forever profile. Measure startup and
first-request compile/assignment, incremental validation p99/max slices, frame tails,
GC stalls, heap and transient old/new generation memory, cumulative resident parts,
load order/combat restrictions and timer cadence on representative hardware. Test
missing metadata, ambiguous variants, bad hashes, mixed/stale generations, interrupted
publication, last-good recovery, session refresh/reload behavior and user-controlled
apply. Establish real partition byte/time/residency limits; 256 KiB is not accepted
by this offline evidence. Genuine source distribution and retained identity coverage
also need independently authorized evaluation.

Next bounded milestone: prove game-to-upstream exact identity mapping using pinned
fixtures, design an inactive data-only delivery/consumer interface, then implement
its sliced validator with focused tests. Keep broad summaries separate from selected
schema-3 history and preserve local reservations/competition. Native acceptance and
explicit activation authorization follow; they are not prerequisites to finishing U1.

M2 compatibility is structural and fixture-tested: **no changes** to schema-3,
working sets, archive/history retention, automatic delivery, beta.5 signing/updating,
pricing algorithms, production APIs, addon runtime/defaults, or TwichUI_MarketData.
There are no imports of U1 from application/runtime sources. U1 stops at this tested
inactive foundation and a reviewable draft PR, without merge/deployment/publication.
