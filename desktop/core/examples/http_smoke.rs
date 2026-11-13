//! Actual HTTP integration; token is environment-only and never printed.
use twichui_market_core::{
    cache::Cache,
    client::{server_url, MarketClient},
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = server_url(&std::env::var("MARKET_TEST_SERVER")?)?.to_string();
    let client = MarketClient::new(&server, std::env::var("MARKET_TEST_TOKEN")?)?;
    client.authenticate()?;
    let directory = tempfile::tempdir()?;
    let mut cache = Cache::open(&directory.path().join("cache.sqlite"))?;
    for _ in 0..100 {
        let cursor = cache.cursor(&server, 1)?;
        let page = client.page(1, cursor.as_deref())?;
        cache.apply(&server, 1, cursor.as_deref(), &page)?;
        if !page.has_more {
            break;
        }
    }
    let status = cache.status(&server, 1)?;
    assert!(status.has_completed_cache && !status.downloading);
    assert_eq!(status.item_count, 2);
    let cursor = cache.cursor(&server, 1)?;
    let page = client.page(1, cursor.as_deref())?;
    assert!(page.changes.is_empty() && !page.has_more);
    cache.apply(&server, 1, cursor.as_deref(), &page)?;
    let exported = cache.export(&server, 1, directory.path())?;
    assert!(std::fs::metadata(exported)?.len() > 100);
    // Credential rejection must not destroy the completed offline generation.
    let invalid = MarketClient::new(&server, "synthetic-invalid-device-token".into())?;
    assert!(invalid.page(1, None).is_err());
    assert_eq!(cache.status(&server, 1)?.item_count, 2);
    println!("Actual HTTP authentication, sync, incremental no-op, offline cache and JSON export verified.");
    Ok(())
}
