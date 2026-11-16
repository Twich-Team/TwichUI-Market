-- Optional genuine-history aggregate procedure. READ ONLY; no export payload,
-- credentials, collection, ANALYZE, new derivation or checkpoint creation.
-- Operator supplies an already approved connection and -v market_id=<integer>.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '10s';
\if :{?market_id}
\else
  \echo 'Required: psql -v market_id=<approved market ID> -f scripts/archive-history-readonly.sql'
  DO $$ BEGIN RAISE EXCEPTION 'Required explicit valid market_id; no evidence collected'; END $$;
\endif
SELECT EXISTS(SELECT 1 FROM markets WHERE id=:'market_id'::integer) AS found_market \gset
\if :found_market
\else
  \echo 'Requested market does not exist; no evidence collected.'
  DO $$ BEGIN RAISE EXCEPTION 'Required explicit valid market_id; no evidence collected'; END $$;
\endif
SELECT id,region,ruleset_id AS transport_ruleset_id,house_id,source_kind,verified
FROM markets WHERE id=:'market_id'::integer;

-- Identity/count basis is retained SnapshotStatistic membership, never an
-- assertion that legacy summaries are canonical daily prices.
WITH retained AS MATERIALIZED (
  SELECT id,snapshot_id,retrieved_at,(retrieved_at AT TIME ZONE 'UTC')::date AS utc_day
  FROM observations WHERE market_id=:'market_id'::integer
), source_snapshots AS MATERIALIZED (
  SELECT DISTINCT snapshot_id FROM retained
), identities AS MATERIALIZED (
  SELECT DISTINCT s.item_id,s.variant_key FROM snapshot_statistics s
  JOIN source_snapshots x ON x.snapshot_id=s.snapshot_id
), current_snapshot AS (
  SELECT snapshot_id FROM retained ORDER BY retrieved_at DESC,id DESC LIMIT 1
), current_identities AS MATERIALIZED (
  SELECT s.item_id,s.variant_key FROM snapshot_statistics s
  JOIN current_snapshot c ON c.snapshot_id=s.snapshot_id
)
SELECT
  (SELECT count(*) FROM retained) AS retained_observations,
  (SELECT min(utc_day) FROM retained) AS first_utc_day,
  (SELECT max(utc_day) FROM retained) AS last_utc_day,
  (SELECT count(DISTINCT utc_day) FROM retained) AS observed_utc_days,
  (SELECT CASE WHEN count(*)=0 THEN 0 ELSE max(utc_day)-min(utc_day)+1-count(DISTINCT utc_day) END FROM retained) AS unobserved_calendar_days,
  (SELECT count(*) FROM source_snapshots) AS unique_retained_snapshots,
  (SELECT count(*) FROM identities) AS retained_statistics_exact_variants,
  (SELECT count(DISTINCT item_id) FROM identities) AS distinct_base_item_ids,
  (SELECT count(*) FROM current_identities) AS current_statistics_variants,
  (SELECT count(*) FROM identities i WHERE NOT EXISTS(SELECT 1 FROM current_identities c WHERE c.item_id=i.item_id AND c.variant_key=i.variant_key)) AS historical_only_variants,
  (SELECT count(*) FROM snapshot_statistics s JOIN source_snapshots x ON x.snapshot_id=s.snapshot_id) AS retained_snapshot_summary_rows,
  (SELECT count(*) FROM snapshot_statistics s JOIN source_snapshots x ON x.snapshot_id=s.snapshot_id WHERE s.supply>0 AND s.priced_supply=0) AS supply_only_snapshot_summary_rows;

WITH ids AS (SELECT DISTINCT snapshot_id FROM observations WHERE market_id=:'market_id'::integer)
SELECT count(*) AS referenced_snapshots,
 count(*) FILTER(WHERE s.raw_retained) AS snapshots_with_originals,
 count(*) FILTER(WHERE s.statistics_retained) AS snapshots_with_retained_statistics,
 count(*) FILTER(WHERE d.snapshot_id IS NOT NULL) AS snapshots_with_canonical_revision_1_derivation
FROM ids JOIN snapshots s ON s.id=ids.snapshot_id
LEFT JOIN bridge_derivations d ON d.snapshot_id=s.id AND d.algorithm='twichui-pricing-v1' AND d.revision=1;

-- Global whole-table allocation (all markets, including indexes), not selected
-- generation bytes or selected-market storage. No table payload is emitted.
SELECT name AS whole_table_name,pg_total_relation_size(name::regclass) AS whole_table_allocated_bytes
FROM (VALUES('observations'),('snapshots'),('listings'),('snapshot_statistics'),('bridge_derived_records')) AS tables(name);
COMMIT;
