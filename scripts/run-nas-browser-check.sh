#!/usr/bin/env bash
# Disposable fixtures only; fixed project name prevents touching production.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p artifacts/backup-nas
nas_dc=(docker --context rootless compose -p twichui-market-nas-browser -f compose.nas-browser.yaml)
docker --context rootless build --memory 1g --cpu-quota 50000 -f deploy/web.Dockerfile -t twichui-market-web:nas-candidate . > artifacts/backup-nas/web-build.log 2>&1
"${nas_dc[@]}" down --volumes > artifacts/backup-nas/browser-reset.log 2>&1
"${nas_dc[@]}" up -d --wait >> artifacts/backup-nas/browser-reset.log 2>&1
"${nas_dc[@]}" exec -T api alembic upgrade head > artifacts/backup-nas/browser-migration.log 2>&1
for nas_seed in seed seed-admin seed-quality seed-private-beta; do
  "${nas_dc[@]}" exec -T api python - < "web/e2e/$nas_seed.py" >> artifacts/backup-nas/browser-seed.log 2>&1
done
docker --context rootless run --rm --network twichui-market-nas-browser_default --memory 1g --cpus 1 --pids-limit 256 --log-driver none -v "$PWD:/work" -w /work/web mcr.microsoft.com/playwright:v1.65.1-noble npm run test:e2e -- backup-nas.spec.ts > artifacts/backup-nas/browser-nas-current.log 2>&1
