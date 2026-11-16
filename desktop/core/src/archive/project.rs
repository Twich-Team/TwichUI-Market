use super::{
    scoped::{self, DeliveryBudget, Sizes},
    store::{unsigned, ArchiveStore},
    wire::{id, need, time_value, Entry, Evidence},
};
use crate::{
    bridge::{canonical, validation::hash, Scope},
    pricing, Error, Result,
};
use chrono::Duration;
use rusqlite::params;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};

/// Build only the requested <=1000 identities. The full archive stays in SQLite.
pub fn project(
    store: &ArchiveStore,
    scope: &Scope,
    request: &Value,
    budget: &DeliveryBudget,
) -> Result<(Value, Value, Sizes)> {
    let r = scoped::selection(request)?;
    let h = store.active(scope)?.ok_or(Error::Invalid(
        "complete a history archive before projection",
    ))?;
    need(
        request["market"] == h.market
            && r.issuer_id == h.issuer_id
            && r.pricing_algorithm == h.pricing_algorithm
            && r.history_basis == h.history_basis,
        "projection market/algorithm context",
    )?;
    let at = h.at()?;
    let today = at.date_naive();
    let from = scoped::day(&r.history_from_day)?;
    let to = scoped::day(&r.history_through_day)?;
    need(
        to <= today && (today - from).num_days() < 60,
        "projection supported history window",
    )?;
    let key = scope.key()?;
    let current = read_one(store, &key, &h.checkpoint_id)?;
    let canonical_model = h.pricing_algorithm == "twichui-pricing-v1";
    let mut observations = Vec::new();
    let mut statement=store.db.prepare("SELECT value,sha256 FROM (SELECT value,sha256,row_number() OVER(PARTITION BY day ORDER BY at_us DESC,source_id DESC) AS ordinal FROM history_entries WHERE scope=?1 AND phase=0 AND source_id IN (SELECT source_id FROM history_members WHERE scope=?1 AND checkpoint=?2 AND phase=0) AND day>=?3 AND day<=?4 AND (?5=0 OR json_extract(value,'$.observation.scope_complete')=1)) WHERE ordinal=1")?;
    for row in statement.query_map(
        params![
            key,
            h.checkpoint_id,
            (today - Duration::days(59)).to_string(),
            today.to_string(),
            canonical_model
        ],
        |row| Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?)),
    )? {
        let (value, sum) = row?;
        observations.push(ArchiveStore::checked(value, sum)?["observation"].clone());
    }
    if !observations
        .iter()
        .any(|o| o["observation_id"] == current["observation_id"])
    {
        observations.push(current.clone());
    }
    observations.sort_by_key(|o| {
        (
            time_value(&o["observed_at"]).unwrap(),
            id(o["observation_id"].as_str().unwrap()).unwrap(),
        )
    });
    let current_ref = observations
        .iter()
        .position(|o| o["observation_id"] == current["observation_id"])
        .unwrap();
    let snapshots = observations
        .iter()
        .map(|o| id(o["snapshot_id"].as_str().unwrap()))
        .collect::<Result<BTreeSet<_>>>()?;
    let selected_json = String::from_utf8(canonical(&request["variants"])?).unwrap();
    let snapshots_json = serde_json::to_string(&snapshots)?;
    // A missing cached row cannot become evidence of absence. Verify complete
    // snapshot membership before interpreting any selected non-membership.
    let mut check=store.db.prepare("SELECT e.source_id,e.value,e.sha256,(SELECT count(*) FROM history_entries v WHERE v.scope=e.scope AND v.phase=2 AND v.source_id=e.source_id) FROM history_entries e WHERE e.scope=?1 AND e.phase=1 AND e.source_id IN (SELECT value FROM json_each(?2))")?;
    let mut checked = 0;
    for row in check.query_map(params![key, snapshots_json], |r| {
        Ok((
            r.get::<_, String>(1)?,
            r.get::<_, String>(2)?,
            unsigned(r, 3)?,
        ))
    })? {
        let (raw, sum, count) = row?;
        let descriptor = ArchiveStore::checked(raw, sum)?;
        need(
            descriptor["record_count"] == count,
            "archive snapshot membership incomplete",
        )?;
        checked += 1;
    }
    need(
        checked == snapshots.len(),
        "archive snapshot descriptor missing",
    )?;
    let mut values = BTreeMap::new();
    let mut q=store.db.prepare("SELECT e.source_id,e.item_id,e.variant,e.value,e.sha256 FROM json_each(?2) chosen CROSS JOIN history_entries e INDEXED BY history_variant_identity ON e.item_id=json_extract(chosen.value,'$.item_id') AND e.variant=json_extract(chosen.value,'$.variant_key') WHERE e.scope=?1 AND e.phase=2 AND e.source_id IN (SELECT value FROM json_each(?3))")?;
    for row in q.query_map(params![key, selected_json, snapshots_json], |row| {
        Ok((
            unsigned(row, 0)?,
            row.get::<_, u32>(1)?,
            row.get::<_, String>(2)?,
            row.get::<_, String>(3)?,
            row.get::<_, String>(4)?,
        ))
    })? {
        let (sid, item, variant, raw, sum) = row?;
        let entry: Entry = serde_json::from_value(ArchiveStore::checked(raw, sum)?)?;
        entry.validate(&h)?;
        if let Entry::Variant { value, .. } = entry {
            values.insert((sid, item, variant), value);
        }
    }
    let mut descriptors: BTreeMap<(u32, String), Option<String>> = BTreeMap::new();
    for ((_, item, variant), v) in &values {
        let entry = descriptors.entry((*item, variant.clone())).or_default();
        if v.variant_json.is_some() {
            *entry = v.variant_json.clone();
        }
    }
    let missing = r
        .variants
        .iter()
        .filter(|v| !descriptors.contains_key(&(v.item_id, v.variant_key.clone())))
        .map(|v| json!({"item_id":v.item_id,"variant_key":v.variant_key}))
        .collect::<Vec<_>>();
    if !missing.is_empty() {
        // Historical-only identity may predate the current 60-day view. Resolve
        // its exact descriptor in one streamed indexed query, never by base ID.
        let mut q=store.db.prepare("SELECT e.item_id,e.variant,e.value,e.sha256 FROM json_each(?2) chosen CROSS JOIN history_entries e INDEXED BY history_variant_identity ON e.item_id=json_extract(chosen.value,'$.item_id') AND e.variant=json_extract(chosen.value,'$.variant_key') WHERE e.scope=?1 AND e.phase=2 AND e.source_id IN (SELECT source_id FROM history_members WHERE scope=?1 AND checkpoint=?3 AND phase=1)")?;
        for row in q.query_map(
            params![key, serde_json::to_string(&missing)?, h.checkpoint_id],
            |row| {
                Ok((
                    row.get::<_, u32>(0)?,
                    row.get::<_, String>(1)?,
                    row.get::<_, String>(2)?,
                    row.get::<_, String>(3)?,
                ))
            },
        )? {
            let (item, variant, raw, sum) = row?;
            let entry: Entry = serde_json::from_value(ArchiveStore::checked(raw, sum)?)?;
            entry.validate(&h)?;
            if let Entry::Variant { value, .. } = entry {
                let e = descriptors.entry((item, variant)).or_default();
                if value.variant_json.is_some() {
                    *e = value.variant_json;
                }
            }
        }
    }
    need(
        r.variants
            .iter()
            .all(|v| descriptors.contains_key(&(v.item_id, v.variant_key.clone()))),
        "requested exact identity unavailable in retained archive",
    )?;
    let mut records = Vec::new();
    for v in &r.variants {
        let mut daily = Vec::new();
        let mut points = Vec::new();
        for (i, o) in observations.iter().enumerate() {
            let day = scoped::day(o["utc_day"].as_str().unwrap())?;
            if canonical_model && o["scope_complete"] != true {
                continue;
            }
            let value = values.get(&(
                id(o["snapshot_id"].as_str().unwrap())?,
                v.item_id,
                v.variant_key.clone(),
            ));
            let p = point(value, o, i, &h.pricing_algorithm);
            if day >= from && day <= to {
                daily.push(p.clone());
            }
            points.push(pricing::DailyPoint {
                algorithm: "twichui-pricing-v1".into(),
                market_key: key.clone(),
                item_id: v.item_id,
                variant_key: v.variant_key.clone(),
                observation_id: id(o["observation_id"].as_str().unwrap())?,
                observed_at: time_value(&o["observed_at"])?,
                complete: o["scope_complete"] == true,
                state: p["state"].as_str().unwrap().into(),
                recent_copper: p["recent_copper"].as_str().map(str::to_owned),
            });
        }
        let refs = if canonical_model {
            pricing::history(&points, &key, v.item_id, &v.variant_key, at)?
        } else {
            legacy_history(&points, time_value(&current["observed_at"])?)
        };
        let value = values.get(&(
            id(current["snapshot_id"].as_str().unwrap())?,
            v.item_id,
            v.variant_key.clone(),
        ));
        let p = point(value, &current, current_ref, &h.pricing_algorithm);
        let metrics = json!({"minimum_copper":p["minimum_copper"],"recent_copper":p["recent_copper"],
            "quantity_weighted_ask_copper":if current["scope_complete"]==true{value.and_then(|v|v.summary.quantity_weighted_ask_copper.clone())}else{None},
            "market_value_copper":refs.market_value_copper,"historical_value_copper":refs.historical_value_copper});
        let descriptor = &descriptors[&(v.item_id, v.variant_key.clone())];
        records.push(json!({"item_id":v.item_id,"variant_key":v.variant_key,"variant_json":descriptor,
            "identity_basis":if descriptor.is_some(){"exact_upstream"}else{"hash_only"},
            "current":{"state":p["state"],"algorithm":h.pricing_algorithm,"metric_basis":if canonical_model{"lower_band_mean"}else{"quantity_weighted_mean"},
               "observation_ref":current_ref,"metrics":metrics,"supply":p["supply"],"priced_supply":p["priced_supply"],"listing_count":p["listing_count"],
               "complete":current["scope_complete"],"arithmetic_status":p["arithmetic_status"],
               "coverage":{"priced_days_14":refs.priced_days_14,"priced_days_60":refs.priced_days_60,"observed_days_60":refs.observed_days_60,"references_complete":true}},
            "daily":daily,"distribution":null,"distribution_status":"omitted_budget"}));
    }
    let days = observations
        .iter()
        .filter(|o| {
            o["utc_day"].as_str().is_some_and(|day| {
                day >= r.history_from_day.as_str() && day <= r.history_through_day.as_str()
            })
        })
        .map(|o| o["utc_day"].as_str().unwrap())
        .collect::<BTreeSet<_>>()
        .len();
    let synthetic:bool=store.db.query_row("SELECT EXISTS(SELECT 1 FROM history_entries WHERE scope=?1 AND phase=0 AND source_id IN (SELECT source_id FROM history_members WHERE scope=?1 AND checkpoint=?2 AND phase=0) AND json_extract(value,'$.observation.synthetic')=1)",params![key,h.checkpoint_id],|r|r.get(0))?;
    let g = json!({"format":"twichui-market-bridge","contract_version":1,"schema_version":3,"transport_version":1,
        "issuer_id":h.issuer_id,"producer":{"server_build":h.server_build,"desktop_build":"not-applicable-server-export"},
        "required_features":["exact_copper","current_summaries","daily_history","scoped_selection"],"market":h.market,
        "pricing_algorithm":h.pricing_algorithm,"history_basis":h.history_basis,"quality_policy":1,
        "watermark_observation_id":h.watermark_observation_id,"current_observation_ref":current_ref,"as_of_utc_day":today.to_string(),
        "generated_at":h.generated_at,"desktop_sync_completed_at":null,"server_checked_at":h.server_checked_at,
        "observations":observations,"coverage":{"scope":if h.market["source_kind"]=="commodities"{"house_commodities"}else{"house_auctions"},
           "generation_complete":false,"current_complete":current["scope_complete"],"history_from_day":r.history_from_day,"history_through_day":r.history_through_day,
           "available_observed_days":days,"delivered_observed_days":days,"history_complete":true,"history_truncated":false,"distribution_complete":false,"omitted_sections":["distributions"]},
        "synthetic":synthetic,"record_count":records.len(),"records":records,
        "scope":{"type":"explicit_variants","selection_id":scoped::stable_id(request)?,"request_digest":hash(request)?,"request":request,
           "requested_count":r.variants.len(),"included":request["variants"],"excluded":[],"scope_complete":true,"whole_market_complete":false,
           "date_coverage":scoped::date_coverage(&observations,&r)?,"record_sha256":records.iter().map(hash).collect::<Result<Vec<_>>>()?}});
    let g = scoped::seal(g)?;
    let receipt = scoped::receipt(&g);
    let sizes = scoped::preflight(&g, &receipt, budget)?;
    scoped::validate(&g, Some(request))?;
    Ok((g, receipt, sizes))
}
fn read_one(store: &ArchiveStore, key: &str, checkpoint: &str) -> Result<Value> {
    let(value,sum):(String,String)=store.db.query_row("SELECT value,sha256 FROM history_entries WHERE scope=?1 AND phase=0 AND source_id IN (SELECT source_id FROM history_members WHERE scope=?1 AND checkpoint=?2 AND phase=0) ORDER BY at_us DESC,source_id DESC LIMIT 1",params![key,checkpoint],|r|Ok((r.get(0)?,r.get(1)?)))?;
    Ok(ArchiveStore::checked(value, sum)?["observation"].clone())
}
fn point(value: Option<&Evidence>, observation: &Value, index: usize, algorithm: &str) -> Value {
    let known = observation["scope_complete"] == true;
    let s = if known {
        value.map(|v| &v.summary)
    } else {
        None
    };
    json!({"observation_ref":index,"state":if !known{"unknown"}else if s.is_some(){"listed"}else{"absent"},"algorithm":algorithm,
      "minimum_copper":s.and_then(|s|s.minimum_listing_copper.clone()),"recent_copper":s.and_then(|s|s.recent_copper.clone()),
      "supply":if !known{None}else{Some(s.map(|s|s.supply).unwrap_or(0))},
      "priced_supply":if !known{None}else{Some(s.map(|s|s.priced_supply).unwrap_or(0))},
      "listing_count":if !known{None}else{Some(s.map(|s|s.listing_count).unwrap_or(0))},
      "arithmetic_status":if s.is_some_and(|s|s.state=="unsupported"){"unsupported"}else{"exact"}})
}
fn legacy_history(
    points: &[pricing::DailyPoint],
    current: chrono::DateTime<chrono::Utc>,
) -> pricing::History {
    let all = points
        .iter()
        .filter(|p| p.observed_at >= current - Duration::days(60))
        .filter_map(|p| {
            p.recent_copper
                .as_ref()
                .and_then(|v| v.parse::<u64>().ok())
                .map(|v| (p.observed_at, v))
        })
        .collect::<Vec<_>>();
    let recent = all
        .iter()
        .filter(|(at, _)| *at >= current - Duration::days(14))
        .map(|(_, v)| *v)
        .collect::<Vec<_>>();
    fn mean(v: &[u64]) -> Option<String> {
        if v.is_empty() {
            None
        } else {
            let sum: u128 = v.iter().map(|v| *v as u128).sum();
            Some(((sum * 2 + v.len() as u128) / (2 * v.len() as u128)).to_string())
        }
    }
    pricing::History {
        market_value_copper: mean(&recent),
        historical_value_copper: mean(&all.iter().map(|(_, v)| *v).collect::<Vec<_>>()),
        priced_days_14: recent.len(),
        priced_days_60: all.len(),
        observed_days_60: points.len(),
    }
}
