# Canonical main baseline and production inventory

The owner authorizes reconciling and merging PR #42 into `main`, with **no deployment or production mutation**. Source baseline is `3b59f0f34617cbcf12a43baddfeed7a1e668feb2` (beta.10 integration); the baseline-record commit adds only inventory, operational snapshots and development instructions. Main becomes the normal feature/PR target after merge. Historical release references remain valid.

## Verified live source, 2026-11-21 UTC

The versioned authority is [deployment manifest](../deploy/baselines/2026-11-21/manifest.json). Full image IDs, per-service ordered Compose paths, resources, mounts and source labels are in [runtime evidence](evidence/production-baseline/runtime.json). Image IDs identify the actual running content, regardless of stale Compose image labels or mutable tags.

| Component | Active source | Immutable image prefix |
| --- | --- | --- |
| Website / Caddy proxy | `fe92999`; candidate's website source produces all 22 identical files | `f48f8f1a7e5a` |
| API and local API | `fe92999` plus retention `3ebd8b3`, Workshop `47ab3cf`, sync `580e2e5`, history `8dfa511`; all 64 Python modules match beta.10 lineage | `428f0acfa92e` |
| Collector | `fe92999`, all 62 Python modules identical | `aab0d6585115` |
| Enrichment | `bf8a04a`, all 57 active `/app/market` modules identical | `3ef6f5796454` |
| Retention and monitor | `fe92999` plus `retention.py` / `retention_worker.py` from `3ebd8b3` | `9712cd35a1f6` |
| Backup manager | `e49de6a`, both service/management modules identical | `79cea119910a` |
| Windows Companion | published `2.0.0-beta.10`, payload `be09ff9` | installer SHA256 `16adc59355cb99c1ec56322941f0a219f877c39fb2030584358044aa0fde527f` |

Full source commits, artifact identity and hashes are in the manifest and [source verification](evidence/production-baseline/component-source-verification.json). API contracts retain two older `addon-source.txt` pins from `4b0ff82` / `3a8ecca`; [file provenance](evidence/production-baseline/historical-file-provenance.json) records exact hashes and Git origins. Candidate pins intentionally reference the final paired addon. No API executable source differs. Enrichment imports from `/app/market`; its installed site-packages has eight older, inactive modules, whose hashes are retained rather than falsely claiming both copies match.

Read-only PostgreSQL inspection confirms schema `retention_20261118`, only market 2 / house 114 enabled at 300 seconds, zero collector failures, retention automation enabled and zero recorded retention batches at observation. This is live evidence, not a fixture. Backup manager scheduled policy is disabled; legacy backup container is stopped. Automatic retention remains recovery-gated under its existing authorization; this merge refreshes no recovery evidence and changes no policy.

The signed store's current pointer and actual installer bytes independently confirm beta.10 source/hash/size. This is server publication verification, not evidence of an installation or opt-in on any owner's PC.

## Included source versus enabled features

Advisor U1 and U2 branches are ancestors of beta.10 despite draft PRs. Their code is offline tooling under `scripts` and experimental contracts; the backend has no Advisor runtime import/route. U2's trust registry is empty. They are preserved source, not enabled player features or approved native mappings.

Automatic Workshop delivery is also ancestral. Its summary API is deployed, and beta.10 includes the client writer through the separately authorized release. `Configuration::load` returns no configuration on a fresh install; setup requires an explicit reviewed destination and confirmation before enabling delivery. Server inventory cannot establish a particular PC's opt-in, game-loaded generation or actual Forever acceptance. Draft state is not evidence that this code is excluded. Existing delivery/bridge bounds, pricing defaults and genuine-history/native acceptance limits remain unchanged.

## Reconstructing the deployment inventory

Do not rebuild every component from current main and describe it as the existing deployment. Use the exact per-component source/image mapping. Historical images remain the rollback authority. The existing layered build recipes are retained in `deploy/retention-local-recovery.Dockerfile`, `deploy/workshop-api.Dockerfile`, `deploy/sync-performance.Dockerfile` and the Workshop-history release overlay/receipt. Full per-file runtime hashes provide a reproducible content check.

There are 27 distinct Compose source paths across service labels; the API uses 25 in order (the prior 24 plus history). [Configuration inventory](evidence/production-baseline/compose-files.json) includes SHA256 and versioned copies of available files. Seven obsolete absolute paths are missing. Their copies are explicitly **reconstructed from the beta.10 Git tree**, not claimed to have been read at runtime. Their effective images/resources/mounts are independently read from containers. Relative paths and `${...}` private inputs still resolve against the original project root; snapshots are audit material, not a new approved runnable production stack. Never supply or commit private `.env`, keyring or token bytes.

Preserve existing production worktrees, volumes, immutable images, signed artifacts, [history API rollback](workshop-history-release.md), [beta.10 rollback](companion-beta10-release.md), retention recovery and backup runbooks. Missing old path references are operational debt; repairing or simplifying production Compose paths needs a separately authorized operational task. This baseline merge does not repair them by changing services.

## Verification and merge record

Local candidate checks: TypeScript/Vite production build and **132 Vitest tests pass**. All **22 website files** match production bytes. Active Python source comparisons pass for both APIs (64 each), collector (62), enrichment (57), retention/monitor (62 each), backup manager (2). Historical whole-package differences are recorded explicitly.

Exact baseline-record source must pass Backend, Private website and Windows companion CI before PR #42 merges. CI includes PostgreSQL regressions/migration preservation, operational/security checks, browser workflows, Windows Rust/Tauri/install/upgrade/retained-data and signed original-byte acceptance. Final run links and merge SHA will be recorded after those checks finish. No installer publication, migrations, service restarts or collection/retention changes are part of verification.

## Branch workflow and cleanup

`main` is the canonical development baseline. Start ordinary feature branches from current `origin/main` and target PRs to `main`. Integration/release branches are exceptional, scoped staging tools; they do not replace main. No branch is deleted or force-pushed by this task.

The beta.10 branch is the baseline PR head until merge, then a retained release reference. `integration/companion-v2-metadata-recovery` and earlier beta integration branches are superseded development bases; preserve their named release/rollback references. Draft Advisor and Workshop feature branches are incorporated ancestry, not independent active feature releases. There is no new feature authorization in this baseline task. Existing personal worktrees remain untouched.

Umbrella PR #1 head `75c6f38` and #2 head `b18927a` are both ancestors of beta.10. Their original commits are included; later intentional revisions supersede older implementation. Neither contains an unincorporated commit. Recommend closing them as superseded after the baseline merge, retaining their review history. Do not merge their obsolete trees over main.

Branches with commits outside the beta.10 ancestry at inspection: `integration/m15-companion-release`, `release/companion-beta5-publication`, `release/explorer-provider-repair-73617a9`, `release/intelligent-metadata-recovery-final-api`, `release/mobile-experience-production`. They need individual documentation/tree comparisons before archival; lack of ancestry is not proof of unique necessary application changes. Retain all branches automatically. Review the fresh remote branch inventory and open PRs before starting new feature work.
