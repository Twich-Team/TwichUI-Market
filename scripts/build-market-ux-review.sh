#!/bin/sh
# Build only the named review images from committed source. Preserve the previous tag if the build fails.
set -eu
cd "$(dirname "$0")/.."
review=.local/review
commit=$(git rev-parse --verify HEAD)
context=$(mktemp -d "$PWD/$review/source.XXXXXXXX")
trap 'rm -rf -- "$context"' EXIT
git archive --format=tar "$commit" backend web contracts deploy .dockerignore > "$context/input.tar"
tar -xf "$context/input.tar" -C "$context"
rm "$context/input.tar"
override="$context/contexts.yml"
cat > "$override" <<EOF
services:
  preview-api: {build: {context: "$context"}}
  proxy: {build: {context: "$context"}}
  backup-manager: {build: {context: "$context"}}
EOF
REVIEW_TAG="$commit" docker --context rootless compose --env-file "$review/review.env" -f compose.market-ux-review.yaml -f "$override" build
python3 - "$review/review.env" "$commit" <<'PY'
import os, pathlib, sys, tempfile
env = pathlib.Path(sys.argv[1])
lines = [line for line in env.read_text().splitlines() if not line.startswith('REVIEW_TAG=')]
with tempfile.NamedTemporaryFile(mode='w',dir=env.parent,delete=False) as updated:
    updated.write('\n'.join([*lines,'REVIEW_TAG='+sys.argv[2]])+'\n')
os.replace(updated.name,env)
PY
