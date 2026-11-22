# PR2 compatible Companion delivery

Stacked on [producer PR #43](https://github.com/Twich-Team/TwichUI-Market/pull/43),
producer commit `b02a190f22fd403a35c0856dfb3c598cd0720bc7`. The paired addon is
stacked on TwichUI PR #99. Contract definition: `contracts/workshop-summary/v3/`.
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
Companion, then addon capability activation. Keep the compatible Companion while
restoring a previous 1/2 generation before downgrading it. Do not mix bank files or
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

The frozen source still needs the existing Windows CI/integration coverage and
owner-directed native latency/frame/memory acceptance; none is inferred from
Linux synthetic timings or fixture output. No physical Windows/game test or
public Companion release is claimed.
