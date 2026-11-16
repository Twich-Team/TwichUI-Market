# ForeverDB rich metadata integration

Owner authorization (2026-11-16): investigate the real authenticated API, implement supported item/related metadata, verify website ownership, test, PR/merge into `integration/companion-v2-metadata-recovery`, and deploy through the existing production process. No bridge, pricing, collector, desktop or L1 branch changes.

Base verified: `73617a9e2ce6b32f539700c72caab4592a443a2f` (PR #11 over #10 and M1.5). Isolated implementation branch: `feature/foreverdb-rich-metadata`. Existing untracked production release overlays are retained untouched.

1. Inventory official live documentation and bounded authenticated response structures; confirm website key scope and entitlement without exposing credentials.
2. Correct detail parser, typed normalization, provenance/availability, persistence and existing field reconciliation; add direct useful relationships without a parallel database.
3. Prioritize missing detailed records and requested/observed items through persistent quota-controlled recovery; preserve failed-refresh data and pending work.
4. Present available details and source qualifiers in existing components; add administrator coverage/build/verification diagnostics.
5. Add exact static ownership proof and explicit non-SPA routing; automated build and HTTP checks.
6. Focused and full backend/frontend/browser/Windows CI on frozen source, diff/secret/contract review, isolated backup restore and release/rollback preparation.
7. Merge verified PR, deploy only existing API/local API/frontend/enrichment services, verify public HTTPS and bounded real enrichment, document provider-side Verify separately.

Live schema and key scope are evidence gates. No fabricated mapping, paid entitlement, quota increase or unrestricted crawl. Owner approval of a bounded diagnostic-budget exception must be explicit; elapsed time provides no approval.
