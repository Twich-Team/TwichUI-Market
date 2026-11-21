# Combined TwichUI Market production acceptance

Live at [market.twich.gg](https://market.twich.gg). Public browser acceptance completed **November 14, 2026, 7:59 PM MST** (November 15, 02:59 UTC); owner-only access and real-key recovery were verified afterward. The owner-supplied Everloot key validated, and the approved initial recovery test is complete. [Machine-readable release evidence](evidence/combined-production-release.json), [deployment/rollback/keyring operations](combined-release-operations.md).

## Release identity and verification

- Final integration/release operations commit: `e7d312974196690dbc8eae70a0aa3d5ecb4cc88e` on `integration/companion-v2-metadata-recovery`.
- Application image build source: `d165629ee3860f1745e854df8dfdfd37b1c4f4e9`. Backend, website and desktop application trees are identical at the final release commit; image module hashes were independently compared with committed source. The website image retains its unchanged earlier build; no approved Market design was replaced.
- Frozen Companion implementation/review: `d9d5ae3` / `75c6f38`; metadata PR #2: `b18927a`; immutable installer payload source: `c7bad2f`. Merge commit `f31050c` retains both feature histories and both native read permission sets.
- API and metadata worker: `sha256:8e2ae844d92be60484e30a0695dd830e8d1fda5050accb4c9fa310bb9112f9ab`.
- Website: `sha256:72d7a79e01b4debc1607aa72ad30a89501a3429e6545b564f1c3131e8f8b605f`.
- Offline release publisher: `sha256:3f757981f846016e3578f78998f4a8e2cb277705771f9bd83bb8daf6468c5b6f`. It has no network, database/provider secrets or signing private key; APIs read its dedicated release volume read-only.

| Canonical exact-release CI | Result | Scope |
| --- | --- | --- |
| [Backend 43671401028](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43671401028) | Passed | 368 PostgreSQL tests; 26 operational/release guards; upgrade/check/downgrade/round trips and preservation; dependency audit |
| [Website 43671401009](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43671401009) | Passed | 60 frontend tests, production build, dependency audit and 22 complete Chromium workflows |
| [Windows 43671401032](https://github.com/Twich-Team/TwichUI-Market/actions/runs/43671401032) | Passed | Rust/Tauri compilation/tests, vault/HTTP/browser authorization, installed native/legacy lifecycle and a separate original-byte signed SDK install/reconnect/export/uninstall run |

The preceding actual application commit `d165629` also passed all three workflows, including signed updater acceptance. Original frozen proof remains unchanged; [combined signed SDK proof](evidence/combined-signed-update-acceptance.json) records the separately reverified payload. Canonical CI installer builds are test artifacts; the published installer is always the original signed c7bad2f bytes.

Python and both complete npm lockfile audits report no vulnerabilities. Rust audit reports zero vulnerabilities across the 176- and 535-dependency lockfiles. Five informational maintenance/GLib unsoundness warnings are retained in evidence; none of the flagged packages occurs in the actual Windows dependency graph. No advisory was suppressed and no dependency/installer campaign was started.

## Database, backup and rollback protection

Migration order was **0012 → 0013 → meta_20261114**, with one intended head, `pg_trgm` and its GIN index. The genuine restored database migration took **2.429 seconds**, passed schema drift checks, and preserved every original column and row across all 21 original tables, including accounts, credentials, preferences, observations, listings, statistics and metadata. Production migration separately preserved all **5,331 existing metadata rows** exactly before local catalog backfill.

The first rollout exposed two genuine Blizzard tooltips containing paragraph breaks that the new catalog source validator rejected. The prepared application rollback was actually executed, preserving the populated additive schema and every old/new record. The bounded fix preserves legitimate multiline plain text while still rejecting HTML and other control characters; four new regressions and the full suite pass. Actual remaining legacy backfill then completed. The public verifier's selector/page-size mistakes were corrected to use the existing UI and 100-item sync contract, preserving all assertions. Attempt evidence is retained separately.

All **23 backup archives** checksum correctly; every earlier archive remains unchanged. The final archive includes the real encrypted Everloot credential and completed recovery job:

- `market-development-20261115T031227463979Z.dump` — 155,526,654 bytes.
- SHA256 `83a308830a2935262661651783043459bb0c817a16a714cf4e22565194791f34`.
- Actual isolated restore verified at `2026-11-15T03:13:09.060988+00:00`.
- The encrypted credential envelope in the archive matches production. Its actual owner key decrypts correctly using a separately restored private keyring file under container UID 10001, without displaying either secret.

The scheduled backup service retains the same image, daily schedule and resource limits; its explicit release settings now keep 30 archives under a 3 GiB archive budget. Manual release backups used the same bounded allowance and `keep=30`. Never run a seven-archive rotation against the preserved release set. The separate encrypted keyring backup/recovery key paths and tested recovery are in the operations runbook. Off-host copies have not been verified.

Rollback images remain available and were exercised. Rollback does not downgrade populated tables, overwrite production from a dump, delete metadata/history or reset credentials. No AMP, Traefik, Komodo, unrelated containers or host network configuration changed.

## Actual production acceptance and monitoring

Trusted public TLS 1.3 was used without ignoring certificate errors. Full actual HTTPS checks pass for login/logout, original public/local sessions and device cursor continuity, preference refresh/logout/relogin, CSRF/origin rejection, member/admin separation, Explorer, genuine current listings and history charts, all Deal Finder modes, item search, administration, market configuration, retention dry-run controls, metadata statistics and recovery controls, empty password key forms, setup/download instructions, browser PKCE approval/one-use exchange, scoped catalog reads, signed native update metadata, refresh and revocation.

A complete genuine live price synchronization passed **260 pages** under the existing 100-item contract. Legacy tokens/cursors remain compatible. This is public server/browser protocol acceptance; it is not a claim that the owner's Windows PC has completed its native/tray walkthrough. No page errors were observed. Temporary test users are disabled and their sessions/device grants revoked; temporary owner acceptance sessions were individually revoked without changing original owner sessions, password, preferences or devices.

House **114 / market 2 / US Normal — Horde** remains the sole enabled collector at **300 seconds**. Its original container/image/start time/resource limits are unchanged, as are PostgreSQL and monitor identities. Historical house-110 records remain. All pre-existing historical/account/session/preference fingerprints match. New normal observations continue to append; the latest result is in machine-readable evidence. Historical pruning remains off with **zero retention batches**. API, worker and database samples are inside their limits, with zero restart loops/OOM. Enrichment is independently limited to 192 MiB / 0.25 CPU. The initial monitoring window includes multiple successful collection cycles and the bounded provider test.

## Published Windows beta

Use **Get Desktop Companion** on the authenticated website, or the [owner-controlled installer download](https://market.twich.gg/api/v1/companion/private-beta/2.0.0-beta.2/windows-x64).

- Version **2.0.0-beta.2**, Windows x64 NSIS, **4,426,483 bytes**.
- Installer SHA256 `0fbc53603c218ffa85c8ee7b4e54f25e53c52a6fc3b2330ae914337714d41869`.
- Actual installed Windows executable SHA256 `fc11b4428f712779e8ac0f954847c8089f869a30567e71c67a422b1ce057d46f`.
- Free Tauri signed-update verification retained; Windows publisher honestly `NotSigned`. No commercial certificate was purchased and no signing private key was exposed.
- Production allowlist is owner account **1 only**. An actual owner-authenticated HTTPS download after temporary access removal matches the original bytes; anonymous download returns 401. Version/signature/no-downgrade and refresh/revocation checks pass.
- Remaining owner-PC work: installation/connected native walkthrough and tray Open/Sync/Pause/Settings/Quit observations. No full stable tray acceptance or installed owner-PC version is claimed.

## Real Everloot validation and fixed-population result

The owner's real key was entered through **Administration → Data Sources**, encrypted at rest and successfully validated by the dedicated worker. Stored key values are absent from read responses. Keyring reads work in public/local APIs and worker. ForeverDB and TheWoWDB remain disabled and unconfigured. No provider key was fabricated.

The bounded window ran **8:02–8:11 PM MST on November 14** (03:02:49–03:11:52 UTC): **one validation + 19 recovery attempts = 20 external attempts**, within the approved 45-minute maximum. The existing next-request time and all provider limits were honored. The job completed; the temporary operator session was revoked and Everloot was disabled again. All automatic provider recovery remains off; the validated encrypted key is retained. The initial 20/day budget is exhausted; further calls require a new administrator-controlled decision/window.

| Fixed market-2 snapshot 26 | Before | After |
| --- | ---: | ---: |
| Distinct observed item IDs | 4,861 | 4,861 |
| Usable names | 2,232 | 2,232 |
| Name coverage | 45.92% | 45.92% |
| Newly gained/lost names | — | 0 / 0 |

Everloot returned **18 HTTP 404 responses and 1 HTTP 200 placeholder without a usable name**. No name was guessed, no item was declared nonexistent, and no coverage improvement is claimed. The same IDs, snapshot hash and price/supply fingerprint match before/after. This 19-item sample cannot establish broader provider coverage or a 90% result. It is separate from historical market-1 coverage receipts. No large import or automatic expansion ran.

The deployment, private beta publication, real-key storage/validation and bounded initial test are complete. Remaining limitations are the owner-PC tray/native observations, the unverified off-host keyring copies, and the still-unresolved item-name coverage. Current measurements and source-specific negative/placeholder results remain visible through the administrator controls.
