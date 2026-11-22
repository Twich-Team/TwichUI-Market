# PR2 compatible Companion delivery

Stacked on [producer PR #43](https://github.com/Twich-Team/TwichUI-Market/pull/43),
producer commit `b02a190f22fd403a35c0856dfb3c598cd0720bc7`. The paired addon is
[consumer PR #100](https://github.com/Twich-Team/TwichUI/pull/100), stacked on TwichUI PR #99. Contract definition: `contracts/workshop-summary/v3/`.
No service operation, deployment, migration, signing or client publication.

## Delivery and compatibility

The installed addon explicitly advertises `summary_current_contract: 3`, current
part/total bounds 1,048,576/33,554,432 bytes and the existing history capability/bounds
2 / 1,048,576 / 67,108,864. Unknown split versions/bounds refuse negotiation.
Older addons retain negotiated 1/2, and older companions can deliver 2 to the new
addon. Fixed same-origin authenticated requests select contract 3 without accepting
arbitrary query strings or redirects. A cached 304 must match that exact contract.

Internal cache keys 0..63 store current and 64..127 rich history. Public routes
remain bucket 0..63 under `parts/` or `history/`. Both projections must match their
own size/hash/canonical/schema/evidence constraints and history must project to
the current digest. Missing/mismatched pairs never activate the private cache.
Matching validated interrupted parts resume; rich bytes can safely reuse a
contract-2 cache during migration, and vice versa, after validation against the
new descriptors. Source/account/market/issuer controls remain intact.

Each bank uses `TwichUI_MarketPartA00` through A63 (and B) for current, plus
`TwichUI_MarketHistoryPartA00` through A63 (and B) for history. These are 64 logical
buckets per projection, up to 256 physical A/B partition folders plus the root.
Current addon TOCs never include history payloads. Both sets are fully written,
read back and verified before the single root replacement. Ownership/permissions,
unknown-file refusal, available-space checks, previous root and SavedVariables
protections remain. The capability is rechecked before publishing/restoring 3,
so an addon downgrade during preparation cannot authorize unsupported data.

Cancellation tests exposed an existing mkdir-before-marker recovery gap. The
publisher now resumes an empty generated directory only; any unowned payload or
unknown file still refuses. Nothing is deleted or silently adopted with contents.

Rollout after review: producer support with default 1 unchanged, compatible
Companion, then addon capability activation. Pause automatic delivery before
rollback. Restore a previous compatible 1/2 generation with the new Companion
before downgrading the addon/Companion. If none remains, keep the new Companion,
install the old addon to negotiate 1/2 and complete that sync before downgrading
the Companion. Resume delivery only with a supported pair. Do not mix bank files or
manually edit roots. The existing private signed updater/release state is unchanged.

## Verification

Linux Rust workspace: 139 tests pass, one pre-existing optional profiler ignored.
This includes complete-pair corruption after rehash, source/variant/evidence
checks, interrupted history download and current-part reuse, migration history
reuse, bound 304, cancellation at each pre-root write, missing bank files,
no-op readback, rollback, unknown contents, ownership and saved-data sentinels.
The first new run caught an interrupted empty-directory recovery defect (fixed)
and a test token that did not match the existing HTTP server fixture (corrected).
All original native assertions remain.

```sh
cargo test --manifest-path desktop/Cargo.toml --locked --workspace --jobs 2
cargo run --manifest-path desktop/Cargo.toml --locked --example workshop_fixture -- \
  contracts/workshop-summary/v3/fixtures/synthetic.json /tmp/new-current-fixture
```

The actual production sealer's fixture was validated/assembled by that native
example, then consumed by the production Lua reader using the existing paired
benchmark, with `WORKSHOP_SUMMARY_ARTIFACT`, `WORKSHOP_SUMMARY_PARTS`, and
`WORKSHOP_SUMMARY_EXPECTED_ITEM=2589`. Current enumeration/value queries load zero
history; explicit history reads load one rich part with the original observations.
This paired test caught a Lua nil-global fallback that could confuse current and
history before the first history addon load; it is fixed and covered in the addon
unit test. It does not prove Windows NTFS/UAC or real Forever behavior.

## Completed coordinated CI and benchmark evidence

At `0ed2edaa5d5fd03eb22501522f6e6dda4a619fa0`, [Windows CI and its artifact
consumer passed](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44975496335),
including actual authenticated contract-3 publication in a disposable Windows
installation (129 variants), then the exact production Lua consumer `c70566f`.
All 64 current buckets load without historical bytes; explicit history loads one
rich bucket. Existing contract-2 installed/large publication checks also pass.
Backend PostgreSQL and website checks pass. This is automated Windows fixture
acceptance, not a physical owner-PC, actual Forever, or signed release claim.

The separate [sync-performance job remains failed](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44975496301):
the frozen baseline executable returns `Error: Network` before the candidate,
with Windows reset 10054, final summary 202/Retry-After 5, server alive and no
request in flight. Cause unresolved; no assertion or retry policy was weakened.
Other price/archive benchmark stages passed. This is an explicit review
limitation, not a fully green integration declaration.

[Consumer PR2 report](https://github.com/Twich-Team/TwichUI/blob/fix/v2-market-cold-pricing/docs/performance/v2-market-cold-pricing-pr2.md)
retains exact commands/source/harness hashes, all samples and limits. In the
30,000-variant/60-day uneven native-file test, current enumeration CPU falls
74.19→6.20 s and current-query retained heap 41.44→3.87 MiB. Both generations
have identical rich bytes; 768 variants of one item and a 921,601-byte historical
bucket are included. Current payload is 3.51 MB versus 36.00 MB rich history;
transport delivers both, adding 9.75% raw bytes and up to 64 part requests on a
fresh generation. No synchronization or actual game latency improvement is
inferred. Large Opportunities redraws remain a PR3 concern.

No production/live service, signed build, updater/publication, game install or
SavedVariables change occurred. Owner-directed client latency/frame/memory and
physical PC acceptance remain. Stop at coordinated draft review.
