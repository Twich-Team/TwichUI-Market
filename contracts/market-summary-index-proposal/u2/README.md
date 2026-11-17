# U2 exact identity resolution — inactive interface

[Implementation](../../../scripts/advisor_identity.py) ·
[provenance corpus](corpus.json) · [report / U3 boundary](../../../docs/advisor-identity-u2.md)

U2 consumes U1 identities without changing its manifest, tuples, 64 routes or
256 KiB cap. There is no active server, Companion, addon consumer, pricing hook or
approved native equivalence registry. Its defaults **cannot resolve a native
variant exactly** without independently approved equivalence evidence.

## Trust and canonical model

`Resolver(expected_context, candidate_bundle, expected_bundle_sha256=pin,
trusted_equivalences={approved_digest: proof})` builds one bounded per-item resolver.
`resolve(identity)` / `resolve_link(link, item_id=..., item_key=...)` return a result.
All inputs are snapshotted, so later caller mutations cannot alter validation.

Three inputs must come from a separate trusted caller boundary:

1. `expected_context`, selected from the validated/pinned U1 manifest and an
   independently verified compatible player market.
2. An expected hash for this item's complete candidate bundle, established by a
   future trusted identity-metadata delivery boundary.
3. The exact approved equivalence content/pins. Provenance strings, a source's
   self-asserted verification flag, and `identity_complete=true` are not authority.

Hashes detect corruption and scope mistakes; they do not authenticate issuers or
prove the underlying equivalence. The caller must never fill the trust registry
from the same untrusted candidate response. The only positive registry in U2 is
constructed in synthetic tests. No production/native approved entries ship.

Normalized game identity is a closed object:

```json
{"item_id":2589,"attributes":{"item_key":{"itemID":2589,"itemLevel":0,"itemSuffix":0,"battlePetSpeciesID":0}}}
```

**This example is synthetic**, not a declaration that zero fields prove the real
base variant. Positive item IDs are integers `1..2^31-1`. `attributes` may contain:

| Attribute | Representation | Verification status |
| --- | --- | --- |
| `item_key` | All four native names shown above; exact integers | API shape source-verified; upstream equivalence unverified |
| `link_fields` | Entire colon-split numeric token array, starting with item ID; empty strings retained | Body/ID extraction source-verified; field layout not established |
| `suffix_id` | Signed integer or null | Explicit adapter observation only; no automatic link-position mapping |
| `random_property_id` | Signed integer or null | Explicit adapter observation only; upstream correspondence unverified |
| `bonus_ids` | Ordered positive integer array or null | No inferred ordering, defaults or cross-format equivalence |
| `modifiers` | Ordered `{type, value}` integer records or null | Unique type IDs; no inferred normalization/equivalence |

Absent attributes mean unobserved, not zero/empty. Explicit null is unknown and
prevents exact resolution. Zero/empty arrays are distinct asserted values and
need their own approved evidence. Unknown attribute names are unsupported.
Contradictory item IDs/suffix inputs, duplicate modifier types and malformed
values fail. Raw link fields are not interpreted as a second semantic layout.

`parse_link` accepts bounded `item:<fields>` and framed `|Hitem:...|h[name]|h`
(with optional color/reset). It extracts ID and preserves **all** fields,
including suffix-like values, empty fields and unknown tails. Names/colors do not
participate. It does not translate field 7 into an upstream random suffix or
field 13 into an upstream bonus list. A truncated link, extra field or changed
field cannot match the old complete proof. The helper accepts a strict numeric
subset; future native nonnumeric link extensions require reviewed support and
currently fail closed. No Blizzard source is copied into this package.

Context uses the existing U1 names/definitions unchanged:
`generation_id`, `issuer_id`, full `market`, `pricing_algorithm`, `history_basis`,
`source_kind`, `confidence_ceiling`, `can_satisfy_local_competition`.
All fields must match exactly. The established market object contains game,
region, player_ruleset, house_id, source_kind, server_market_id,
transport_ruleset_id, mapping_verified, mapping_evidence_sha256 and realm_scope.
Both expected and supplied contexts require a verified mapping, known ruleset and
intact 64-hex evidence reference. The caller must verify the actual mapping
receipt/authority; U2 has no database and cannot re-establish that evidence.
Transport aliases and display labels are not market identity.

## Candidate and equivalence inputs

A candidate bundle is closed:
`{context, item_id, complete, candidates}`. `complete=true` asserts the authoritative
candidate set delivered for that item at that exact generation. Partial sets are
refused. Each candidate has:

- `variant_key`: exact lowercase 64-hex hash.
- `variant_json`: full canonical upstream JSON descriptor text, or null for hash-only.
- `identity_basis`: existing `exact_upstream` or `hash_only` vocabulary.
- `evidence_status`: `supported`, `historical_only`, `unsupported`, `unavailable`.

The original frozen serializer verifies `variant_json`, its item ID and SHA-256.
Every upstream descriptor member participates, including unknown members. Dictionary
keys sort, but array order, missing members, zero and empty arrays do not normalize
into one identity. A descriptor is never reconstructed from only an item ID.
Duplicate candidates are invalid, even if repeated identically. Hash-only candidates
cannot supply a reversible descriptor and cannot produce an exact result here,
even with an independently known descriptor proof. Historical-only/unavailable/
unsupported candidates are refused as a conservative U2 policy, without implying
absence or erasing retained history.

An approved equivalence is closed:
`{format, issuer_id, market, game_identity, variant_json, identity_complete, provenance}`.
Format is `twichui-item-equivalence-u2`. The entire normalized game identity maps
to one complete canonical upstream descriptor, qualified by issuer and full market.
`identity_complete` must be true, with nonempty known game attributes. Provenance
is `{classification, reference}`, classified as source_verified, recorded_upstream,
repository_fixture or synthetic_control. These labels describe provenance, not trust.

Approval must establish that the entire stated game attribute set identifies that
upstream descriptor and excludes other price-relevant variants. U2 provides no
wildcard matching, per-field translation profiles or automatic approvals. Extra,
missing or reordered observed attributes cannot silently match a smaller proof.
Two approved proofs for the same game signature but different descriptors are
ambiguous even if only one target happens to be delivered.

This is a bounded exact-vector foundation. Generalizing to verified normalization
profiles or broader variant coverage requires new authoritative evidence; it is
not implied by the synthetic positives.

## Outcomes and algorithm

Every result contains `status`, stable `reason`, nullable `identity`, nullable
`generation_id`, and sorted `evidence_ids`. Only exact has a nonnull
`identity={item_id, variant_key}`. It contains no price, action, proceeds or supply.

| Status | Meaning / representative reason |
| --- | --- |
| `exact` | One supported descriptor and approved complete equivalence; `trusted_descriptor_equivalence` |
| `ambiguous` | Multiple unverified possibilities or conflicting approved mappings |
| `insufficient_identity` | Missing attributes, unverified equivalence, or incomplete candidate set |
| `unsupported` | Unknown attribute, hash-only target, historical-only/unsupported/unavailable candidate |
| `unverified_market` | Mapping missing/unverified, market/issuer mismatch, equivalence market mismatch |
| `not_found` | Item outside this bundle or exact identity not delivered; **not market absence** |
| `invalid_input` | Malformed identity, link, descriptor, hash, duplicate, corrupt pin, or mixed generation/contract |
| `unavailable` | Candidate evidence unavailable |

Construction validates/pins all source inputs once. Lookup validates one bounded
identity, finds its exact approved game signature, requires one descriptor target,
checks the corresponding exact candidate and returns the existing hash. It hashes
only the independently established upstream descriptor; it never hashes a game
link to guess Market identity. No item-ID aggregate fallback exists.

Limits: one item/generation, 128 candidates / 64 KiB bundle, 32 proofs / 64 KiB
trusted registry, 4 KiB game identity and each descriptor, 1,000-byte link,
64 raw link fields, 32 bonus IDs, 16 modifiers, frozen serializer depth limit 12.
Oversize/malformed sets refuse; they are never pruned. Callers must bound decoding
before passing in-memory objects; these APIs bound serialized/retained inputs,
not arbitrary allocations already made by a caller.

Resident state is O(bounded candidates + proofs); lookup serializes/validates one
small identity and allocates a result. It scans no U1 partitions, other items or
markets. The [test-only adapter](../../../scripts/tests/advisor_identity_support.py)
loads one item's candidate metadata keyed by item, `item_id % 64`, generation;
then calls U1 lookup only for exact resolution. U1 availability/confidence and
corruption failure remain authoritative. Missing summaries remain unavailable.
The adapter and synthetic fixture helpers are not runtime delivery infrastructure.
