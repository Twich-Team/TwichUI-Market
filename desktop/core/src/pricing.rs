//! Pure M1a conformance calculations/validation. Not used by sync, cache or scheduler.
use crate::{Error, Result};
use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashSet};

fn required_nullable<'de, D, T>(d: D) -> std::result::Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(d)
}

pub const ALGORITHM: &str = "twichui-pricing-v1";
pub const MAX_COPPER: u64 = 99_999_999_999;
pub const MAX_COUNT: u64 = 9_007_199_254_740_991;

/// Capability check only. Full schema, semantic and integrity validation belongs
/// to the future reader; this function never accepts/imports a generation.
pub fn supports_bridge_header(h: &serde_json::Value) -> bool {
    let basis = match h["pricing_algorithm"].as_str() {
        Some(ALGORITHM) => "canonical_complete_scope_close",
        Some("asking-v1-provisional") => "market_rolling_daily_means",
        _ => return false,
    };
    let Some(features) = h["required_features"].as_array() else {
        return false;
    };
    let expected: HashSet<_> = ["exact_copper", "current_summaries", "daily_history"]
        .into_iter()
        .collect();
    h["format"].as_str() == Some("twichui-market-bridge")
        && [
            "contract_version",
            "schema_version",
            "transport_version",
            "quality_policy",
        ]
        .iter()
        .all(|k| h[k].as_u64() == Some(1))
        && h["history_basis"].as_str() == Some(basis)
        && features.len() == 3
        && features
            .iter()
            .filter_map(|v| v.as_str())
            .collect::<HashSet<_>>()
            == expected
}

pub fn copper(value: &str) -> Result<u64> {
    if value.is_empty()
        || value.len() > 19
        || !value.bytes().all(|b| b.is_ascii_digit())
        || (value.len() > 1 && value.starts_with('0'))
    {
        return Err(Error::Invalid("canonical copper string"));
    }
    value
        .parse::<u64>()
        .ok()
        .filter(|n| *n <= i64::MAX as u64)
        .ok_or(Error::Invalid("copper range"))
}

fn price(value: &str) -> Result<u64> {
    let amount = copper(value)?;
    if amount == 0 || amount > MAX_COPPER {
        return Err(Error::Invalid("canonical price range"));
    }
    Ok(amount)
}

fn algorithm(value: &str) -> Result<()> {
    if value != ALGORITHM {
        return Err(Error::Invalid("pricing algorithm"));
    }
    Ok(())
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Tier {
    pub unit_copper: String,
    pub quantity: u64,
    pub listing_count: u32,
}

/// Exact u128 tenths at the band edge; no binary floating-point arithmetic.
pub fn recent(tiers: &[Tier], version: &str) -> Result<Option<String>> {
    algorithm(version)?;
    if tiers.len() > 150_000 {
        return Err(Error::Invalid("tier limit"));
    }
    if tiers.is_empty() {
        return Ok(None);
    }
    let mut values = Vec::with_capacity(tiers.len());
    let (mut total, mut previous, mut listings) = (0u64, 0u64, 0u64);
    for tier in tiers {
        let p = price(&tier.unit_copper)?;
        if p <= previous
            || tier.quantity == 0
            || tier.quantity > MAX_COUNT
            || tier.listing_count == 0
            || tier.listing_count as u64 > tier.quantity
        {
            return Err(Error::Invalid("tier order/count"));
        }
        total = total
            .checked_add(tier.quantity)
            .filter(|q| *q <= MAX_COUNT)
            .ok_or(Error::Invalid("quantity sum"))?;
        listings += tier.listing_count as u64;
        if listings > 150_000 {
            return Err(Error::Invalid("listing count"));
        }
        previous = p;
        values.push((p, tier.quantity));
    }
    let mut cumulative = 0u128;
    let mut anchor = 0;
    for (p, q) in &values {
        cumulative += *q as u128;
        if 4 * cumulative > total as u128 {
            anchor = *p;
            break;
        }
    }
    let eligible: Vec<_> = values
        .into_iter()
        .filter(|(p, _)| 2 * p >= anchor)
        .collect();
    let weight: u128 = 3 * eligible.iter().map(|(_, q)| *q as u128).sum::<u128>();
    let (mut remaining, mut sum) = (weight, 0u128);
    for (p, q) in eligible {
        let take = remaining.min(10 * q as u128);
        sum = sum
            .checked_add(
                (p as u128)
                    .checked_mul(take)
                    .ok_or(Error::Invalid("price product"))?,
            )
            .ok_or(Error::Invalid("price sum"))?;
        remaining -= take;
        if remaining == 0 {
            break;
        }
    }
    let numerator = sum
        .checked_mul(2)
        .and_then(|s| s.checked_add(weight))
        .ok_or(Error::Invalid("rounding range"))?;
    Ok(Some((numerator / (2 * weight)).to_string()))
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DailyPoint {
    pub algorithm: String,
    pub market_key: String,
    pub item_id: u32,
    pub variant_key: String,
    pub observation_id: u64,
    pub observed_at: DateTime<Utc>,
    pub complete: bool,
    pub state: String,
    #[serde(deserialize_with = "required_nullable")]
    pub recent_copper: Option<String>,
}

#[derive(Debug, PartialEq)]
pub struct History {
    pub market_value_copper: Option<String>,
    pub historical_value_copper: Option<String>,
    pub priced_days_14: usize,
    pub priced_days_60: usize,
    pub observed_days_60: usize,
}

fn median(values: &mut [(u64, u32)]) -> Option<String> {
    values.sort_unstable_by_key(|v| v.0);
    let total: u32 = values.iter().map(|v| v.1).sum();
    let mut count = 0;
    for (v, w) in values {
        count += *w;
        if 2 * count >= total {
            return Some(v.to_string());
        }
    }
    None
}

pub fn history(
    points: &[DailyPoint],
    market: &str,
    item: u32,
    variant: &str,
    as_of: DateTime<Utc>,
) -> Result<History> {
    if market.is_empty()
        || market.len() > 320
        || item == 0
        || item > i32::MAX as u32
        || variant.len() != 64
        || !variant
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
        || points.len() > 100_000
    {
        return Err(Error::Invalid("history identity or bound"));
    }
    let mut days: BTreeMap<NaiveDate, &DailyPoint> = BTreeMap::new();
    let mut seen = HashSet::new();
    for p in points {
        algorithm(&p.algorithm)?;
        if p.market_key != market
            || p.item_id != item
            || p.variant_key != variant
            || p.observation_id == 0
            || p.observation_id > i64::MAX as u64
            || !seen.insert(p.observation_id)
            || p.observed_at > as_of
        {
            return Err(Error::Invalid("history identity/time"));
        }
        if !["listed", "absent", "unknown"].contains(&p.state.as_str()) {
            return Err(Error::Invalid("presence state"));
        }
        if let Some(v) = &p.recent_copper {
            price(v)?;
            if p.state != "listed" {
                return Err(Error::Invalid("price without listing"));
            }
        }
        let day = p.observed_at.date_naive();
        let age = (as_of.date_naive() - day).num_days();
        if !p.complete || !(0..60).contains(&age) {
            continue;
        }
        if days.get(&day).is_none_or(|old| {
            (p.observed_at, p.observation_id) > (old.observed_at, old.observation_id)
        }) {
            days.insert(day, p);
        }
    }
    let (mut mv, mut hv) = (Vec::new(), Vec::new());
    for (day, point) in &days {
        if let Some(value) = &point.recent_copper {
            let amount = price(value)?;
            hv.push((amount, 1));
            let age = (as_of.date_naive() - *day).num_days();
            if age < 14 {
                mv.push((
                    amount,
                    if age <= 2 {
                        4
                    } else if age <= 6 {
                        2
                    } else {
                        1
                    },
                ));
            }
        }
    }
    Ok(History {
        market_value_copper: median(&mut mv),
        historical_value_copper: if hv.len() >= 3 { median(&mut hv) } else { None },
        priced_days_14: mv.len(),
        priced_days_60: hv.len(),
        observed_days_60: days.len(),
    })
}
