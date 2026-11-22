# Game-ready current prices: coordinated implementation

Owner-authorized development only. No merge, production service/data change,
signing, release or installed game-file change is authorized.

Baseline: Market main `e2882dd822b356ffa081efebbff167827f9bf364`; addon main
`b541c5b39f324c9d356cb3783cff67db1362787b`. Investigation and benchmark source:
[addon draft #127](https://github.com/Twich-Team/TwichUI/pull/127). Chart draft
[#117](https://github.com/Twich-Team/TwichUI/pull/117) remains independent.

1. Server: versioned, explicitly requested source-bound integrity sidecar and
   shared vectors. No economic formula, historical observation, schema migration
   or default summary negotiation changes.
2. Companion: independent native encoder/validator; safe deterministic current
   files, 16/32 opt-in layout, original history, A/B readback and rollback.
3. Addon: authenticated exact lookups/misses, bounded shared scheduling, visible
   demand priority and individual completion; preserve existing caches/engine
   and history APIs.
4. Integration: actual producer/native files/production Lua and Opportunities;
   compatibility, interruption/corruption, memory and matched 60-day benchmarks.

Stage 1 focused SQLite verification: `DATABASE_URL=sqlite:// python -m pytest -q
 tests/test_workshop_prepared.py tests/test_workshop_summary.py` (from `backend/`)
passes **36 tests, one existing PostgreSQL-only test skipped**, in 2.82 seconds.
The source-bound shared vectors and schema are included. No database, deployment
configuration, price formula, history bytes or release identity changes. The
first test expected auth 403 for an absent POST handler; the framework correctly
returned 405. The test now asserts that precise denial and separately checks
scoped authorization on existing routes. No production assertion was weakened.
Existing PostgreSQL-specific query behavior remains a separate required check.

See the [versioned contract](../contracts/workshop-prepared/v1/README.md) for the
exact source/encoding/hash boundary and explicit 4/32 MiB prepared bounds.
Oversized prepared projections retain the complete legacy format without pruning.
Actual Forever latency remains an owner-directed acceptance requirement, not
an offline timing claim.

## First hosted verification and correction

At `074abfc`, the Backend run `45057534987` passed 740 tests and failed seven
new prepared tests because their module did not import the existing autouse
`contract_bundle` fixture. Installed-package CI correctly refuses to discover
contracts from an arbitrary working directory. The fix imports that existing
fixture; production contract discovery is unchanged. An explicit missing-root
local reproduction fails before the fix and passes afterward. Full failed logs
are retained in the task workspace; no failed receipt is called passing.

Windows build/picker/signed-update verification and existing consumer acceptance
passed. The separate performance run `45057534933` failed in **baseline repeat 1**
with native `Error: Network`, after actual 202 preparation responses; the candidate
automatic-publication comparison did not complete. Its credential-free failure
artifact is `14768591665`. This is not a prepared-format performance result or
a passing baseline. Preserve the failure and the separate release gate.
