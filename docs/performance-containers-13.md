# Final thirteen-addon packaging implementation

**Review hold:** implementation/testing only. No merge, deployment, signing,
publication, activation or release. Parent sources: Market49 `1e105b1` (includes
46/47/48 and the verified Windows/automatic-sync repairs), addon131 `ecc369d`
(includes investigation127). Chart117 and temporary codec-probe135 are excluded.

## Native evidence and contract

The owner reports Forever1.60.1/build71037:26 passed,1 unsupported,0 failed;
external raw Deflate and Base64 decode correctly, zlib wrappers unsupported;
512KiB largest tested output,1.363ms worst native inflate,2.842ms worst probe
step,12.511ms across16 separately scheduled history calls. No full raw capture
was supplied. These are native bounded-fixture observations; native allocation
ceilings, complete physical-addon loading and gameplay behavior remain unknown.

The source API, Contract3 projections, prepared v1 attestation, generation and
economic data are unchanged. The necessary producer adaptation is local to the
Companion; **no server endpoint or schema change is required**. Raw Deflate is
provided by pinned flate2/miniz dependencies; no custom codec enters WoW.

The new explicit installed capability negotiates summary transport3, independently
of prepared-current v1 and API Contract3. Root fields remain manifest/bank/receipt/
prepared. Physical names are `TwichUI_MarketCurrentContainerA00..01`,
`TwichUI_MarketHistoryContainerA00..03`, the corresponding B names, and shared
`TwichUI_MarketData`: **13 folders total**, including both banks on fresh install.
Current logical bucket0..31 and history bucket0..63 map to group floor(bucket/16).
Empty source buckets retain their existing authenticated absence semantics.

Containers contain only fixed Lua literals. Each logical current data/proof
stream and historical JSON stream is split at524288 output bytes, compressed
deterministically with raw Deflate level6 and Base64 encoded. The publisher
refuses a container Lua source over8MiB. It builds and independently reads back
all six destination containers, validating full source digests, proof trees,
record counts, history and identity before root-last activation. There is no
full-container decode in TOC execution or dynamic execution of decoded data.

The reader loads the relevant physical container and yields, then processes only
the requested logical streams, one native block per scheduled callback. Existing
Merkle membership/nonmembership and historical semantic/digest checks gate every
returned value. Existing current-string retention and one decoded history cache
are preserved. Cancellation uses the existing generation/job ownership model.

Expected-length and input checks do not impose a native output-allocation cap.
Only the verified publisher's locally generated streams are admitted; arbitrary
malicious streams/bombs are not a supported input or tested. A synchronous native
call cannot be interrupted. Post-call heap samples exclude native buffers/peaks.

## Installation, recovery and downgrade

* Close WoW before the one-time layout migration. Existing game-process detection
  rejects migration/downgrade/rollback while running. A full restart is required
  to discover new folders. Ordinary later A/B updates retain normal reload behavior.
* The Companion validates the installed active generation and every owned legacy
  folder before writes. Unknown files, linked paths and foreign markers fail
  closed. All existing user settings, SavedVariables and unrelated addons remain.
* Exact old roots are retained under `Interface/.twichui-market-legacy/`. Owned
  old folders move there only after the complete new bank is validated and its
  root committed. This removes obsolete entries from AddOns without discarding
  restoration bytes. An interrupted move resumes from the union of both paths.
* Existing Disconnect → restore previous data verifies/restores legacy folders
  before activating an old root; compressed-bank rollback requires a capable
  addon. Conflicting recovery bytes are never overwritten or automatically purged.
* To downgrade after further compressed generations, keep this Companion installed
  initially, exit WoW, install the compatible older addon, then let this Companion
  publish its supported uncompressed format. Verify completion before installing
  an older Companion. Never point an old Companion at a transport3 root and assume
  it understands it. Preserve the recovery directory and prior installer/source.
* A later layout migration encountering a different old file at an already saved
  recovery path fails closed. Preserve the existing snapshot separately before
  an explicitly supervised new migration; automatic recovery-data retention or
  cleanup is outside this change. Normal compressed generation replacement does
  not create new snapshots or have this conflict.

A new container-capable Companion refuses activation when prepared metadata is
unavailable; it does not silently reinstall193/257 folders. Last-good data stays.

An older Companion with the new addon on a legacy/fresh destination continues
using its supported uncompressed format; it cannot provide the13-folder benefit.
Contract2 and prepared transport2 remain readable. Installing an older addon does
not make an existing transport3 root readable: follow the downgrade sequence.

## Reproducible verification

Use the existing environment and runner; no large campaign joins ordinary checks:

```sh
cargo test --manifest-path desktop/Cargo.toml -p twichui-market-core --lib --locked
./tests/run.sh development market-performance --jobs 2  # in paired addon
```

`scripts/verify-workshop-e2e.py --current --prepared 32 --containers` adds the
actual authenticated synthetic API/native publisher/production Lua scenario to
the existing harness. Windows CI uses its actual versioned PE fixture; Unix's
explicit ignored-test driver substitutes only the existing cfg(test) executable
identity. All publication, ownership, integrity and source validation is real.
`scripts/verify-prepared-layout-pair.py` independently parses generated syntax
without executing it and compares exact prices/variants and all64 histories.

The existing opt-in `measure-workshop-prepared.py --containers` compares the
frozen193 architecture and candidate with identical source data, full economic
oracle, warm-up and repeats. Its `codec_zlib_offline.c` adapter measures system
zlib/OpenSSL under host Lua5.1; it is never shipped or treated as native Forever
timing. The modeled60Hz scheduler is not WoW's frame scheduler.

Final repeated measurements, exact source identities and hosted check receipts
are added at the final verified checkpoint. This document does not claim those
pending checks have passed.

## Verified implementation checkpoint

* Native core:84 passed,0 failed,2 existing opt-in tests excluded from ordinary
  execution (the synthetic pipeline driver is invoked explicitly below).
* Actual authenticated synthetic API → production native cache/publisher →13
  folders → production Lua/proofs/history → incremental Opportunities passes
  at129 variants and60 days. Warm304 preserves exact root bytes/mtime; the
  independent non-executing inspector finds129 exact current rows and64 histories.
* Paired addon fast group:15 passed; separate diagnostics/perf engine checks pass.
  The earlier local full run had325 passing tests but rejected certification
  because source changed during execution. That failed guard receipt is retained;
  only frozen-source final hosted verification can certify the final tree.
* Windows-specific lifecycle acceptance is wired into the existing private
  publisher fixture, including real game-process refusal, migration, native
  restore and re-migration. Its hosted result is pending, not presumed passing.

No existing assertion, timeout, automatic-sync repair or picker test is weakened.

Resource review additionally reserves space for a complete legacy restoration
before migration and preflights missing-byte capacity before copying a snapshot
back. Ordinary packed updates validate only recovery paths they will touch,
so the inactive legacy snapshot does not add repeated file/ACL validation.
