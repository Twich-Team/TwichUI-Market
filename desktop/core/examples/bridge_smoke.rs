//! Disposable local HTTP → SQLite → fixed Lua bridge test. Token comes from test-only environment.
use std::{path::PathBuf,time::Instant};
use twichui_market_core::{bridge::{BridgeCache,Scope,export_staging},client::MarketClient};
fn main()->Result<(),Box<dyn std::error::Error>> {
 let args=std::env::args().skip(1).collect::<Vec<_>>();if args.len()!=5{return Err("server account market cache staging-root required".into())}
 let scope=Scope{server:twichui_market_core::client::server_url(&args[0])?.to_string(),account_id:args[1].parse()?,market_id:args[2].parse()?,algorithm:"twichui-pricing-v1".into()};
 let client=MarketClient::new(&scope.server,std::env::var("TWICHUI_BRIDGE_TEST_TOKEN")?)?;let mut cache=BridgeCache::open(&PathBuf::from(&args[3]))?;
 let start=Instant::now();client.download_bridge(&mut cache,&scope,||false)?;let download_ms=start.elapsed().as_secs_f64()*1000.;
 let start=Instant::now();let path=export_staging(&cache,&scope,&PathBuf::from(&args[4]))?;let export_ms=start.elapsed().as_secs_f64()*1000.;
 let(g,receipt)=cache.completed(&scope)?.ok_or("missing completed cache")?;
 println!("{}",serde_json::json!({"generation_id":g["generation_id"],"market":g["market"],"schema_version":g["schema_version"],"record_count":g["record_count"],"algorithm":g["pricing_algorithm"],"lua_path":path,"lua_bytes":std::fs::metadata(&path)?.len(),"payload_bytes":twichui_market_core::bridge::canonical(&g)?.len(),"download_ms":download_ms,"export_ms":export_ms,"receipt":receipt}));Ok(())
}
