# Metadata recovery release procedure

This release is explicitly owner-authorized after successful acceptance. It is not deployed yet. Durable free-space headroom currently blocks the fresh retained production backup, isolated real restore and compatible image build. Do not infer approval to prune old archives, change storage budgets, clear provider caches or remove devices. Source integration can proceed independently after exact-source checks; production promotion cannot bypass this blocker.

## Release identity and compatibility

Start from integrated mobile `fa089a2`, preserve Companion beta.5's existing private store, signatures and updater contracts. No desktop, addon, price/ingest/collector source changes. Deploy the API, local API, frontend and enrichment together. Use the current production project's original environment and all overlays listed on the actual proxy (including usability and mobile), then append the final release image overlay last. Never print resolved Compose secrets. The final image identities must be actual verified build digests, not assumed tags.

Required schema: one linear head `recovery_20261117`, following `usability_20261117`. It adds optional source/task evidence, append-only per-invocation records, bounded item decisions and a small worker fairness/audit cursor; an index supports the latest verified ForeverDB build lookup. It does not backfill invented requests or rewrite existing provenance. `alembic check`, synthetic predecessor-column preservation and guarded round trips pass; the real restored population must still be rehearsed before production.

## Required production preparation

1. Resolve durable headroom without deleting retained data or changing storage policy implicitly. Recheck filesystem, memory, existing rootless services and ports. Stop if the safety margin is inadequate.
2. Retain all existing archive hashes. Make a fresh bounded custom PostgreSQL dump into the approved durable release location, checksum/length-check it, and verify the keyring's separately retained encrypted recovery copy without displaying credentials. Do not write a new dump into an already full scheduled budget.
3. Restore into a separate PostgreSQL database named `market_test`, bounded memory/CPU/tmpfs/logs and no worker/provider campaign. Rehearse the additive migration and compare original-column fingerprints: accounts/sessions/devices/preferences, encrypted provider envelopes/configuration/usage, source/version/catalog rows, observations/listings/statistics/daily history, markets/schedules and bridge/Companion data. Existing live rows remain untouched. Verify decryptability in memory with the existing keyring, never by printing keys.
4. Confirm actual final integration SHA, exact-source backend/website/Windows CI, exactly one intended Alembic head and compatible old API reads on the restored additive schema. Reconcile any genuine concurrent source changes without merging unrelated Advisor work.
5. Build/package only from that source, compare locked dependencies and contract bytes, and record actual API/frontend image IDs/revisions. Pin the predecessor API `fa5d8f4…`, frontend `f2c1010…` and enrichment `b25a1b3…` for rollback. Resource/settings/environment/mount deltas must be restricted to the intended images.

## Scoped promotion

Drain/stop only the existing enrichment service, apply the rehearsed additive migration using the new API image and original production environment, then replace **api local-api proxy enrichment** with explicit `up -d --no-deps --wait` targets. Never start the whole collector profile, recreate the database, replace the collector, or change provider configuration. Existing budget reservations, cooldowns and source retry windows remain. No separate recovery campaign is needed for acceptance; observe the already-authorized automatic schedule under preserved limits.

Public authenticated acceptance must cover `/administration?metadata_view=tracker`, the existing Item Metadata overview/Recovery Jobs/Recent Provider Results, Data Sources and shared quotas, Explorer/Details/attribution, and existing Companion authentication/sync. Check secret redaction, browser-only administrator authorization/CSRF, selected-period denominators and clearly qualified historical evidence. Compare protected original rows, provider settings/envelopes, container identities and the existing beta.5 store. Confirm house 114 alone/300 seconds, successful subsequent collection, no new failures, no duplicate worker, retention still unauthorized/disabled and no outbound request burst.

## Immediate compatible rollback

Append [the pinned predecessor overlay](../compose.metadata-recovery-rollback.yaml) last to the **same complete original production Compose command**, and explicitly replace only `api local-api proxy enrichment` with `--no-deps --wait`. Keep schema `recovery_20261117`, all request/source/quota evidence and every new auction observation. Never restore a dump over production, downgrade populated evidence, delete new history or revoke existing credentials to roll back application images. Recheck public authentication, metadata/Explorer/Companion behavior and collection. A forward correction can use the retained new evidence.

## Measurement boundaries

Historical tasks overwrite retries and often lack requested goals/deltas. Their final outcomes/reservations are not precise outbound counts. New ledger rows distinguish completed invocations, queued quota deferrals and unfinished crash reservations; artwork and validation are separate request kinds. Useful rate counts metadata invocations committing a missing field or a verified changed value once, regardless of how many fields changed. Empty optional equipment fields do not imply endless missing work. Missing details and provider errors never prove that an observed item does not exist.

The old/new replay and 5,000-item selector measurements are synthetic, not production improvement claims. The new policy spends additional local CPU to avoid external work; PostgreSQL server CPU is not included in process CPU figures. Local allocation/RSS figures do not establish a production p95. Observe genuine postdeployment results separately without starting a campaign to manufacture evidence.
