# TwichUI Market engineering instructions

Read docs/implementation-plan.md and docs/progress.md before each cycle. Implement small complete tasks, verify behavior, inspect diffs, commit and push checkpoints on a development branch. Never claim live observations from fixtures.

Operate only in this repository and the marketdev rootless Docker context. Never use root/sudo or touch AMP, other users, unrelated containers, firewall, SSH or host proxies. Bind services to localhost. Check resources and ports before allocation. Limit container CPU, memory, logs and retained data. Never commit secrets.

Architecture: FastAPI, PostgreSQL, SQLAlchemy/Alembic, Python worker, React/TypeScript/Vite, Compose/Caddy, versioned REST/contracts, provisional Tauri desktop. Tests: pytest, Vitest, Playwright and Windows CI. No main addon repository changes.

Design approval is required for the three major player-facing pages before finalizing. Continue independent tasks while approval or upstream credentials are pending. Retain listings as observations, never as completed sales. Workshop pricing compatibility requires documented formulas and reference fixtures; do not invent compatibility evidence.

Active modernization milestone: follow docs/item-modernization-plan.md and docs/item-modernization-progress.md. Preserve collector schedules, real history, legacy APIs and desktop contracts. Catalogue parent prices are explicit ranges across variants; never present a blended variant price as an exact item price. Rich metadata and icon/tooltip fields require provenance and exact game-edition identity. Unknown fields stay unknown. Maintain account isolation when introducing server-state caches. Significant visual changes are review candidates pending explicit approval. Destructive/performance fixtures use isolated market_test databases only.

Private metadata-priority caches use bounded batches and must clear across accounts, including delayed failed requests. Market supply is the current variant total; never label an individual deal's stack quantity as market supply. Variant captions expose verified upstream identifiers without inventing bonus names. Significant frontend promotion remains gated by explicit owner visual approval; a separate bounded preview is permitted for verification.
