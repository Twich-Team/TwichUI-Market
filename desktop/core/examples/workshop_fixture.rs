//! Bounded synthetic producer fixture -> actual native validation/transport.
//! Never discovers a game, publishes to AddOns, or reads player data.
use std::{collections::BTreeMap,fs,path::PathBuf};
use serde_json::{json,Value};
use twichui_market_core::{bridge::Scope,workshop_summary::{self,Bundle,HISTORY_TOTAL}};
fn main()->Result<(),Box<dyn std::error::Error>> {
    let args=std::env::args().skip(1).collect::<Vec<_>>();if args.len()!=2{return Err("synthetic-fixture.json new-output-folder".into())}
    let input=PathBuf::from(&args[0]);let output=PathBuf::from(&args[1]);
    if fs::metadata(&input)?.len()>HISTORY_TOTAL as u64*3||output.exists(){return Err("bounded fixture and new empty output required".into())}
    let v:Value=serde_json::from_slice(&fs::read(input)?)?;
    if v["manifest"]["synthetic"]!=true{return Err("explicitly synthetic input required".into())}
    let b=Bundle{manifest:v["manifest"].clone(),parts:v["parts"].as_object().ok_or("parts")?.iter().map(|(k,v)|Ok((k.parse::<u8>()?,v.as_str().ok_or("raw part")?.as_bytes().to_vec()))).collect::<Result<BTreeMap<_,_>,Box<dyn std::error::Error>>>()?};
    let scope=Scope{server:"http://127.0.0.1:18888/".into(),account_id:1,market_id:b.manifest["market"]["server_market_id"].as_u64().ok_or("market")? as u32,algorithm:"twichui-pricing-v1".into()};
    b.validate(&scope,None)?;
    fs::create_dir_all(&output)?;let root=output.join("TwichUI_MarketData");fs::create_dir(&root)?;
    let receipt=json!({"schema_version":1,"generation_id":b.manifest["generation_id"],"desktop_build":"synthetic-history-benchmark","completed_at":"2026-11-19T00:00:00Z"});
    fs::write(root.join("Data.lua"),workshop_summary::root_artifact(&b.manifest,"A",&receipt)?)?;
    for (&bucket,raw) in &b.parts {let dir=output.join(format!("TwichUI_MarketPartA{bucket:02}"));fs::create_dir(&dir)?;fs::write(dir.join("Data.lua"),workshop_summary::part_artifact("A",bucket,raw))?;}
    println!("{}",json!({"synthetic":true,"game_publication":false,"records":b.manifest["record_count"],"parts":b.parts.len(),"raw_bytes":b.parts.values().map(Vec::len).sum::<usize>()}));Ok(())
}
