# Mobile Experience Modernization production release

Owner explicitly approved PR #23 for controlled merge and frontend-only deployment on 2026-11-17. Physical iPhone acceptance follows deployment and does not block this approved test release. Earlier review-only holds are superseded for this exact scope.

## Frozen source and preflight

PR #23 merged into `integration/companion-v2-metadata-recovery` at **fa089a2660e745d6f77f5c2b0b7bbcb9109d6ae8** from approved review head `b9db6b76bb874e800fccae8a1c39176d620c7492`. The merge tree equals the reviewed head; application source equals verified `9fbd10efa3d747d322ddeefc5d21cd57465f4b14`. No integration conflict, force push or unrelated change.

Production preflight retains API/collector application `2920f366f7b5cd32178ae06ae94cea84701ff87f`, schema `usability_20261117`, enrichment `6bb71a6`, and already published signed Companion beta.5. Backend/contracts have no diff from the retained API source. No database migration, provider campaign, pricing change or Companion publication is part of this release.

Fresh [backup](evidence/mobile-release/backup.json) is retained privately under `.worktrees/mobile-release/artifacts/mobile-release/`: 537,544,711 bytes, SHA-256 `02484c55eea3c72d1a2ae3cc8670944b87c3fb73f1187f4ae9928b39db3c5346`. A bounded, network-isolated `market_test` restore preserves all 982 original observations, 87 snapshots and 10,163,661 listing rows; [original-column fingerprints](evidence/mobile-release/restore-preservation.json) match. The first isolated fingerprint query exhausted its 5 GiB temporary filesystem while sorting; using the existing ordered indexes completed the identical check without increasing its limits. The isolated database is retired. All previous scheduled archives pass hashes and remain intact. The pre-existing full scheduled-backup budget remains unchanged; no archive was pruned or storage policy expanded. Off-host recovery copies remain unverified.

[Compose preflight](evidence/mobile-release/compose-preflight.json) proves only the `proxy` image changes, and rollback restores its exact prior configuration. New image **sha256:f2c101081b74615f4220062d91975d80d1de2e53c269acfabbba57797e7f13bb**, built from the merged frontend and previous production Caddy runtime. Previous **sha256:197b01f4f4b9e7cf35d574e4c3e6f60f94a462e3dd5b9dccd488fb128d3743d9** remains tagged `twichui-market-web:mobile-rollback-197b01f`.

Status at preflight checkpoint: exact merged-source CI and public deployment acceptance continue. No production replacement is claimed by this checkpoint.
