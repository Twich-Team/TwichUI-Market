# Provider rate management

Baseline: `68c075138d5f50608c741b0e51b7013d9bf8769d`, the pushed integration head inspected on 2026-11-15. Branch: `feature/provider-rate-management`, isolated Cloud worktree `/workspace/provider-rate-management`. Original checkout is untouched. Active integration is `integration/companion-v2-metadata-recovery`; Workshop work is `feature/workshop-bridge-m1`. Production is documented at `7202e07`; no production connection is used.

1. Audit current reservations, credentials, jobs and official provider contracts; preserve exact baseline and isolation evidence.
2. Extend existing persistent scheduler with independently configured windows, TheWoWDB token bucket, conservative accounting, response observations and bounded adaptive cooldown. Preserve legacy committed usage and account-wide key-rotation state.
3. Add administrator-only limits API and approachable Data Sources controls, estimated/reported usage and job waiting labels. Keep credentials, provider enablement and campaigns independent.
4. Verify PostgreSQL atomic reservations, restarts, migration preservation, mocked adapter/recovery behavior, UI/browser accessibility and mobile screenshots. Measure bounded resources and inspect latest integration ancestry.
5. Commit/push verified checkpoints and open a draft PR against the pinned application's integration branch. Deliver review, migration/deployment/rollback instructions. Stop before merge/deployment.

All provider calls in tests are mocked. Use a disposable `market_test` PostgreSQL database, localhost ports 19432/19480/19481, rootless Cloud Docker only if needed, separate project/image names and bounded resources. Never start the auction collector or contact real provider APIs.
