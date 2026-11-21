# Retained history archive — protocol 1

This API mirrors **all currently retained observation metadata and unique snapshot price/supply summaries** for one authorized market and explicitly chosen pricing algorithm. It does not copy every raw auction listing, distribution or metadata-provider response. Intraday observations remain individually addressable; repeated references to one snapshot share its evidence. The desktop retains older completed evidence if later server retention changes.

This is a separate versioned archive protocol. It changes no bridge-v1/schema-1/schema-2 semantics or limits. WoW delivery remains the approved [schema-3 selection contract](../../bridge/scoped-l1/README.md): contract 1, transport 1, required `scoped_selection`. The [closed JSON schema](archive.schema.json), [producer](../../../backend/market/archive_api.py), and [strict Rust wire checks](../../../desktop/core/src/archive/wire.rs) define this archive. JSON schema validates structure; the semantic/hash/transaction checks below are also mandatory.

## Authorization and endpoints

Use the existing device bearer authorization. Native companion permissions grant only the new GET checkpoint/pages and POST scoped paths; browser administrator permissions are not inherited. Existing verified market membership rules remain authoritative. Checkpoint identity includes account, authenticated desktop device (stable across access-token renewal), full market identity, algorithm, protocol and source watermark. A legacy device token uses its own credential identity. Revocation stops subsequent requests. No token, password, refresh secret or credential payload enters exported history/Lua.

- `GET /api/v1/archive/markets/{id}/checkpoint?algorithm=twichui-pricing-v1[&base={checkpoint}]`: prepare or return an immutable checkpoint envelope. Provisional `asking-v1-provisional` is an explicit alternative, never an automatic canonical fallback.
- `GET /api/v1/archive/markets/{id}/pages?checkpoint={id}&cursor={opaque}[&limit=100]`: bounded ordered evidence page. Page-size choice changes only batching, not the query or selected evidence.
- `POST /api/v1/archive/markets/{id}/scoped?checkpoint={id}`: approved L1 selection JSON, at most 128 KiB; deterministic source-sealed schema-3 generation or structured refusal. No production addon consumer is activated by this endpoint.

Missing canonical derivations are prepared by the existing bounded original-listing pricing code. One unique snapshot/digest is prepared per cold request. More work returns HTTP 202 with exactly `{"state":"preparing","retry_after_seconds":1}`; completed preparation persists. Canonical originals that were not retained cannot be fabricated from legacy means. Such a request refuses; provisional history requires a separate explicit algorithm request and cache scope.

A checkpoint is created only after the pinned evidence is ready. Repeated equivalent requests within its UTC day reuse a valid checkpoint. New observations, different base/context, retention membership or a new UTC as-of day require a new checkpoint. No route invokes collection or metadata providers.

## Checkpoint and evidence integrity

The header supplies protocol/evidence revision 1; account and issuer; full bridge market identity; algorithm/history basis; immutable observation watermark and UTC as-of; retained first/last UTC day; server checked-at/build; explicit retention layer; full and transfer observation/snapshot/variant counts and bytes; base checkpoint/watermark; metadata SHA-256; checkpoint identity and expiry. Nullable values are required explicit nulls. Unknown fields/versions refuse.

`archive_complete=true` describes the **source checkpoint's complete retained layer**. A staged client is never complete merely because it received that header. A desktop completion timestamp exists only after all pages, graph/counts/digests and durable promotion succeed. Absence of history before the retained range says nothing about observations that were never collected or no longer retained.

Evidence is ordered by phase:

1. Observation metadata, increasing numeric observation ID. Each carries exact UTC timestamp/day, snapshot reference/content hash, source payload hash, namespace, upstream provenance, synthetic status and market-scope completeness.
2. Unique snapshot descriptors, increasing numeric snapshot ID. Each carries source content hash, record count, canonical record-byte count and SHA-256.
3. Variant summaries, increasing `(numeric snapshot ID, numeric item ID, full variant SHA-256)`.

A variant entry preserves canonical `variant_json` where retained, exact identity, and `state`, `supply`, `priced_supply`, `listing_count`, `minimum_listing_copper`, `recent_copper`, `quantity_weighted_ask_copper`. Distribution arrays are intentionally outside this archive profile. Exact copper remains decimal text; unsupported canonical/Lua arithmetic remains unsupported. This is asking-price/supply evidence, never completed sales.

Canonical JSON is the frozen bridge encoding: ASCII escaped, sorted object keys, compact separators, integers only, no duplicate JSON keys or executable values. SHA-256 definitions:

- Snapshot `records_sha256`: concatenated canonical variant entries for that snapshot in order, **one LF after each entry**. `records_bytes` includes those LF bytes.
- `metadata_sha256`: concatenated canonical observation entries then snapshot descriptors in phase order, each followed by LF. This root covers every snapshot record digest as well as every observation's provenance.
- Page `page_sha256`: canonical JSON array of this page's entries, without added LF.
- Page chain starts with 32 zero bytes. Next chain is SHA-256 of the previous **binary** 32-byte chain plus canonical page-entry array.

Each page includes checkpoint/account/market, exact offset, previous/page/chain hashes, `has_more` and required nullable next cursor. Signed opaque cursors bind authenticated account/device, market, checkpoint, protocol/domain, keyset, offset, chain and expiry; source algorithm/query are fixed by that checkpoint. Tampering or mixing context refuses. No deep OFFSET scan is used.

The desktop verifies strict record types/order, exact variant-descriptor hashes, integer/copper ranges and page continuity before transactionally advancing the cursor. Final validation reconstructs the full metadata root, counts, retained date bounds, observation→snapshot content-hash graph and every transferred snapshot's record count/bytes/hash. An immutable old row cannot change during an incremental update. Active checkpoint membership is explicit; retained evidence from another checkpoint cannot silently fill a source gap. Projection additionally checks snapshot membership counts before turning selected-item nonmembership into absence.

## Incremental updates and recovery

A base must belong to this authenticated desktop/account/market/algorithm. New observation IDs transfer even when their observed UTC dates are old (late imports). A revised provisional day is a new observation/snapshot, not an overwrite. Reused snapshots transfer only the new observation. Newly referenced snapshots transfer their descriptor and all summary evidence exactly once. A new full metadata root seals both old and new membership.

The base's retained observation prefix must still match. Retention changes, missing evidence, unavailable/expired page checkpoints, invalid cursors and wrong context return HTTP 409. The native client abandons only staged state and attempts a fresh bootstrap, with a bounded reset count; it does not discard completed history. Source errors/corrupt data/capacity failures preserve active and previous state. Replayed pages cannot advance a persisted cursor twice. Interrupted processes resume from their committed cursor and chain.

Download cursors expire after 24 hours. Completed desktop data remains usable offline after that time. Server base metadata is normally retained up to seven days; pressure can reclaim **expired** checkpoints sooner. Equivalent requests reuse existing metadata, and active peer downloads are never evicted for a new request. An unavailable base causes a full checkpoint bootstrap without deleting older desktop evidence. When a source checkpoint legitimately excludes pruned source observations, those older locally retained rows remain on disk and the prior completed pointer remains available; the new generation uses only its own pinned membership.

## Resource and storage policy

These archive bounds are distinct from all WoW bridge limits:

| Layer | Initial implementation bound |
|---|---:|
| Retained source checkpoint | 100,000 observations; 4,096 unique snapshots; 100,000,000 normalized summary entries |
| Source metadata per checkpoint | 64 MiB |
| Disposable checkpoint metadata across service | 512 checkpoints / 256 MiB; refuse storage pressure without evicting unexpired peers |
| Transfer bytes per checkpoint | 1 TiB safety ceiling; practical desktop disk policy is much smaller |
| Page / entry | at most 100 entries / 1 MiB page / 64 KiB entry |
| Source database operation | existing advisory retention/ingestion lock; PostgreSQL 10-second per-statement timeout; no collector calls |
| Desktop archive | default 4 GiB; explicit manual budget 64–65,536 MiB |
| Detailed working-set policy | default 100 variants; 2 MiB exact canonical / 3 MiB exact Lua |
| Existing absolute bridge bounds | unchanged: 32 MiB canonical / 130 MiB Lua; schema-3 manifest 256 KiB and selection ceiling 1,000 |

The archive's 100-million-row guard allows retained intraday evidence without confusing it with the 1,000-record WoW scope ceiling. It is a refusal bound, not measured capacity. There is no unlimited-storage claim. Real retained composition and chosen disk policy still need genuine-history acceptance. Initial server preparation is bounded by one existing snapshot operation, not a demonstrated whole-request CPU deadline on every possible 150,000-listing shape.

SQLite is a new, separate `history-archive-v1.sqlite` (`user_version=1`), preserving the installed scalar and `bridge-v1.sqlite` stores. Tables: `history_headers` (staging/active/previous plus cursor/chain/completion), `history_entries` (immutable normalized evidence with checksum), `history_stage`, `history_members` (checkpoint-specific observation/snapshot membership), and private `history_selections`. Scope keys include origin/account/market/algorithm. Data uses WAL, FULL synchronous writes, indexed exact identity/time/day access and a set-based promotion transaction. A newer schema refuses without downgrading/reinitializing it; structural corruption fails closed.

Before staging, the client estimates transfer storage; this is not an exact SQLite allocation prediction. Every page and final promotion also checks actual allocation/WAL, a 16 MiB free-space reserve and SQLite page limits. SQLite-full errors roll back cursor/progress. No required history is silently pruned. Old immutable evidence and reusable freed pages remain on disk; selection replacement never deletes archival evidence. Increasing a disk budget can allow a pending download to resume. Backups, full physical-device failure and production backup/restore acceptance remain operational gates.

## Scoped projection and manual publication

Server and desktop independently reproduce the same approved schema-3 generation from the pinned archive. Exact selection sorting/hashing, complete eligible UTC daily closes, current provisional state, supporting reference observations and source integrity reuse the approved L1 and canonical pricing primitives. A known historical-only identity can resolve from older retained evidence; a completely unknown exact identity refuses before it can become an absent item. Supported projection is an explicitly requested window within the latest 60 UTC days, without silently shortening it. The archive itself retains older evidence.

`scope.scope_complete=true`, `scope.whole_market_complete=false`, and `coverage.generation_complete=false` remain explicit. Every requested identity appears; `excluded=[]` means none was silently omitted. Unrequested identities are `outside_scope`, not zero or absent. A complete source observation may prove absence; incomplete/missing source coverage cannot. Bid-only supply has no invented price. Unsupported arithmetic remains explicit. Distribution sections are explicitly omitted by `daily_research_v1`.

Count preflight precedes materialization. Exact final canonical/manifest/Lua byte checks precede publication. Dense histories can fail byte budgets even with a permitted count. Refusals identify the exceeded limit and actual/allowed values; no pruning, alternate identity, shorter window or partial-success fallback occurs. Generation source hashes stay independent of the validated desktop delivery receipt. The receipt is minted after validation, identifies its generation, and cannot predate source generation time.

Manual companion controls download/resume, persist exact selections, preview actual sizes and export only to controlled companion staging. Existing fixed assignment grammar, strict escapes, TOC, path ownership, symlink/junction/reparse/ACL checks, flush/sync, readback, atomic replacement and `Previous.lua` retention are reused. No executable server code, SavedVariables declaration, arbitrary destination, game discovery, installation or reload exists. Corrupt/unowned existing files refuse replacement. `Previous.lua` is not loaded automatically by the TOC.

Current production Workshop accepts schemas 1/2, not 3. The manual panel says so and requires an explicit testing acknowledgement for scoped publication. Old desktop/server/consumer combinations keep their legacy path or refuse unsupported schema; schema 3 is never rewritten as a legacy complete market. Files changed on disk do not change an already loaded addon. L3 and real Windows/Forever acceptance are separate milestones.
