# Item Metadata Recovery implementation plan

Baseline: `64ef6d2d08e7453458ed37d06d29f263ac19d126`; independent branch `feature/item-metadata-recovery`.
This goal supersedes Companion priority for this checkout only. Never access the other session or production. No merge, release or deployment authorization. New UI is an owner-review candidate.

| Milestone | Dependencies | Deliverable and verification |
| --- | --- | --- |
| M0 isolated baseline | none | Verify SHA, clean checkout, locked dependencies, private disposable market_test PostgreSQL, no collectors/production settings; representative smoke; create branch and durable ledger. |
| M1 contracts and catalog | M0 | Bounded documented provider probes; exact edition/build/identity validators; additive source-versioned PostgreSQL catalog; field provenance, precedence/conflicts; local indexed name projection; bulk and incremental import tests. |
| M2 recovery and secrets | M1 | Persistent jobs/tasks, dedupe, leases, pause/resume/cancel, budgets/cooldowns/negative caches/ETags, isolated worker and automatic priorities; AEAD encrypted credentials and staged replacement validation, admin/CSRF, rotation/runbook. PostgreSQL and security tests. |
| M3 website integration | M2 | Administration Item Metadata and Data Sources, preview/enqueue and monitoring; metadata labels/search/tooltips via local APIs; existing style/contracts/prices preserved. Frontend/build and browser tests. |
| M4 acceptance and delivery | M3 | Full relevant regressions/migration drift/up-down, actual browser screenshots/axe/responsive checks, bounded performance fixture, honest coverage evidence, read-only latest Companion migration inspection; reviewed coherent commits/push; separate draft PR against dev/s1-s5-implementation, attach PR. |

## Acceptance checklist

- [ ] Versioned local catalog, per-field provenance, conflict visibility and Blizzard precedence.
- [ ] Everloot documented adapter (real keyless validation where available); ForeverDB gated by documented contract/access; optional TheWoWDB errors honest.
- [ ] No client provider requests; local names/search/attributes/artwork and desktop additive read contract.
- [ ] Manual single/missing/stale recovery; persistent resumable bounded deduplicated jobs and audited controls.
- [ ] Conservative independently scheduled automatic recovery with persistent provider limits.
- [ ] Encrypted provider secrets outside backup key boundary; staged validation and safe rotation; admin + CSRF; expiry warnings.
- [ ] Actual DB statistics, provider health, recent results and request estimates in accessible admin UI.
- [ ] Focused and full relevant tests, migration preservation, screenshots and performance evidence.
- [ ] Latest Companion committed schema checked without modifying its branch/session; v1 export preserved.
- [ ] Coverage source/age/sample limits explicit; 90% is a target, never fabricated.
- [ ] Draft PR, operational setup/migration/rollback and remaining approval/credential steps documented.

External gates only block dependent work: real provider credentials/approval, owner-managed master secret, unavailable market snapshot, owner visual review, merge/deployment authorization. Fixtures never establish production coverage.
