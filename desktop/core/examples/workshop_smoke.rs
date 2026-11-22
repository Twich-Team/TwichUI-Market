//! Synthetic actual-HTTP summary acceptance. No archive or provider access.
use std::{path::PathBuf,time::Instant};
use serde_json::json;
use twichui_market_core::{bridge::{self,Scope},client::MarketClient,delivery::{self,Configuration},workshop_summary as summary,Error};
fn main()->Result<(),Box<dyn std::error::Error>> {
 let a=std::env::args().skip(1).collect::<Vec<_>>();
 if a.len()!=6{return Err("server account market private-base game publish|stage".into())}
 let scope=Scope{server:twichui_market_core::client::server_url(&a[0])?.to_string(),account_id:a[1].parse()?,market_id:a[2].parse()?,algorithm:"twichui-pricing-v1".into()};
 let base=PathBuf::from(&a[3]);let game=PathBuf::from(&a[4]);
 let c=Configuration{version:2,enabled:true,scope:scope.clone(),installation:game,selection:json!({"kind":"broad_summary","market_id":scope.market_id,"region":"us"}),history_days:0};
 let client=MarketClient::new(&scope.server,std::env::var("TWICHUI_SUMMARY_TEST_TOKEN")?)?;
 let start=Instant::now();
 let result:Result<serde_json::Value,Error>=(||{
  if a[5]=="publish" {
   c.save_confirmed(&base,true)?;
   let status=delivery::synchronize(&base,&client,&c,||false)?;
   Ok(json!({"ready":true,"status":status,"elapsed_ms":start.elapsed().as_secs_f64()*1000.}))
  }else if a[5]=="stage" {
   let(bundle,bytes,requests)=summary::download(&base,&client,&c,&||false)?;
   if bundle.manifest["synthetic"]!=true{return Err(Error::Invalid("synthetic acceptance source required"))}
   let out=base.join("publication");std::fs::create_dir_all(&out)?;
   let root=out.join("TwichUI_MarketData");std::fs::create_dir_all(&root)?;
   let receipt=json!({"schema_version":1,"generation_id":bundle.manifest["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)});
   std::fs::write(root.join("Data.lua"),summary::root_artifact(&bundle.manifest,"A",&receipt)?)?;
   for (&bucket,raw) in &bundle.parts {let dir=out.join(format!("TwichUI_Market{}PartA{:02}",if bucket>=64{"History"}else{""},bucket%64));std::fs::create_dir_all(&dir)?;std::fs::write(dir.join("Data.lua"),summary::part_artifact("A",bucket,raw))?;}
   Ok(json!({"ready":true,"manifest":bundle.manifest,"download_bytes":bytes,"requests":requests,"publication":out,"elapsed_ms":start.elapsed().as_secs_f64()*1000.}))
  }else{Err(Error::Invalid("summary acceptance action"))}
 })();
 match result {
  Ok(v)=>println!("{}",v),
  Err(Error::SummaryPreparing(seconds))=>println!("{}",json!({"ready":false,"retry_after":seconds,"elapsed_ms":start.elapsed().as_secs_f64()*1000.})),
  Err(e)=>return Err(e.into()),
 }
 let _=bridge::canonical(&json!({"verified":"same production codec"}))?;
 if base.join("history-archive-v1.sqlite").exists(){return Err("summary created a history archive".into())}
 Ok(())
}
