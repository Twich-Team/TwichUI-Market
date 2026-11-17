-- Read-only baseline. Run with psql -X -At -f; no provider I/O or secrets.
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '20s';
WITH recent AS (
 SELECT t.*, t.result_json::jsonb AS r, j.mode,
 lag(t.updated_at) OVER (PARTITION BY t.region,t.item_id,t.provider ORDER BY t.updated_at,t.id) AS previous_at
 FROM metadata_tasks t JOIN metadata_jobs j ON j.id=t.job_id
 WHERE t.updated_at >= now()-interval '30 days'
), grouped AS (
 SELECT provider, count(*) AS task_records,
 sum(attempts) AS committed_request_reservations,
 count(*) FILTER (WHERE attempts>0 AND r ? 'http_status') AS final_responses_recorded,
 count(*) FILTER (WHERE r->'new_fields' ? 'name') AS final_requests_new_name,
 count(*) FILTER (WHERE r->'new_fields' ? 'icon_reference') AS final_requests_new_icon_reference,
 count(*) FILTER (WHERE EXISTS (SELECT 1 FROM jsonb_array_elements_text(coalesce(r->'new_fields','[]'::jsonb)) f WHERE f NOT IN ('name','icon_reference'))) AS final_requests_new_attributes,
 count(*) FILTER (WHERE r->>'outcome'='already_known') AS final_already_known,
 count(*) FILTER (WHERE r->>'http_status'='304') AS final_304,
 count(*) FILTER (WHERE r->>'http_status'='404') AS final_404,
 count(*) FILTER (WHERE r->>'outcome'='no_usable_data') AS final_no_usable_data,
 count(*) FILTER (WHERE r->>'outcome'='rate_limited') AS final_429,
 count(*) FILTER (WHERE r->>'outcome' IN ('wrong_identity','invalid_response','credentials_invalid','access_blocked','unavailable')) AS final_errors,
 count(*) FILTER (WHERE attempts>1) AS overwritten_retry_records,
 count(*) FILTER (WHERE attempts>0 AND NOT (r ? 'new_fields')) AS gain_evidence_incomplete,
 count(*) FILTER (WHERE previous_at IS NOT NULL AND updated_at-previous_at < CASE provider WHEN 'blizzard' THEN interval '30 days' WHEN 'foreverdb' THEN interval '1 day' ELSE interval '1 hour' END) AS within_nominal_refresh_needs_review
 FROM recent GROUP BY provider
)
SELECT json_build_object('captured_at',now(),'period_days',30,'providers',(SELECT json_agg(row_to_json(g)) FROM grouped g),
 'limitations','Tasks overwrite retry results. Reservations are not exact outbound counts; only final responses/gains survive. Within-window repeats may be justified by errors, 404/429 windows, mapping or build changes. Icon downloads and validation are outside this task ledger. Historical requested goals/skip decisions are unrecorded.');
WITH ids AS (SELECT DISTINCT item_id FROM snapshot_statistics WHERE snapshot_id=(SELECT snapshot_id FROM observations WHERE market_id=2 ORDER BY retrieved_at DESC,id DESC LIMIT 1))
SELECT json_build_object('market_id',2,'snapshot_id',(SELECT snapshot_id FROM observations WHERE market_id=2 ORDER BY retrieved_at DESC,id DESC LIMIT 1),
 'observed',count(*),'names',count(*) FILTER(WHERE coalesce(m.name,m.fallback_name) IS NOT NULL),
 'icons',count(*) FILTER(WHERE a.data IS NOT NULL),
 'quality',count(*) FILTER(WHERE coalesce(m.quality,m.catalog_json::jsonb->'fields'->>'quality') IS NOT NULL),
 'essential_definition','Quality and class for all base items; level and slot only for verified Weapon/Armor classes. Unknown classification is not assumed equipment.',
 'missing_applicable_essential',count(*) FILTER(WHERE coalesce(m.catalog_json::jsonb->'fields'->>'quality',m.quality) IS NULL OR m.catalog_json::jsonb->'fields'->>'class' IS NULL OR (m.catalog_json::jsonb->'fields'->>'class' IN ('Weapon','Armor') AND (m.catalog_json::jsonb->'fields'->>'level' IS NULL OR m.catalog_json::jsonb->'fields'->>'slot' IS NULL))))
FROM ids LEFT JOIN item_metadata m ON m.region='us' AND m.item_id=ids.item_id LEFT JOIN item_media a ON a.region='us' AND a.item_id=ids.item_id;
ROLLBACK;
