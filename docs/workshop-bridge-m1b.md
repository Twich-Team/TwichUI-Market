# M1b execution and integration boundaries

Owner authorization: implement the server → companion → data-only addon → Workshop bridge on isolated branches, publish separate draft PRs, and stop before deployment, automatic installation, default source switching or M2/M3.

## Foundation review

Market #7 is merged as `2f0b6c850a767c82fe176932326b8086589a3253` into `integration/companion-v2-metadata-recovery`; no newer owner-approved integrated companion branch supersedes it. The final M1a head `d39d329` passed Backend 43736623138, website 43736623123, Windows/signed update 43736623129. The legacy commit-status API had no statuses and returned pending; actual check runs were all completed/success. No failing check or protection was bypassed. TwichUI #21 then merged as `572da3a04fe1a64581b3d1cd0208038c0104cfe3` into `feature/workshop`; no PR workflows are configured there. Fresh review tests: Python 119 passed, addon fast market 14 modules passed, both golden generations valid, all nine mirrored files byte-identical with checked manifests. M1a adds no production migration, default pricing selection or local saved-history writes.

The old M1a workspaces and active `/workspace/TwichUI` are preserved. Implementation branches are `feature/workshop-bridge-m1` and `feature/workshop-market-bridge-m1`; detached review worktrees are separate from implementation worktrees.

## Reused boundaries and plan

1. Retain existing device identity/authentication and narrowly authorize two bridge GET routes. Materialize immutable bounded generations under the existing collection/retention lock; signed account-bound cursors page the stored records, so later collection or raw retention cannot mix pages. Versioned derived evidence and bridge materializations use additive tables only. No original observations or legacy sync results are rewritten.
2. Reuse Rust networking, credentials and SQLite patterns with a separate bridge database. Stage pages transactionally, validate complete integrity/identity before promoting, retain the previous completed generation, and expose a manual export action into the companion staging directory. Do not change schema-2 legacy caches or scheduling.
3. Produce a fixed data-only LoD addon with bounded quoted manifest/record strings and separate delivery receipt. Validate and publish outside game directories with atomic replacement and recoverable previous files.
4. Add an explicit, cooperative Workshop reader and a source-specific history adapter. Reuse current charts through explicit external source selection; do not change local Prices/History2/Valuation, Advisor, Sell, Shopping or CraftPlanner. Add registered diagnostics for loading, validation, record/history reads and retained caches.
5. Test a real authenticated HTTP download through Rust and generated Lua into the actual Workshop reader. Compare to pinned independent expectations, preserve gaps/provenance and local SavedVariables, exercise corruption/recovery, run mutation/property and full applicable regression verification, then publish draft PRs.

## Contract review amendment

See `contracts/bridge/v1/AMENDMENT-001.md`. The server cannot claim a future desktop completion timestamp inside an immutable generation hash. Schema 2 permits that value to be explicitly unknown; an actual desktop receipt is separate from the immutable source generation. Contract and transport remain 1; old schema-1 fixtures remain unchanged. Schema 2 also corrects the schema-1 overescaped fractional UTC timestamp pattern. Both fixes are coordinated across authoritative schema, validators, generated transport and pinned addon fixtures; older readers fail closed.

## Genuine evidence boundary

The authorized read-only public route still returns Cloud proxy 403 (November 15). The owner previously confirmed no alternate export path. Committed genuine November 14 listing excerpts may be replayed with their real provenance, but they are not full scopes or two-day retained history. Synthetic two-date/gap scenarios are explicitly synthetic. A manual authenticated read-only production acceptance procedure will remain open; no full 14/60-day or production acceptance is inferred.
