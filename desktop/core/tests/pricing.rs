use chrono::{DateTime, Utc};
use serde_json::Value;
use std::collections::BTreeMap;
use twichui_market_core::pricing::{self, DailyPoint, Tier, ALGORITHM};

#[test]
fn approved_snapshot_fixtures_use_exact_shared_strings() {
    let document: Value =
        serde_json::from_str(include_str!("../../../contracts/pricing/v1/snapshots.json")).unwrap();
    let mut supported = 0;
    for case in document["cases"].as_array().unwrap() {
        let mut tiers: BTreeMap<u64, (u64, u32)> = BTreeMap::new();
        for row in case["listings"].as_array().unwrap() {
            let q = row["quantity"].as_u64().unwrap();
            let price = if let Some(u) = row["unit_copper"].as_str() {
                pricing::copper(u).unwrap()
            } else if let Some(b) = row["total_copper"].as_str() {
                pricing::copper(b).unwrap().div_ceil(q)
            } else {
                continue;
            };
            let t = tiers.entry(price).or_default();
            t.0 += q;
            t.1 += 1;
        }
        let rows: Vec<_> = tiers
            .into_iter()
            .map(|(p, (q, l))| Tier {
                unit_copper: p.to_string(),
                quantity: q,
                listing_count: l,
            })
            .collect();
        let result = pricing::recent(&rows, ALGORITHM);
        if let Some(expected) = case["expected"]["workshop_recent"].as_str() {
            assert_eq!(result.unwrap().as_deref(), Some(expected), "{}", case["id"]);
            supported += 1;
        } else if rows.is_empty() {
            assert_eq!(result.unwrap(), None);
        } else {
            assert!(result.is_err());
        }
    }
    assert_eq!(supported, 19);
}

#[test]
fn approved_temporal_fixtures_preserve_absence_complete_closes_and_sparse_history() {
    let document: Value =
        serde_json::from_str(include_str!("../../../contracts/pricing/v1/temporal.json")).unwrap();
    for case in document["cases"].as_array().unwrap() {
        let as_of = case["as_of"]
            .as_str()
            .unwrap()
            .parse::<DateTime<Utc>>()
            .unwrap();
        let points: Vec<_> = case["points"]
            .as_array()
            .unwrap()
            .iter()
            .enumerate()
            .map(|(i, p)| DailyPoint {
                algorithm: ALGORITHM.into(),
                market_key: "fixture-market".into(),
                item_id: 2589,
                variant_key: "a".repeat(64),
                observation_id: i as u64 + 1,
                observed_at: p["observed_at"].as_str().unwrap().parse().unwrap(),
                complete: p["complete"].as_bool().unwrap(),
                state: p["state"].as_str().unwrap().into(),
                recent_copper: p["unit_copper"].as_str().map(str::to_string),
            })
            .collect();
        let got =
            pricing::history(&points, "fixture-market", 2589, &"a".repeat(64), as_of).unwrap();
        assert_eq!(
            got.market_value_copper.as_deref(),
            case["expected"]["canonical_market_value"].as_str(),
            "{}",
            case["id"]
        );
        assert_eq!(
            got.historical_value_copper.as_deref(),
            case["expected"]["canonical_historical_value"].as_str()
        );
        assert_eq!(
            got.priced_days_60,
            case["expected"]["canonical_priced_days_60"]
                .as_u64()
                .unwrap() as usize
        );
        let reversed: Vec<_> = points.into_iter().rev().collect();
        assert_eq!(
            pricing::history(&reversed, "fixture-market", 2589, &"a".repeat(64), as_of).unwrap(),
            got
        );
    }
}

#[test]
fn precision_versions_and_strict_shapes_fail_closed() {
    assert_eq!(
        pricing::copper("9007199254740993").unwrap(),
        9_007_199_254_740_993
    );
    for value in ["01", "-1", "1e3", "9223372036854775808", ""] {
        assert!(pricing::copper(value).is_err());
    }
    assert!(pricing::recent(&[], "asking-v1-provisional").is_err());
    assert!(
        serde_json::from_str::<Tier>(r#"{"unit_copper":100,"quantity":1,"listing_count":1}"#)
            .is_err()
    );
    assert!(serde_json::from_str::<Tier>(
        r#"{"unit_copper":"100","quantity":1,"listing_count":1,"future":true}"#
    )
    .is_err());
    let tiers = vec![
        Tier {
            unit_copper: "2500".into(),
            quantity: 5,
            listing_count: 1,
        },
        Tier {
            unit_copper: "5000".into(),
            quantity: 20,
            listing_count: 1,
        },
    ];
    assert_eq!(
        pricing::recent(&tiers, ALGORITHM).unwrap().as_deref(),
        Some("3333")
    );
    assert_eq!(
        twichui_market_core::protocol::ALGORITHM,
        "asking-v1-provisional"
    );
}

#[test]
fn frozen_bridge_capabilities_keep_both_algorithms_distinct() {
    for raw in [
        include_str!("../../../contracts/bridge/v1/canonical-generation.json"),
        include_str!("../../../contracts/bridge/v1/provisional-generation.json"),
    ] {
        let mut g: Value = serde_json::from_str(raw).unwrap();
        assert!(pricing::supports_bridge_header(&g));
        g["contract_version"] = 2.into();
        assert!(!pricing::supports_bridge_header(&g));
        g["contract_version"] = 1.into();
        g["history_basis"] = "legacy-local-buckets".into();
        assert!(!pricing::supports_bridge_header(&g));
    }
}
