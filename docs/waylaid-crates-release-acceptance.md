# Waylaid Crates production acceptance

[PR #61](https://github.com/Twich-Team/TwichUI-Market/pull/61) merged and deployed on November 25, 2026 as `83588a4061d17da198ffd50a3df35a4f3cdbe374`. The merged tree matched the checked feature head `b9663c6440397b8ae1735a97bf0ee8c04d9ee00e`. The deployed redesign was already serving production from `d6044df` and was reconciled to main through [PR #60](https://github.com/Twich-Team/TwichUI-Market/pull/60).

Sign in to [Waylaid Crates](https://market.twich.gg/waylaid-crates) with an active Market account. Administrators can edit the tier values or queue a catalogue refresh in [Administration → Waylaid Crates](https://market.twich.gg/admin/waylaid-crates). [Pricing definitions and API](waylaid-crates.md) · [Six isolated browser captures](evidence/waylaid-crates/README.md).

## Production checks

| Check | Result |
| --- | --- |
| Application and migration | Both API instances, Caddy website and enrichment verified at `83588a4`; schema `waylaid_20261125` |
| ForeverDB | Worker confirmed build `1.60.1.71091` at 06:08:43 UTC via one successful quota-accounted request |
| Coverage | 30 exact empty crate identities, 96 filling choices and 15 distinct sealed items. Exact sealed outputs are unknown. All 126 crate/material IDs already had cached names and artwork in US Normal Horde. |
| Rewards | Apprentice 5, Journeyman 10, Expert 15, Artisan unconfigured for Common crates. Other qualities have unknown payouts. |
| Prices | Live read-only checks on snapshot 225 returned costs for all 30 crates and 11 comparable current estimates. The selected Silverleaf material resolved through Market 2 item research and returned cached artwork. |
| Access | Public HTTPS delivered the exact reviewed bundle and both anonymous API requests returned 401. The deployed app was queried in-process under read-only transactions using existing member and administrator roles. Member results returned 200, admin access for a member returned 403 and administrator data returned 200. Actual signed-in journeys used the isolated review accounts. |
| Collection and logs | Natural market 2 / house 114 check at 06:10:06 UTC. Both feeds and the 300-second schedule remained healthy. The bounded post-cutover log sample had zero 5xx or application/worker errors. |

[Backend CI](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45557034018), [Private website CI](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45557034019), [Native NAS CI](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45557034009), and [Windows Companion CI](https://github.com/Twich-Team/TwichUI-Market/actions/runs/45557034023) passed on the tree-identical head. Local checks included 824 PostgreSQL tests, 42 focused PostgreSQL checks at the final source, 161 Vitest tests, 158 operational and 16 contract tests, Alembic round-trip/schema drift, and Chromium and iPhone-sized WebKit fixture and isolated HTTPS journeys. Eight consecutive Chromium runs reproduced the successful admin navigation after fixing a first-load routing race.

## Deployment record and rollback

Only `api`, `local-api`, `proxy`, and `enrichment` were replaced. Their environment, limits and mounts match the previous services. All other production container identities and the existing collector schedule were verified. The pinned protected database archive created November 24 at 13:39:40 UTC had an actual NAS restore receipt at 18:58:39 UTC. The archive inventory reported its existing integrity digest and the recovery evidence was current at cutover.

| Service | Image |
| --- | --- |
| API / local API | `sha256:7a468d06e9553301f11cd5af6664ebfec379dda3a4c1a4a7d491543c5de9d8fb` |
| Website proxy | `sha256:cf6833c3993d1801980f2087c118937e48d65078758f1f23f714b8d3a0f35693` |
| Enrichment | `sha256:0c3482dd133b7c9c83d758e889672be4d9b2c729e58466d65b856516b542fe32` |

The active production Compose pins and immediate predecessor pins are retained privately in `.worktrees/waylaid-crates/.local/waylaid/release/` relative to the primary Market checkout. Retain this directory and the pinned images. The release files are `app-release.json` and `worker-release.json`. The rollback files preserve the exact preceding API and proxy images (`d6044df`) and the previous enrichment image. Roll back affected services only, keeping the additive migration, catalogue records and rewards. Allow a running Waylaid refresh to finish before reverting enrichment when the worker is healthy.

```sh
release=/home/marketdev/projects/TwichUI-Market/.worktrees/waylaid-crates/.local/waylaid/release
docker --context rootless compose -p twichui-market --env-file /dev/null \
  -f "$release/app-rollback.json" up -d --no-deps --no-build --wait api local-api proxy
docker --context rootless compose -p twichui-market --env-file /dev/null \
  -f "$release/worker-rollback.json" --profile metadata up -d --no-deps --no-build enrichment
```

Verify the public health check, pinned image IDs and natural collection afterward. Keep the current database, protected backups, backup manager, retention, credentials and signed Companion releases in place.
