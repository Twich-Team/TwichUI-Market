#!/bin/sh
# Manage only this rootless, loopback-bound review installation.
set -eu
cd "$(dirname "$0")/.."
review=.local/review
dc() { docker --context rootless compose --env-file "$review/review.env" -f compose.market-ux-review.yaml "$@"; }
case "${1:-status}" in
  status) dc ps ;;
  stop)
    dc stop proxy
    dc stop preview-api
    umask 077
    dc exec -T db pg_dump -U market -d market_test -Fc > "$review/market-test.dump.tmp"
    mv "$review/market-test.dump.tmp" "$review/market-test.dump"
    dc down ;;
  start)
    test -s "$review/accounts.json" && test -s "$review/review.env"
    dc up -d --wait db
    initialized=$(dc exec -T db psql -U market -d market_test -Atc "SELECT to_regclass('public.users') IS NOT NULL")
    if [ "$initialized" = f ] && [ -s "$review/market-test.dump" ]; then
      dc exec -T db pg_restore --exit-on-error --single-transaction --no-owner -U market -d market_test < "$review/market-test.dump"
    fi
    dc up -d preview-api backup-manager
    attempt=0
    until dc exec -T preview-api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health',timeout=3)" >/dev/null 2>&1; do
      attempt=$((attempt + 1))
      [ "$attempt" -lt 40 ] || { echo "Review API did not start; inspect compose logs." >&2; exit 1; }
      sleep 1
    done
    members=$(dc exec -T db psql -U market -d market_test -Atc 'SELECT count(*) FROM users')
    if [ "$members" = 0 ]; then
      for fixture in seed seed-admin seed-recovery-tracker; do
        dc exec -T preview-api python - < "web/e2e/$fixture.py"
      done
      dc exec -T preview-api sh -c "cat > /tmp/review-seed.py" < scripts/seed-market-ux-review.py
      dc exec -T preview-api python /tmp/review-seed.py < "$review/accounts.json"
    fi
    # Refuse to expose a partially seeded database containing stock CI passwords.
    reviewed=$(dc exec -T db psql -U market -d market_test -Atc "SELECT count(*) FROM users WHERE active AND username IN ('review_member','review_admin')")
    stock=$(dc exec -T db psql -U market -d market_test -Atc "SELECT count(*) FROM users WHERE active AND (username IN ('owner','member_fixture') OR username LIKE 'prefs_%')")
    [ "$reviewed" = 2 ] && [ "$stock" = 0 ] || { echo "Review bootstrap is incomplete; inspect the private database." >&2; exit 1; }
    dc exec -T preview-api python - < scripts/seed-market-ux-activity.py
    dc up -d --no-deps proxy
    dc cp proxy:/data/caddy/pki/authorities/local/root.crt "$review/preview-root.crt"
    curl --retry 5 --retry-all-errors --retry-delay 1 --max-time 10 -fsS --cacert "$review/preview-root.crt" https://localhost:18444/api/v1/health ;;
  *) echo "Usage: $0 start|stop|status" >&2; exit 2 ;;
esac
