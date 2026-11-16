use crate::{
    bridge::{
        canonical,
        validation::{schema_check, time},
    },
    Error, Result,
};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use std::sync::OnceLock;

pub(super) fn need(ok: bool, why: &'static str) -> Result<()> {
    if ok {
        Ok(())
    } else {
        Err(Error::Invalid(why))
    }
}
pub(super) fn hex(s: &str) -> bool {
    s.len() == 64
        && s.bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
pub(super) fn id(s: &str) -> Result<u64> {
    let n = s
        .parse::<u64>()
        .map_err(|_| Error::Invalid("archive identifier"))?;
    need(
        n > 0 && n <= i64::MAX as u64 && n.to_string() == s,
        "archive identifier",
    )?;
    Ok(n)
}
fn nullable<'de, D: Deserializer<'de>>(d: D) -> std::result::Result<Option<String>, D::Error> {
    Option::deserialize(d)
}
pub(super) fn legacy_schema() -> &'static Value {
    static S: OnceLock<Value> = OnceLock::new();
    S.get_or_init(|| {
        serde_json::from_str(include_str!(
            "../../../../contracts/bridge/v1/generation-schema2.schema.json"
        ))
        .unwrap()
    })
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
#[serde(deny_unknown_fields)]
pub struct Header {
    pub format: String,
    pub protocol_version: u32,
    pub checkpoint_id: String,
    pub account_id: u32,
    pub issuer_id: String,
    pub market: Value,
    pub pricing_algorithm: String,
    pub history_basis: String,
    pub evidence_revision: u32,
    pub watermark_observation_id: String,
    #[serde(deserialize_with = "nullable")]
    pub base_checkpoint_id: Option<String>,
    pub base_watermark_observation_id: String,
    pub generated_at: String,
    pub expires_at: String,
    #[serde(deserialize_with = "nullable")]
    pub server_checked_at: Option<String>,
    pub server_build: String,
    pub retention_basis: String,
    pub archive_complete: bool,
    pub retained_from_day: String,
    pub retained_through_day: String,
    pub total_observations: u64,
    pub total_snapshots: u64,
    pub total_records: u64,
    pub transfer_observations: u64,
    pub transfer_snapshots: u64,
    pub transfer_records: u64,
    pub transfer_bytes: u64,
    pub metadata_sha256: String,
}
impl Header {
    pub fn validate(&self, scope: &crate::bridge::Scope) -> Result<()> {
        scope.key()?;
        need(
            self.format == "twichui-history-archive"
                && self.protocol_version == 1
                && self.evidence_revision == 1
                && self.archive_complete,
            "archive protocol/version/completeness",
        )?;
        need(
            self.account_id == scope.account_id
                && self.market["server_market_id"] == scope.market_id
                && self.pricing_algorithm == scope.algorithm,
            "archive account/market/algorithm",
        )?;
        schema_check(&legacy_schema()["properties"]["market"], &self.market)?;
        schema_check(
            &legacy_schema()["properties"]["issuer_id"],
            &self.issuer_id.clone().into(),
        )?;
        need(
            (self.pricing_algorithm == "twichui-pricing-v1"
                && self.history_basis == "canonical_complete_scope_close")
                || (self.pricing_algorithm == "asking-v1-provisional"
                    && self.history_basis == "market_rolling_daily_means"),
            "archive history basis",
        )?;
        need(
            hex(&self.checkpoint_id)
                && hex(&self.metadata_sha256)
                && self.base_checkpoint_id.as_deref().is_none_or(hex),
            "archive digest",
        )?;
        let watermark = id(&self.watermark_observation_id)?;
        let base = self
            .base_watermark_observation_id
            .parse::<u64>()
            .map_err(|_| Error::Invalid("archive base watermark"))?;
        need(
            base <= watermark && (self.base_checkpoint_id.is_some() || base == 0),
            "archive base watermark",
        )?;
        let at = time(&self.generated_at.clone().into())?;
        need(
            time(&self.expires_at.clone().into())? > at
                && self
                    .server_checked_at
                    .as_ref()
                    .is_none_or(|s| time(&s.clone().into()).is_ok_and(|t| t <= at)),
            "archive timestamps",
        )?;
        let first = chrono::NaiveDate::parse_from_str(&self.retained_from_day, "%Y-%m-%d")
            .map_err(|_| Error::Invalid("archive retained date"))?;
        let last = chrono::NaiveDate::parse_from_str(&self.retained_through_day, "%Y-%m-%d")
            .map_err(|_| Error::Invalid("archive retained date"))?;
        need(
            first <= last && last <= at.date_naive(),
            "archive retained date range",
        )?;
        need(
            !self.server_build.is_empty()
                && self.server_build.len() <= 80
                && self.retention_basis == "all_retained_observations_and_snapshot_summaries",
            "archive evidence basis",
        )?;
        need(
            self.total_observations > 0
                && self.total_observations <= 100_000
                && self.total_snapshots > 0
                && self.total_snapshots <= 4096
                && self.total_records <= 100_000_000
                && self.transfer_observations <= self.total_observations
                && self.transfer_snapshots <= self.total_snapshots
                && self.transfer_records <= self.total_records
                && self.transfer_bytes <= 1024 * 1024 * 1024 * 1024,
            "archive counts/bounds",
        )?;
        Ok(())
    }
    pub fn at(&self) -> Result<DateTime<Utc>> {
        time(&self.generated_at.clone().into())
    }
    pub fn transferred(&self) -> u64 {
        self.transfer_observations + self.transfer_snapshots + self.transfer_records
    }
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    pub header: Header,
    pub cursor: String,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Page {
    pub format: String,
    pub protocol_version: u32,
    pub checkpoint_id: String,
    pub account_id: u32,
    pub market_id: u32,
    pub offset: u64,
    pub entries: Vec<Value>,
    pub previous_sha256: String,
    pub page_sha256: String,
    pub chain_sha256: String,
    pub has_more: bool,
    #[serde(deserialize_with = "nullable")]
    pub next_cursor: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Summary {
    pub state: String,
    pub supply: u64,
    pub priced_supply: u64,
    pub listing_count: u64,
    #[serde(deserialize_with = "nullable")]
    pub minimum_listing_copper: Option<String>,
    #[serde(deserialize_with = "nullable")]
    pub recent_copper: Option<String>,
    #[serde(deserialize_with = "nullable")]
    pub quantity_weighted_ask_copper: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Evidence {
    #[serde(deserialize_with = "nullable")]
    pub variant_json: Option<String>,
    pub summary: Summary,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(tag = "kind", deny_unknown_fields)]
pub enum Entry {
    #[serde(rename = "observation")]
    Observation { observation: Value },
    #[serde(rename = "snapshot")]
    Snapshot {
        snapshot_id: String,
        content_sha256: String,
        record_count: u64,
        records_sha256: String,
        records_bytes: u64,
    },
    #[serde(rename = "variant")]
    Variant {
        snapshot_id: String,
        item_id: u32,
        variant_key: String,
        value: Evidence,
    },
}
pub(super) type Order = (u8, u64, u32, String);
impl Entry {
    pub(super) fn order(&self) -> Result<Order> {
        Ok(match self {
            Self::Observation { observation: o } => (
                0,
                id(o["observation_id"]
                    .as_str()
                    .ok_or(Error::Invalid("archive observation"))?)?,
                0,
                String::new(),
            ),
            Self::Snapshot { snapshot_id, .. } => (1, id(snapshot_id)?, 0, String::new()),
            Self::Variant {
                snapshot_id,
                item_id,
                variant_key,
                ..
            } => (2, id(snapshot_id)?, *item_id, variant_key.clone()),
        })
    }
    pub(super) fn validate(&self, h: &Header) -> Result<()> {
        match self {
            Self::Observation { observation: o } => {
                schema_check(&legacy_schema()["properties"]["observations"]["items"], o)?;
                need(
                    id(o["observation_id"].as_str().unwrap())? <= id(&h.watermark_observation_id)?,
                    "archive future watermark",
                )?;
                let stamp = time(&o["observed_at"])?;
                need(
                    stamp <= h.at()?
                        && stamp.date_naive().to_string() == o["utc_day"].as_str().unwrap(),
                    "archive observation time",
                )?;
                if !o["upstream_updated_at"].is_null() {
                    need(
                        time(&o["upstream_updated_at"])? <= stamp,
                        "archive upstream time",
                    )?;
                }
            }
            Self::Snapshot {
                snapshot_id,
                content_sha256,
                record_count,
                records_sha256,
                records_bytes,
            } => {
                id(snapshot_id)?;
                need(
                    hex(content_sha256)
                        && hex(records_sha256)
                        && *record_count <= 150_000
                        && *records_bytes <= 150_000 * 65537,
                    "archive snapshot",
                )?;
            }
            Self::Variant {
                snapshot_id,
                item_id,
                variant_key,
                value,
            } => {
                id(snapshot_id)?;
                need(
                    *item_id > 0 && *item_id <= i32::MAX as u32 && hex(variant_key),
                    "archive exact variant",
                )?;
                if let Some(raw) = &value.variant_json {
                    let d = crate::bridge::parse(raw.as_bytes(), 4096)?;
                    need(
                        d.is_object()
                            && d["id"] == *item_id
                            && canonical(&d)? == raw.as_bytes()
                            && format!("{:x}", sha2::Sha256::digest(raw.as_bytes()))
                                == *variant_key,
                        "archive variant descriptor",
                    )?;
                }
                let s = &value.summary;
                need(
                    ["priced", "unpriced", "unsupported"].contains(&s.state.as_str())
                        && s.supply <= 9_007_199_254_740_991
                        && s.priced_supply <= s.supply
                        && s.listing_count <= 150_000,
                    "archive summary counts",
                )?;
                for v in [
                    &s.minimum_listing_copper,
                    &s.recent_copper,
                    &s.quantity_weighted_ask_copper,
                ]
                .into_iter()
                .flatten()
                {
                    need(
                        v.len() <= 19
                            && !v.is_empty()
                            && v.bytes().all(|b| b.is_ascii_digit())
                            && (v == "0" || !v.starts_with('0'))
                            && v.parse::<u64>().is_ok_and(|n| n <= i64::MAX as u64),
                        "archive exact copper",
                    )?;
                }
                need(
                    (s.priced_supply != 0)
                        || (s.minimum_listing_copper.is_none()
                            && s.recent_copper.is_none()
                            && s.quantity_weighted_ask_copper.is_none()),
                    "archive unpriced state",
                )?;
                need(
                    s.state != "unsupported"
                        || (s.minimum_listing_copper.is_none() && s.recent_copper.is_none()),
                    "archive unsupported arithmetic",
                )?;
                if h.pricing_algorithm == "twichui-pricing-v1" {
                    for v in [&s.minimum_listing_copper, &s.recent_copper]
                        .into_iter()
                        .flatten()
                    {
                        need(
                            v.parse::<u64>()
                                .is_ok_and(|n| (1..=99_999_999_999).contains(&n)),
                            "archive canonical range",
                        )?;
                    }
                }
            }
        }
        Ok(())
    }
}
use sha2::Digest;

pub(super) fn time_value(v: &Value) -> Result<DateTime<Utc>> {
    time(v)
}
