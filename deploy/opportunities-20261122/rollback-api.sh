#!/usr/bin/env bash
set -euo pipefail
# Prepared against the actual rootless project and all 25 original overlays.
# Default mode validates only. Never restores a database or recreates dependencies.
case "${1:---check}" in --check|--execute) ;; *) echo 'Use --check or --execute' >&2; exit 2;; esac
[[ "$(id -u)" = 1002 ]]
[[ "$(docker --context rootless info --format '{{json .SecurityOptions}}')" == *rootless* ]]
export MARKET_MANAGED_BACKUP_ROOT=/home/marketdev/projects/TwichUI-Market/backups
export MARKET_BACKUP_TOKEN_FILE=/home/marketdev/projects/TwichUI-Market/.local/backup-management/token
dc=(
  docker
  --context
  rootless
  compose
  -p
  twichui-market
  --project-directory
  /home/marketdev/projects/TwichUI-Market
  --env-file
  /home/marketdev/projects/TwichUI-Market/.env
  --env-file
  /home/marketdev/projects/TwichUI-Market/.env.combined-release
  -f
  /home/marketdev/projects/TwichUI-Market/compose.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.tls.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.traefik.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.companion-private-beta.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.combined-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.admin-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.explorer-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.polish-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.foreverdb-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/usability-release/compose.usability-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/mobile-release/compose.mobile-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-chart.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/intelligent-metadata-recovery/compose.metadata-recovery-api.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.owner-backup-policy.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.unified-coverage-release.yaml
  -f
  /home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market/compose.backup-management.yaml
  -f
  /home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market/compose.backup-review-images.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/compose.companion-beta7-web.yaml
  -f
  /home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market/compose.retention-cap.yaml
  -f
  /home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market/compose.retention-release.yaml
  -f
  /home/marketdev/.codex/worktrees/automatic-historical-retention/TwichUI-Market/compose.retention-activation.yaml
  -f
  /home/marketdev/.codex/worktrees/workshop-dev-build/TwichUI-Market/compose.workshop-api-release.yaml
  -f
  /home/marketdev/.codex/worktrees/companion-sync-performance/TwichUI-Market/compose.sync-performance-release.yaml
  -f
  /home/marketdev/.codex/worktrees/workshop-live-status/TwichUI-Market/compose.workshop-history-release.yaml
  -f
  /home/marketdev/projects/TwichUI-Market/.worktrees/market-opportunities-release/deploy/opportunities-20261122/compose.api-rollback.yaml
)
docker --context rootless image inspect sha256:428f0acfa92ec42fcc40d467e072ad3d14f7175c02ad76303d141d6824b983af >/dev/null
[[ "$(docker --context rootless inspect twichui-market-backup-1 --format '{{.State.Status}} {{.HostConfig.RestartPolicy.Name}}')" = 'exited no' ]]
[[ "$(docker --context rootless inspect twichui-market-migrate-1 --format '{{.State.Status}}')" = exited ]]
"${dc[@]}" config --quiet
if [[ "${1:---check}" = --execute ]]; then
  "${dc[@]}" up -d --no-deps --no-build --pull never --wait api local-api
else
  echo 'Rollback chain/configuration and prior immutable API image are available; no service changed.'
fi
