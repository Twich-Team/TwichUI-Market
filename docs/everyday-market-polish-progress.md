# Everyday Market polish — continuation ledger

Owner request: preserve approved Explorer/Details split, polish player-facing metadata/controls/loading/navigation/timezones, repair provider results, deliver verified commits and draft PR. Stop before deployment pending owner visual review.

Baseline: branch `feature/everyday-market-polish` from `e34b149`; actual production proxy image revision `4ddf137712084292b899e7b352fe41b751e8e70b`, API `e9c4d299cdf781be0e362edb26b4de6097a33e6a`, confirmed via image/container inspection and public asset names. No production mutation. House 114 alone enabled at 300 seconds, read-only SQL confirmed. Supplied attachment contains text only; prior release screenshots provide visual baseline, with fresh isolated before/after captures planned.

Initial findings:
- Catalogue query lacks previous-data retention; rows clear on page/sort changes. Parent expansion is placed below item link. Oversized separated controls expose snapshot IDs.
- ItemFacts always renders complete field provenance and repeated source/build/timestamps.
- Parent Details always requires variant selection, even with a sole valid current variant.
- History compact response drops existing observation instants; chart labels use UTC bucket strings.
- Real persisted provider tasks exist (1,773 at bounded read-only sample, changing through existing automatic worker). API handler read-only queries succeed: market 1 has 3, market 2 has 1,770. UI silently restricts attempts to selected market. Default will explicitly cover all markets, with optional job-market scope. No new recovery campaign or provider request is authorized.

Next: implement focused fixes and regression coverage, isolated PostgreSQL/browser verification, visual evidence, push coherent checkpoints, draft PR and CI, final production read-only unchanged check.

Implementation checkpoint: compact Explorer controls; previous-data retention with last-success fallback on errors; chevron column; additive verified sole-variant links and safe parent resolution; optional provenance with exact unique credits; local observation instants retained in compact history without UTC rebucketing; all-market/7-day provider defaults with explicit scope, name/ID search and historical delta qualification. Added `last_seen_at` separately from collection observation so disappeared variants never borrow a newer market check.

Verification in progress: 113 frontend tests and build pass. Fresh baseline captures complete. Focused browser checks found row-height and measurement issues; parent rows increased to 72px and viewport-vs-document scroll measurements corrected. Initial PostgreSQL harness omitted migrations/pg_trgm; corrected by running the standard migration first. No production settings or records changed. Safe candidate handler diagnostics can be reproduced with `scripts/diagnose-provider-results.py` (read-only transaction enforced by PostgreSQL).
