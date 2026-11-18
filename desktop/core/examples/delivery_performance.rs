//! Isolated synthetic loopback acceptance, using actual native synchronization,
//! durable stores, cryptographic validation and atomic publication routines.
use std::{path::PathBuf,time::{Instant,Duration},io::Write};
use serde_json::json;
use sha2::{Digest,Sha256};
use twichui_market_core::{archive::{ArchiveStore,DEFAULT_DISK_BUDGET},bridge::Scope,client::MarketClient,delivery::{self,Configuration},performance::Capture,scheduler::{Scheduler,SystemClock},settings::Settings,synchronizer,workshop_summary,Error};
fn main()->Result<(),Box<dyn std::error::Error>> {
 let a=std::env::args().skip(1).collect::<Vec<_>>();if a.len()!=4||!a[0].starts_with("http://127.0.0.1:"){return Err("synthetic loopback origin private-base game archive|auto".into())}
 let base=PathBuf::from(&a[1]);let game=PathBuf::from(&a[2]);let client=MarketClient::new(&a[0],std::env::var("SYNC_PERF_TOKEN")?)?;
 let capture=Capture::begin();let started=Instant::now();let bootstrap=client.bootstrap()?;let market=bootstrap.resolve_market(Some(2)).ok_or("fixture market unavailable")?;
 let scope=Scope{server:format!("{}/",a[0].trim_end_matches('/')),account_id:bootstrap.account.id,market_id:market.id,algorithm:"twichui-pricing-v1".into()};
 let extra;let values_hash;
 if a[3]=="archive" {
  let path=base.join("history.sqlite");let mut store=ArchiveStore::open(&path,DEFAULT_DISK_BUDGET)?;
  client.download_archive(&mut store,&scope,||false)?;
  twichui_market_core::performance::sqlite_size(&path);
  let header=store.active(&scope)?.ok_or("missing completed archive")?;if header.protocol_version!=2{return Err("unified archive v2 required".into())}
  let db=rusqlite::Connection::open(&path)?;let mut query=db.prepare("SELECT phase,source_id,item_id,variant,value FROM history_entries ORDER BY phase,source_id,item_id,variant")?;
  let mut rows=query.query([])?;let mut hash=Sha256::new();let mut count=0;
  while let Some(row)=rows.next()? {let value=(row.get::<_,i64>(0)?,row.get::<_,i64>(1)?,row.get::<_,u32>(2)?,row.get::<_,String>(3)?,row.get::<_,String>(4)?);hash.update(serde_json::to_vec(&value)?);hash.update(b"\n");count+=1;}
  values_hash=format!("{:x}",hash.finalize());extra=json!({"archive_records":header.total_records,"stored_entries":count,"archive_bytes":store.allocated_bytes()?,"archive_metrics":store.metrics(),"archive_complete":header.archive_complete});
 }else if a[3]=="auto" {
  let config=Configuration{version:2,enabled:true,scope:scope.clone(),installation:game.clone(),selection:json!({"kind":"broad_summary","market_id":scope.market_id,"region":"us"}),history_days:0};
  #[cfg(windows)] config.save_confirmed(&base,true)?;
  let mut scheduler=Scheduler::new(SystemClock,Settings{selected_market:Some(2),..Settings::default()},true)?;let run=scheduler.sync_now().ok_or("fixture scheduler")?;
  let mut attempts=0;let mut slept_ms=0u64;
  let status=loop {attempts+=1;if attempts>160{return Err("preparation bound".into())}
   synchronizer::synchronize(&client,&scope.server,&base.join("market.sqlite"),&run,Some(2),&SystemClock,&|_|{},|_|{})?;
   match attempt(&base,&client,&config) {Ok(s)=>break s,Err(Error::SummaryPreparing(seconds))=>{let delay=seconds.clamp(1,3600)*1000;slept_ms+=delay;std::thread::sleep(Duration::from_millis(delay));},Err(e)=>return Err(e.into())}
  };
  let (bundle,_,_)=workshop_summary::download(&base,&client,&config,&||false)?;
  if bundle.manifest["synthetic"]!=true{return Err("synthetic fixture required".into())}
  let mut hash=Sha256::new();for (bucket,raw) in &bundle.parts {hash.update([*bucket]);hash.update(raw);}values_hash=format!("{:x}",hash.finalize());
  let warm=attempt(&base,&client,&config)?;if warm.download_bytes!=Some(0)||warm.download_requests!=Some(1){return Err("unchanged Workshop transferred data".into())}
  extra=json!({"workshop_records":status.summary_records,"attempts":attempts,"actual_preparation_sleep_ms":slept_ms,"zero_byte_warm_workshop":true,"game_files_published":cfg!(windows),"physical_game":false});
 }else{return Err("unknown fixture mode".into())}
 let result=json!({"mode":a[3],"seconds":started.elapsed().as_secs_f64(),"trace":capture.report(),"values_sha256":values_hash,"detail":extra,"os":std::env::consts::OS});std::io::stdout().write_all(serde_json::to_string(&result)?.as_bytes())?;Ok(())
}

fn attempt(base:&std::path::Path,client:&MarketClient,c:&Configuration)->twichui_market_core::Result<delivery::Status> {
 #[cfg(windows)] {delivery::synchronize(base,client,c,||false)}
 #[cfg(not(windows))] {
  // Linux cannot authorize a Windows game installation. Measure the same
  // authenticated download and native Lua codec in private staging only.
  let(bundle,bytes,requests)=workshop_summary::download(base,client,c,&||false)?;
  let out=base.join("staged-output");std::fs::create_dir_all(&out)?;
  let receipt=json!({"schema_version":1,"generation_id":bundle.manifest["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)});
  let root=workshop_summary::root_artifact(&bundle.manifest,"A",&receipt)?;workshop_summary::inspect_root(&root,&c.scope,Some("us"))?;std::fs::write(out.join("Data.lua"),root)?;
  for(bucket,raw) in &bundle.parts {std::fs::write(out.join(format!("{bucket:02}.lua")),workshop_summary::part_artifact("A",*bucket,raw))?;}
  Ok(delivery::Status{download_bytes:Some(bytes),download_requests:Some(requests),summary_records:bundle.manifest["record_count"].as_u64(),..Default::default()})
 }
}
