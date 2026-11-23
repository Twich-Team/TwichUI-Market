//! Offline PRIVATE DEV acceptance only. No network, credentials or game discovery.
//! All native integrity, ownership, capacity, readback and A/B publication stay enabled.
use std::{collections::BTreeMap, path::Path};
use serde_json::{json, Value};
use twichui_market_core::{delivery::Configuration, workshop_summary::{self, Bundle}};

fn read(path: &Path, maximum: u64) -> Result<Vec<u8>, Box<dyn std::error::Error>> {
    for ancestor in path.ancestors() {
        let metadata=std::fs::symlink_metadata(ancestor)?;
        #[cfg(windows)]
        let reparse={use std::os::windows::fs::MetadataExt; metadata.file_attributes() & 0x400 != 0};
        #[cfg(not(windows))]
        let reparse=false;
        if metadata.file_type().is_symlink() || reparse {
            return Err("linked private snapshot refused".into());
        }
    }
    if std::fs::metadata(path)?.len() > maximum {return Err("private snapshot file bound".into());}
    Ok(std::fs::read(path)?)
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    if !cfg!(all(windows, feature="private-dev")) {return Err("Windows private-dev build required".into());}
    let args=std::env::args().skip(1).collect::<Vec<_>>();
    let lifecycle=args.len()==4 && args[3]=="--verify-container-lifecycle";
    if args.len()!=3 && !lifecycle {return Err("DEV_APPDATA FROZEN_SNAPSHOT 16|32 [--verify-container-lifecycle]".into());}
    if lifecycle && (std::env::var("GITHUB_ACTIONS").as_deref()!=Ok("true") || args[2]!="32") {return Err("container lifecycle is disposable Windows CI only".into());}
    let base=Path::new(&args[0]); let source=Path::new(&args[1]);
    if base.file_name().and_then(|p|p.to_str())!=Some("team.twich.market.dev") {
        return Err("only the isolated DEV AppData is accepted".into());
    }
    let count:usize=args[2].parse()?;
    if ![16,32].contains(&count) {return Err("layout must be 16 or 32".into());}
    let c=Configuration::load(base)?.ok_or("Connect Workshop in DEV first")?;
    if c.version!=2 || !c.enabled {return Err("a confirmed DEV Workshop destination is required".into());}
    // Explicit marker is created only in the owner's independent VM game copy.
    let marker=c.installation.join(".twichui-private-native-test");
    if read(&marker,256)?!=b"PRIVATE VM ONLY\n" {return Err("private VM game marker required".into());}
    let scope:Value=serde_json::from_slice(&read(&source.join("scope.json"),2048)?)?;
    if serde_json::to_value(&c.scope)?!=scope {return Err("snapshot must match this DEV account/market/origin".into());}
    let manifest:Value=serde_json::from_slice(&read(&source.join("manifest.json"),65536)?)?;
    let mut parts=BTreeMap::new();
    for position in 0..128u8 {
        parts.insert(position,read(&source.join("parts").join(format!("{position:02}.json")),1048576)?);
    }
    let prepared:Value=serde_json::from_slice(&read(&source.join(format!("prepared-{count}.json")),65536)?)?;
    let bundle=Bundle{manifest,parts,prepared:Some(prepared)};
    bundle.validate(&c.scope,c.selection["region"].as_str())?;
    let actual=twichui_market_core::installation::prepared_layout(&c.installation)?;
    if actual!=Some(count) {return Err("set the private installed MarketDelivery.json layout first".into());}
    // The publisher enforces actual PE/addon identity and owned game output.
    let changed=workshop_summary::publish(&c,&bundle,&||false)?;
    if lifecycle {
        let cap=c.installation.join("Interface/AddOns/TwichUI_Workshop/MarketDelivery.json");
        let original=read(&cap,4096)?;let root=c.installation.join("Interface/AddOns/TwichUI_MarketData/Data.lua");
        let before=read(&root,3*1024*1024)?;
        if !before.starts_with(twichui_market_core::workshop_prepared::ROOT_PREFIX){return Err("legacy prepared lifecycle baseline required".into());}
        let mut value:Value=serde_json::from_slice(&original)?;
        for(k,v)in [("container_packaging_version",json!(1)),("container_codec",json!("raw-deflate-base64")),("container_block_bytes",json!(524288)),("current_containers",json!(8)),("history_containers",json!(4))]{value[k]=v;}
        std::fs::write(&cap,serde_json::to_vec(&value)?)?;
        // Genuine Windows process inventory must prevent removal of old addons
        // while the versioned, long-running fixture executable is still alive.
        let mut game=std::process::Command::new(c.installation.join("Wow.exe")).spawn()?;
        let blocked=workshop_summary::publish(&c,&bundle,&||false);game.kill()?;game.wait()?;
        if blocked.is_ok() || read(&root,3*1024*1024)?!=before{return Err("running-game migration did not preserve old root".into());}
        if !workshop_summary::publish(&c,&bundle,&||false)?{return Err("container migration missing".into());}
        let count=std::fs::read_dir(c.installation.join("Interface/AddOns"))?.filter(|e|e.as_ref().is_ok_and(|e|e.file_name().to_string_lossy().starts_with("TwichUI_Market"))).count();
        if count!=25{return Err("migration must leave twenty-five physical Market addons".into());}
        let mut disconnected=c.clone();disconnected.enabled=false;disconnected.save_confirmed(base,false)?;
        workshop_summary::restore_previous(base,&disconnected)?;
        if read(&root,3*1024*1024)?!=before{return Err("legacy restore changed exact root".into());}
        c.save_confirmed(base,true)?;
        // Re-migration must clean the byte-identical restored copies safely.
        if !workshop_summary::publish(&c,&bundle,&||false)?{return Err("re-migration missing".into());}
        disconnected.save_confirmed(base,false)?;workshop_summary::restore_previous(base,&disconnected)?;
        std::fs::write(&cap,original)?;c.save_confirmed(base,true)?;
        if read(&root,3*1024*1024)?!=before{return Err("final compatible restoration failed".into());}
    }
    println!("{}",json!({"generation":bundle.manifest["generation_id"],"layout":count,
                         "history_partitions":64,"changed":changed,"offline":true,"container_lifecycle_verified":lifecycle,
                         "source_commit":option_env!("COMPANION_DEV_SHA").unwrap_or("CI fixture"),
                         "source_synthetic":bundle.manifest["synthetic"]}));
    Ok(())
}
