# Storage & Backups production release

PR [#58](https://github.com/Twich-Team/TwichUI-Market/pull/58) is merged into main and deployed directly to production. Main and deployed application source are **3836c2a19cd5fcd21c5c1793c6370fecbe0b6e7f**. The four-service cutover finished November 24, 2026 at **2:07 p.m. America/Denver**, after exact merged-source CI passed. No preview was required.

Only `api`, `local-api`, `backup-manager` and `proxy` were replaced. Their image revisions and approved source-file hashes match main; the public index matches the exact main frontend build. Runtime dependencies were inherited from the previous immutable production images. All original environments, mounts (including the manager's anonymous volume), resource budgets, security settings, ingress, networks and logging were compared before and after. Collector, database, retention, monitor, restore service and enrichment container IDs/start times are unchanged. No schema migration occurred.

## CI and production acceptance

All four post-merge workflows passed, with actual job-log proofs identifying `event=push`, `source_kind=commit`, exact main source and an unchanged checkout:

- [Backend](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45485478700).
- [Private website](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45485478756), including actual management-boundary Chromium/WebKit checks.
- [Native NAS](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45485478696).
- [Windows Companion](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45485478733), including signed SDK and installed-release checks. No client release was published.

Actual authenticated production browser verification passed Overview, Backups, Storage and Maintenance at 1920, 1280 and 390 pixels. All charts/data were allowed to settle before capture. Fourteen production screenshots, including masked settings and backup details, were visually inspected; narrow layouts received an independent review. Capacity/device consumption, database allocation, physical copies, recovery count and migration state were cross-checked against actual APIs. No browser mutation, console error, page error or HTTP 5xx occurred. Production/service/collector/retention logs contain no unexpected errors. Screenshots remain in the owner's local delivery package rather than this public source repository because they expose actual administration configuration.

## NAS, recovery and preservation

NAS remains the active destination and is accessible. Migration succeeded at 11:30 a.m.; all six NAS recovery points remain, totaling **9,420,978,411 bytes (8.77 GiB)**. Each of the six local originals was fully SHA256-checked against the completed migration plan both before and after deployment. Physical storage therefore contains **12 copies / 18,841,956,822 bytes (17.55 GiB)** while recovery-point count remains six. The interface correctly distinguishes them. Five points are protected.

The latest protected NAS point was successfully restored into the separate verification PostgreSQL service at **11:58 a.m.** before this deployment. Recovery evidence remains valid until **November 25 at 6:39 a.m. Mountain time**. No new restore, migration, archive deletion or manual maintenance was initiated by deployment acceptance. Existing automatic retention continued independently under its unchanged authorization, including an ordinary bounded 60,000-row cycle; those normal policy operations are not attributed to this task.

Backup policy remains enabled every 86,400 seconds, retaining two scheduled UTC daily points, with one minimum recovery point and the original 3 GiB warning reserve. Next scheduled backup is **November 24 at 9:30 p.m. Mountain time**, with the existing automatic isolated-restore behavior. Retention remains 7/90/365 days, 60-day support, the same authorization and five-minute/0.25-CPU limits. No authorization or policy was modified. Original 99 user/password/role records, 23 preferences, four encrypted provider configurations, keyring, immutable distribution inventory and market settings retain their fingerprints. Encrypted NAS settings, active/previous destinations and backup policy also match exactly. Temporary grants 512/513 were revoked, both rejected with HTTP401, and their token file was removed.

Both auction and commodity feeds continued after cutover with zero failures, retaining market2/house114/300 seconds. Existing sync cursor continuation succeeded. The current Companion contract3 summary completed normal preparation and reported **33,717 variants** after deployment. Four sampled current/history partitions from the preceding immutable generation remained downloadable with matching sizes/SHA256 across cutover. This verifies server delivery, not a physical owner-PC or game-session acceptance.

## Performance and remaining limits

Measured dedicated dashboard API reads were **18–561 ms** across the initial browser pass; final checks were **32–361 ms**. Fully settled initial pages, including all background administration reads, charts and screenshot capture, took approximately **4.0–7.2 seconds** while Companion preparation was active; primary content appeared earlier. Current/history sample downloads took31–49 ms and sync continuation83 ms. Cold Companion generation preparation took about 80–86 seconds through the existing bounded retry protocol; warm summary reads were 34 ms. No production load benchmark or resource reduction is claimed.

The existing large ECharts build warning remains. NAS capacity history is not recorded, so NAS forecasting stays unavailable; the PostgreSQL filesystem forecast uses actual observations and remains an estimate of the whole filesystem/account reserve. Historical missed backup schedules are not reconstructible. Explicit connectivity test snapshots age; current readable inventory and an old permission-test timestamp are distinct facts. The pre-existing legacy bridge manifest endpoint returned HTTP413 before deployment; its limits were preserved. Current summary/sync delivery was verified without bypassing them. The existing reviewed local-only recovery policy was preserved; NAS accessibility/restoration alone does not establish an independently attested failure domain.

## Retained release and rollback

Keep `/home/marketdev/.codex/worktrees/storage-backups-dashboard/TwichUI-Market` and its ignored `.local/storage-release` directory: running Compose labels reference this checkout. Also keep `/home/marketdev/projects/TwichUI-Market/.worktrees/backup-nas`, which still supplies the original secret/keyring mounts. Do not archive these live-referenced checkouts.

The private release definition is `.local/storage-release/compose.release.json`; exact image IDs are in `.local/storage-release/images.env`. It preserves the original private environment files and existing external volumes/networks. Validate it with `docker compose -p twichui-market --env-file .local/storage-release/images.env -f .local/storage-release/compose.release.json config --quiet`. Replacements must be explicitly scoped with `up -d --no-deps` to the four named services, after fresh operation/recovery checks. The recorded cutover acquired the existing backup flock, rechecked idle durable jobs and stopped the idle manager before replacement; APIs passed health gates before the frontend was replaced.

`.local/storage-release/compose.rollback.json` pins the previous NAS-aware manager **f8b2490c9f7a**, API **d05cac0444af** and frontend **c6b7aa8e28ff**, with original configuration and volumes. It validates and all immutable images remain local. If a significant regression requires rollback, follow the established retention-quiescing and no-active-operation checks, then scope the rollback `up -d --no-deps` to `backup-manager api local-api proxy`. Do not restore an old manager-state snapshot over live state, delete archives or use a pre-NAS manager. No rollback was necessary. No further administrator action is required for this deployment.

[Sanitized verification record](evidence/storage-dashboard-release/verification.json) contains exact runtime IDs, source proofs, timings and final health.
