//! Owner-authorized bounded HTTPS acceptance, private disposable cache only.
use std::time::{Duration, Instant};
use sha2::{Digest, Sha256};
use twichui_market_core::{cache::Cache, client::MarketClient, performance::Capture, scheduler::{Scheduler, SystemClock}, settings::Settings, synchronizer, worker::Execution};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let server = "https://market.twich.gg";
    let client = MarketClient::new(server, std::env::var("SYNC_RELEASE_TOKEN")?)?;
    let temporary = tempfile::tempdir()?;
    let path = temporary.path().join("acceptance.sqlite");
    let mut reports = Vec::new();
    for attempt in 0..2 {
        let capture = Capture::begin();
        let started = Instant::now();
        let mut scheduler = Scheduler::new(SystemClock, Settings { selected_market: Some(2), ..Settings::default() }, true)?;
        let run = scheduler.sync_now().ok_or("acceptance scheduler")?;
        let progress = |pages| assert!(pages <= 500 && started.elapsed() < Duration::from_secs(120), "bounded native acceptance deadline");
        let result = synchronizer::synchronize(&client, server, &path, &run, Some(2), &SystemClock, &progress, |_| {})?;
        if !matches!(result, Execution::Completed(_)) { return Err("acceptance did not complete".into()); }
        let trace = capture.report();
        drop(capture);
        let cache = Cache::open(&path)?;
        let items = cache.items("https://market.twich.gg/", 2)?;
        let integrity: String = rusqlite::Connection::open(&path)?.query_row("PRAGMA integrity_check", [], |r| r.get(0))?;
        if integrity != "ok" || items.is_empty() || items.iter().any(|i| i.value.synthetic) { return Err("genuine cache acceptance".into()); }
        reports.push(serde_json::json!({"attempt":attempt,"records":items.len(),"seconds":started.elapsed().as_secs_f64(),"values_sha256":format!("{:x}",Sha256::digest(serde_json::to_vec(&items)?)),"trace":trace,"integrity":integrity}));
    }
    println!("{}", serde_json::json!({"authenticated_https":true,"actual_native_sync":true,"synthetic":false,"game_publication":false,"runs":reports}));
    Ok(())
}
