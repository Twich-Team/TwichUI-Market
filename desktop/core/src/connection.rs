//! Minimal owned account/market bootstrap. Full website preferences never enter the native app.
//! Bootstrap v1 is additive; sync/export v1 keep their separate strict schemas.
use crate::{Error, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Account {
    pub id: u32,
    pub username: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Device {
    pub id: u32,
    pub user_id: u32,
    pub name: String,
    pub platform: String,
    pub app_version: String,
    pub authorized_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub revoked: bool,
    pub last_connection_at: Option<DateTime<Utc>>,
    pub last_sync_at: Option<DateTime<Utc>>,
    pub selected_market_id: Option<u32>,
    pub selected_market_name: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Provenance {
    pub market_id: u32,
    pub server_checked_at: Option<DateTime<Utc>>,
    pub upstream_updated_at: Option<DateTime<Utc>>,
    pub observation_id: Option<String>,
    pub watermark_observation_id: Option<String>,
    pub snapshot_id: Option<String>,
    pub generation: Option<String>,
    pub valuation_generation: Option<String>,
    pub synthetic: bool,
    pub valuation_synthetic: Option<bool>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Market {
    pub id: u32,
    pub label: String,
    pub region: String,
    pub enabled: bool,
    pub verified: bool,
    pub player_identity_verified: bool,
    pub available_for_sync: bool,
    pub next_check: Option<DateTime<Utc>>,
    pub source: Provenance,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Bootstrap {
    pub contract_version: u32,
    pub account: Account,
    pub markets: Vec<Market>,
    pub preferred_market_id: Option<u32>,
    pub suggested_market_id: Option<u32>,
    pub preference_fallback: bool,
    pub device: Option<Device>,
}
pub(crate) fn observation_id(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 10
        || !value.bytes().all(|b| b.is_ascii_digit())
        || value.starts_with('0')
        || value
            .parse::<u32>()
            .ok()
            .is_none_or(|id| id > i32::MAX as u32)
    {
        return Err(Error::Invalid("observation identity"));
    }
    Ok(())
}
impl Provenance {
    pub fn validate(&self, market: u32) -> Result<()> {
        if self.market_id != market || market == 0 || market > i32::MAX as u32 {
            return Err(Error::Invalid("source market identity"));
        }
        for value in [
            &self.observation_id,
            &self.watermark_observation_id,
            &self.snapshot_id,
        ]
        .into_iter()
        .flatten()
        {
            observation_id(value)?;
        }
        if self.observation_id.is_some() != self.snapshot_id.is_some()
            || self.observation_id.is_some() != self.watermark_observation_id.is_some()
            || self.generation.is_some() != self.snapshot_id.is_some()
            || self
                .observation_id
                .as_ref()
                .zip(self.watermark_observation_id.as_ref())
                .is_some_and(|(head, watermark)| {
                    head.parse::<u32>().unwrap_or(u32::MAX) > watermark.parse::<u32>().unwrap_or(0)
                })
        {
            return Err(Error::Invalid("source receipt identity"));
        }
        if let Some(value) = &self.valuation_generation {
            if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
                return Err(Error::Invalid("valuation generation"));
            }
        }
        if let Some(value) = &self.generation {
            let (id, hash) = value
                .split_once(':')
                .ok_or(Error::Invalid("source generation"))?;
            observation_id(id)?;
            if hash.len() != 64
                || !hash.bytes().all(|b| b.is_ascii_hexdigit())
                || self.snapshot_id.as_deref() != Some(id)
            {
                return Err(Error::Invalid("source generation"));
            }
        }
        Ok(())
    }
}
impl Bootstrap {
    pub fn validate(&self) -> Result<()> {
        if self.contract_version != 1
            || self.account.id == 0
            || self.account.username.is_empty()
            || self.account.username.len() > 320
            || self.markets.len() > 200
        {
            return Err(Error::Invalid("account bootstrap"));
        }
        let mut ids = HashSet::new();
        for market in &self.markets {
            market.source.validate(market.id)?;
            if !ids.insert(market.id)
                || market.label.is_empty()
                || market.label.len() > 320
                || !market.verified
                || market.available_for_sync
                    && (!market.enabled || !market.player_identity_verified)
            {
                return Err(Error::Invalid("available market identity"));
            }
        }
        if let Some(id) = self.suggested_market_id {
            if !self
                .markets
                .iter()
                .any(|market| market.id == id && market.available_for_sync)
            {
                return Err(Error::Invalid("suggested market"));
            }
        }
        if let Some(device) = &self.device {
            if device.user_id != self.account.id
                || device.id == 0
                || device.platform != "Windows"
                || device.revoked
            {
                return Err(Error::Authentication);
            }
        }
        Ok(())
    }
    /// An unavailable local override is explicit; do not silently choose a different market.
    /// With no local override, use the server's saved-preference suggestion/fallback.
    pub fn resolve_market(&self, local_override: Option<u32>) -> Option<&Market> {
        let id = local_override.or(self.suggested_market_id)?;
        self.markets
            .iter()
            .find(|market| market.id == id && market.available_for_sync)
    }
}
