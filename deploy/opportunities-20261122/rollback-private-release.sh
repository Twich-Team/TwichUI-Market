#!/usr/bin/env bash
set -euo pipefail
# Actual retained pre-release version and OS operator; no database/ingress access.
case "${1:---check}" in --check|--execute) ;; *) echo 'Use --check or --execute' >&2; exit 2;; esac
[[ "$(id -u)" = 1002 ]]
[[ "$(sha256sum /home/marketdev/.codex/worktrees/companion-beta10/TwichUI-Market/desktop/target/release/examples/verify_release | cut -d ' ' -f 1)" = 9e47f51bad9a675c4f45b33b9b9743fb7588d9abfe7f6b0b9228d02b6b13ea32 ]]
docker --context rootless image inspect sha256:c8686b5be272bcef4589df5a99a539cf9311dc111d0ba31ac8eee6c31f3802ec >/dev/null
operator=(
  docker
  --context
  rootless
  run
  --rm
  --network
  none
  --read-only
  --memory
  256m
  --memory-swap
  256m
  --cpus
  1
  --pids-limit
  64
  --log-driver
  none
  --tmpfs
  /tmp:rw,size=32m
  --env-file
  /home/marketdev/projects/TwichUI-Market/.worktrees/market-opportunities-release/.local/opportunities-resume/operator-public.env
  -v
  /home/marketdev/projects/TwichUI-Market/.worktrees/market-opportunities-release/.local/opportunities-resume/operator-source:/work:ro
  -v
  /home/marketdev/.codex/worktrees/companion-beta10/TwichUI-Market/desktop/target/release/examples/verify_release:/verifier/verify_release:ro
  -w
  /work
  --entrypoint
  python
)
if [[ "${1:---check}" = --execute ]]; then
  "${operator[@]}" -v twichui-market_companion-private-beta:/private-beta sha256:c8686b5be272bcef4589df5a99a539cf9311dc111d0ba31ac8eee6c31f3802ec -m market.private_beta_publisher rollback 2.0.0-beta.10 --actor marketdev
else
  "${operator[@]}" -v twichui-market_companion-private-beta:/private-beta:ro sha256:c8686b5be272bcef4589df5a99a539cf9311dc111d0ba31ac8eee6c31f3802ec -c 'from market import companion_private_beta as b; from market.release_publisher import verify_installer; m,a=b.load("2.0.0-beta.10"); verify_installer(a.parent/"manifest.json",a); print("Retained signed beta.10, reviewed policy and independent verifier pass; no pointer change.")'
fi
# Pointer rollback never forces installed clients to downgrade. Pause delivery and
# restore a complete compatible 1/2 generation before downgrading consumer support.
