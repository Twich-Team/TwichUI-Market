# Configure shared metadata quotas and recover from provider throttling

Draft PR destination: **Twich-Team/TwichUI-Market**

Head: `feature/provider-rate-management`

Base: `integration/companion-v2-metadata-recovery`

## Prepared description

ForeverDB's application ceilings could not represent an approved key's allowance, and administrators could not see minute/token-bucket usage or reliably understand cooldown recovery. Data Sources now supports independently saved provider allowances, labelled usage estimates/provider observations, automatic cooldown status and recovery-job waits.

The existing PostgreSQL scheduler shares atomic reservations across recovery, validation, artwork and diagnostics. It preserves committed usage/credentials across edits and restarts, implements TheWoWDB's documented refill/burst rules, respects Retry-After from response receipt and adds bounded adaptive pacing. Exhausted campaigns preserve rate-limited work for explicit retry allowance. Blizzard metadata safeguards, collection, source/build checks, pricing and desktop/addon contracts are retained.

Validation: 550 PostgreSQL tests, 119 frontend unit tests, 36 operational checks, 38 existing local browser workflows and the new provider workflow pass. TypeScript/Vite and dependency audits pass. Migration preservation/downgrade/re-upgrade rehearsals pass at `rates_20261115`, descending from `bridge_20261115`. Ten synthetic-data screenshots include desktop/mobile accessibility checks with zero violations. One existing private-download browser test requires the normal CI-only `proxy` hostname and was not run locally; hosted CI results must be checked after this draft opens.

See [review/evidence](provider-rate-management-review.md), [official contract research](provider-rate-management-research.md), [gallery](evidence/provider-rates/README.md), and [operation/rollback](provider-rate-management-operations.md). Configured values are not proof of a key's entitlement. Cloud per-container cgroup enforcement could not be established and is documented separately from process memory measurements.

Baseline: `68c075138d5f50608c741b0e51b7013d9bf8769d`. Final fetched integration is unchanged. No merge, deployment, production access, live provider calls or credential changes. This remains an owner-review candidate.
