# Operations

Use only `docker --context rootless` and project-scoped Compose commands. Do not enumerate or modify unrelated containers. No sudo. Before startup inspect `ss -ltn`, `free -h`, `df -h .` and confirm rootless security options. Services bind to 127.0.0.1; external HTTPS/domain/firewall work requires a separate administrator action and is not authorized here.

Never put credentials in command arguments, Git, logs or fixtures. Read Blizzard credentials from environment. Store local configuration in ignored .env. Probe output must exclude access tokens and Authorization headers.

## Local development deployment

Copy .env.example to .env (mode 600), choose a random URL-safe POSTGRES_PASSWORD, recheck port 18780, then run `docker --context rootless compose up -d --build`. Alembic runs before API startup. Caddy exposes only 127.0.0.1:18780. Health: `/api/v1/health`. Local HTTP uses COOKIE_SECURE=false; HTTPS deployment requires true and exact APP_ORIGIN. External HTTPS is not deployed yet.

Bootstrap the first administrator using `docker --context rootless compose run --rm -e MARKET_ADMIN_USERNAME -e MARKET_ADMIN_PASSWORD api python -m market.bootstrap` with credentials already exported in the shell. Never pass secret values in arguments. Bootstrap refuses if any users exist. Browser login returns a CSRF token required as X-CSRF-Token on mutations; session cookies are HttpOnly/SameSite Strict. Invitations are single-use, expire in seven days and create members only. Administrator browser sessions can change roles/disable users; the final active administrator is protected. Device tokens expire in 90 days, are stored hashed server-side, cannot mint more devices and cannot perform administrator actions.

## Tests

`docker --context rootless build -t twichui-market-backend:dev backend`

`docker --context rootless compose -p twichui-market-test -f compose.yaml -f compose.test.yaml run --rm test`

The test overlay uses an isolated tmpfs database; tests refuse non-test PostgreSQL database names. Clean up only its resources with the same compose arguments followed by `down`. Never use the overlay with the development project name. PostgreSQL tests recreate schema; migration verification must run separately against a disposable database before tests. SQLite provides quick tests but does not establish PostgreSQL concurrency correctness.

Backup, restoration and Windows release instructions will be added alongside verified implementations. No production deployment or backup verification exists yet.
