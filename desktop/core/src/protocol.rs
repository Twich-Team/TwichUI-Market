use crate::{Error, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

pub const ALGORITHM: &str = "asking-v1-provisional";
pub const MAX_PAGE_BYTES: u64 = 2 * 1024 * 1024;

fn required_nullable<'de, D, T>(deserializer: D) -> std::result::Result<Option<T>, D::Error>
where
    D: serde::Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(deserializer)
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Valuation {
    #[serde(deserialize_with = "required_nullable")]
    pub recent_price: Option<String>,
    #[serde(deserialize_with = "required_nullable")]
    pub lowest_buyout: Option<String>,
    #[serde(deserialize_with = "required_nullable")]
    pub market_value: Option<String>,
    #[serde(deserialize_with = "required_nullable")]
    pub historical_value: Option<String>,
    pub supply: u64,
    pub priced_supply: u64,
    pub listing_count: u64,
    pub coverage_days: u32,
    pub market_coverage_days: u32,
    pub synthetic: bool,
}

impl Valuation {
    pub fn validate(&self) -> Result<()> {
        for value in [
            &self.recent_price,
            &self.lowest_buyout,
            &self.market_value,
            &self.historical_value,
        ]
        .into_iter()
        .flatten()
        {
            if value.is_empty()
                || value.len() > 19
                || !value.bytes().all(|b| b.is_ascii_digit())
                || (value.len() > 1 && value.starts_with('0'))
                || value.parse::<i64>().is_err()
            {
                return Err(Error::Invalid("copper amount"));
            }
        }
        if self.supply > 9_007_199_254_740_991
            || self.priced_supply > self.supply
            || self.listing_count > 250_000
            || self.coverage_days > 61
            || self.market_coverage_days > 15
        {
            return Err(Error::Invalid("supply or coverage bounds"));
        }
        if self.priced_supply == 0 && (self.recent_price.is_some() || self.lowest_buyout.is_some())
        {
            return Err(Error::Invalid("price without priced supply"));
        }
        Ok(())
    }
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum Operation {
    Upsert,
    Delete,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Change {
    pub operation: Operation,
    pub item_id: u32,
    pub variant_key: String,
    #[serde(deserialize_with = "required_nullable")]
    pub value: Option<Valuation>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Page {
    pub contract_version: u32,
    pub market_id: u32,
    pub algorithm: String,
    pub changes: Vec<Change>,
    pub cursor: String,
    pub has_more: bool,
    pub target_observation_id: String,
    #[serde(deserialize_with = "required_nullable")]
    pub observed_at: Option<String>,
    pub synthetic: bool,
}

impl Page {
    pub fn validate(&self, market: u32) -> Result<()> {
        if self.contract_version != 1
            || self.algorithm != ALGORITHM
            || self.market_id != market
            || market == 0
            || market > i32::MAX as u32
            || self.changes.len() > 100
            || self.cursor.is_empty()
            || self.cursor.len() > 2048
            || self.target_observation_id.is_empty()
            || !self
                .target_observation_id
                .bytes()
                .all(|b| b.is_ascii_digit())
            || (self.target_observation_id.len() > 1 && self.target_observation_id.starts_with('0'))
            || self.target_observation_id.parse::<u64>().is_err()
        {
            return Err(Error::Invalid("page identity, size or version"));
        }
        if self.target_observation_id == "0" {
            if !self.changes.is_empty() || self.has_more || self.observed_at.is_some() {
                return Err(Error::Invalid("empty watermark contains observations"));
            }
        } else if self.observed_at.is_none() {
            return Err(Error::Invalid("observation timestamp required"));
        }
        if let Some(date) = &self.observed_at {
            chrono::DateTime::parse_from_rfc3339(date)
                .map_err(|_| Error::Invalid("observation timestamp"))?;
        }
        let mut keys = HashSet::new();
        for change in &self.changes {
            if change.item_id == 0
                || change.item_id > i32::MAX as u32
                || change.variant_key.len() != 64
                || !change
                    .variant_key
                    .bytes()
                    .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
                || !keys.insert((change.item_id, &change.variant_key))
            {
                return Err(Error::Invalid("duplicate or invalid item variant"));
            }
            match (&change.operation, &change.value) {
                (Operation::Upsert, Some(value)) => value.validate()?,
                (Operation::Delete, None) => {}
                _ => return Err(Error::Invalid("change operation and value disagree")),
            }
        }
        Ok(())
    }
}
