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

## Collector

The collector is opt-in: `docker --context rootless compose --profile collector up -d worker`. It does not run for disabled or unverified markets. Do not mark markets verified until S1 live evidence establishes their mapping and payload semantics. Set BLIZZARD_CLIENT_ID/BLIZZARD_CLIENT_SECRET in ignored .env; they are passed only to the worker. OAuth tokens remain in worker memory. Never print Compose's rendered configuration because it contains credentials.

Collection is sequential across processes using a PostgreSQL advisory lock. Failed payload ingestion rolls back while the failure run is retained. HTTP errors trigger bounded exponential backoff, honoring Retry-After up to 24 hours. Polling is at least five minutes. Source modification timestamps stay separate from successful HTTP check time. A 304 reuses existing contents without inventing an upstream modification. Missing auctions arrays fail closed until empty-house behavior is verified. The default MAX_DATABASE_BYTES is 5 GiB; reaching it suspends new ingestion rather than deleting long-term history. This is a collection guard, not a filesystem quota: leave disk headroom for WAL, backups and other VM uses. No raw response bodies are retained.
