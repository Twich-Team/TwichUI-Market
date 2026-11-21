//! Actual authenticated HTTPS acceptance. Downloads validated data to a disposable
//! private directory; never calls the game publisher or changes account settings.
use twichui_market_core::{bridge::Scope,client::{MarketClient,server_url},delivery::Configuration,workshop_summary,Error};
fn main()->Result<(),Box<dyn std::error::Error>> {
    let server=std::env::var("WORKSHOP_PROBE_SERVER")?;
    let client=MarketClient::new(&server,std::env::var("WORKSHOP_PROBE_TOKEN")?)?;
    let b=client.bootstrap()?;let market=b.resolve_market(Some(2)).ok_or("Market unavailable")?;
    let d=tempfile::tempdir()?;
    let c=Configuration{version:2,enabled:true,scope:Scope{server:server_url(&server)?.to_string(),account_id:b.account.id,market_id:market.id,algorithm:"twichui-pricing-v1".into()},installation:d.path().join("no-game-installation"),selection:serde_json::json!({"kind":"broad_summary","market_id":market.id,"region":market.region}),history_days:0};
    let deadline=std::time::Instant::now()+std::time::Duration::from_secs(480);let mut preparations=0;
    let (bundle,bytes,requests)=loop {match workshop_summary::download(d.path(),&client,&c,&||false) {
        Ok(result)=>break result,
        Err(Error::SummaryPreparing(delay)) if std::time::Instant::now()<deadline=>{preparations+=1;eprintln!("Workshop preparation response {preparations}");std::thread::sleep(std::time::Duration::from_secs(delay.clamp(1,5)));},
        Err(e)=>return Err(e.into()),
    }};
    let records=bundle.manifest["record_count"].as_u64().ok_or("Missing count")?;
    let mut report=serde_json::json!({"authenticated_https":server.starts_with("https://"),"native_summary_validation":true,"records":records,"download_bytes":bytes,"download_requests":requests,"preparation_responses":preparations,"game_publication":false,"physical_windows_acceptance":false,"synthetic":bundle.manifest["synthetic"],"generation":bundle.manifest["generation_id"]});
    // Collection may advance while downloading the sealed generation. Its next
    // preparation is a separate valid outcome, never failure of this download.
    match workshop_summary::download(d.path(),&client,&c,&||false) {
        Ok((warm,warm_bytes,warm_requests))=>{
            if warm.manifest!=bundle.manifest||warm_bytes!=0||warm_requests!=1{return Err("Unchanged generation acceptance failed".into())}
            report["warm_304"]=true.into();report["warm_bytes"]=warm_bytes.into();
        },
        Err(Error::SummaryPreparing(_))=>{report["warm_304"]=false.into();report["next_generation_preparing"]=true.into();},
        Err(e)=>return Err(e.into()),
    }
    println!("{report}");Ok(())
}
