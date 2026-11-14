# TwichUI Market

Private, self-hosted World of Warcraft: Forever market research for a small group. FastAPI, PostgreSQL, a scheduled Python collector, React/TypeScript, Caddy and a Windows Tauri companion.

Development is active. One US Forever auction feed is live-verified and collecting genuine data. Exact player-facing house routing, long-run refresh cadence and Workshop pricing compatibility remain unverified; major page designs await owner approval. The website is an explicitly labeled review candidate. Synthetic test fixtures are never represented as live data. No main addon repository changes or live SavedVariables writes are included.

## Local deployment

Use the dedicated marketdev account and approved rootless Docker context. Check ports, RAM and disk first; never modify AMP or other services.

```bash
python3 scripts/init-env.py
docker --context rootless compose -f compose.yaml -f compose.tls.yaml up -d --build
python3 scripts/bootstrap-owner.py
python3 scripts/verify-https.py
```

The application binds only to `https://localhost:18443`. Caddy uses a project-local CA; verification explicitly trusts its public certificate without changing host trust. Browser/client trust or an externally trusted certificate must be arranged separately. No firewall, host reverse proxy or SSH configuration is changed.

Initial owner credentials are in ignored `.local/bootstrap.env` (mode 600). Read privately and change the password after first sign-in; remove that bootstrap file afterward. Provisioning refuses to overwrite existing users. Private configuration lives in ignored `.env`.

Daily local backups are opt-in: `docker --context rootless compose -f compose.yaml -f compose.tls.yaml --profile operations up -d --build backup`. Collection stays off until credentials and market mappings are live-verified. Encrypted off-host backup copies and external HTTPS routing remain owner deployment tasks.

## Evidence and work remaining

See [acceptance evidence and blockers](docs/acceptance.md), [progress](docs/progress.md), [implementation plan](docs/implementation-plan.md), [operations](docs/operations.md), [API feasibility](docs/api-feasibility.md), [website](docs/website.md), and [Windows companion](docs/desktop.md). [Draft PR #1](https://github.com/Twich-Team/TwichUI-Market/pull/1) tracks the implementation.

Reproducible checks cover PostgreSQL migrations/permissions/pricing/collection/sync, browser workflows, Docker persistence, backup restoration, Rust cache/HTTP integration and Windows credential/build CI. Completion is gated on live upstream evidence, approved designs and all remaining acceptance criteria.
