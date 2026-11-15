# Metadata source decisions — 2026-11-14

Public documentation was read on 2026-11-14. These are contract findings, not live data validation. Six bounded, credential-free execution-host GET attempts (Everloot OpenAPI, item tooltip 720, two-row item page, export pointer; ForeverDB meta; TheWoWDB 720) failed at the Cloud proxy with `Tunnel connection failed: 403 Forbidden`. The clean environment without proxy also could not connect. No access restriction was bypassed. The web research service could read documentation but could not retrieve the actual item APIs. No real provider success, source overlap, name gain or 90% coverage claim is possible here.

## Everloot first supplemental adapter

[API](https://everloot.app/docs/api), [items](https://everloot.app/docs/api/items), [tooltip](https://everloot.app/docs/api/tooltip), [keys](https://everloot.app/docs/api/keys), [bulk files](https://everloot.app/docs/api/data-files), [licensing](https://everloot.app/docs/licence).

The adapter separates single-card names from paged client categories. `/api/items` is not a name catalog. The key is a Bearer header; public access exists with lower quotas. The UI stages encrypted keys and a worker validates against the actual items contract before activation. Keyless defaults stay below published limits, even for single-card requests. A validated unexpired key permits a bounded administrator increase to 240/hour and 2,000/day; keyless limits remain enforced if that credential is absent or expired. Pagination reconstructs a fixed host/path/offset and never follows returned URLs. Page limits remain 500 even with a key; no benefit is claimed from a higher allowance.

Tooltip titles can be provider placeholders; these never count as recovered names. Player consensus names retain Everloot CC BY-SA 4.0 credit/link/license and source provenance. Client categories are explicitly unconfirmed game-file data with a build and Blizzard credit. Only the documented Forever 1.60 family is accepted. Missing client build on the separately identified player-name layer stays unknown. No tooltip HTML, scripts, remote tooltip text/art, prices or upload-level player records are imported. Everloot's art reuse guidance does not permit an assumption of bulk icon redistribution: this adapter deliberately leaves icons to the independent existing Blizzard cache.

Published export indexes describe immutable NDJSON files and hashes. None was accessible here. Paged `/api/items` imports implement the permitted bulk path; an export-file downloader and player-upload consensus aggregator are not guessed from inaccessible schemas. No extraction of names from unrelated game editions is allowed. Derived Everloot data keeps its share-alike notice in provenance/API and attribution in UI; it is not relicensed as application code.

## Blizzard

Existing OAuth, bounded Forever item/media paths, namespace/region validation and independent media caching remain. New durable jobs apply source-specific negative caches and shared persistent budgets. Previously valid names/fields survive upstream errors. Migration is additive and local legacy data is backfilled in bounded worker batches. Artwork continues through authenticated local endpoints with strict HTTPS host/path, no redirects, size/type/signature checks and a 32 MiB cache ceiling.

## ForeverDB

[Developer contract](https://foreverdb.net/developers) identifies `/api/v1/meta`, `/api/v1/items/{id}`, authenticated headers, envelopes, quota/forbidden/subscription errors and build identity. The configurable adapter accepts only a minimal exact item ID/name/build envelope and rejects unsupported shapes. It is disabled by default and explicitly labelled pending authorized fixture verification. No successful response shape or current coverage is claimed. The approved owner key must be entered through Data Sources when available; the first authorized response must verify the documented envelope before enabling automated use. Rich stats and bulk parsing remain gated on an actual approved contract sample rather than invented field mappings. Attribution is retained on all supplied names.

## TheWoWDB

[Documentation](https://thewowdb.com/developers/) and repository's earlier successful beta fixtures support the retained exact Forever item/ID/build parser. Current requests remain inaccessible, and previous production probes were provider HTTP 403. Disabled by default. A forbidden response triggers persistent cooldown, never item nonexistence. No bypass, undocumented scrape or edition substitution.

## Legitimate client catalogs

[WoWDBDefs](https://github.com/wowdev/WoWDBDefs) supplies build-specific layouts; [ItemSparse definitions](https://github.com/wowdev/WoWDBDefs/blob/master/definitions/ItemSparse.dbd) include a Forever 1.60 family. [DBCD](https://github.com/wowdev/DBCD) reads supported DBC/DB2 formats using these definitions; [DBC2CSV](https://github.com/Marlamin/DBC2CSV) converts already obtained client files rather than supplying them. These are extraction tools/layouts, not permission to redistribute game assets or evidence that a client record is currently server-observed. Exact installed build, locale, layout hash, extraction tool revision, hotfix state, rights and unencrypted readable records must be established before any import. No client installation or authorized dataset exists in Cloud, so no client catalog is imported and no extra dependency/tool is installed. Never fill hidden/encrypted records with zeros or import Retail/Classic names to inflate coverage. Maintained exact-build client extraction is a possible follow-up if authorized inputs become available; the versioned field catalog can accommodate another adapter after its identity and retention contract are validated.

## Coverage boundary

The most recent repository coverage receipt available to Cloud is market 1/snapshot 12, 4,978 IDs, 1,191 Blizzard names and 3,787 unresolved (23.93%), recorded 2026-11-14 14:08 UTC. It is historical and precedes the production market-2 context. The repository has aggregate counts rather than all 4,978 IDs/names; supplemental overlap, conflicts, icons and basic attribute recovery on that same snapshot cannot be reconstructed. UI measurements always query its connected local DB and identify latest-recorded-snapshot scope. Synthetic benchmark/browser recovery is evidence of functionality only.
