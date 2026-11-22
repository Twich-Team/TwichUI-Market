# Workshop split projection contract 3

Explicitly negotiated `GET /api/v1/workshop/markets/{id}/summary?contract_version=3`.
The default is still 1; contracts 1/2 and their immutable outputs stay available.

A canonical generation manifest binds both projections and all original market,
source-observation, exact-variant, algorithm, freshness, confidence and coverage
semantics. Current rows are the unchanged first thirteen columns of contract 2,
including precomputed market/historical references and coverage. Historical rows
retain all fourteen contract-2 fields and actual daily closings. No prices are
recalculated or variant identities collapsed.

`partitions` describes current rows at `/parts/{bucket}`. `history_partitions`
describes rich rows at `/history/{bucket}`. Both have the same ordered modulo-64
bucket/record counts. Projecting each history row to its first thirteen columns
and canonical-encoding the array MUST produce the current descriptor's digest.
Consumers validate this binding when history is decoded; native delivery verifies
it before committing any root. Each independently consumed part still requires
its own size/hash/canonical/schema/evidence validation. A shared manifest digest
alone is not permission to skip payload verification.

Current bounds: 1 MiB per part, 32 MiB total. History retains 1 MiB per part,
64 MiB total, sixty observed UTC dates, 150,000 exact current variants. The manifest
remains bounded to 64 KiB. Overflow refuses the generation; nothing is silently
truncated. Database export positions 0..63 are current and 64..127 are history;
public bucket numbers remain 0..63. No schema migration or source-history deletion.

The compatible companion writes separate current/history load-on-demand folders
under the same inactive A/B bank, verifies/readbacks both, then commits one root.
Cache checkpoints, 304 and resumed parts remain bound to the negotiated contract
and complete generation. A current-only or mismatched pair MUST NOT publish.
The addon can use verified current bytes without loading history. Rich history is
verified lazily and never mixed with a different active generation.

Activation after review: server supports 3 with default 1 unchanged; compatible
companion adds capability negotiation; new addon advertises split support. Older
companions ignore the additive capability and deliver 2. Older addons request 1/2.
Unsupported schemas fail closed with update guidance. Restore a previous compatible
generation using the compatible companion before downgrading it; do not manually
combine bank files. No services, clients or addons are deployed by this PR.

Rebuild the synthetic fixture with the production sealer:

```sh
DATABASE_URL=sqlite:// python scripts/build-workshop-current-fixture.py > /tmp/current-fixture.json
```

The producer PR is independent of Companion/addon implementation and does not
activate contract 3 for any existing client. Native and Lua paired tests belong
to their follow-up review checkpoints.
