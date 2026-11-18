# Automatic Workshop delivery review candidate

Market draft [#31](https://github.com/Twich-Team/TwichUI-Market/pull/31) and addon draft [#55](https://github.com/Twich-Team/TwichUI/pull/55) implement archive-free automatic Workshop summaries. No merge, deployment, signing or public release is performed. The signed beta.5 release remains intact.

## Player experience and boundaries

Sign in, select the existing account market and connect Workshop once. The native Companion checks a remembered owned installation, bounded registry/common locations and a real Windows folder picker, then validates executable edition/version, compatible addon capability, ownership, ACLs and reparse protections. Multiple installations require one native choice. Its existing scheduler obtains authenticated summaries, validates identity/schema/hashes, and publishes an owned two-bank partition set atomically. A running WoW defers writes; unchanged generations preserve file times; failures retain previous valid data and SavedVariables. Optional archives and manual engineering controls remain under developer diagnostics.

The server reuses canonical pricing and reference assembly. It prepares at most one missing snapshot derivation or 1,000 projected variants per call, persists bounded progress in existing disposable export tables, and uses independent nonblocking locks. Append-only sorted staging chunks avoid repeatedly rewriting accumulated output. No second scheduler, new distributed service or feature-specific migration is introduced. Merged integration #30 adds its own source-coverage migration and archive protocol 2; this candidate preserves those changes and excludes precoverage days from summary reference support.

Current observed exact variants are delivered across 64 load-on-demand partitions, up to 128 KiB each / 8 MiB aggregate / 150,000 records. Overflow refuses the generation instead of truncating it. Current/recent/minimum asking-price references, supported historical references, supply, source observation, verified market identity, support counts and explicit unavailable states are delivered. Historical-only items and daily series are outside this declared universe. Full market raw auctions/history are never copied to WoW.

U1 #21 and stacked U2 #22 retain their histories in the candidate; neither original draft is merged upstream by this work. Their routing, tuple, integrity and refusal foundations are reused with a separate versioned production-candidate contract. There are **zero approved native-link/upstream mappings**. Item IDs cannot collapse exact variants or authorize local competition, Advisor or transactions. The addon reuses Bridge/ServerMarket and existing Market research presentation; focused item research loads one relevant partition, genuine charts remain independent, and local preferences/defaults remain unchanged.

Transport trust is authenticated configured HTTPS (loopback only in fixtures), canonical SHA-256 integrity and owned filesystem publication. Hashes are not asymmetric data signatures. The existing signed application/updater trust is preserved; no unsigned downloaded blob is accepted merely because it contains a hash.

## Measurements

All capacity figures below are synthetic isolated tests, not production performance or native Forever acceptance. Source-qualified JSON receipts are in [evidence](evidence/workshop-automatic-delivery/server-capacity.json).

| Measurement | Result |
|---|---:|
| Exact variants / raw listings per synthetic snapshot | 45,125 / 135,375 |
| Summary partition bytes / largest partition | 5,099,189 / 79,779 |
| Bounded preparation calls including two warm reads | 50 |
| Total server wall / CPU, 0.5 CPU and 384 MiB API | 60.255 s / 22.844 s |
| Maximum request / maximum projection request | 15.935 s / 3.284 s |
| Peak API RSS | 102,125,568 bytes |
| Logical stage + sealed record payload written | 10,198,360 bytes; not physical WAL |
| Warm lookup | 11 SQL statements / 5.555 ms |
| Original single cold request | 74.638 s, exceeding the native timeout |

The earlier rewrite-based resumable prototype took 101.130 s and 133,963,776-byte peak RSS on the same fixture. The final append-only representation removes that measured overhead. These are local engineering comparisons, never claims of live production improvement.

Actual scoped-authenticated Linux API → native codec → generated files → production Lua reader → Workshop Market passes for 45,125 variants: 49 native calls, 113 HTTP requests, 45.220 s, no mandatory archive, actual warm HTTP 304 with zero download bytes. This is Linux staging; Windows publication has separate acceptance receipts.

Desktop Lua 5.1 measurement of that actual native output: root compile 51 μs; all-part compilation/execution 22 ms; header validation 18 ms / 57 KiB retained; full enumeration/validation 9,718 ms CPU; worst callback 3,201 μs; 1,000 exact lookups 4,038 μs; 5,410 KiB retained, with 706 decoded rows in the one-part cache. This full-catalogue cost is material and must be measured in Forever. The existing research list displays at most 20,000 rows with explicit capping, independently of the untruncated delivered dataset.

A read-only production observation at 2026-11-18 01:04 UTC contained 127,670 listings, 5,260 item IDs and 25,872 exact variants (observation 1072 / snapshot 95, genuine source). Those are source counts, not a deployed summary measurement. No production summary generation or provider campaign was performed.

## Verification and review gates

Local reconciled tests, final CI receipts and Windows-produced artifact consumption are recorded in the progress ledger as they complete. Addon `1f437e384d0e024be9c1da2be343d79e04d49840` has full CI 44211817471: **267 passed, zero failed**. Frozen Market mutation campaign killed **255/255**, with another **4/4** targeted kills for focused lookup; do not combine these into an invented full campaign on a different source. Simulator Workshop/Auction Preview scenarios are prepared, but the lab is absent and they have not run.

The actual installed Windows flow at `9a669b2` passed native picker cancellation/selection, wrong-game refusal, multiple-candidate selection, one permission, archive-free worker publication, automatic update, 304/no rewrite, running-game deferral, corrupt-response preservation/recovery, legacy upgrade/archive compatibility and retained-data uninstall. That run subsequently failed its independent large-producer directory ACL fixture; production ownership checks were retained and the fixture corrected. Final coordinated large Windows producer and production Lua consumer acceptance is tracked separately.

[Gallery](evidence/workshop-automatic-delivery/review.html) distinguishes actual installed Windows scenes from mocked-IPC mobile layout evidence. [Native owner procedure](workshop-automatic-delivery-owner-test.md) explicitly leaves actual Forever executable recognition, loaded-generation identity and game frame/GC/visual acceptance pending. No simulator or installed synthetic PE can pass those gates. No source release or deployment is implied by draft delivery.
