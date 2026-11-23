# Thirteen-addon prototype: native codec gate

The owner approved only a bounded packaging prototype on 22 November 2026. The
first instruction is binding: **if the required Forever behavior cannot be
established, stop and report the blocker.** No merge, production deployment,
signing, publication, release or automatic fallback is authorized.

## Gate result: blocked before implementation

The available target UI source is Forever 1.60.1.70938 at
`bebcb6bf309cf41b41bd74f8ca651e6a105b2676`. Generated
`EncodingUtilDocumentation.lua` documents Base64 and Deflate APIs, and
`CooldownViewerSettingsDataStoreSerialization.lua:269–281` invokes them. Neither
contains the native decoder implementation, known captured interoperability
vectors, allocation ceilings or native timing evidence. There is no documented
caller-supplied decompressed-output limit. This does **not** prove the client
has no internal limit; its behavior remains unknown.

The available simulator 0.1.37 uses 1.60.1.70532 UI source
`ca8368f2f2380cbe696854f7f2646387c278a61b`. The explicit-method probe uses
`Enum.CompressionMethod.Deflate`, known raw-Deflate and zlib vectors and a 4,600-byte
repetitive input. Both vector comparisons fail and compression returns the
unchanged original input. These are identity stubs, not a usable codec.

No genuine Forever executable, executable-access environment, native codec
implementation or independently verified native performance/resource capture
was found among the available task inputs. Test PE files have synthetic version
resources and are explicitly not game executables. Existing LibDeflate is pure
Lua and is not evidence for `C_EncodingUtil` behavior. Host zlib results also do
not establish the game client's wrapper format, bounds, CPU or allocations.
Do not substitute either for this required native gate or introduce a new codec.

Consequently:

* Thirteen physical addons remain a **candidate**, not a verified viable format.
* Actual decompression CPU, peak allocations, corrupt/truncated-input behavior
  and allocation limits are **not measured**.
* Complete 193-versus-13 pricing comparisons at 120/1,000/5,000 recipes,
  compressed-history correctness, migration/removal and rollback are **not run**.
  Running a stub-based candidate would supply misleading evidence.
* No Companion container writer, addon decoder/mapping, capability/format or
  production runtime changes have been made for this prototype.
* The 32-current/64-history prepared work, incremental engine, authentication,
  existing banks and compatibility paths remain intact. Chart PR117 is separate.
  No 73- or 193-folder release/fallback was selected.

The prior source-loading experiment remains feasibility evidence only. On its
less-compressible synthetic history, seven compressed containers reached
64.83 ms synchronous history source load; thirteen reached 10.96 ms. Those are
host Lua source measurements **before native decompression**, not client
callbacks or a completed prototype. Existing raw grouping preserved the full
economic oracle; that does not certify a compressed format or its rollback.

## Precisely what would unblock this gate

A disposable actual Forever process, or independent evidence traceable to its
exact decoder implementation/build, must establish:

1. Known externally encoded vectors decode to exact original bytes, covering the
   wrapper variant and intended Base64 form; an identity round trip is insufficient.
2. Truncation, malformed streams and output-size/resource boundaries fail safely.
   A length check after an unbounded allocation is not proof of bounded memory.
3. Decompression CPU and retained/peak allocations for complete admitted logical
   current and substantial 60-day historical blocks are measured. Synchronous
   native calls cannot be assumed to obey the Lua coroutine frame budget.

This is the owner's explicit prerequisite, not a newly imposed general
real-client release rule. The earlier personal 16/32 comparison waiver does not
establish these codec facts. Stop packaging work here until evidence or a new
owner direction is available; do not start a different architecture.

## Independent CI repair

Prepared integration checkpoint `1e61ff41747b0d49edc024b174f9df6b4e6dd925` passes
PostgreSQL, website, prepared Windows producer/consumer, picker and updater
verification. Its ordinary installed Windows job fails at the legacy-close
subprocess timeout and then the native picker returns the previous wrong-folder
condition instead of the deliberately missing Summary.lua condition. Its
downstream legacy consumer is skipped, not passing. Original evidence is
preserved in `evidence/prepared-integration-blockers/windows-ui-45084411116.json`.

The fixture previously changed an arbitrary Edit control and immediately
accepted the shell dialog. Production `installation.rs:285` uses
`SHBrowseForFolderW`, which returns the selected PIDL. The test-only correction
uses documented `BFFM_SETSELECTIONW` on the checked dialog/process and requires
an enabled native confirmation. Additional real Windows tests switch first →
second → invalid → first and verify the returned path and validation each time.
No product picker, IPC result or economic assertion is mocked or bypassed.

The legacy-close timeout has no stage evidence in the original log, so its
precise blocking stage is unresolved. .NET Framework's reference source already
uses PostMessage in CloseMainWindow; changing it to another PostMessage is not
a demonstrated repair. Bounded stage output now records process lookup, close
post and actual exit, preserving the 15-second subprocess and 10-second exit
limits and all upgrade/data-retention assertions. Failure remains failure.

Automatic-sync lifecycle repair runs independently. Its status and final hosted
source/check links are recorded in the integration readiness report. No required
failure is suppressed and no native acceptance claim follows from a host test.

Automatic-sync run [45084411108](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45084411108)
now passes at `1e61ff41747b0d49edc024b174f9df6b4e6dd925`: all six comparisons
have identical values, the server stops, and no active requests or background
loop errors remain. Receipt: `evidence/prepared-integration-blockers/automatic-sync-passed-45084411108.json`.
The separate first picker regression at `efe5262` fails because UIA cannot find
the confirmation button after navigation. The follow-up uses native IDOK/IDCANCEL
handles and waits for child readiness within the original discovery budget;
this does not retry an application failure. Actual Windows re-verification is
required; the failed run remains evidence, not a passing exception.
