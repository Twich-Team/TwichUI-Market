# Market usability milestone progress

## Baseline — 2026-11-14

Started at f84fea9 on clean dev/s1-s5-implementation. Read AGENTS.md, implementation/progress, item modernization and Traefik plans. Docker context rootless. Existing production and localhost18444 read-only preview are running; only current collector retained. Host has approximately 11 GiB available RAM and 20 GiB free filesystem space. No unrelated resources touched.

Plan: [market-usability-plan.md](market-usability-plan.md). Initial inspection finds page/sort-driven catalogue auto-selection, internal variant fingerprints in normal browsing, missing selected heading icon, comparison UI, noninteractive current listings and environment-only opt-in compaction. Player-facing mapping remains unresolved pending independent evidence. Existing primary metadata/media queues are separate from collection; optional community fallback is disabled.

Approval gates: final visual promotion, verified market transition, proposed live destructive retention policy after backup/restore tests. No live pruning or collection changes applied.
