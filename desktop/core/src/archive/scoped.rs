//! Approved schema-3 semantics, reusing the frozen evidence validator privately.
use super::wire::{legacy_schema, need, time_value};
use crate::{
    bridge::{
        canonical,
        validation::{hash, schema_check},
    },
    Error, Result,
};
use chrono::{Duration, NaiveDate};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::OnceLock;

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct VariantIdentity {
    pub item_id: u32,
    pub variant_key: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Selection {
    pub format: String,
    pub contract_version: u32,
    pub expected_schema_version: u32,
    pub issuer_id: String,
    pub market: Value,
    pub scope_type: String,
    pub variants: Vec<VariantIdentity>,
    pub history_from_day: String,
    pub history_through_day: String,
    pub pricing_algorithm: String,
    pub history_basis: String,
    pub profile: String,
}
fn schema(which: bool) -> &'static Value {
    static REQUEST: OnceLock<Value> = OnceLock::new();
    static GENERATION: OnceLock<Value> = OnceLock::new();
    let cell = if which { &GENERATION } else { &REQUEST };
    cell.get_or_init(|| {
        let request: Value = serde_json::from_str(include_str!(
            "../../../../contracts/bridge/scoped-l1/selection.schema.json"
        ))
        .unwrap();
        let generation: Value = serde_json::from_str(include_str!(
            "../../../../contracts/bridge/scoped-l1/generation-schema3.schema.json"
        ))
        .unwrap();
        fn expand(v: &Value, request: &Value) -> Value {
            if let Some(reference) = v.get("$ref").and_then(Value::as_str) {
                let (uri, pointer) = reference.split_once('#').unwrap_or((reference, ""));
                let target = if uri == legacy_schema()["$id"].as_str().unwrap() {
                    legacy_schema()
                } else if uri == request["$id"].as_str().unwrap() {
                    request
                } else {
                    panic!("unrecognized embedded schema reference")
                };
                return expand(
                    if pointer.is_empty() {
                        target
                    } else {
                        target.pointer(pointer).unwrap()
                    },
                    request,
                );
            }
            match v {
                Value::Object(m) => Value::Object(
                    m.iter()
                        .map(|(k, v)| (k.clone(), expand(v, request)))
                        .collect(),
                ),
                Value::Array(a) => a.iter().map(|v| expand(v, request)).collect(),
                _ => v.clone(),
            }
        }
        expand(if which { &generation } else { &request }, &request)
    })
}
pub fn selection(value: &Value) -> Result<Selection> {
    need(
        canonical(value)?.len() <= 128 * 1024,
        "selection request bytes",
    )?;
    schema_check(schema(false), value)?;
    let request: Selection = serde_json::from_value(value.clone())?;
    need(
        request
            .variants
            .windows(2)
            .all(|w| (w[0].item_id, &w[0].variant_key) < (w[1].item_id, &w[1].variant_key)),
        "duplicate or unordered exact selection",
    )?;
    let from = day(&request.history_from_day)?;
    let to = day(&request.history_through_day)?;
    need(
        (0..60).contains(&(to - from).num_days()),
        "selection history window",
    )?;
    Ok(request)
}
pub fn normalize(mut value: Value) -> Result<Value> {
    let rows = value
        .get_mut("variants")
        .and_then(Value::as_array_mut)
        .ok_or(Error::Invalid("selection variants"))?;
    rows.sort_by(|a, b| {
        (a["item_id"].as_u64(), a["variant_key"].as_str())
            .cmp(&(b["item_id"].as_u64(), b["variant_key"].as_str()))
    });
    selection(&value)?;
    Ok(value)
}
pub(super) fn day(s: &str) -> Result<NaiveDate> {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").map_err(|_| Error::Invalid("scope date"))
}
pub(super) fn stable_id(request: &Value) -> Result<String> {
    let mut stable = request.clone();
    let o = stable
        .as_object_mut()
        .ok_or(Error::Invalid("scope request"))?;
    o.remove("history_from_day");
    o.remove("history_through_day");
    hash(&stable)
}
pub(super) fn seal(mut g: Value) -> Result<Value> {
    let o = g
        .as_object_mut()
        .ok_or(Error::Invalid("scoped generation"))?;
    o.remove("generation_id");
    o.remove("integrity");
    let id = hash(&g)?;
    let mut header = g.clone();
    header.as_object_mut().unwrap().remove("records");
    let integrity = json!({"records_bytes":canonical(&g["records"])?.len(),"records_sha256":hash(&g["records"] )?,"manifest_sha256":hash(&header)?});
    g["generation_id"] = id.into();
    g["integrity"] = integrity;
    Ok(g)
}
pub(super) fn date_coverage(observations: &[Value], request: &Selection) -> Result<Vec<Value>> {
    let from = day(&request.history_from_day)?;
    let to = day(&request.history_through_day)?;
    let mut result = Vec::new();
    for n in 0..=(to - from).num_days() {
        let date = (from + Duration::days(n)).to_string();
        let mut latest = None;
        let mut complete = None;
        for (i, o) in observations
            .iter()
            .enumerate()
            .filter(|(_, o)| o["utc_day"] == date)
        {
            let stamp = (
                time_value(&o["observed_at"])?,
                o["observation_id"]
                    .as_str()
                    .unwrap()
                    .parse::<u64>()
                    .map_err(|_| Error::Invalid("scope observation id"))?,
            );
            if latest.as_ref().is_none_or(|(old, _)| stamp > *old) {
                latest = Some((stamp, i));
            }
            if o["scope_complete"] == true && complete.as_ref().is_none_or(|(old, _)| stamp > *old)
            {
                complete = Some((stamp, i));
            }
        }
        let chosen = complete.or(latest);
        result.push(json!({"day":date,"state":if complete.is_some(){"complete_close"}else if latest.is_some(){"incomplete_only"}else{"no_observation"},"observation_ref":chosen.map(|(_,i)|i)}));
    }
    Ok(result)
}
pub fn validate(g: &Value, expected: Option<&Value>) -> Result<()> {
    need(
        canonical(g)?.len() <= 32 * 1024 * 1024,
        "scoped canonical hard limit",
    )?;
    schema_check(schema(true), g)?;
    let sealed = seal(g.clone())?;
    need(
        g["generation_id"] == sealed["generation_id"] && g["integrity"] == sealed["integrity"],
        "scoped generation integrity",
    )?;
    let mut header = g.clone();
    header.as_object_mut().unwrap().remove("records");
    need(
        canonical(&header)?.len() <= 256 * 1024,
        "scoped manifest hard limit",
    )?;
    let scope = &g["scope"];
    let request = &scope["request"];
    let selected = selection(request)?;
    need(
        expected.is_none_or(|e| e == request)
            && scope["request_digest"] == hash(request)?
            && scope["selection_id"] == stable_id(request)?,
        "scoped selection digest/context",
    )?;
    need(
        request["market"] == g["market"]
            && request["issuer_id"] == g["issuer_id"]
            && request["pricing_algorithm"] == g["pricing_algorithm"]
            && request["history_basis"] == g["history_basis"],
        "scoped source identity",
    )?;
    need(
        request["history_from_day"] == g["coverage"]["history_from_day"]
            && request["history_through_day"] == g["coverage"]["history_through_day"],
        "scoped history window",
    )?;
    let records = g["records"].as_array().unwrap();
    let identities = records
        .iter()
        .map(|r| json!({"item_id":r["item_id"],"variant_key":r["variant_key"]}))
        .collect::<Vec<_>>();
    need(
        Value::Array(identities.clone()) == request["variants"]
            && Value::Array(identities) == scope["included"]
            && scope["requested_count"] == records.len()
            && g["record_count"] == records.len(),
        "scoped exact membership/count",
    )?;
    let sums = records.iter().map(hash).collect::<Result<Vec<_>>>()?;
    need(
        serde_json::to_value(sums)? == scope["record_sha256"],
        "scoped per-record integrity",
    )?;
    need(
        serde_json::to_value(date_coverage(
            g["observations"].as_array().unwrap(),
            &selected,
        )?)? == scope["date_coverage"],
        "scoped calendar coverage",
    )?;
    need(
        g["producer"]["desktop_build"] == "not-applicable-server-export",
        "scoped receipt separation",
    )?;
    let mut view = g.clone();
    view.as_object_mut().unwrap().remove("scope");
    view["schema_version"] = 2.into();
    view["required_features"] = json!(["exact_copper", "current_summaries", "daily_history"]);
    view["coverage"]["generation_complete"] = true.into();
    crate::bridge::validate(&seal(view)?)
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DeliveryBudget {
    pub canonical_bytes: u64,
    pub lua_bytes: u64,
    pub records: u64,
}
impl Default for DeliveryBudget {
    fn default() -> Self {
        Self {
            canonical_bytes: 2 * 1024 * 1024,
            lua_bytes: 3 * 1024 * 1024,
            records: 100,
        }
    }
}
#[derive(Clone, Debug, Serialize)]
pub struct Sizes {
    pub canonical_bytes: u64,
    pub lua_bytes: u64,
    pub manifest_bytes: u64,
    pub records: u64,
}
pub fn sizes(g: &Value, receipt: &Value) -> Result<Sizes> {
    fn literal(n: &Value) -> Result<u64> {
        Ok(2 + canonical(n)?
            .iter()
            .map(|b| {
                if (32..=126).contains(b) && *b != b'"' && *b != b'\\' {
                    1
                } else {
                    4
                }
            })
            .sum::<u64>())
    }
    let mut header = g.clone();
    header
        .as_object_mut()
        .ok_or(Error::Invalid("scoped header"))?
        .remove("records");
    let records = g["records"]
        .as_array()
        .ok_or(Error::Invalid("scoped records"))?;
    let mut source =
        b"TwichUIMarketData = { transport_version = 1, manifest = , records = {\n}, receipt =  }\n"
            .len() as u64
            + literal(&header)?
            + literal(receipt)?;
    for r in records {
        source += literal(r)? + 2;
    }
    Ok(Sizes {
        canonical_bytes: canonical(g)?.len() as u64,
        lua_bytes: source,
        manifest_bytes: canonical(&header)?.len() as u64,
        records: records.len() as u64,
    })
}
pub fn preflight(g: &Value, receipt: &Value, budget: &DeliveryBudget) -> Result<Sizes> {
    need(
        budget.canonical_bytes > 0 && budget.lua_bytes > 0 && budget.records > 0,
        "delivery policy",
    )?;
    validate_receipt(g, receipt)?;
    let s = sizes(g, receipt)?;
    for (kind, actual, maximum) in [
        (
            "canonical_bytes",
            s.canonical_bytes,
            budget.canonical_bytes.min(32 * 1024 * 1024),
        ),
        (
            "lua_bytes",
            s.lua_bytes,
            budget.lua_bytes.min(130 * 1024 * 1024),
        ),
        ("records", s.records, budget.records.min(1000)),
        ("manifest_bytes", s.manifest_bytes, 256 * 1024),
    ] {
        if actual > maximum {
            return Err(Error::Capacity {
                limit: kind,
                actual,
                maximum,
            });
        }
    }
    Ok(s)
}
pub fn validate_receipt(g: &Value, r: &Value) -> Result<()> {
    need(
        r.as_object().is_some_and(|o| o.len() == 4)
            && r["schema_version"] == 1
            && r["generation_id"] == g["generation_id"]
            && r["desktop_build"]
                .as_str()
                .is_some_and(|s| !s.is_empty() && s.len() <= 80),
        "scoped delivery receipt",
    )?;
    let stamp = r["completed_at"]
        .as_str()
        .ok_or(Error::Invalid("scoped receipt time"))?;
    let fraction = stamp.get(19..stamp.len().saturating_sub(1)).unwrap_or("");
    need(
        stamp.len() == 20
            || ((2..=7).contains(&fraction.len())
                && fraction.starts_with('.')
                && fraction[1..].bytes().all(|b| b.is_ascii_digit())),
        "scoped receipt precision",
    )?;
    need(
        time_value(&r["completed_at"])? >= time_value(&g["generated_at"])?,
        "scoped receipt predates generation",
    )
}
pub fn receipt(g: &Value) -> Value {
    json!({"schema_version":1,"generation_id":g["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)})
}
