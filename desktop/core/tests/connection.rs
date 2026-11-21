use chrono::{TimeZone, Utc};
use serde_json::json;
use twichui_market_core::{
    cache::{Cache, Completion},
    connection::{Bootstrap, Provenance},
    scheduler::{Scheduler, SystemClock},
    settings::Settings,
};

fn bootstrap() -> Bootstrap {
    let source = json!({"market_id":2,"server_checked_at":"2026-11-14T12:05:00Z","upstream_updated_at":"2026-11-14T12:00:00Z",
        "observation_id":"12","watermark_observation_id":"14","snapshot_id":"7","generation":format!("7:{}","a".repeat(64)),
        "valuation_generation":"b".repeat(64),"synthetic":false,"valuation_synthetic":true});
    serde_json::from_value(json!({"contract_version":1,"account":{"id":1,"username":"synthetic"},"preferred_market_id":2,"suggested_market_id":2,
        "preference_fallback":false,"device":null,"markets":[{"id":2,"label":"US — Normal — Horde","region":"us","enabled":true,
        "verified":true,"player_identity_verified":true,"available_for_sync":true,"next_check":"2026-11-14T12:10:00Z","source":source}]})).unwrap()
}
#[test]
fn website_preference_local_override_and_disabled_market_are_resolved_without_mutation() {
    let mut value = bootstrap();
    value.validate().unwrap();
    assert_eq!(value.resolve_market(None).unwrap().id, 2);
    assert!(value.resolve_market(Some(1)).is_none());
    assert_eq!(value.preferred_market_id, Some(2));
    value.markets[0].enabled = false;
    value.markets[0].available_for_sync = false;
    value.suggested_market_id = None;
    value.preference_fallback = true;
    value.validate().unwrap();
    assert!(value.resolve_market(None).is_none());
    assert!(value.resolve_market(Some(2)).is_none());
    assert_eq!(value.preferred_market_id, Some(2));
}
#[test]
fn bootstrap_cannot_offer_unverified_duplicate_or_cross_account_device_identity() {
    let good = bootstrap();
    let mut value = good.clone();
    value.markets[0].player_identity_verified = false;
    assert!(value.validate().is_err());
    let mut value = good.clone();
    value.markets.push(value.markets[0].clone());
    assert!(value.validate().is_err());
    let mut value = good.clone();
    value.contract_version = 99;
    assert!(value.validate().is_err());
    let mut raw = serde_json::to_value(good).unwrap();
    raw["device"] = json!({"id":7,"user_id":99,"name":"Wrong account","platform":"Windows","app_version":"2.0.0",
        "authorized_at":"2026-11-14T12:00:00Z","expires_at":"2026-12-14T12:00:00Z","revoked":false,"last_connection_at":null,"last_sync_at":null,
        "selected_market_id":2,"selected_market_name":"US — Normal — Horde"});
    assert!(serde_json::from_value::<Bootstrap>(raw)
        .unwrap()
        .validate()
        .is_err());
}
#[test]
fn additive_bootstrap_fields_are_safe_but_untrusted_generation_and_market_ids_are_rejected() {
    let mut raw = serde_json::to_value(bootstrap()).unwrap();
    raw["new_server_field"] = json!("additive");
    let value: Bootstrap = serde_json::from_value(raw.clone()).unwrap();
    value.validate().unwrap();
    raw["markets"][0]["source"]["generation"] = json!("8:wrong");
    assert!(serde_json::from_value::<Bootstrap>(raw)
        .unwrap()
        .validate()
        .is_err());
    let mut source = bootstrap().markets.remove(0).source;
    source.market_id = 1;
    assert!(source.validate(2).is_err());
}
fn page(cursor: &str, target: &str, more: bool) -> twichui_market_core::protocol::Page {
    serde_json::from_value(json!({"contract_version":1,"market_id":2,"algorithm":"asking-v1-provisional","changes":[],"cursor":cursor,
        "has_more":more,"target_observation_id":target,"observed_at":"2026-11-14T12:05:00Z","synthetic":true})).unwrap()
}
#[test]
fn completion_survives_restart_keeps_distinct_timestamps_and_isolated_markets() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("cache.sqlite");
    let server = "https://market.example/";
    let source = bootstrap().markets.remove(0).source;
    let receipt = Completion {
        schema_version: 1,
        last_sync_ms: Utc
            .with_ymd_and_hms(2026, 11, 14, 12, 6, 0)
            .unwrap()
            .timestamp_millis(),
        source,
    };
    let mut cache = Cache::open(&path).unwrap();
    cache
        .apply(server, 2, None, &page("complete", "14", false))
        .unwrap();
    cache.record_completion(server, 2, &receipt).unwrap();
    drop(cache);
    let cache = Cache::open(&path).unwrap();
    let saved = cache.completion(server, 2).unwrap().unwrap();
    assert_eq!(saved.last_sync_ms, receipt.last_sync_ms);
    assert_eq!(saved.source.observation_id.as_deref(), Some("12"));
    assert!(cache.completion(server, 1).unwrap().is_none());
    assert!(cache
        .completion("https://other.example/", 2)
        .unwrap()
        .is_none());
    let settings = Settings {
        selected_market: Some(2),
        sync_on_startup: false,
        ..Settings::default()
    };
    let mut scheduler = Scheduler::new(SystemClock, settings, true).unwrap();
    let deadline = scheduler.snapshot().next_sync_ms;
    scheduler.restore_completion(&saved).unwrap();
    let state = scheduler.snapshot();
    assert_eq!(state.last_sync_ms, Some(receipt.last_sync_ms));
    assert_eq!(
        state.last_server_check_ms,
        Some(receipt.source.server_checked_at.unwrap().timestamp_millis())
    );
    assert_ne!(state.last_server_check_ms, state.upstream_update_ms);
    assert!(!state.received_new_generation);
    assert_eq!(state.next_sync_ms, deadline);
    let version: u32 = rusqlite::Connection::open(&path)
        .unwrap()
        .pragma_query_value(None, "user_version", |r| r.get(0))
        .unwrap();
    assert_eq!(version, 2);
}
#[test]
fn completion_cannot_claim_a_different_or_unfinished_cache_generation() {
    let source: Provenance = bootstrap().markets.remove(0).source;
    let server = "https://market.example/";
    let receipt = Completion {
        schema_version: 1,
        last_sync_ms: 1,
        source,
    };
    let mut cache = Cache::memory().unwrap();
    assert!(cache.record_completion(server, 2, &receipt).is_err());
    cache
        .apply(server, 2, None, &page("partial", "14", true))
        .unwrap();
    assert!(cache.record_completion(server, 2, &receipt).is_err());
    cache
        .apply(server, 2, Some("partial"), &page("complete", "14", false))
        .unwrap();
    cache.record_completion(server, 2, &receipt).unwrap();
    let mut wrong = receipt.clone();
    wrong.source.watermark_observation_id = Some("15".into());
    assert!(cache.record_completion(server, 2, &wrong).is_err());
    assert_eq!(
        cache
            .completion(server, 2)
            .unwrap()
            .unwrap()
            .source
            .watermark_observation_id
            .as_deref(),
        Some("14")
    );
    let mut scheduler = Scheduler::new(
        SystemClock,
        Settings {
            selected_market: Some(1),
            ..Settings::default()
        },
        true,
    )
    .unwrap();
    assert!(scheduler.restore_completion(&receipt).is_err());
}
