# Workshop history API rollout

The owner authorized “deploy market updates” and separately “also merge the addon changes into main”. This authorizes the Market API update and addon main merge, without a new signed Companion or addon publication. TwichUI PR62 is merged at `074435e41521e97ad125e3094c45a9eb767f90e1`, after the required exact-head verification passed. Its application remains equivalent to the reviewed `12a55a5` source.

The API image is `sha256:428f0acfa92ec42fcc40d467e072ad3d14f7175c02ad76303d141d6824b983af`, derived from the exact live `a79a7f0fca9c8fb6257201d53b6509e08b7630296661b1d672a1c828bb1bd907` image. Only `workshop_summary.py` in both runtime locations and the new summary-v2 contract directory differ. The module matches exact verified source `8dfa5116397403bb93e90160e8706285f272f64f`. Bridge, pricing, authentication/sync and retention modules are unchanged. The actual image passes 128 focused PostgreSQL/authentication/sync/retention checks in an isolated disposable database. [Image proof](evidence/workshop-history-release/image-source.json), [image tests](evidence/workshop-history-release/image-tests.json).

## Procedure and rollback

Keep all 24 original overlays from the live API Compose labels, in order, with their existing environment files and managed-backup interpolation paths. Append this worktree's `compose.workshop-history-release.yaml` last. Recreate only `api local-api` with `up -d --no-deps --no-build --pull never --wait`; do not recreate other services. [Preflight](evidence/workshop-history-release/compose-preflight.json) proves that only these image fields change and the effective API environment matches production.

Rollback retains that full chain and appends an image-only override selecting `sha256:a79a7f0fca9c8fb6257201d53b6509e08b7630296661b1d672a1c828bb1bd907` for both APIs. Recreate only those services. There is no database migration or provider/collector/retention/backup policy change. Legacy summary contract 1 remains available; negotiated contract 2 adds actual dated daily observations and explicit gaps.

The existing protected local recovery gate passes; automatic backup scheduling remains disabled. Preserve all source observations, accounts/credentials/preferences, provider configuration/envelopes/keyring, collector identities/settings and signed releases. The rollout status and genuine HTTPS/native acceptance will be recorded after replacement; preflight alone is not a live-success claim.

The addon merge is a development integration. Real Forever AddOns appearance, first-install discovery/reload and frame/GC behavior remain unverified. Current private Companion publication remains beta.9; native client-side retry/game-open/history-negotiation changes need a separately authorized newer signed Companion version.
