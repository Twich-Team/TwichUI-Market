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

Completed repeated measurements and exact source identities are recorded below.
The live final-head check links remain authoritative for any pending CI; a pending
check is never declared passing by this document.

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
  restore and re-migration. Its native producer/consumer run passed at4b2c025;
  the final combined run also includes the independently verified fixture repair.

No existing assertion, timeout, automatic-sync repair or picker test is weakened.

Resource review additionally reserves space for a complete legacy restoration
before migration and preflights missing-byte capacity before copying a snapshot
back. Ordinary packed updates validate only recovery paths they will touch,
so the inactive legacy snapshot does not add repeated file/ACL validation.

## Comparable completed measurements

Accepted [Session](evidence/market-containers-13/session.json) and
[UI/reopen](evidence/market-containers-13/ui-reopen.json) campaigns use the same
fabricated generation `ae761007c97a7456827f0d2d61925fa52ee4edf1623eab009572f65b6b2e1abc`,
16,384 rows,21,501,173 canonical historical bytes across60 days, shared materials,
variants and unavailable-price cases. Each case discards one warm-up and measures
three fresh Lua processes, cold addon/pricing caches and a warm OS filesystem
cache. Host:AMD EPYC9V74/Linux6.18.57/Lua5.1+bitop. The
193-layout reader is frozen addon `ecc369d`; candidate is addon `5b25af4`.
Session producer code is `00ac736`; UI producer code is `4b2c025` (the only
intervening change is the Tauri lock dependency entry, not benchmark/runtime
pricing code). Full source hashes, clean start state and unchanged guards are
retained. Later evidence/fixture-only commits do not alter those runtime hashes.

The baseline label193 means its complete two-bank architecture; its fresh
publication creates97 active-bank folders. Candidate fresh publication creates
all13, with inactive-bank placeholders. Loading/pricing compares the same active
32 logical current partitions. The producer validates every history partition;
the selected chart probe additionally uses the production Lua history reader.

Median Session results after root admission (seconds are **modeled60Hz scheduling**,
CPU is actual host process CPU; these are not real-game latency predictions):

| Recipes | Layout | First priced opportunity s | First12 settle s | Full price settlement s | Pricing CPU ms | Warm model query ms |
|---:|---:|---:|---:|---:|---:|---:|
|120|193|0.233|1.033|4.583|626.969|0.056|
|120|13|0.500|1.500|5.150|687.697|0.058|
|1000|193|0.717|1.117|27.150|3659.397|0.066|
|1000|13|0.833|1.533|27.500|3662.899|0.114|
|5000|193|0.800|4.083|34.500|5876.624|0.073|
|5000|13|0.767|4.200|34.983|5952.101|0.069|

Pricing CPU changes are +9.7%,+0.10%,+1.28%. Complete economic snapshots, prices,
quantities, costs, craft/buy results, profitability/rankings and missing-price
outcomes match in every accepted sample. Warm queries create zero new crafts or
reader calls and reuse the estimator. The separate actual authenticated
[API/native/Lua receipt](evidence/market-containers-13/api.json) and independent
non-executing parser verify129 current variants, all64 histories, lazy history,
source generation and unchanged304/root-mtime behavior. Native readback validates
complete histories before every activation, including the large campaign.

For the120-recipe full UI-handler workload, first12 settlement is2.483→2.917s,
full price settlement4.717→5.350s. Root validation is separately approximately
53–54ms CPU /0.5 modeled seconds; add it for a genuinely cold root. Thus the
candidate UI-visible result including root is approximately3.42 modeled seconds,
**not a demonstrated strict <=3s end-to-end pass**. The10s full-price goal holds
for120 recipes in this model;1,000/5,000 do not meet it on either layout. This
packaging change does not repair that inherited large-catalog limit.

A warm model query is not full-window paint. Five reopen/drain cycles cost
775.452→771.715ms aggregate CPU, including asynchronous history/render work;
both have zero new price-reader calls, crafts or full-list calculations. This
does not measure initial paint per reopen or certify a <=10ms full UI reopen.

### Loads, codec, memory and GC

Across Session samples,32 logical current parts require64 separately scheduled
native stream inflations from two physical current loads; no histories load for
pricing. Median combined current inflate CPU is14.762–16.906ms, Base64 totals
2.192–4.278ms. Worst single current inflate is1.156ms. A selected60-day history
probe adds one history-container load and one logical inflate; observed host
inflate maxima reach2.115ms. A second valid history hit loads/inflates nothing;
its lookup costs0.35–0.50ms. Existing one-partition history churn remains possible
when different histories are requested; it has not been redesigned.

Current Lua source read for all32 parts falls4,773,024→2,805,251 bytes (41.2%).
Physical current loads fall32→2. Aggregate source compilation medians are
18.46–18.75→9.81–15.52ms; literal execution totals remain below0.13ms. Reduced
aggregate compile work does not erase the per-load tail below.
**Synchronous loading regresses:** baseline worst current load3.126ms versus
candidate29.206ms; candidate worst current callback29.232ms. The120 candidate's
per-run worst loads are7.033/17.659/29.206ms. The UI harness sees up to23.822ms
loads and25.582ms callbacks (baseline11.629/25.449ms). These tails are retained,
not filtered as outliers or hidden by the coroutine budget. History probe
scheduler steps reach28.661ms candidate versus22.749ms baseline; these include
host scheduling/GC overhead and are not isolated native inflate durations.

The hook reads/compiles actual files with host Lua loadstring; this includes a
Lua source buffer and incidental GC, unlike an established measurement of the
actual native LoadAddOn internals. Attribution of the long load tail to compiler,
input-buffer allocation or GC is not isolated. We **cannot certify native
frame safety or call the loading regression acceptable from these data**.
Straightforward bounds are already applied: loads return to the scheduler before
inflation, each native block has its own scheduled callback, and oversize source
containers refuse publication. LoadAddOn itself remains synchronous; a Lua
coroutine cannot preempt it. No GC tuning, custom loader or automatic larger-folder
fallback is introduced to hide this limitation. Real Forever13-container loading
must be measured before claiming this acceptance condition satisfied.

Retained/sample-peak Lua heap deltas (MiB, medians; includes recipe engine):

| Recipes |193 retained/peak|13 retained/peak|
|---:|---:|---:|
|120|6.51/17.22|9.27/17.94|
|1000|17.80/34.97|20.50/36.98|
|5000|59.55/112.27|62.24/109.36|

UI-handler120 deltas are35.59/81.37→38.75/83.10MiB. Candidate retains about
2.7MiB additional compressed current strings in the Session fixture. Natural
sampled heap-drop counts are14/115/180 baseline and18/73/154 candidate; these are
not exact collection counts or pause attribution. Existing post-work diagnostic
full-GC measurements are outside workload CPU and never used by production code.
Native buffers/RSS and exact allocator peaks are unknown. Prepared per-generation
32MiB and source history64MiB bounds remain; both A/B banks can stay loaded in
WoW, plus the retained current/previous contexts. Source cap8MiB/container is an
admission ceiling, not a promise that an8MiB synchronous compile is frame-safe.

### Reproduce these campaigns

Use the frozen baseline addon and paired candidate, the standard environment,
and the existing native test driver shown by cargo test --no-run:

```sh
cc -shared -fPIC -O2 scripts/codec_zlib_offline.c -lz -lcrypto -o /tmp/market-codec.so
python scripts/measure-workshop-prepared.py --containers \
  --addon-root "$candidate_addon" --baseline-addon-root "$baseline_addon" \
  --rust-test-driver "$driver" --native-codec /tmp/market-codec.so \
  --recipes 120 1000 5000 --reps 3 --history-probe --out "$session_results"
python scripts/measure-workshop-prepared.py --containers \
  --addon-root "$candidate_addon" --baseline-addon-root "$baseline_addon" \
  --rust-test-driver "$driver" --native-codec /tmp/market-codec.so \
  --recipes 120 --reps 3 --view ui --scenario reopen --history-probe --out "$ui_results"
```

These variables are paths selected by the operator; they are not production
locations. Commands are opt-in and never part of fast development checks. The
permanent receipts retain every measured sample and min/median/max range.

## Final review and acceptance status

[Addon full/fast CI](https://github.com/Twich-Team/TwichUI/pull/136/checks) passes
325 full unit tests and the15-module fast group at exact addon `5b25af4`.
[Market final checks](https://github.com/Twich-Team/TwichUI-Market/pull/50/checks)
are authoritative for the final head; pending/skipped checks are never counted
as successful. Native Windows producer/consumer, migration/restore, old-client
compatibility and actual signed-updater verification pass at `4b2c025` except
the separately observed foreground-precondition fixture failure. The corrected
[focused native run](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45102490747)
passes all four exact path/validation selections with verified foreground/focus.
It uses a process/point-checked real click to activate the dialog before text
input; original20s/10s limits and all selection assertions remain. The patch is
included for final full verification, not treated as an exception. Original
[failed receipts](evidence/market-containers-13/verification.json) remain visible.

The13-installed-addon architecture and lossless bounded codec path are implemented;
**release acceptance is not unconditionally satisfied**. Remaining evidence gaps:
non-preemptible loading/GC tails in actual Forever, strictly cold visible latency,
full UI repaint latency, real memory/native buffers and behavior at larger actual
Market cardinalities. Automated correctness and migration results do not replace
those measurements. No alternate73/193 layout is selected or silently published.

Minimum later native check in an isolated installation: close WoW, synchronize a
complete generation with the paired sources, verify13 Market folders and retained
recovery data, restart WoW, use `/tui perf start workshop 3`, mark
`opportunities-open`, open Opportunities, select two previously cold histories,
reopen the page, stop capture and export from `/tui perf`. Check container-load,
Base64/inflate and callback tails, aggregate addon memory and first/full settlement.
Repeat once after a complete generation replacement; verify reload-required
behavior instead of mixed data. Do not test rollback during live gameplay.
The owner must approve any native installation, coordinated merge or activation;
no such action occurred here. Do not merge probe135 or its temporary ZIP.


Final focused presentation follow-up: the first click-activation correction
passed its focused run, but full run45104103504 safely refused a foreign pointer
target (job137461324518). The fixture now makes only its process-checked disposable
dialog topmost with one asynchronous NOACTIVATE operation, observes the owned
point becoming visible within the original deadline, then uses the same real
click/foreground/focus/path assertions. It never clicks an occluding window.
Focused Windows [45104815135](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45104815135)
passes all four exact paths with verified foreground/focus. This is test-only
presentation, not a production picker or security-policy change. Final combined
verification remains mandatory; neither earlier failed run is reclassified.
