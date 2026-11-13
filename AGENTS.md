# TwichUI Market engineering instructions

Read docs/implementation-plan.md and docs/progress.md before each cycle. Implement small complete tasks, verify behavior, inspect diffs, commit and push checkpoints on a development branch. Never claim live observations from fixtures.

Operate only in this repository and the marketdev rootless Docker context. Never use root/sudo or touch AMP, other users, unrelated containers, firewall, SSH or host proxies. Bind services to localhost. Check resources and ports before allocation. Limit container CPU, memory, logs and retained data. Never commit secrets.

Architecture: FastAPI, PostgreSQL, SQLAlchemy/Alembic, Python worker, React/TypeScript/Vite, Compose/Caddy, versioned REST/contracts, provisional Tauri desktop. Tests: pytest, Vitest, Playwright and Windows CI. No main addon repository changes.

Design approval is required for the three major player-facing pages before finalizing. Continue independent tasks while approval or upstream credentials are pending. Retain listings as observations, never as completed sales. Workshop pricing compatibility requires documented formulas and reference fixtures; do not invent compatibility evidence.
