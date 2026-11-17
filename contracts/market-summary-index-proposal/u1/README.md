# Inactive U1 partition foundation

`manifest.schema.json` is a separate experimental envelope named
`twichui-market-summary-partitions-u1`, schema 1, `experimental=true`.
It is **not** a production protocol/capability. No API, Companion, scheduled job,
installer, addon manifest or pricing default references it.

The original L2 proposal, schema, sizing implementation and fixtures remain
unchanged. U1 references its metadata definitions and uses exactly its nine tuple
columns, state codes, confidence codes and canonical copper range. The new
manifest removes the monolithic `records` / `records_sha256` fields, permits zero
records, describes independently hashed partitions and permits explicit partial
retained-universe coverage. This does not redefine detailed-history schema 3.

Implementation: [offline library](../../../scripts/advisor_summary.py).
Evidence and the future consumer boundary: [U1 report](../../../docs/advisor-summary-u1.md).

## Input and projection

`write_index(records, metadata, new_directory)` consumes a strictly ordered,
unique `(item_id, variant_key)` stream. Records contain `observation_id`,
`item_id`, `variant_key`, and optional `current`. The current object uses existing
`bridge_api.assemble_record` field names: `algorithm`, `state`, `complete`,
`arithmetic_status`, `supply`, `metrics.recent_copper`,
`metrics.market_value_copper`, `metrics.minimum_copper`. Extra detailed-history
fields are ignored; the producer neither needs nor constructs history.

Metadata is the manifest's shared metadata without `partitioning`, `partitions`,
`record_count` and `generation_id`. It must include all original proposal metadata,
with the U1 format name. `schema_version` remains 1 within this separate format.
The benchmark's `metadata()` / `records()` functions provide executable synthetic
examples. The source fixture projection test also uses the real existing canonical
bridge contract fixture, without importing application/database code.

The caller must pin the input iterator to one exact issuer, market, algorithm and
source observation/watermark. In a later database/archive adapter, validate the
observation reference against that snapshot before assigning `observation_id`.
The exporter verifies the per-record observation ID and algorithm; it cannot
independently prove that an upstream iterator supplied all retained identities.
`coverage.complete` is that caller's explicit assertion. No active adapter exists.

A complete listed record projects the supported existing metrics without price
calculation. A missing `current`, incomplete current, or incomplete observation
projects `unknown`, null prices and null supply. Complete absence alone projects
`absent` with zero supply. Unsupported arithmetic projects `unsupported` with
null prices/supply. Missing essential metadata/identity, mixed observations or
algorithms, malformed money and contradictory supported supply fail the export.

## Exact output

Partitions are canonical JSON arrays of fixed tuples:

| Position (1-based) | Field | Meaning |
| --- | --- | --- |
| 1 | `item_id` | Positive signed-32-bit ID |
| 2 | `variant_key` | Exactly 64 lowercase hex characters; upstream exact variant hash |
| 3 | `state` | 0 priced, 1 supply_only, 2 absent, 3 unknown, 4 unsupported |
| 4 | `recent_copper` | Supported ask-derived recent reference, decimal text or null |
| 5 | `market_value_copper` | Existing canonical Market Value, decimal text or null |
| 6 | `minimum_copper` | Observed minimum ask, decimal text or null |
| 7 | `supply` | Observed total variant quantity; integer or null |
| 8 | `age_seconds` | Floor of generated_at minus source observed_at |
| 9 | `confidence` | 0 limited, 1 unavailable; price confidence, never confirmed sale confidence |

Supported money remains `1..99,999,999,999` copper. Values above the existing
pricing ceiling, including integers beyond IEEE-double precision, cannot be
smuggled through as supported canonical prices. They fail unless upstream marks
arithmetic unsupported, in which case no price is exported. Zero/float/exponential
or noncanonical decimal representations fail. Supported large values are text
throughout; there is no float conversion.

Shared fields: `format`, `schema_version`, `experimental`, full `market`,
`issuer_id`, `pricing_algorithm`, `history_basis`, `source_kind`,
`confidence_ceiling`, `can_satisfy_local_competition`, `source_watermark`,
`source_observation` (observation_id, observed_at, scope_complete), `generated_at`,
`identity_basis`, `columns`, `states`, `confidence_states`, `coverage`,
`record_count`, `partitioning`, `partitions`, `generation_id`.

`market` preserves game, region, player_ruleset, house_id, source_kind,
server_market_id, transport_ruleset_id, mapping_verified,
mapping_evidence_sha256, realm_scope. A verified mapping requires actual ruleset
and evidence. Unverified mapping remains explicit and cannot authorize a game
consumer's market choice.

`coverage` contains type `all_retained_exact_identity_summaries`, boolean
`complete`, missing `unavailable`, and detailed_history `independent`.
Retained-universe coverage, observation scope completeness and supported price
availability are independent. Even an absent bucket or a missing row in a fully
delivered, complete snapshot returns unavailable; the reader never infers absent
or zero from missing membership. There is no claim of a universal item catalogue.

`source_kind=market_server_asking_summary`, `confidence_ceiling=limited`,
`can_satisfy_local_competition=false` are mandatory. Supply-only has unavailable
price confidence (the unchanged L2 code); absence/unknown/unsupported also have
unavailable price confidence. There are no vendor, sale, disenchant, local
competition or guaranteed-proceeds fields.

## Partitioning and integrity

Route with `item_id % 64`. The manifest lists only occupied buckets in ascending
order; each file retains strict `(item_id, variant_key)` order. Related variants
are discoverable together without a whole-market hash table or descriptor index.
No display names, item-ID aggregate prices or detailed working sets participate.

Each partition descriptor has `bucket`, `file`, `bytes`, `record_count`, `sha256`.
The basename is `NN-<sha256>.json`. Its hash covers **all canonical file bytes**.
`generation_id` is SHA-256 of the canonical manifest excluding `generation_id`;
therefore it binds metadata, every part's content hash, routing, sizes and counts.
The reader requires an independently pinned expected generation ID. SHA-256 is
integrity/content identity, not authentication or permission to trust an issuer.
A future delivery protocol must establish that trusted pin separately.

Hard bounds: 64 buckets, 256 KiB per partition, 64 KiB manifest, 150,000 records.
The caller may lower the partition bound, never raise it. A skewed bucket refuses
the entire generation with bucket/item/limit details. Reviewed deterministic
subdivision would require a new explicit routing scheme; U1 implements refusal.
It never splits a variant, truncates a bucket or prunes identities. Empty markets
have zero parts and zero records.

The writer uses 64 buffered temporary disk spools, one record and at most one
bounded encoded partition at a time. Aggregate partition disk is at most 16 MiB,
plus manifest. It checks order, identity, state, arithmetic range and sizes during
the single pass, then renames the completed directory to a fresh destination.
Failure removes only its disposable staging and publishes no generation. Existing
generation directories are refused. This is a local offline artifact boundary,
not a crash-durable installer, network publisher or last-good recovery protocol.

The reference `Index` verifies canonical manifest bytes/schema/pinned hash and
checks sorted unique routes, safe content filenames, aggregate counts and bounds.
It verifies each requested part's size/hash/count/rows/order/route before using it.
A missing/corrupt part is an error; callers must present unavailable evidence,
never zero or absence. `verify_all()` validates sequentially without retaining the
complete index. `lookup()` caches one part and uses binary search; switching parts
releases its prior Python cache. Returned rows are copies.
