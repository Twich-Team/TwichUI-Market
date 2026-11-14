# Architecture

One FastAPI service owns versioned REST endpoints, authorization and PostgreSQL transactions. A separate process from the same Python package schedules upstream collection. A small independently scheduled process records bounded hourly PostgreSQL allocation measurements, including when collection is disabled. PostgreSQL stores identities, observations, valuations, security events and sync changes. React/Vite serves the private research application through Caddy. Only Caddy binds to localhost; PostgreSQL remains on an internal Compose network. Tauri consumes data-only versioned sync contracts and exports outside live SavedVariables.

Market identity includes game, region, ruleset, auction house and source kind. Do not merge rulesets or houses merely because observed payloads match. Preserve response hashes, retrieval timestamps, upstream modification timestamps and source namespace. Auction disappearance is not proof of sale.

Initial limits: database 768 MiB/1 CPU, API 384 MiB/0.5 CPU, worker 384 MiB/0.5 CPU, proxy 128 MiB/0.25 CPU, storage monitor 128 MiB/0.25 CPU. Rotated logs, bounded response size and collection concurrency one. Validate enforcement on this rootless host before deployment claims.

Item modernization (active): an additive catalogue surface will query compact per-snapshot statistics with batched daily references and explicit parent/variant separation. Rich metadata/media keep independent provenance and cache status. The browser will use TanStack Query/Table, conditional Virtual, Apache ECharts and Base UI while preserving the existing React/Vite/Docker deployment. See item-modernization-plan.md for acceptance and privacy constraints.
