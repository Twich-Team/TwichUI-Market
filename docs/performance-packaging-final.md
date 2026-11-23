# Final packaging refinement and conditional release

The owner authorizes choosing only A (13), B (17) or C (25), adapting the existing
prepared containers, verifying both repositories, merging in dependency order and
deploying the backend/private Companion through the existing signing/distribution
process, provided all gates pass. No public addon release or temporary codec probe
merge is authorized. Offline observations are never real Forever results.

## Source and dependency inventory

Market main is `e2882dd822b356ffa081efebbff167827f9bf364`. Draft chain:
46 (`fce5c057`) → 47 (`2fcd450a`) → 48 (`1e61ff41`) → 49 (`1e105b16`)
→ 50 (`50246f1d`). Preserve ordinary merge ancestry and all Windows repairs.
TwichUI 131 (`ecc369d5`) must precede 136 (`5b25af4e`). Current addon main is
`2835d71`; it advanced independently and 131 requires conflict reconciliation.
Chart 117 and temporary probe 135 are excluded.

The addon Protect main ruleset requires a PR and passing `verify`, zero mandatory
approvals, no bypass actors and no force pushes. The connected app cannot read
legacy branch-protection endpoints (403); that is not evidence of absent rules.
Market has no visible repository rulesets; its legacy branch protection also
cannot be inspected through the app. Actual merges must still respect GitHub's
enforcement and required checks.

## Bounded performance experiment

`scripts/compare-current-containers.py` reuses the existing native publisher,
production Lua benchmark and complete economic oracle. It builds one frozen
16,384-record/60-day source. Experimental B/C publications regroup the verified
native A publisher's exact assignment lines, without re-encoding. An independent
non-executing parser requires every decompressed current/proof/history stream to
match A. Only the current physical lookup divisor changes in disposable reader
snapshots. This experiment does not establish native B/C migration acceptance;
the selected layout still needs implementation and full native/Windows checks.

Thirty fresh Lua processes per 120/1,000/5,000 workload and layout follow one
discarded warmup. Fixed-seed interleaving reduces timing-order bias. Reader and
pricing caches are cold; the OS filesystem cache is warm. All load samples,
read/compile/execute CPU phases, before/after heaps, callback tails, codec costs,
warm reuse, historical probes, retained/sample-peak Lua heaps and economic hashes
are retained. GC heap drops indicate correlation, not exact GC pause attribution.
CPU and process elapsed times are actual execution; scheduler seconds are modeled.

The first attempt failed while serializing the newly added trace, before accepting
any measurements. The strict production JSON codec rejects untagged tables and
fractional JSON numbers. The harness now emits typed arrays/objects and decimal
strings for fractional trace observations. The production codec and assertions
are unchanged. The failed receipt remains in local evidence.

## Read-only production preflight

At approximately 04:33 UTC on November 23, both APIs and PostgreSQL report healthy;
the actual `/api/v1/health` endpoint returns 200. A mistaken `/health` probe returned
403 and is not counted as service failure or endpoint success.

Actual API/local API image is
`sha256:a3f8226431fbef2794187df8f7a4667f7ef5b96ca1f7a294c1ae3ffdccf8f88c`;
the existing Workshop-current overlay remains last. Proxy remains `f48f8f1a7e5a`;
collector remains `aab0d6585115`. Private current pointer is `2.0.0-beta.11`.
Schema is `retention_20261118`. These are live read-only observations.

**Pre-existing collection gate failure:** house 114/market 2 alone remains enabled
at 300 seconds. Last complete market/auction success is
`2026-11-22T21:24:35.749844Z`; market failure count is 84. Commodities continue
successfully, most recently `2026-11-23T04:28:23.079860Z`. Auction failures return
HTTP 200 followed by `Feed transport, identity or payload validation failed`.
The latest recorded failure is `2026-11-23T02:47:31.827206Z`; seven auction
failures have scheduled persisted backoff until `2026-11-23T08:07:31.827206Z`.
The exact rejected payload condition is not retained by the generic diagnostic
and has not been inferred. The collector correctly retains the last complete
observation. No provider requests, retry overrides, settings or data changes were
made by this task. A healthy collection gate cannot currently be certified.

Performance work and independent safe verification continue. No merge, deployment,
signing, distribution-pointer change or installed-PC update has occurred.


## Selected implementation checkpoint

Current mapping is eight physical current containers per bank (four logical
partitions each), four history containers per bank unchanged, plus the root:
**25 Market addons**. Names extend current A/B slots through 07. Installed
`current_containers: 8` is strictly required by the producer; different declared
physical layouts fail before root activation. No API, pricing, compression,
authentication or scheduler change accompanies this refinement.

At the selected source checkpoint, all 85 native core tests pass (two explicit
integration drivers remain ignored in ordinary discovery). The 42-module focused
addon Market run passes; its local container could not read the external git
metadata, so it is preliminary functional evidence, not immutable-source
certification. Exact paired-addon CI remains mandatory. Native end-to-end
publication initially failed for missing read-only worktree metadata, then for a
retained partial output directory and an outdated exact-addon pin. Those receipts
remain in ignored local evidence. None is claimed as passing acceptance.

The complete simulator catalog is blocked before execution on both the local
rootless host and standard Ubuntu 24.04 GitHub runner: `unshare -Ur true` fails
writing `/proc/self/uid_map` with `Operation not permitted`. Hosted run
[45119849609](https://github.com/Twich-Team/TwichUI/actions/runs/45119849609),
job 137510875627, retains the failure; no suite was skipped into a passing verdict.
The existing Bubblewrap sandbox and host security were not relaxed. This blocks
the coordinated release even after production collection recovers. Independent
collector repair and native/Windows/data verification continue.
