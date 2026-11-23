//! Diagnostic only: reproduce the fixture's HTTP/1 idle-boundary pool race.
//! Same reqwest constructor policy as MarketClient; no production credentials.
use std::time::{Duration,Instant};
use serde_json::json;
fn main()->Result<(),Box<dyn std::error::Error>> {
    let args=std::env::args().skip(1).collect::<Vec<_>>();
    if args.len()!=3 || !args[0].starts_with("http://127.0.0.1:") {return Err("loopback-origin cycles delay-ms".into());}
    let cycles:usize=args[1].parse()?;let delay:u64=args[2].parse()?;
    if cycles>1000 || !(10..=5000).contains(&delay){return Err("diagnostic bound".into());}
    let http=reqwest::blocking::Client::builder().redirect(reqwest::redirect::Policy::none()).no_proxy()
        .connect_timeout(Duration::from_secs(10)).timeout(Duration::from_secs(30)).build()?;
    for cycle in 0..cycles {
        let at=Instant::now();
        let response=match http.get(format!("{}/bootstrap",args[0])).send(){Ok(v)=>v,Err(e)=>{
            println!("{}",json!({"ok":false,"cycle":cycle,"stage":"next-bootstrap","stage_us":at.elapsed().as_micros(),"error":format!("{e:?}")}));return Ok(())
        }};
        if response.status()!=200{return Err("probe bootstrap status".into());}response.bytes()?;
        let response=http.get(format!("{}/summary",args[0])).send()?;
        if response.status()!=202{return Err("probe preparation status".into());}
        // Establish the eligible pooled state observed in the real failure's
        // completed 202 response (the frozen client can receive it in-buffer).
        response.bytes()?;std::thread::sleep(Duration::from_millis(delay));
    }
    println!("{}",json!({"ok":true,"cycles":cycles}));Ok(())
}
