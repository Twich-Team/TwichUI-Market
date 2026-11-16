# Provider limits: operation, deployment and rollback

This is a development/review candidate. No production commands have been run. Credentials remain encrypted under the existing owner-managed keyring; budgets never rewrite a secret.

## Administration

Open Administration → Data Sources. Connection settings, credential replacement and Rate limits save independently. A rate edit neither enables a provider nor creates a recovery campaign. Polling retains unsaved form edits.

ForeverDB accepts the approved key's actual minute/day allowance, with an optional hourly application safety budget and minimum interval. Only the documented free and paid allowances appear as presets. Higher-than-free values require acknowledgement; this is an administrator statement, not authenticated entitlement discovery. Everloot supports its validated keyed hourly allowance and up to 5,000 records per applicable page; page size is unrelated to request quota or name coverage. TheWoWDB exposes sustained requests/second and short burst allowance, with hourly/daily **application safety** guards. Concurrency stays one shared request per provider. Blizzard metadata keeps 240/hour, 2,000/day and at least 15 seconds; auction/OAuth safeguards remain separate.

The first applicable guard wins. An hourly safety budget can intentionally be tighter than a provider's minute allowance. Settings and documented values are separate from provider observations. Unknown provider entitlement/reset boundaries remain unknown. Application remaining counts represent **reserved attempts**, including conservatively charged interrupted requests; other applications/keys using the same account or IP are not visible.

429 suspends eligible calls, persists the event and resumes automatically within the existing campaign budget. Retry-After starts at response receipt, supports seconds/dates and conservative server-Date skew handling. Repeated 429s add bounded backoff; pacing returns to configured maximums after 15 minutes without further throttling after the cooldown. A provider cannot refill an immediate burst while waiting out a 429. 401, 402, 403, missing items, malformed responses and temporary 503 remain distinct.

Every actual retry is charged. If a 429 spent a campaign's final permitted request, the job pauses with its item queued and **Allow one retry** offers explicit additional allowance (campaign cap 1,000). This preserves work without silently exceeding the owner's selected budget. Pause/Resume/Cancel continue to work. Increasing a limit does not bypass provider/source retry times, reset usage or resume a manually paused campaign.

## Additive administrator API

- `GET /api/v1/admin/metadata-providers` adds `rate_limits`: configured/effective values, sources, rolling-window estimates, timestamped provider observations, cooldown/adaptive state and HTTP/recovery timestamps. Existing fields remain for compatibility.
- `PATCH /api/v1/admin/metadata-providers/{provider}/rate-limits` accepts finite `hourly_budget`, `daily_budget`, `minimum_interval`, `max_concurrent: 1`; ForeverDB also requires `minute_budget`, TheWoWDB requires `requests_per_second`/`burst_capacity`, Everloot requires `page_size`. Inapplicable fields must be null. `entitlement_acknowledged` is required for values above documented defaults. An unexpired validated credential is required to raise authenticated allowances. This endpoint never changes secrets/enablement.
- The existing provider PATCH accepts enablement/automatic settings without resubmitting budgets. Legacy budget payloads keep their conservative validation.
- Job responses add `waiting` with provider/resumption time and `retry_allowance_needed`. `POST /api/v1/admin/item-metadata/jobs/{job_id}/retry-allowance` accepts a positive bounded `additional_requests`, only for paused exhausted campaigns. It never resets committed request counts.
- All mutations retain administrator browser-session, CSRF, origin and read-only-listener protections. Device/member access remains denied. Rate responses/logs contain no secret values, raw provider headers or unvalidated response bodies.

## Deployment after separate owner approval

1. Obtain explicit visual/release approval and green exact-source CI. Verify the final integration head, single Alembic head and production's actual revision. The pinned parent includes `bridge_20261115`; this feature's migration is `rates_20261115`. If that parent has not been approved for production, rehearse/review its ancestry rather than skipping migrations or silently promoting unrelated work.
2. Use the current documented production backup/keyring preservation and isolated restore procedures. Record fingerprints for credentials, provider settings, jobs, market history and the sole house-114 collector. Confirm the collector schedule remains 300 seconds.
3. Drain/pause only metadata enrichment while applying the additive migration. It adds nullable configuration/state columns, an initial zero rate-limit streak and a bounded quota-bucket table. It changes no existing credentials, budgets, timestamps, histories or job rows.
4. Replace only the approved API/frontend/metadata-enrichment images using the current integration release procedure and existing resource limits. Never start the `collector` profile wholesale; target metadata enrichment explicitly. No extra worker/service/production network is required.
5. Confirm health, administrator/CSRF restrictions, preserved secrets/settings/counters and exactly one unchanged collector. Check the UI's source labels and estimates against persisted reservations. Provider validation and any live campaign require their own explicit bounded authorization. Do not raise a production limit as part of deployment; the owner enters their actual grant separately.
6. Observe metadata pacing and cooldown recovery within the existing memory/CPU budgets. The worker now wakes for configured eligibility (maximum four ticks/second, idle delay up to 15 seconds), so a former 15-second polling floor no longer unnecessarily constrains approved metadata allowances. No auction collection loop or schedule was changed.

## Rollback

Stop only metadata enrichment and restore the retained compatible API/frontend/enrichment images. Keep the additive schema and all quota/cooldown state. The older scheduler still sees its preserved anchored counters and cooldowns and applies its conservative ceilings. Retain the new rolling history for a later forward upgrade. Verify sessions, keys, current metadata, pending jobs and collector identity/schedule again.

Schema downgrade intentionally refuses populated rate settings/accounting. Export/review them before any separately authorized schema downgrade; never delete accounting merely to force rollback. This feature requires no key replacement, revocation, master-key rotation, historical-data restore, auction reset or addon/desktop release.

## Isolated verification

Use a **disposable PostgreSQL database named `market_test`**, with no live keys. Install the backend lock and run `python -m pytest -q backend/tests`, frontend unit/build checks and the existing operational suite. `scripts/verify-provider-rate-migration.py`, the legacy metadata/Companion migration verifiers and `scripts/benchmark-provider-rates.py` refuse production database names. Migration verifiers deliberately recreate only the disposable schema; run them sequentially after tests.

The normal browser suite runs before `web/e2e/seed-provider-rates.py` and `provider-rates.spec.ts`; the latter fixtures contain fake encrypted credentials and synthetic quota observations. No provider worker is started. CI uploads the ten screenshot scenes and accessibility/verification receipt. All live provider verification remains excluded from this candidate.
