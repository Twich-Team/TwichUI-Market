# Unified commodity coverage — production accepted

The missing trade goods fix is deployed at **`70f144ca35bd7041dcf17391f9fc8c96fd3c4ef8`**, merged through [PR #30](https://github.com/Twich-Team/TwichUI-Market/pull/30) into `integration/companion-v2-metadata-recovery`. Database revision **`coverage_20261117`**. Source-aware private Companion **`2.0.0-beta.6`** is published. [Final runtime/collector health](evidence/unified-coverage/final-health.json), [actual HTTPS browser gallery](evidence/unified-coverage/production/review.html).

## Diagnosis and source identity

Market 2 collected ordinary auctions only. Bounded authenticated Forever probes found all three examples in commodities, absent from regular auctions and retained Market-2 statistics. Missing metadata was a secondary naming gap. Static Forever item responses independently verified the names, IDs, classes and COMMON rarity. [Upstream evidence and plan](unified-coverage-plan.md).

Both source streams are verified **US / ruleset 2 Normal / house 114 Horde / `dynamic-forever-us`**. The house response explicitly links its commodity endpoint. A bounded same-time comparison of houses 113 and 114 showed distinct commodity books with no shared listing IDs; no retail-wide scope was assumed. The guarded activation repeated four bounded live identity requests, verified the retained Normal/Horde registry mapping, audited activation and preserved Market 2 and its next check. [Activation proof](evidence/unified-coverage/feed-activation.json).

## Collection and data correctness

The existing worker collects sequentially at **300 seconds**, with separate verified feed state, immutable captures/checks and a frozen source manifest. It publishes one logical snapshot only when both streams check successfully. Partial successes remain captured, while the previous complete snapshot stays stale; failures cannot create false zero supply. No additional collector or selectable market exists.

Commodity unit prices stay integer copper; quantity is separate and listing spend is unit × quantity. Exact variants and ordinary pricing remain. Commodity coverage starts at the first real observation, with no backfill or pre-coverage zero events. Deal Finder requires three genuinely priced days for commodities even if the requested general coverage minimum is lower.

The first complete production snapshot was recorded **2026-11-18 01:59:12 UTC**, taking **28 seconds**: **133,692 ordinary listings / 5,289 items** plus **106,945 commodity listings / 1,292 items**. Checks at 02:04 and 02:09 returned unchanged feeds safely, with zero failures. Collector peak measured **325.9 MiB / 384 MiB**, zero OOM/restarts. [Health](evidence/unified-coverage/final-health.json).

| Genuinely observed item | Supply | Listings | Minimum unit copper |
| --- | ---: | ---: | ---: |
| Silk Cloth — 4306 | 19,702 | 761 | 195 |
| Mooncloth — 14342 | 38 | 37 | 300,900 |
| Savory Deviate Delight — 6657 | 2,759 | 100 | 113 |

These are timestamped asking listings, not sales or permanent prices. Captured raw source, normalized listings and stored statistics agree exactly. Live authenticated HTTPS verifies each name and ID, price/supply/counts, item details, 24H coverage and legacy sync. Ordinary Dirty Leather Vest listings remain. All three commodities have COMMON rarity, real metadata names and local icons. Newly covered goods are withheld from Deal Finder. [Source-to-storage proof](evidence/unified-coverage/live-source-prices.json), [API verification](evidence/unified-coverage/live-api-after.json), [metadata](evidence/unified-coverage/live-item-metadata.json).

Actual production Chromium at 1440/390px and WebKit at 390px pass search, details/history, no horizontal overflow, no page errors and zero checked WCAG A/AA violations. [Browser receipt](evidence/unified-coverage/live-browser.json). All 18 deployed frontend files match the built assets byte-for-byte through public HTTPS. [Asset hashes](evidence/unified-coverage/public-assets.json).

## Tests, preservation and controlled promotion

Exact integrated **push-source** workflows for `70f144c` all pass:

- [Backend 44217371235](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44217371235): **661 PostgreSQL tests**, all **eight** populated migration rehearsals, operational/contract checks.
- [Website 44217371290](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44217371290): **132 frontend tests**, build/audit, **66 browser cases** across the ordinary and specialist Chromium/WebKit suites.
- [Windows 44217371313](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44217371313): native/core/HTTP/archive/Workshop export compatibility, packaged installation, actual legacy upgrade, installed/cache/credential/revocation/uninstall retention.

A temporary **596,366,938-byte** production archive, SHA-256 `87c058cb7213c076e81b9ed975347c81fb7695fa5e6a621b62bb6d1828a8cced`, restored in isolation. The additive migration preserved every original field across **41 tables**, with no schema drift; original and candidate images decrypted both provider envelopes using the unchanged read-only keyring and no provider requests. The isolated containers/network are retired. [Restore before](evidence/unified-coverage/restore-before.json), [after](evidence/unified-coverage/restore-after.json), [credential continuity](evidence/unified-coverage/restore-new-credential-continuity.json).

Production migration and final original-column fingerprints preserve the baseline history/accounts/preferences. Before deployment, the real Windows PC rotated credential 272 normally: only its `revoked` flag changed false→true; reconstructing that one old value reproduces the complete original credential hash. This legitimate rotation is explicitly reconciled without modifying or reviving credentials. [Rotation proof](evidence/unified-coverage/credential-rotation-proof.json), [final preservation](evidence/unified-coverage/preservation-final.json).

Only **api, local-api, proxy and worker** were replaced, with `up -d --no-deps --no-build --pull never --wait`. Existing provider configuration/encrypted envelopes, keyring and enrichment/database/monitor identities remain. All **46 original immutable private distribution files** remain; only the current pointer intentionally moved. No synthetic observation or historical retention batch exists. Both temporary release verification grants are revoked and return HTTPS 401. [Scoped configuration](evidence/unified-coverage/integrated-compose-preflight.json), [images](evidence/unified-coverage/integrated-images.json), [runtime preservation](evidence/unified-coverage/final-runtime-preservation.json), [revocation](evidence/unified-coverage/verification-grants-revoked.json).

## Companion and Workshop

The beta.5 reader accepts protocol 1 only, whose schema cannot represent per-item commodity coverage. Keeping its original regular-only exports valid while providing correct commodity Workshop history independently requires the source-aware update. Protocol 2 carries commodity source/coverage boundaries; the native cache preserves prior protocol-1 data and saved selections while staging the separate archive. Bridge/addon contracts and pricing defaults remain. No addon repository change or release occurred.

Published **beta.6** original installer: **4,771,009 bytes**, SHA-256 **`8383217c595d46dcc1a982f60dd500852d6402d613e261a7fd1b6e2a9c5ffb3c`**; payload source `70f144c`, installed executable `dbd2354c6943bc5a36304994f989b2a3d0858e91e893319fa95d04a51896272b`. Existing owner key fingerprint remains `5794736c840c7c09a49396e60cd569ff6b5f24f872eb0318ed95d55c16616ecf`.

[Actual beta.6 signed SDK run 44218796052](https://github.com/Twich-Team/TwichUI-Market/actions/runs/44218796052) verifies exact signature/version, tamper and wrong-version rejection, real installation/executable bytes, reconnect/sync/export and uninstall data retention. Harness `7a8139c` changes public release evidence only. [Receipt](evidence/unified-coverage/beta6-signed-update-acceptance.json). The detached installer process exit was not observed directly; installed state and executable bytes were verified independently. Physical-PC tray/toast behavior remains unverified.

The offline publisher independently reverified the immutable bundle and atomically moved beta.5 → beta.6, retaining older versions. Actual authenticated HTTPS downloads the original signed bytes, beta.5 receives the beta.6 update, beta.6/newer get 204, anonymous gets 401, and beta.5 still downloads unchanged. The downloaded beta.6 bytes independently verify offline. [Publication](evidence/unified-coverage/beta6-publication.json), [HTTPS](evidence/unified-coverage/published-beta-acceptance.json), [download verification](evidence/unified-coverage/downloaded-beta6-signature.json).

Both real archive protocols return the documented **202 Preparing** state while incrementally preparing cold historical digests. Two bounded operator requests confirmed that progress; no full production bootstrap, PC installation or on-PC commodity export is claimed. Actual source-aware sync/export lifecycle passes Windows fixtures. Existing offline data stays retained while the new full archive warms. [Live archive responses](evidence/unified-coverage/live-archive-preparation.json).

## Storage policy and remaining limits

At the owner's explicit request, **33 PostgreSQL dump copies / 4.913 GiB** were removed, recurring backup was stopped with restart disabled, and public status changed to `disabled_by_owner`. The temporary release dump and redundant local build/candidate copies are now also removed after acceptance (**635,998,000 bytes**). About **5.8 GiB** is free at the final check. Live data, signing material, source, rollback images and published installers/evidence remain. Keep `compose.owner-backup-policy.yaml` in the production overlay chain; do not restart recurring backups. [Original cleanup](evidence/unified-coverage/backup-cleanup.json), [temporary cleanup](evidence/unified-coverage/temporary-release-cleanup.json).

The existing **5 GiB database safety cap** is unchanged; collection pauses safely at that bound. The database is about 3.75 GiB at acceptance, and retaining both books increases growth. No history pruning, cap increase, provider campaign/quota change or unrelated cleanup is authorized by this release. Large cold archive preparation remains bounded and may take time; previous data is preserved. Price references and deal confidence grow only with genuine future observations.

## Operations and rollback

Append the stable root checkout's `compose.owner-backup-policy.yaml` and `compose.unified-coverage-release.yaml` after the full existing metadata/mobile overlay chain. Keep the metadata release → chart → API overlay order. Replace only explicitly named services with `--no-deps --no-build --pull never`; do not start stale migration/dependency services.

Before commodity activation, the original pinned images remain compatible with the additive schema. After activation, retain a source-aware API/worker: an old worker can publish false commodity absence. A frontend-only rollback can retain the compatible API/worker. For an urgent incompatible backend rollback, stop collection and put data routes into maintenance first, preserve the populated schema and every observation, then repair/roll forward. Never downgrade populated coverage tables or restore a dump over production. Both predecessor images and the source-aware images in the image receipt are retained. Private release rollback changes only its audited pointer, preserves all versions, and never forces installed clients to downgrade.
