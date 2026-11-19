//! Owner-authorized genuine HTTPS readback. Private cache only; no game discovery,
//! AddOns publication, archive download, provider request or gameplay action.
use std::{fs,path::PathBuf,time::{Duration,Instant}};
use serde_json::json;
use twichui_market_core::{bridge::Scope,client::{server_url,MarketClient},delivery::Configuration,workshop_summary,Error};

fn main()->Result<(),Box<dyn std::error::Error>> {
    let a=std::env::args().skip(1).collect::<Vec<_>>();
    if a.len()!=4||server_url(&a[0])?.as_str()!="https://market.twich.gg/" {return Err("approved HTTPS origin account market new-private-cache".into())}
    let root=PathBuf::from(&a[3]);if root.exists(){return Err("new private cache required".into())}
    fs::create_dir_all(&root)?;
    #[cfg(unix)] {use std::os::unix::fs::PermissionsExt;fs::set_permissions(&root,fs::Permissions::from_mode(0o700))?;}
    let account=a[1].parse()?;let market=a[2].parse()?;
    let client=MarketClient::new(&a[0],std::env::var("TWICHUI_WORKSHOP_RELEASE_TOKEN")?)?;
    let bootstrap=client.bootstrap()?;
    if bootstrap.account.id!=account||bootstrap.resolve_market(Some(market)).is_none(){return Err("authenticated scope differs".into())}
    let scope=Scope{server:server_url(&a[0])?.to_string(),account_id:account,market_id:market,algorithm:"twichui-pricing-v1".into()};
    let started=Instant::now();let mut reports=Vec::new();
    for version in [1,2] {
        let base=root.join(format!("contract-{version}"));let installation=base.join("capability-fixture");
        if version==2 {
            let addon=installation.join("Interface/AddOns/TwichUI_Workshop");fs::create_dir_all(&addon)?;
            fs::write(addon.join("MarketDelivery.json"),br#"{"summary_history_contract":2,"summary_history_partition_bytes":1048576,"summary_history_total_bytes":67108864}"#)?;
        }
        let configuration=Configuration{version:2,enabled:true,scope:scope.clone(),installation,
            selection:json!({"kind":"broad_summary","market_id":market,"region":"us"}),history_days:0};
        let mut preparing=0;
        let (bundle,bytes,requests)=loop {
            if started.elapsed()>Duration::from_secs(420)||preparing>80{return Err("bounded readback deadline".into())}
            match workshop_summary::download(&base,&client,&configuration,&||false) {
                Ok(value)=>break value,
                Err(Error::SummaryPreparing(seconds))=>{
                    let wait=Duration::from_secs(seconds.clamp(1,3600));
                    if started.elapsed()+wait>Duration::from_secs(420){return Err("preparation exceeds readback budget".into())}
                    preparing+=1;std::thread::sleep(wait);
                },
                Err(error)=>return Err(error.into()),
            }
        };
        if bundle.manifest["synthetic"]!=false||bundle.manifest["contract_version"]!=version{return Err("genuine negotiated generation required".into())}
        let warm=match workshop_summary::download(&base,&client,&configuration,&||false) {
            Ok((next,bytes,requests))=>json!({"zero_byte_304":bytes==0&&requests==1,"generation":next.manifest["generation_id"],"bytes":bytes,"requests":requests}),
            Err(Error::SummaryPreparing(_))=>json!({"next_generation_preparing":true,"zero_byte_304":false}),
            Err(error)=>return Err(error.into()),
        };
        reports.push(json!({"contract_version":version,"records":bundle.manifest["record_count"],"generation":bundle.manifest["generation_id"],
            "source_observation":bundle.manifest["source_observation"],"observations":bundle.manifest.get("observations"),"download_bytes":bytes,
            "download_requests":requests,"preparation_responses":preparing,"warm":warm}));
    }
    println!("{}",json!({"authenticated_https":true,"native_contract_and_hash_validation":true,"synthetic":false,
        "game_publication":false,"physical_windows_acceptance":false,"seconds":started.elapsed().as_secs_f64(),"versions":reports}));
    Ok(())
}
