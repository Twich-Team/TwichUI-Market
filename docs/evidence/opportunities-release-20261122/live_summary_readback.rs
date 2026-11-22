//! Operator-only genuine HTTPS readback. Frozen core; no Windows install or game activation.
use std::{path::PathBuf,fs};
use serde_json::json;
use twichui_market_core::{bridge::Scope,client::MarketClient,delivery::Configuration,workshop_summary as summary,Error};
fn main()->Result<(),Box<dyn std::error::Error>> {
 let a=std::env::args().skip(1).collect::<Vec<_>>();if a.len()!=5{return Err("server account market private-base capability-root".into())}
 let scope=Scope{server:twichui_market_core::client::server_url(&a[0])?.to_string(),account_id:a[1].parse()?,market_id:a[2].parse()?,algorithm:"twichui-pricing-v1".into()};
 let base=PathBuf::from(&a[3]);let c=Configuration{version:2,enabled:true,scope:scope.clone(),installation:PathBuf::from(&a[4]),selection:json!({"kind":"broad_summary","market_id":scope.market_id,"region":"us"}),history_days:0};
 let client=MarketClient::new(&scope.server,std::env::var("TWICHUI_SUMMARY_TEST_TOKEN")?)?;
 match summary::download(&base,&client,&c,&||false) {
  Err(Error::SummaryPreparing(seconds))=>println!("{}",json!({"ready":false,"retry_after":seconds})),
  Err(e)=>return Err(e.into()),
  Ok((bundle,bytes,requests))=>{
   if bundle.manifest["synthetic"]!=false{return Err("genuine production source required".into())}
   let out=base.join("publication");fs::create_dir_all(&out)?;
   // Both verified projections are staged/read back before emitting the root artifact.
   if bytes>0 || !out.join("TwichUI_MarketData/Data.lua").is_file() {
   for (&bucket,raw) in &bundle.parts {let name=format!("TwichUI_Market{}PartA{:02}",if bucket>=64{"History"}else{""},bucket%64);let dir=out.join(name);fs::create_dir_all(&dir)?;let artifact=summary::part_artifact("A",bucket,raw);let path=dir.join("Data.lua");fs::write(&path,&artifact)?;if fs::read(&path)?!=artifact{return Err("staging readback differs".into())}}
   let root=out.join("TwichUI_MarketData");fs::create_dir_all(&root)?;let receipt=json!({"schema_version":1,"generation_id":bundle.manifest["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)});fs::write(root.join("Data.lua"),summary::root_artifact(&bundle.manifest,"A",&receipt)?)?;
   }
   println!("{}",json!({"ready":true,"manifest":bundle.manifest,"download_bytes":bytes,"requests":requests,"staged_projection_parts":bundle.parts.len(),"publication":out,"synthetic":false,"real_game":false,"mode":"Linux source-qualified core readback/staging; not installed Windows publication"}));
  }
 }
 Ok(())
}
