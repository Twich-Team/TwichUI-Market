use twichui_market_core::{
    cache::Cache,
    client::server_url,
    protocol::{Change, Operation, Page, Valuation, ALGORITHM},
    vault,
};
const SERVER: &str = "https://market.example/";

fn value(price: &str) -> Valuation {
    Valuation {
        recent_price: Some(price.into()),
        lowest_buyout: Some(price.into()),
        market_value: Some("100".into()),
        historical_value: Some("100".into()),
        supply: 2,
        priced_supply: 2,
        listing_count: 1,
        coverage_days: 3,
        market_coverage_days: 3,
        synthetic: true,
    }
}
fn page(cursor: &str, target: &str, more: bool, items: &[(u32, Option<&str>)]) -> Page {
    Page {
        contract_version: 1,
        market_id: 1,
        algorithm: ALGORITHM.into(),
        changes: items
            .iter()
            .map(|(id, price)| Change {
                operation: if price.is_some() {
                    Operation::Upsert
                } else {
                    Operation::Delete
                },
                item_id: *id,
                variant_key: format!("{:064x}", id),
                value: price.map(value),
            })
            .collect(),
        cursor: cursor.into(),
        has_more: more,
        target_observation_id: target.into(),
        observed_at: Some("2026-11-13T12:00:00+00:00".into()),
        synthetic: true,
    }
}

#[test]
fn interrupted_sync_preserves_offline_generation_and_resumes_after_restart() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("cache.sqlite");
    let mut cache = Cache::open(&path).unwrap();
    cache
        .apply(
            SERVER,
            1,
            None,
            &page("complete-1", "1", false, &[(1, Some("100"))]),
        )
        .unwrap();
    cache
        .apply(
            SERVER,
            1,
            Some("complete-1"),
            &page("partial-2", "2", true, &[(1, Some("50"))]),
        )
        .unwrap();
    assert_eq!(
        cache.items(SERVER, 1).unwrap()[0]
            .value
            .recent_price
            .as_deref(),
        Some("100")
    );
    assert!(cache.status(SERVER, 1).unwrap().downloading);
    let export = cache.export(SERVER, 1, directory.path()).unwrap();
    assert!(std::fs::read_to_string(export)
        .unwrap()
        .contains("\"recent_price\":\"100\""));
    drop(cache);
    let mut cache = Cache::open(&path).unwrap();
    assert_eq!(
        cache.cursor(SERVER, 1).unwrap().as_deref(),
        Some("partial-2")
    );
    cache
        .apply(
            SERVER,
            1,
            Some("partial-2"),
            &page("complete-2", "2", false, &[(2, Some("200"))]),
        )
        .unwrap();
    let items = cache.items(SERVER, 1).unwrap();
    assert_eq!(items.len(), 2);
    assert_eq!(items[0].value.recent_price.as_deref(), Some("50"));
    assert!(!cache.status(SERVER, 1).unwrap().downloading);
}

#[test]
fn invalid_pages_and_stale_retries_cannot_advance_cursor() {
    let mut cache = Cache::memory().unwrap();
    cache
        .apply(SERVER, 1, None, &page("a", "1", false, &[(1, Some("100"))]))
        .unwrap();
    let mut bad = page("b", "2", false, &[(1, Some("99999999999999999999"))]);
    assert!(cache.apply(SERVER, 1, Some("a"), &bad).is_err());
    bad.changes[0].value = Some(value("-1"));
    assert!(cache.apply(SERVER, 1, Some("a"), &bad).is_err());
    assert!(cache
        .apply(SERVER, 1, None, &page("b", "2", false, &[]))
        .is_err());
    assert_eq!(cache.cursor(SERVER, 1).unwrap().as_deref(), Some("a"));
    assert_eq!(
        cache.items(SERVER, 1).unwrap()[0]
            .value
            .recent_price
            .as_deref(),
        Some("100")
    );
}

#[test]
fn incremental_deletion_reset_and_cross_server_isolation() {
    let mut cache = Cache::memory().unwrap();
    cache
        .apply(
            SERVER,
            1,
            None,
            &page("a", "1", false, &[(1, Some("100")), (2, Some("200"))]),
        )
        .unwrap();
    cache
        .apply(SERVER, 1, Some("a"), &page("b", "2", false, &[(1, None)]))
        .unwrap();
    assert_eq!(cache.items(SERVER, 1).unwrap().len(), 1);
    assert!(cache.items("https://other.example/", 1).unwrap().is_empty());
    cache.reset(SERVER, 1).unwrap();
    assert!(cache.cursor(SERVER, 1).unwrap().is_none());
    assert_eq!(cache.items(SERVER, 1).unwrap().len(), 1);
    cache
        .apply(SERVER, 1, None, &page("c", "3", false, &[]))
        .unwrap();
    assert!(cache.items(SERVER, 1).unwrap().is_empty());
}

#[test]
fn exports_are_data_only_and_savedvariables_is_rejected() {
    let directory = tempfile::tempdir().unwrap();
    let saved = directory.path().join("SavedVariables");
    std::fs::create_dir(&saved).unwrap();
    let mut cache = Cache::memory().unwrap();
    assert!(cache.export(SERVER, 1, directory.path()).is_err());
    cache
        .apply(SERVER, 1, None, &page("a", "1", false, &[(1, Some("100"))]))
        .unwrap();
    assert!(cache.export(SERVER, 1, &saved).is_err());
    let output = cache.export(SERVER, 1, directory.path()).unwrap();
    let data: serde_json::Value = serde_json::from_slice(&std::fs::read(&output).unwrap()).unwrap();
    assert_eq!(data["format"], "twichui-market-addon-data");
    assert_eq!(output.extension().unwrap(), "json");
    assert!(data.get("cursor").is_none());
    cache.export(SERVER, 1, directory.path()).unwrap(); // Atomic replacement also works on Windows.
}

#[test]
fn invalid_versions_duplicates_and_unknown_fields_are_rejected() {
    let mut bad = page("a", "1", false, &[(1, Some("100")), (1, Some("100"))]);
    assert!(bad.validate(1).is_err());
    bad.changes.pop();
    bad.contract_version = 2;
    assert!(bad.validate(1).is_err());
    let mut data = serde_json::to_value(page("a", "1", false, &[])).unwrap();
    data["execute"] = serde_json::json!("never allowed");
    assert!(serde_json::from_value::<Page>(data).is_err());
}

#[test]
fn server_and_credential_scoping_requires_secure_origin() {
    assert!(server_url("http://market.example").is_err());
    assert!(server_url("https://user:secret@market.example").is_err());
    assert!(server_url("https://market.example/path").is_err());
    assert!(server_url("http://127.0.0.1:18780").is_ok());
    assert_eq!(
        vault::credential_target("https://MARKET.example").unwrap(),
        vault::credential_target(SERVER).unwrap()
    );
    assert_ne!(
        vault::credential_target(SERVER).unwrap(),
        vault::credential_target("https://other.example/").unwrap()
    );
}

#[test]
fn compacted_cursor_automatically_rebuilds_without_losing_completed_offline_data() {
    use std::io::{Read, Write};
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let server = format!("http://{}/", listener.local_addr().unwrap());
    let body =
        serde_json::to_string(&page("fresh-cursor", "2", false, &[(2, Some("200"))])).unwrap();
    let worker = std::thread::spawn(move || {
        for (status, body) in [("409 Conflict", "{}".to_string()), ("200 OK", body)] {
            let (mut connection, _) = listener.accept().unwrap();
            let mut request = [0u8; 8192];
            connection.read(&mut request).unwrap();
            write!(connection,"HTTP/1.1 {status}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",body.len()).unwrap();
        }
    });
    let mut cache = Cache::memory().unwrap();
    cache
        .apply(
            &server,
            1,
            None,
            &page("old-cursor", "1", false, &[(1, Some("100"))]),
        )
        .unwrap();
    let client = twichui_market_core::client::MarketClient::new(
        &server,
        "synthetic-test-device-token".into(),
    )
    .unwrap();
    assert!(!client.synchronize_page(&mut cache, 1).unwrap());
    assert_eq!(
        cache.cursor(&server, 1).unwrap().as_deref(),
        Some("fresh-cursor")
    );
    let items = cache.items(&server, 1).unwrap();
    assert_eq!(items.len(), 1);
    assert_eq!(items[0].item_id, 2);
    worker.join().unwrap();
}

#[cfg(windows)]
#[test]
fn native_windows_credential_round_trip() {
    let server = format!("https://credential-test-{}.invalid/", std::process::id());
    vault::save(&server, "synthetic-test-device-token").unwrap();
    assert_eq!(vault::load(&server).unwrap(), "synthetic-test-device-token");
    vault::remove(&server).unwrap();
    assert!(vault::load(&server).is_err());
}
