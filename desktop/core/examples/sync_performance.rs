//! Actual native HTTP/SQLite benchmark. Only explicit loopback fixtures are accepted.
use std::{path::PathBuf,time::Instant};
use twichui_market_core::{cache::Cache,client::MarketClient,performance::Capture,scheduler::{Scheduler,SystemClock},settings::Settings,synchronizer};
use sha2::{Digest,Sha256};
fn main()->Result<(),Box<dyn std::error::Error>> {
    let server=std::env::var("SYNC_PERF_SERVER")?;
    if !server.starts_with("http://127.0.0.1:"){return Err("explicit loopback benchmark fixture required".into())}
    let path=PathBuf::from(std::env::var("SYNC_PERF_CACHE")?);
    let market=std::env::var("SYNC_PERF_MARKET").unwrap_or("2".into()).parse()?;
    let mut client=MarketClient::new(&server,std::env::var("SYNC_PERF_TOKEN")?)?;
    let limit=std::env::var("SYNC_PERF_LIMIT").unwrap_or("50".into()).parse()?;
    client=client.with_page_limit(limit)?;
    let trace=Capture::begin();
    let mut scheduler=Scheduler::new(SystemClock,Settings{selected_market:Some(market),..Settings::default()},true)?;
    let run=scheduler.sync_now().ok_or("fixture scheduler did not begin")?;
    let started=Instant::now();
    let result=synchronizer::synchronize(&client,&server,&path,&run,Some(market),&SystemClock,&|_|{twichui_market_core::performance::sqlite_size(&path);},|_|{})?;
    if !matches!(result,twichui_market_core::worker::Execution::Completed(_)){return Err("native sync did not complete".into())}
    let elapsed=started.elapsed().as_secs_f64();let report=trace.report();drop(trace);
    let cache=Cache::open(&path)?;let origin=twichui_market_core::client::server_url(&server)?.to_string();
    let items=cache.items(&origin,market)?;let exact=serde_json::to_vec(&items)?;
    let integrity=rusqlite::Connection::open(&path)?.query_row("PRAGMA integrity_check",[],|r|r.get::<_,String>(0))?;
    if integrity!="ok"{return Err("benchmark cache integrity".into())}
    println!("{}",serde_json::json!({"seconds":elapsed,"page_limit":limit,"item_count":items.len(),"cache_values_sha256":format!("{:x}",Sha256::digest(&exact)),"trace":report,"integrity":integrity,"os":std::env::consts::OS}));Ok(())
}
