# M1.5 evidence inventory

[Acceptance report](../../workshop-bridge-m15.md) explains scope, frozen sources, tables and limitations. All observations here are synthetic or offline diagnostic measurements. None establish production-history or real-client acceptance.

- `capacity.json`: completed final matrix, five interleaved matched pairs per accepted shape, every sample, summaries/ranges/MAD, noise decisions, source/binary hashes, CPU/wall time, RSS, Lua heap, load/compile, cache, navigation and worst slices. The over-cap shape is a preflight refusal, not a server export.
- `baseline-reproduction.json`: original 1,000-record workload, three exploratory reproduction samples.
- `exploratory-index-pairs.json` and `exploratory-checksum-pairs.json`: earlier five-pair comparisons. They are retained, including unfavorable tails; they do not replace final-matrix samples.
- `exploratory-*-candidate.json`: intermediate allocation/scheduling/index/checksum observations. These predate the frozen final source and are diagnostic only.
- `exploratory-profile-baseline.json`: exclusive phase attribution with instrumentation overhead.
- `exploratory-quantum-profile.log`: intermediate normal/no-GC diagnostics. No-GC is an offline experiment only. These samples do not establish a hard runtime slice bound or sole cause.
- `server.json`: disposable SQLite and actual authenticated ASGI requests, with imports, cold/warm materialization, query counts and RSS separated.
- `compatibility.json`: old Lua/new compact artifact, new Lua/legacy artifact, candidate native readback over legacy staging, actual compiled injection sentinels and corruption/local-state checks.
- `e2e.json`: independent shared fixtures through actual authenticated HTTP → Rust client/cache/export → actual Lua reader.
- `verification.json`: source/fixture identities and completed correctness/regression results; links to the addon full-run and negative-control evidence.

Measurements were not removed when slower or larger than desired. Runtime-changing exploratory experiments are labeled separately rather than blended into the frozen comparison. No additional benchmarking campaign is needed for review; unresolved scheduling redesign is a separate follow-up.
