# Administration tables and provider investigation

Owner request: continue the deployed Companion v2 / metadata release. Development branch: `development/admin-tables-provider-diagnostics`, starting at `35f5fdd`. No production frontend promotion before visual approval. No collector, retention, account, credential or infrastructure changes.

## Checkpoints

1. Inventory every administration record display; verify deployed revision, current provider controls and fixed market-2 population. Review official provider contracts and existing evidence before outbound diagnostics.
2. Extend the existing `web/src/data-table.tsx` for accessible details, states and filters; convert record displays. Add bounded server-side history, unresolved and job queries. Keep credential/configuration forms separate. Make request success distinct from useful recovery, with safe diagnostics and guarded retry.
3. Validate adapter behavior against authentic sanitized fixtures and run a reproducible representative experiment. All investigation requests share an overall 200-attempt ceiling; start with positive controls, respect existing cooldowns and stop on systematic failure. Never bypass a disabled provider or increase automatic budgets. Confirm the live operator window and account for concurrent activity before requests.
4. Verify PostgreSQL/frontend/browser behavior and performance, capture desktop/mobile before/after evidence, inspect diffs and secrets, push coherent commits. Prepare consolidated findings, deployment/rollback and owner visual review. Finish independent UI work if a provider remains inaccessible.

## Inventory and intended treatment

| Section | Existing display | Intended treatment |
| --- | --- | --- |
| Overview: collection readiness | Repeated market list | Shared table with mapping, schedule, last success and failure |
| Overview: icon-cache status | Repeated status list | Compact shared table |
| Overview: artwork failures | Shared table | Stable identity, timestamp and states |
| Members | Shared table | Retain role/disable controls and stable identity |
| Invitations | Shared table | Retain one-time secret form and revoke control |
| Markets and schedules | Shared table plus configuration form | Retain controls/safety checks; add stable identity/details consistency |
| Collection runs / failures | Shared table of bounded recent runs | Server-side filtering/sorting/pagination, failure filter, safe details |
| Storage measurements | Shared table | Stable timestamp identity, newest first |
| Retention | Policy forms, preview summary, static approval explanation | Justified exception: keep forms and scalar summaries; no record list |
| Desktop companions | Stacked device cards, manual Show more | Shared table in administration; preserve ownership/revoke confirmation and account card UX |
| Legacy devices | Shared table | Retain permissions/actions; stable identity |
| Security / audit events | Shared client table, most recent 200 | Server-side page/search/category/date filters and expandable redacted details |
| Item Metadata: recovery jobs | Repeated rows | Server-side shared table, progress, provider/counts/times and Pause/Resume/Cancel/Details |
| Item Metadata: job results | Repeated blocks, cursor pages | Shared table over existing bounded cursor pages |
| Item Metadata: provider health | Repeated paragraphs | Shared provider table |
| Item Metadata: recent attempts | Twenty repeated paragraphs | Server-side shared table, restrained source emblems, explicit outcomes/fields, local timestamps, safe expansion, permitted retry and period summaries |
| Item Metadata: unresolved names | No dedicated record display | Server-side shared table over observed IDs with lookup/retry/icon/presence fields |
| Data Sources | Repeated status/credential cards | Shared health/status table; separate existing configuration and key-entry forms |
| Settings/preferences, recovery input, charts, overview totals | Forms/scalar summaries/visualizations | Justified exceptions: retain purpose-built controls |

## Initial live observations

Read-only inspection on November 14, 2026 (America/Denver) found market 2 / house 114 alone collecting at 300 seconds. Snapshot 27, observation 292: 4,893 distinct IDs, 2,238 named; ID hash `bbbacaf1ed0d9d35f997a16f83d92b6f0f009bd126284d3868d7115f8b076fc1`. This preliminary observation is not a completed fixed-snapshot experiment.

Live metadata controls differ from the prior acceptance receipt: Blizzard enabled/automatic; Everloot disabled but automatic=true and configured 240/hour, 2,000/day; TheWoWDB disabled with one recent validation attempt. Preserve these settings. Reconcile current operations and freeze exact per-ID baseline before outbound work; do not infer authorization from old receipt settings or silently reset usage/cooldowns.
