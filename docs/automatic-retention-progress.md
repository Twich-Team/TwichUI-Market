# Automatic historical retention — active owner goal

Owner request authorizes collection safeguards, automatic retention infrastructure, additive migrations, isolated destructive rehearsal, and verified deployment. **Production history deletion remains unauthorized.** Preserve saved policy revision 2 (7/90/365 days, 60 support, logs 90/365), current market 2 / house 114 / 300 seconds, unified feeds, backup schedule disabled, desktop/Workshop and metadata releases.

Base: integration/companion-beta7-website-copy `16de8ea`, descendant of deployed backup-management `e49de6a`, includes source-aware collector `70f144c`. Main is only the initial commit. Isolated feature/automatic-historical-retention; no other worktrees edited.

Initial measured production: PostgreSQL 17.12, revision coverage_20261117, database 4,560,287,411 bytes. Rootless volume twichui-market_market-data maps /home/marketdev/.local/share/docker/volumes/twichui-market_market-data/_data to PGDATA. Server-side df confirms expanded ext4 filesystem 266,736,099,328 bytes, available approximately 160,302,305,280 bytes. WAL 285,224,960 allocated bytes. Collector source exactly matches baseline; old guard 5,368,709,120 bytes. Collection is healthy at entry, both feeds 304 after genuine successful ingestion; zero policy authorizations/batches.

Initial deployment policy: allocation cap 64 GiB; independent physical available-space reserve 32 GiB, measured on the same PostgreSQL volume. At current allocation, growth to cap leaves approximately 89 GiB available before other workload growth. Guard reports allocation versus filesystem versus missing measurement separately. Generic Compose fallback 16 GiB/2 GiB is not the production capacity policy.

Next: verify narrow safeguard, retain rollback config, deploy capacity configuration promptly; implement durable exact-policy/scope/budget authorization and bounded scheduler with production authorization absent; fresh manager archive and isolated restore; complete tests/CI, deployment and activation proposal. Do not enable recurring backups, modify external storage, or prune production history.
