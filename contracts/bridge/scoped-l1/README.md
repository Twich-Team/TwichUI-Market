# L1 scoped bridge proposal: contract 1 / schema 3 / transport 1

**Status: offline foundation only, not a production feature.** Market owns these proposed schemas and synthetic fixtures. No existing `contracts/bridge/v1` bytes, server routes, Rust cache/publisher, Workshop runtime files or TOCs change. L2/L3/L4/M2 remain separate milestones.

## Authority and version decision

Inspected Market base: `73617a9e2ce6b32f539700c72caab4592a443a2f` (`integration/companion-v2-metadata-recovery`); TwichUI: `732ccf87b825c7f93d7dbb73cae9fa9bfb001fd8` (`feature/workshop`). Market #10/provider management and #11/Explorer fixes are already integrated and untouched.

[Research PR #12](https://github.com/Twich-Team/TwichUI-Market/pull/12) remains **open, draft, unmerged**, pinned input `49cfa2bc5701657c054d01ee44817ad4a3662aa3`, `docs/workshop-bridge-large-market-investigation.md`. Its branch is not changed or merged. M0's original chat is unavailable; [M0.5](../../../docs/unified-pricing-m05.md) records its architectural decisions. Also reviewed M0.5 migration, M1a implementation/acceptance, [M1b](../../../docs/workshop-bridge-m1b.md), [AMENDMENT-001](../v1/AMENDMENT-001.md), [M1.5](../../../docs/workshop-bridge-m15.md), current exporter/cache/publisher and actual addon loader/validator/history consumers.

Choose **new schema 3**, same `format=twichui-market-bridge`, contract 1, transport 1, with new required feature `scoped_selection`. It adds explicit membership/coverage while preserving existing record shape, exact copper, algorithms, history bases, source identity and canonical hash definitions. Existing Python/Rust/Lua select only schemas 1/2 and reject 3; they cannot mistake it for a full generation. A new major contract is unnecessary. Schema 3 is in a separate proposed directory, not silently substituted into frozen schema-1/2 files or deployed endpoints. The schemas reuse immutable schema-2 properties by URI/JSON Pointer; the offline registry resolves them locally with no network access.

This resolves two research recommendations against actual code: (1) research suggested contract/transport 2 as a possible boundary, but existing schema refusal permits the smaller explicit schema extension; (2) the actual exporter marks accepted observations `scope_complete=true` and selects each day's latest accepted observation. It does not query a separate incomplete-observation column. Schema 3 nevertheless preserves incomplete/unknown states supported by existing fixtures/validators; future L2 must not invent production partial-state availability. A full existing bridge source is limited to a 60-date view, **not** all-time desktop history.

## Two storage roles, two meanings of completeness

The approved architecture retains all server-retained evidence on server and future desktop storage. WoW receives only selected exact variants and a bounded window. **L1 does not implement an archive download protocol or unlimited desktop store.** The prototype uses a small, validated v1-shaped archive fixture to prove projection without modifying the source; it cannot download an oversized production generation. L2 must stream normalized complete retained evidence, not reuse the 32 MiB whole-generation cache as an archive.

“Full history” means all evidence still retained by the source, with original timestamps, algorithm/basis and provenance; it does not promise deleted raw listings or canonical recomputation from legacy summaries. Desktop retention must preserve every retained observation/daily winner needed to reproduce the requested supported view, including later corrections. Older dates may be stored indefinitely under explicit disk/retention policy. A schema-3 WoW view preserves **all eligible daily closes in its requested window**, not every intraday raw listing or old weekly aggregate. The supported inherited view has at most 60 days within the as-of day's existing retention envelope.

A published schema-3 generation guarantees:

- Every requested exact identity has exactly one sorted record. `requested_count == record_count == len(included) == len(request.variants)`.
- Every eligible daily close required by its requested window and supported algorithm is in every selected record. No date pruning, sampling or shortened-window fallback.
- Source absence requires a complete **market observation**, regardless of how few variants were exported.
- `scope.scope_complete=true`; `scope.whole_market_complete=false`; legacy `coverage.generation_complete=false` is mandatory. Neither field can be true for the whole market merely because every requested identity was delivered.
- `coverage.history_complete=true` and `history_truncated=false` mean complete delivery of eligible closes in this explicit scope/window. They do **not** mean an observation exists every day. The mandatory per-calendar-day table identifies gaps.

The producer owns absence/completeness assertions under its pinned source checkpoint. A receiver verifies consistency, exact inclusion and hashes, but cannot cryptographically prove the producer did not hide a source observation. Content SHA-256 is integrity, not a signature or independent source attestation; use authenticated transport and trusted local publisher as today.

## Selection model and canonical identity

[selection.schema.json](selection.schema.json) is the bounded request. It carries format, contract 1, expected schema 3, issuer UUID, the **entire existing market identity**, explicit exact variants, inclusive `history_from_day`/`history_through_day`, pricing algorithm/history basis and `profile=daily_research_v1`.

Market identity includes Forever edition, region, player ruleset, house, source kind, issuer-local market ID, transport ruleset ID and mapping provenance. Unknown mapping stays unknown. A changed mapping can change request identity conservatively. Never infer a realm, combine houses/rulesets or equate transport ruleset aliases with economic identity. Local Workshop item-ID aggregates/links cannot establish full upstream variant hashes. L2 must require explicit variant resolution, not guess from display names.

Variants are pairs `(item_id, full upstream variant_key SHA-256)`. Sort by ascending integer item ID then lowercase ASCII 64-hex key. Duplicate pairs are **errors**, even when entered in a different order; no duplicate silently disappears. A UI/reference normalization helper may sort unordered distinct input; a published request must already be sorted. Two variants of one base item remain separate entries. Unknown/invalid/mismatched descriptors do not become a base-item record. Hash-only identities retain their original unknown-attributes semantics; equality is still the full upstream key.

Canonical encoding reuses v1: UTF-8 JSON with sorted string keys, ASCII escaping, no whitespace, no floats/NaN, exact decimal money strings, bounded depth, closed schemas. Hash = lowercase SHA-256 hex of those bytes. No hash over display labels, UI order or rounded numbers.

- `request_digest = SHA256(canonical(normalized_request))`: binds market, variants, dates, profile, algorithm and expected schema.
- `selection_id`: same digest input **excluding only the two history-date fields**. Same exact selection and profile has a stable identity across window choices; changing market, exact variant, algorithm or schema changes it.
- Generation ID: existing v1 hash of the whole source body excluding `generation_id` and `integrity`, now including the entire `scope` object. Changed selection, date window, effective watermark, coverage, source times or record bytes changes it.
- Record hashes: `scope.record_sha256[i] = SHA256(canonical(records[i]))`, in the same strict record order. Existing whole-record-array hash, byte length and manifest-body hash remain required. The source hash includes those record hashes as well.

Named working sets are desktop-local saved mappings `{stable local id, label, normalized request}`. They resolve to `explicit_variants` and do not add a new semantic scope type or mutable name to source hashes. A future tracked-item assembler resolves an opt-in tracked/base-ID set into explicit exact variants and shows the expansion/budget; it is not implemented. Unknown `scope_type` values are refused. Full-market legacy generations remain schemas 1/2 with their original meaning. An explicit selection that happens to match today's full union **still** carries `whole_market_complete=false`; equality today is not a negotiated full-market contract.

## Authorization and private context

Account/device identity is trusted transport/cache context, **not game payload metadata**. Existing authenticated device credentials and origin/account isolation must be reused in L2. The request names issuer and market, not a bearer token. The prototype requires a session tuple `(origin, account_id, device_id)` to equal an independently supplied authorized context and requires request issuer/market to match the permitted source. This is a pure authorization invariant proof, not an implemented identity service. Caller-supplied copies of the same tuple are not authentication.

L2's signed cursors must bind origin/issuer, authenticated account/device credential, market, algorithm, effective observation watermark/checkpoint, request digest, position, encoding/schema and expiry. Credential revocation, wrong account/market and checkpoint expiry refuse/reset staging only. Persist named selections and caches under the full private context; do not put private identifiers or credentials into addon files or receipts. Server reuse can share identical authorized content but authorization is always rechecked.

## Publication, omissions and outcome states

[Generation schema](generation-schema3.schema.json) retains inherited current summaries, observation/provenance table and daily rows. `scope.request` is the exact canonical request; `included` repeats the resolved exact identities; `excluded=[]` states **no requested identity was excluded**. The unrequested universe is not enumerated into the manifest: it is precisely the complement of `request.variants` in the source identity domain. Lookups outside that list return `outside_scope` and no record/value. No claim that unrequested variants exist or do not exist is made.

Profile `daily_research_v1` explicitly requests current metrics/supply/status and full selected daily history. It does not request distributions: `distribution_complete=false`, `omitted_sections=["distributions"]`, records carry null distributions and `omitted_budget` status using the existing enum. This deterministic profile exclusion is declared **before** selection, never an overflow fallback. Reference support up to 60 days, provenance OR and current source observation remain retained even for a shorter delivered chart range. Full-window metrics are not recalculated from the delivered subset.

| Condition | Published generation or request-level outcome | Value semantics |
|---|---|---|
| Included priced | Record, `listed`, exact supported price strings | Price is a listing metric, never a sale |
| Included bid-only/supply-only | Record, `listed`, supply>0, priced_supply=0 | Price null/unavailable; supply is known |
| Included absent at complete close | Daily/current `absent` with source complete, zero counts | Price null; zero supply only for that proven observation |
| Included unknown at incomplete current | `unknown`, null counts/prices | Unknown is not zero/absent |
| Missing market date | Calendar `no_observation`, null ref; no fabricated daily row | Gap, not absence |
| Incomplete-only date | Calendar `incomplete_only`, latest source ref; no canonical daily close | Coverage unknown; provisional basis follows inherited daily rules |
| Outside requested set | Lookup `outside_scope`, no record | No zero price or absence claim |
| Malformed identity / wrong item-key pairing / unavailable retained identity | Whole request rejected (`identity_unavailable` or schema/identity failure) | Never produce an empty synthetic absent record |
| Not authorized | Whole request rejected before publication, no private data echoed | No per-item authorization leak |
| Over capacity | Whole request rejected with sizing diagnostics | No dropped variants, shortened window or daily pruning |
| Unsupported algorithm/basis/profile/schema | Whole request rejected | No implicit provisional conversion or algorithm relabeling |
| Missing source history support / requested window unavailable | Whole request rejected | Never claim complete delivery from incomplete retained evidence |
| Partial download/corrupt generation | Reject candidate activation | Previous validated generation stays usable |

No partially fulfilled scope is publishable in L1. A future explicitly requested partial-result contract would need distinct completeness/status fields and negotiation; it is not a fallback here. `outside_scope` is a lookup result, not a new price-state enum inserted into v1 records. Error codes in the reference distinguish capacity/auth/history/identity failures; production HTTP/status/error schema is L2 work. JSON Schema errors must be mapped to stable bounded request errors without logging bodies or secrets.

## Dates, references and provenance

Calendar coverage contains every date in the requested inclusive window (1..60 dates), in ascending order. `complete_close` points to the latest complete observation on that day ordered by full-precision `(observed_at, numeric observation_id)`; `incomplete_only` points to the latest observation if no complete one exists; `no_observation` has no reference. References are zero-based indices into the existing bounded observation table (≤61). The prototype retains support observations outside the delivered chart window as well.

Canonical daily rows reference the day's latest complete market observation, not the latest appearance of that item. If selected item listings are absent from that complete observation, keep an explicit absent point. Missing dates have no rows and no interpolated prices. Today's close remains provisional until the day ends; its date is derived from `as_of_utc_day`, not delivery time. Current selection follows source chronology, watermark bounds IDs including late historical imports, and fractional timestamps remain exact. Preserve snapshot/payload hashes, namespace, upstream raw/parsed time, synthetic conservative OR and mapping evidence. A newer unchanged 304/check or desktop receipt never freshens old content.

Existing `twichui-pricing-v1` / `canonical_complete_scope_close` and explicit `asking-v1-provisional` / `market_rolling_daily_means` remain separate. Legacy weekly aggregates are not exact canonical daily rows. Signed-64 descriptive copper stays a string; conversion beyond Workshop's supported 99,999,999,999 range returns `unsupported`, never a rounded Lua double. No trading or quality policy changes.

## Integrity, receipts, reuse and activation

The source is sealed once per immutable `(market, algorithm, source checkpoint/as-of, request digest, profile/schema)` projection. Repeated equivalent requests may reuse the exact sealed generation, including its original `generated_at`; regenerating with a new timestamp would change identity. Receipt timestamps/builds are outside the source hash per AMENDMENT-001. `desktop_sync_completed_at=null`, source producer desktop build `not-applicable-server-export`; the separate schema-1 receipt binds generation ID, real completion time and desktop build. The offline reference verifies completion time ≥ source generation time; no account/device fields are allowed.

Validate all schema, source/selection equality, sizes, exact membership/order, per-record and full hashes, dates/references, absent/unknown semantics, algorithms, copper and receipt **before** activation. Download/staging is not a completed generation. Failed candidates cannot mutate active/previous. An unchanged generation must not overwrite the preceding distinct recovery generation. The reference `LastGood` models this in memory only; it is not a transactional SQLite implementation or power-loss proof.

The Python/Lua proof reuses v1 record validators via a **private evidence validation view**: remove schema-3 scope, restore schema-2 feature/header preconditions and recompute internal validation hashes. This view is never published, returned as full data or activated by the production reader. Its `generation_complete=true` is solely the legacy validator's precondition, not proof of membership. Schema-3 scope/hashes are verified independently before/alongside inherited semantics. L2/L3 should factor shared evidence checks or use a similarly unexposed adapter; they must never let this internal view escape as a legacy full-market generation.

## Capability negotiation and compatibility

Do not send schema 3 through today's routes by default. L2 should add an explicitly scoped selection endpoint/capability and accept only negotiated schema/profile. New consumer supports schemas 1/2 plus 3 through distinct validation dispatch; unknown schema/feature refuses. Desktop cannot discover installed in-game capabilities by magic: require explicit supported target configuration/verified capability information. The L1 assignment name `TwichUIMarketDataL1` is test-only, not a shipped addon or namespace decision.

| Producer desktop / consumer | Required behavior |
|---|---|
| Old desktop + old addon | Existing valid whole-market schemas 1/2, unchanged limits/semantics |
| New desktop + old addon | Legacy compatible path only, or refuse scoped delivery; never relabel a subset schema 2 |
| Old desktop + new addon | New runtime may read legacy schemas 1/2 unchanged; no scoped capability appears in old desktop |
| New desktop + new addon | Explicit schema-3 negotiation, full scoped validation before activation |
| Unsupported future schema/features | Refuse candidate and retain last good; do not “best effort” parse |
| Interrupted multi-generation update | Keep completed source/cache/artifact; no mixed records/manifests/receipts |
| Wrong market/account/device/request digest | Refuse/reset private staging, do not expose another context's active data |
| Valid legacy schema 2 | Old/new reader accepts only as full-market legacy evidence |
| Valid scoped schema 3 | New compatible reader only; old validator rejects schema 3 |
| Corrupt scoped generation | Reject before activation, retain active and previous |
| Downgrade desktop/consumer | Restore a complete supported artifact; old narrow publisher may refuse schema 3. Do not mutate new stores downwards |

A hash-valid candidate for a different selection is still wrong for the pending request. After restart `Previous.lua` is not automatically loaded by the current TOC; publisher recovery must explicitly restore the preceding valid artifact. Existing Windows ACL/reparse/ownership/atomic replace/readback protections remain required. Files changed on disk do not update an already loaded addon. Expect one player-chosen refresh boundary for a coalesced update, verify actual discovery/load behavior in L4; never promise dynamic reread or implement reload here.

## Budgets and targeted capacity

Hard proposed schema-3 limits: existing 32 MiB canonical, 64 KiB per record, 60 daily rows/variant and ≤61 observation refs, bounded nesting/exact arithmetic; **1,000 selected identities**, **128 KiB selection request**, **256 KiB manifest including integrity/scope**, and existing separate **130 MiB expanded source** ceiling. The larger proposed schema-3 manifest bound does not change deployed schema-1/2's 64 KiB bound. It accommodates explicit scope metadata; real game parsing for that size is an L3/L4 gate. Count is a protocol ceiling, never an operational guarantee.

Administrator-configurable budgets may only tighten hard limits; diagnostics name actual and permitted bytes/count. Desktop policy initially proposes ≤2 MiB canonical, ≤3 MiB Lua, ≤1,000 exact variants; the default selection candidate is **100**, not a production safety claim. Optional stricter local policies are allowed. Overflow refuses the whole candidate before publication. The reference predicts exact expanded Lua lengths without allocating expanded source, then tests predictions against the serializer for eligible contract cases. It still builds a small candidate in memory: L2 must stream/count before retaining a large graph or disk publication.

[capacity-evidence.json](capacity-evidence.json) is eight targeted synthetic Python measurements, not a five-pair matrix. Dense has 60 available daily closes; sparse has four available observations across a 60-day calendar, not 60 rows with absent items. Profiles intentionally omit distributions. Capacity includes selection identity list repetition, calendar statuses, per-record hashes, existing shared observation refs and receipt/wrapper escape expansion. Hash timings are mean CPU over 20 repeated selection hashes in one process, not game timing or an optimization claim. Bytes are exact, not estimated. See the report for the table and M1.5 client evidence.

The 1,000-record cases exceed this proposal's manifest bound even though sparse total bytes fit desktop policy. This is a useful explicit refusal: the count ceiling does not promise every count/window fits. Do not raise the manifest limit to make the fixture pass. If a real product needs thousand-entry scopes, evaluate removing redundant membership fields or a separately hashed selection manifest in a future reviewed revision, with new hash vectors and client tests.

Real-client performance gates remain proposals: ~2 ms nominal slices, p99 ≤3 ms/max ≤10 ms, compile/load ≤10 ms, incremental steady heap ≤5 MiB, old+candidate transient ≤16 MiB and owner-approved readiness (candidate ≤5 s). No such bound is established by this proof. Existing M1.5 dense-1k cost ~27 s CPU and ~112 ms median offline compile; 100 dense variants still need real measurement. Global Lua GC, timer cadence, compiler and other addons can defeat cooperative slice targets. Do not force GC or alter runtime budgets during L1.

## Shared fixture coverage and reproduction

`SHA256SUMS.json` hashes 15 authoritative payload files: two schemas plus 13 JSON fixture documents (11 source/request/generation/receipt examples, independent expectations and a table of 18 negative mutations). Original v1 fixtures remain unchanged. `build_fixtures.py` regenerates the 11 examples deterministically; independent arithmetic expectations and negative cases are authored separately. Schema 3 never recomputes independent pricing expectations from its own output.

| Required case | Evidence |
|---|---|
| Two selected priced variants | scoped items 10001/10002, exact 100 copper; independent expectations |
| Selected absent date / historical-only | item 10000 priced first date, absent current/second close |
| Missing observation date | November 14 has no observation or daily row |
| Bid-only | item 10003 supply ten, zero priced supply, null price |
| Exact mismatch / valid excluded | negative fixture; item 10005 remains only in full source; same-base different-variant unit test |
| Duplicate / invalid market / future schema / corrupt hash | closed schemas plus negative mutations, independently rehashed semantic negatives |
| Missing required close | negative retains other rows/hashes, omitted eligible date refused |
| Oversized copper / unsupported numeric conversion | signed-64 overflow refused; valid signed-64 descriptive string retained and Lua conversion refused |
| Byte budget / incomplete generation | exact boundary and one-byte-over tests, missing record negative, targeted capacity refusals |
| Legacy schema 2 | exact source fixture represented canonically, original byte-hash manifests unchanged |
| Equivalent order / different windows | sort distinct selections; same selection ID, changed request/generation digests for changed window |
| Previous after failures | Python/Lua activation tests retain active/previous on invalid or over-budget candidates |
| Unknown coverage / unknown is not zero | inherited partial fixture, null current supply, incomplete-only date; zero-insertion negative |

Run from Market root:

```sh
python3 -m unittest discover -s contracts/bridge/scoped-l1 -v
python3 contracts/bridge/scoped-l1/capacity.py > /tmp/scoped-l1-capacity.json
```

Timing values vary between runs; compare exact byte fields/statuses rather than byte-comparing CPU timings. TwichUI mirrors only authoritative schemas/fixture payloads and the hash manifest, pinned to the Market fixture commit; its offline Lua proof reuses actual `BridgeCodec`, `BridgeValidate` and schema-2 plans, with **no runtime file edits**. The pure expanded test-schema plan is trusted harness code, not server-supplied executable data. Data bytes pass through existing strict parsing. No simulator, game assets or installation is necessary. See [milestone report](../../../docs/workshop-scoped-bridge-l1.md) for exact test results and L2–M2 plan.
