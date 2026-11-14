# Operations

Use only `docker --context rootless` and project-scoped Compose commands. Do not enumerate or modify unrelated containers. No sudo. Before startup inspect `ss -ltn`, `free -h`, `df -h .` and confirm rootless security options. Services bind to 127.0.0.1; external HTTPS/domain/firewall work requires a separate administrator action and is not authorized here.

Never put credentials in command arguments, Git, logs or fixtures. Read Blizzard credentials from environment. Store local configuration in ignored .env. Probe output must exclude access tokens and Authorization headers.

## Local development deployment

Copy .env.example to .env (mode 600), choose a random URL-safe POSTGRES_PASSWORD, recheck port 18780, then run `docker --context rootless compose up -d --build`. Alembic runs before API startup. Caddy exposes only 127.0.0.1:18780. Health: `/api/v1/health`. Local HTTP uses COOKIE_SECURE=false; HTTPS deployment requires true and exact APP_ORIGIN. External HTTPS is not deployed yet.

Set SYNC_CURSOR_SECRET to a separate random secret of at least 32 characters before using desktop synchronization. Retain it across restarts; rotation requires clients to rebuild their cache. Never expose it to clients or place it in Git. Server sync returns 503 if this configuration is absent.

### Verified local HTTPS

Run `python3 scripts/init-env.py` to generate missing private secrets while preserving configured values. Start with `docker --context rootless compose -f compose.yaml -f compose.tls.yaml up -d --build` after checking port 18443. This exposes only 127.0.0.1:18443, sets secure cookies and exact HTTPS origin, and uses a persistent project-local Caddy CA with host trust installation explicitly disabled. The previous HTTP binding is removed while this overlay is active. Keep using both Compose files when restarting/updating the HTTPS stack.

`python3 scripts/bootstrap-owner.py` creates the first owner only if no users exist. Generated credentials stay in ignored .local/bootstrap.env with private directory/file permissions and are passed through environment only. Read them privately, change the password through Account & devices, then remove the bootstrap credential file. A second bootstrap invocation safely skips existing users.

`python3 scripts/verify-https.py` extracts only the public local CA certificate and explicitly trusts it for verification. It checks the real certificate chain, application CSP, secure/HttpOnly/SameSite cookies, initial owner authentication, session CSRF recovery, administrator access and logout. It does not bypass TLS validation or modify the host trust store. This passes locally. The verifier uses the initial bootstrap credentials unless administrator credentials are supplied through environment.

External access remains separate: an administrator must arrange a domain, externally trusted certificate/routing or an owner-controlled tunnel/client trust setup. This run does not modify existing reverse proxies, public ports or firewall rules. The private web designs remain unapproved review candidates.

Bootstrap the first administrator using `docker --context rootless compose run --rm -e MARKET_ADMIN_USERNAME -e MARKET_ADMIN_PASSWORD api python -m market.bootstrap` with credentials already exported in the shell. Never pass secret values in arguments. Bootstrap refuses if any users exist. Browser login returns a CSRF token required as X-CSRF-Token on mutations; session cookies are HttpOnly/SameSite Strict. Invitations are single-use, expire in seven days and create members only. Administrator browser sessions can change roles/disable users; the final active administrator is protected. Device tokens expire in 90 days, are stored hashed server-side, cannot mint more devices and cannot perform administrator actions.

## Tests

`docker --context rootless build -t twichui-market-backend:dev backend`

`docker --context rootless compose -p twichui-market-test -f compose.yaml -f compose.test.yaml run --rm test`

The test overlay uses an isolated tmpfs database; tests refuse non-test PostgreSQL database names. Clean up only its resources with the same compose arguments followed by `down`. Never use the overlay with the development project name. PostgreSQL tests recreate schema; migration verification must run separately against a disposable database before tests. SQLite provides quick tests but does not establish PostgreSQL concurrency correctness.

Windows release instructions will be added alongside the companion implementation. No production deployment exists yet.

## Collector

The collector is opt-in: `docker --context rootless compose --profile collector up -d worker`. It does not run for disabled or unverified markets. Do not mark markets verified until S1 live evidence establishes their mapping and payload semantics. Set BLIZZARD_CLIENT_ID/BLIZZARD_CLIENT_SECRET in ignored .env; they are passed only to the worker. OAuth tokens remain in worker memory. Never print Compose's rendered configuration because it contains credentials.

Collection is sequential across processes using a PostgreSQL advisory lock. Failed payload ingestion rolls back while the failure run is retained. HTTP errors trigger bounded exponential backoff, honoring Retry-After up to 24 hours. Polling is at least five minutes. Source modification timestamps stay separate from successful HTTP check time. A 304 reuses existing contents without inventing an upstream modification. Missing auctions arrays fail closed until empty-house behavior is verified. The default MAX_DATABASE_BYTES is 5 GiB; reaching it suspends new ingestion rather than deleting long-term history. This is a collection guard, not a filesystem quota: leave disk headroom for WAL, backups and other VM uses. No raw response bodies are retained.

## Backups and restore rehearsals

Start daily backups with `docker --context rootless compose --profile operations up -d --build backup`. The bounded PostgreSQL-client container uses no Docker socket or host scheduler. It takes a custom-format dump at startup and every BACKUP_INTERVAL_SECONDS (default 86400, minimum 3600). BACKUP_KEEP defaults to seven archives (1–30). MAX_BACKUP_BYTES defaults to 2 GiB total; a further 2 GiB of free filesystem headroom is reserved before starting. Insufficient budget stops backup creation for operator review. Rotation happens only after a successful dump and never deletes market history.

Archives and manifests are in ignored backups/ (directory 700, files 600). They contain private application data; arrange an owner-managed encrypted off-host copy for disaster recovery. This implementation verifies local restoration but does not provide off-host durability. API administration reads only a separate status mount, not archives or credentials. Backups use PostgreSQL's consistent pg_dump snapshot, atomically rename completed archives and record SHA-256. Shared locking serializes the scheduled worker, manual backup and restore verification.

Manual dump: `python3 scripts/backups.py create`. Restore rehearsal: `python3 scripts/backups.py verify-restore backups/<archive>.dump`. The rehearsal verifies SHA-256 and size, starts a fresh memory-limited PostgreSQL instance without a host port, runs pg_restore with constraints, queries revision/data counts and records evidence before removing that disposable instance. It never restores over the running application database. The 512 MiB tmpfs rehearsal supports current small datasets; larger backups require a separately planned bounded restore volume and sufficient capacity.

Run `python3 scripts/verify-backup.py` for a repeatable nonempty synthetic-data rehearsal plus corrupted-archive rejection. It uses dedicated twichui-market-recovery and twichui-market-restore projects, separate from regression tests. Verified locally on 2026-11-13: synthetic administrator, market, observation, listing and buyout sum survive restoration; corrupted archive rejected. A real scheduled development archive (currently empty application data) was also restored successfully. Persistent development PostgreSQL retained migration 2541add7d379 across restart, and the HTTP health check recovered with 200.

## Operational retention

`python -m market.maintenance` reports a dry run; `--apply` prunes only operational records. The collector invokes this once per day. COLLECTION_LOG_DAYS defaults to 90 (range 7–3650); SECURITY_EVENT_DAYS defaults to 365 (30–3650). Login rate-limit windows older than one day and expired credentials/invitations older than 30 days are pruned. All historical market observations, snapshots and listings are preserved indefinitely. Tests explicitly verify that 500-day-old market history survives operational cleanup. No automatic database vacuum-full or host disk maintenance is performed.
