# TwichUI Market engineering instructions

Read docs/implementation-plan.md and docs/progress.md before each cycle. Implement small complete tasks, verify behavior, inspect diffs, commit and push checkpoints on a development branch. Never claim live observations from fixtures.

Operate only in this repository and the marketdev rootless Docker context. Never use root/sudo or touch AMP, other users, unrelated containers, firewall, SSH or host proxies. Bind services to localhost. Check resources and ports before allocation. Limit container CPU, memory, logs and retained data. Never commit secrets.

Architecture: FastAPI, PostgreSQL, SQLAlchemy/Alembic, Python worker, React/TypeScript/Vite, Compose/Caddy, versioned REST/contracts, provisional Tauri desktop. Tests: pytest, Vitest, Playwright and Windows CI. No main addon repository changes.

Design approval is required for the three major player-facing pages before finalizing. Continue independent tasks while approval or upstream credentials are pending. Retain listings as observations, never as completed sales. Workshop pricing compatibility requires documented formulas and reference fixtures; do not invent compatibility evidence.

Active modernization milestone: follow docs/item-modernization-plan.md and docs/item-modernization-progress.md. Preserve collector schedules, real history, legacy APIs and desktop contracts. Catalogue parent prices are explicit ranges across variants; never present a blended variant price as an exact item price. Rich metadata and icon/tooltip fields require provenance and exact game-edition identity. Unknown fields stay unknown. Maintain account isolation when introducing server-state caches. Significant visual changes are review candidates pending explicit approval. Destructive/performance fixtures use isolated market_test databases only.

Private metadata-priority caches use bounded batches and must clear across accounts, including delayed failed requests. Market supply is the current variant total; never label an individual deal's stack quantity as market supply. Variant captions expose verified upstream identifiers without inventing bonus names. Significant frontend promotion remains gated by explicit owner visual approval; a separate bounded preview is permitted for verification.

Owner-authorized Traefik task: private HTTP only at 10.0.4.46:18780 restricted to the verified Traefik peer; interactive unapproved preview only at 127.0.0.1:18444. This supersedes the localhost-only default for that exact production listener. See docs/traefik-preview-plan.md. Never promote modernized frontend assets without owner approval.

**Current two-phase authorization:** PR #3 administration/provider diagnostics and item colors are deployed and verified at `e9c4d29`; see [release acceptance](docs/admin-modernization-release-acceptance.md). The owner authorizes implementing [Explorer / Item Details](docs/explorer-item-details-plan.md) from this integrated source, with separate feature-branch commits/pushes and a draft PR. Stop Phase 2 before production promotion pending final owner visual approval. Earlier review-only language is historical for these explicitly authorized scopes.

**Explorer review candidate complete:** application `b3e48bd`, [draft PR #4](https://github.com/Twich-Team/TwichUI-Market/pull/4), [review report](docs/explorer-item-details-review.md) and [screenshot gallery](docs/evidence/explorer-details/review.html). All required verification is complete; production remains `e9c4d29`. Stop Phase 2 here until explicit owner visual approval; do not infer promotion authorization from the completed implementation.
