//! Archive-free delivery on the existing worker; fixed owned publication banks.
use crate::{bridge::{self,Scope},client::MarketClient,delivery::{self,Configuration,Status},Error,Result};
use chrono::Utc;
use serde_json::{Value,json};
use sha2::{Digest,Sha256};
use std::{collections::BTreeMap,fs,path::{Path,PathBuf},sync::OnceLock};

pub const MAX_PART:usize=128*1024;
pub const MAX_TOTAL:usize=8*1024*1024;
pub const MAX_MANIFEST:usize=64*1024;
pub fn review_nonce()->Result<String> {let mut bytes=[0u8;32];getrandom::getrandom(&mut bytes).map_err(|_|Error::Invalid("Windows setup randomness unavailable"))?;Ok(bytes.iter().map(|b|format!("{b:02x}")).collect())}
const ROOT_PREFIX:&[u8]=b"TwichUIMarketData = { summary_version = 1, manifest = ";
const ROOT_MAX:usize=MAX_MANIFEST*4+16384;
const PART_MAX:usize=MAX_PART*4+256;
fn need(ok:bool,why:&'static str)->Result<()> {if ok{Ok(())}else{Err(Error::Invalid(why))}}
fn hex(v:&Value)->bool {v.as_str().is_some_and(|s|s.len()==64&&s.bytes().all(|c|c.is_ascii_digit()||(b'a'..=b'f').contains(&c)))}
fn number(v:&Value,max:u64)->Result<u64>{v.as_u64().filter(|n|*n<=max).ok_or(Error::Invalid("summary integer bound"))}
fn identifier(v:&Value)->Result<u64>{let s=v.as_str().ok_or(Error::Invalid("summary observation identity"))?;need(!s.is_empty()&&s.len()<=19&&!s.starts_with('0')&&s.bytes().all(|c|c.is_ascii_digit()),"summary observation identity")?;s.parse::<u64>().ok().filter(|n|*n<=i64::MAX as u64).ok_or(Error::Invalid("summary observation identity"))}
fn closed(v:&Value,keys:&[&str])->Result<()> {need(v.as_object().is_some_and(|m|m.len()==keys.len()&&keys.iter().all(|k|m.contains_key(*k))),"summary closed object")}
fn schema()->&'static Value {static S:OnceLock<Value>=OnceLock::new();S.get_or_init(||serde_json::from_str(include_str!("../../../contracts/workshop-summary/v1/manifest.schema.json")).expect("committed summary schema"))}
fn sha(raw:&[u8])->String {format!("{:x}",Sha256::digest(raw))}

pub fn validate_manifest(h:&Value,scope:&Scope,region:Option<&str>)->Result<()> {
    scope.key()?;
    let props=schema()["properties"].as_object().unwrap();
    let object=h.as_object().ok_or(Error::Invalid("summary manifest"))?;
    need(object.len()==props.len()&&object.keys().all(|k|props.contains_key(k)),"summary manifest fields")?;
    for (key,definition) in props {if let Some(constant)=definition.get("const"){need(h[key]==*constant,"summary protocol/capability")?;}}
    need(hex(&h["generation_id"])&&bridge::canonical(h)?.len()<=MAX_MANIFEST,"summary manifest bound")?;
    let mut signed=h.clone();signed.as_object_mut().unwrap().remove("generation_id");
    need(sha(&bridge::canonical(&signed)?)==h["generation_id"],"summary manifest digest")?;
    let issuer=h["issuer_id"].as_str().ok_or(Error::Invalid("summary issuer"))?;
    need(issuer.len()==36&&issuer.bytes().enumerate().all(|(i,b)|if [8,13,18,23].contains(&i){b==b'-'}else{b.is_ascii_digit()||(b'a'..=b'f').contains(&b)}),"summary issuer")?;
    let m=&h["market"];
    closed(m,&["game","region","player_ruleset","faction","house_id","source_kind","server_market_id","transport_ruleset_id","mapping_verified","mapping_evidence_sha256","realm_scope"])?;
    need(m["game"]=="wow-forever"&&m["mapping_verified"]==true&&hex(&m["mapping_evidence_sha256"])
        &&m["realm_scope"]=="ruleset_house"&&m["region"].as_str().is_some_and(|r|["us","eu","kr","tw"].contains(&r))
        &&m["player_ruleset"].as_str().is_some_and(|r|["Normal","PvP","Roleplay","Roleplay PvP"].contains(&r))
        &&m["faction"].as_str().is_some_and(|r|["Horde","Alliance","Blackwater"].contains(&r))
        &&m["source_kind"].as_str().is_some_and(|r|["auctions","commodities"].contains(&r)),"summary Forever market identity")?;
    for key in ["house_id","server_market_id","transport_ruleset_id"] {need(number(&m[key],i32::MAX as u64)?>0,"summary market identity")?;}
    need(m["server_market_id"]==scope.market_id&&h["pricing_algorithm"]==scope.algorithm
        &&region.is_none_or(|r|m["region"]==r),"summary selected market")?;
    let o=&h["source_observation"];
    closed(o,&["observation_id","observed_at","scope_complete"])?;
    need(o["scope_complete"]==true&&identifier(&o["observation_id"])?<=identifier(&h["source_watermark"])?
        &&h["synthetic"].is_boolean()&&h["generated_at"]==o["observed_at"],"summary source evidence")?;
    bridge::validation::time(&o["observed_at"])?;
    let count=number(&h["record_count"],150000)?;
    let coverage=&h["coverage"];
    closed(coverage,&["scope","complete","source_records","delivered_records","missing","detailed_history"])?;
    need(coverage["scope"]=="current_observed_exact_variants"&&coverage["complete"]==true
        &&coverage["source_records"]==count&&coverage["delivered_records"]==count
        &&coverage["missing"]=="unavailable"&&coverage["detailed_history"]=="not_delivered","summary coverage")?;
    need(h["partitioning"]==Value::Object(schema()["properties"]["partitioning"]["properties"].as_object().unwrap().iter().map(|(k,v)|(k.clone(),v["const"].clone())).collect()),"summary partition policy")?;
    let parts=h["partitions"].as_array().ok_or(Error::Invalid("summary partitions"))?;
    need(parts.len()<=64,"summary partition count")?;
    let(mut previous,mut rows,mut bytes)=(None,0,0);
    for p in parts {
        closed(p,&["bucket","bytes","record_count","sha256"])?;
        let bucket=number(&p["bucket"],63)?;
        need(previous.is_none_or(|n|n<bucket)&&hex(&p["sha256"]),"summary partition ordering/pin")?;
        let size=number(&p["bytes"],MAX_PART as u64)?;let n=number(&p["record_count"],150000)?;
        need(size>=2&&n>0,"summary partition bounds")?;previous=Some(bucket);rows+=n;bytes+=size;
    }
    need(rows==count&&bytes<=MAX_TOTAL as u64,"summary total coverage/bytes")
}

pub fn validate_part(h:&Value,p:&Value,raw:&[u8])->Result<()> {
    need(raw.len()<=MAX_PART&&p["bytes"]==raw.len()&&p["sha256"]==sha(raw),"summary partition integrity")?;
    let values=bridge::parse(raw,MAX_PART)?;
    need(bridge::canonical(&values)?==raw,"canonical summary partition")?;
    let rows=values.as_array().ok_or(Error::Invalid("summary rows"))?;
    need(p["record_count"]==rows.len(),"summary partition record count")?;
    let mut prior=None;
    for value in rows {
        let row=value.as_array().filter(|r|r.len()==13).ok_or(Error::Invalid("summary row shape"))?;
        let item=number(&row[0],i32::MAX as u64)?;
        need(item>0&&hex(&row[1])&&item%64==p["bucket"].as_u64().unwrap(),"summary exact identity/route")?;
        let key=(item,row[1].as_str().unwrap());need(prior.is_none_or(|k|k<key),"summary row ordering")?;prior=Some(key);
        let state=number(&row[2],4)?;let confidence=number(&row[8],1)?;
        need(row[7]==0,"summary observation age binding")?;
        for i in [3,4,5,9] {if !row[i].is_null() {
            let s=row[i].as_str().ok_or(Error::Invalid("summary exact copper"))?;
            need(!s.is_empty()&&s.len()<=11&&!s.starts_with('0')&&s.bytes().all(|b|b.is_ascii_digit())
                &&s.parse::<u64>().is_ok_and(|n|n<=99_999_999_999),"summary supported copper")?;
        }}
        let prices=[3,4,5,9].iter().any(|i|!row[*i].is_null());
        match state {
            0=>need(prices&&confidence==0&&number(&row[6],9_007_199_254_740_991)?>0,"summary priced evidence")?,
            1=>need(!prices&&confidence==1&&number(&row[6],9_007_199_254_740_991)?>0,"summary supply-only evidence")?,
            2=>need(!prices&&confidence==1&&row[6]==0,"summary observed absence")?,
            _=>need(!prices&&confidence==1&&row[6].is_null(),"summary unavailable evidence")?,
        }
        let a=number(&row[10],14)?;let b=number(&row[11],60)?;let c=number(&row[12],60)?;
        need(a<=b&&b<=c&&(!row[9].is_string()||b>=3)&&(!row[4].is_string()||a>0),"summary reference coverage")?;
    }
    let _=h;Ok(())
}

#[derive(Clone,Debug)]
pub struct Bundle {pub manifest:Value,pub parts:BTreeMap<u8,Vec<u8>>}
impl Bundle {
    pub fn validate(&self,scope:&Scope,region:Option<&str>)->Result<()> {
        validate_manifest(&self.manifest,scope,region)?;
        need(self.parts.len()==self.manifest["partitions"].as_array().unwrap().len(),"summary complete bundle")?;
        for p in self.manifest["partitions"].as_array().unwrap() {
            let raw=self.parts.get(&(p["bucket"].as_u64().unwrap() as u8)).ok_or(Error::Invalid("summary missing partition"))?;
            validate_part(&self.manifest,p,raw)?;
        }Ok(())
    }
}

fn cache_dir(base:&Path,scope:&Scope)->Result<PathBuf> {
    delivery::owned(base)?;let root=base.join(format!("workshop-summary-{}",scope.key()?));
    if !root.exists(){fs::create_dir(&root)?;}delivery::owned(&root)?;
    for bank in ["A","B"] {let p=root.join(bank);if !p.exists(){fs::create_dir(&p)?;}delivery::owned(&p)?;}
    Ok(root)
}
fn cache_state(root:&Path)->Result<Option<Value>> {
    let path=root.join("current.json");if !path.try_exists()?{return Ok(None)}
    let state=bridge::parse(&delivery::read(&path,MAX_MANIFEST+128)?,MAX_MANIFEST+128)?;
    closed(&state,&["bank","manifest"])?;need(state["bank"]=="A"||state["bank"]=="B","summary cache bank")?;Ok(Some(state))
}
fn cached_bundle(root:&Path,state:&Value,scope:&Scope,region:Option<&str>)->Result<Bundle> {
    let h=state["manifest"].clone();validate_manifest(&h,scope,region)?;
    let bank=state["bank"].as_str().ok_or(Error::Invalid("summary cache bank"))?;need(bank=="A"||bank=="B","summary cache bank")?;
    let mut parts=BTreeMap::new();
    for p in h["partitions"].as_array().unwrap() {
        let bucket=p["bucket"].as_u64().unwrap() as u8;
        let raw=delivery::read(&root.join(bank).join(format!("{bucket:02}.json")),MAX_PART)?;
        validate_part(&h,p,&raw)?;parts.insert(bucket,raw);
    }Ok(Bundle{manifest:h,parts})
}

/// Two fixed local slots retain the completed generation while interrupted
/// downloads resume from independently validated content in the inactive slot.
pub fn download(base:&Path,client:&MarketClient,c:&Configuration,cancelled:&impl Fn()->bool)->Result<(Bundle,u64,u32)> {
    let root=cache_dir(base,&c.scope)?;let state=cache_state(&root)?;
    let active=state.as_ref().map(|s|cached_bundle(&root,s,&c.scope,c.selection["region"].as_str())).transpose()?;
    if cancelled(){return Err(Error::Cancelled)}
    let endpoint=format!("api/v1/workshop/markets/{}/summary",c.scope.market_id);
    let etag=active.as_ref().and_then(|b|b.manifest["generation_id"].as_str());
    let Some(raw)=client.summary_request(&endpoint,etag,MAX_MANIFEST+128)? else {return Ok((active.ok_or(Error::Invalid("unbound summary 304"))?,0,1));};
    let envelope=bridge::parse(&raw,MAX_MANIFEST+128)?;closed(&envelope,&["account_id","manifest"])?;
    need(envelope["account_id"]==c.scope.account_id,"summary authenticated account")?;
    let manifest=envelope["manifest"].clone();validate_manifest(&manifest,&c.scope,c.selection["region"].as_str())?;
    if let Some(old)=&active {need(old.manifest["market"]==manifest["market"]&&old.manifest["issuer_id"]==manifest["issuer_id"],"summary source changed; reconnect Workshop")?;}
    let bank=if state.as_ref().is_some_and(|s|s["bank"]=="A"){"B"}else{"A"};
    let pending=json!({"bank":bank,"manifest":manifest});
    delivery::atomic(&root.join("pending.json"),&bridge::canonical(&pending)?)?;
    let mut bytes=raw.len() as u64;let mut requests=1;let mut parts=BTreeMap::new();
    for p in manifest["partitions"].as_array().unwrap() {
        if cancelled(){return Err(Error::Cancelled)}
        let bucket=p["bucket"].as_u64().unwrap() as u8;let target=root.join(bank).join(format!("{bucket:02}.json"));
        let resumed=if target.try_exists()? {let b=delivery::read(&target,MAX_PART)?;if validate_part(&manifest,p,&b).is_ok(){Some(b)}else{None}}else{None};
        let reused=active.as_ref().and_then(|b|b.parts.get(&bucket)).filter(|b|validate_part(&manifest,p,b).is_ok()).cloned();
        let raw=if let Some(raw)=resumed.or(reused){raw}else{
            let path=format!("{endpoint}/{}/parts/{bucket}",manifest["generation_id"].as_str().unwrap());
            let b=client.summary_request(&path,None,MAX_PART)?.ok_or(Error::Invalid("unbound summary part"))?;
            bytes+=b.len() as u64;requests+=1;b
        };
        validate_part(&manifest,p,&raw)?;delivery::atomic(&target,&raw)?;parts.insert(bucket,raw);
    }
    let bundle=Bundle{manifest,parts};bundle.validate(&c.scope,c.selection["region"].as_str())?;
    if cancelled(){return Err(Error::Cancelled)}
    if let Some(s)=state {delivery::atomic(&root.join("previous.json"),&bridge::canonical(&s)?)?;}
    delivery::atomic(&root.join("current.json"),&bridge::canonical(&pending)?)?;
    Ok((bundle,bytes,requests))
}

pub fn root_artifact(manifest:&Value,bank:&str,receipt:&Value)->Result<Vec<u8>> {
    need(bank=="A"||bank=="B","summary publication bank")?;
    let mut out=ROOT_PREFIX.to_vec();bridge::export::literal(&bridge::canonical(manifest)?,&mut out);
    out.extend_from_slice(b", bank = ");bridge::export::literal(bank.as_bytes(),&mut out);
    out.extend_from_slice(b", receipt = ");bridge::export::literal(&bridge::canonical(receipt)?,&mut out);out.extend_from_slice(b" }\n");Ok(out)
}
pub fn inspect_root(raw:&[u8],scope:&Scope,region:Option<&str>)->Result<(Value,String,Value)> {
    need(raw.len()<=ROOT_MAX&&raw.starts_with(ROOT_PREFIX),"summary root transport")?;let mut i=ROOT_PREFIX.len();
    let h=bridge::parse(&bridge::export::read_literal(raw,&mut i,MAX_MANIFEST)?,MAX_MANIFEST)?;
    need(raw.get(i..i+9)==Some(b", bank = "),"summary root bank")?;i+=9;
    let bank=bridge::export::read_literal(raw,&mut i,1)?;
    need(raw.get(i..i+12)==Some(b", receipt = "),"summary root receipt")?;i+=12;
    let receipt=bridge::parse(&bridge::export::read_literal(raw,&mut i,4096)?,4096)?;
    need(raw.get(i..)==Some(b" }\n")&&(bank==b"A"||bank==b"B"),"summary root syntax")?;
    validate_manifest(&h,scope,region)?;closed(&receipt,&["schema_version","generation_id","desktop_build","completed_at"])?;
    need(receipt["schema_version"]==1&&receipt["generation_id"]==h["generation_id"]&&receipt["desktop_build"].as_str().is_some_and(|s|!s.is_empty()&&s.len()<=80)
        &&bridge::validation::time(&receipt["completed_at"])? >= bridge::validation::time(&h["generated_at"])? ,"summary receipt")?;
    Ok((h,String::from_utf8(bank).unwrap(),receipt))
}
fn part_name(bank:&str,bucket:u8)->String {format!("TwichUI_MarketPart{bank}{bucket:02}")}
fn part_prefix(bank:&str,bucket:u8)->Vec<u8> {format!("TwichUIMarketParts = TwichUIMarketParts or {{}}\nTwichUIMarketParts[\"{bank}{bucket:02}\"] = ").into_bytes()}
pub fn part_artifact(bank:&str,bucket:u8,raw:&[u8])->Vec<u8>{let mut out=part_prefix(bank,bucket);bridge::export::literal(raw,&mut out);out.push(b'\n');out}
fn read_part_artifact(bank:&str,bucket:u8,bytes:&[u8])->Result<Vec<u8>> {
    let prefix=part_prefix(bank,bucket);need(bytes.starts_with(&prefix)&&bytes.len()<=PART_MAX,"summary part transport")?;
    let mut i=prefix.len();let raw=bridge::export::read_literal(bytes,&mut i,MAX_PART)?;need(bytes.get(i..)==Some(b"\n"),"summary part syntax")?;Ok(raw)
}
fn part_toc()->&'static [u8] {b"## Interface: 16001\n## Title: TwichUI Market Summary Part\n## Notes: Companion-generated bounded research data.\n## LoadOnDemand: 1\nData.lua\n"}
fn main_dir(c:&Configuration)->PathBuf {c.installation.join("Interface/AddOns/TwichUI_MarketData")}
fn identity(c:&Configuration)->Result<Value> {Ok(json!({"version":2,"server":c.scope.server,"account_id":c.scope.account_id,"installation":fs::canonicalize(&c.installation)?.to_string_lossy()}))}
fn installation_identity(path:&str)->String {
    #[cfg(windows)]{path.trim_start_matches(r"\\?\").replace('/',"\\").trim_end_matches('\\').to_lowercase()}
    #[cfg(not(windows))]{path.to_string()}
}
fn marker(c:&Configuration,folder:&Path)->Result<()> {
    let p=folder.join(".twichui-delivery.json");if p.try_exists()? {
        let old=bridge::parse(&delivery::read(&p,4096)?,4096)?;
        let actual=fs::canonicalize(&c.installation)?.to_string_lossy().into_owned();
        let original=old["installation"].as_str().ok_or(Error::Invalid("destination ownership path"))?;
        let relocated=c.selection["previous_installation"].as_str().is_some_and(|p|installation_identity(p)==installation_identity(original));
        need(installation_identity(original)==installation_identity(&actual)||relocated,"destination belongs to another installation")?;
        let mut expected=identity(c)?;expected["installation"]=old["installation"].clone();
        if old["version"]==1 {
            closed(&old,&["version","scope","installation","market","issuer_id"])?;
            need(old["scope"]==c.scope.key()?||c.selection.get("previous_scope").is_some_and(|v|*v==old["scope"]),"destination belongs to another account or market")?;
        } else {need(old==expected,"destination belongs to another account or origin")?;}
    }Ok(())
}
fn folder(folder:&Path,allowed:&[&str])->Result<()> {
    delivery::owned(folder)?;
    for entry in fs::read_dir(folder)? {let path=entry?.path();delivery::owned(&path)?;
        need(path.is_file()&&allowed.contains(&path.file_name().unwrap().to_string_lossy().as_ref()),"unknown files in Market addon; preserve them and review manually")?;
    }Ok(())
}
fn root_header(c:&Configuration,raw:&[u8])->Result<(Value,Option<String>)> {
    if raw.starts_with(ROOT_PREFIX) {
        let mut i=ROOT_PREFIX.len();let header=bridge::parse(&bridge::export::read_literal(raw,&mut i,MAX_MANIFEST)?,MAX_MANIFEST)?;
        let mut previous=c.scope.clone();previous.market_id=number(&header["market"]["server_market_id"],i32::MAX as u64)? as u32;
        let(h,bank,_)=inspect_root(raw,&previous,None)?;Ok((h,Some(bank)))
    } else {let(g,_)=bridge::inspect_artifact(raw)?;Ok((g,None))}
}
pub fn inspect_destination(c:&Configuration)->Result<Value> {
    crate::installation::validate(&c.installation)?;let dir=main_dir(c);let mut existing=None;
    if dir.try_exists()? {
        folder(&dir,&["TwichUI_MarketData.toc","Data.lua","Previous.lua",".twichui-delivery.json"])?;marker(c,&dir)?;
        let toc=dir.join("TwichUI_MarketData.toc");if toc.try_exists()? {need(delivery::known_toc(&delivery::read(&toc,1024)?),"incompatible Market data TOC")?;}
        let data=dir.join("Data.lua");if data.try_exists()? {existing=Some(root_header(c,&delivery::read(&data,3*1024*1024)?)?.0);}
        if !dir.join(".twichui-delivery.json").try_exists()? {need(fs::read_dir(&dir)?.next().is_none()||toc.is_file()&&data.is_file(),"unowned incomplete Market folder")?;}
    }
    Ok(json!({"installation":c.installation,"destination":dir,"existing_generation":existing.as_ref().map(|h|&h["generation_id"]),"requires_adoption":dir.join("Data.lua").is_file()&&!dir.join(".twichui-delivery.json").try_exists()?,"summary_delivery_version":1}))
}
fn verify_bank(c:&Configuration,h:&Value,bank:&str)->Result<()> {
    for p in h["partitions"].as_array().unwrap() {let b=p["bucket"].as_u64().unwrap() as u8;let name=part_name(bank,b);let dir=c.installation.join("Interface/AddOns").join(&name);
        folder(&dir,&[&format!("{name}.toc"),"Data.lua",".twichui-delivery.json"])?;
        need(dir.join(".twichui-delivery.json").is_file(),"unowned summary partition")?;marker(c,&dir)?;
        need(delivery::read(&dir.join(format!("{name}.toc")),1024)?==part_toc(),"summary part TOC")?;
        let raw=read_part_artifact(bank,b,&delivery::read(&dir.join("Data.lua"),PART_MAX)?)?;validate_part(h,p,&raw)?;
    }Ok(())
}
fn write_game(path:&Path,bytes:&[u8],cancelled:&impl Fn()->bool)->Result<()> {
    if cancelled(){return Err(Error::Cancelled)}
    need(!delivery::game_running()?,"Waiting for World of Warcraft to close.")?;
    if path.try_exists()?&&delivery::read(path,bytes.len()).is_ok_and(|old|old==bytes){return Ok(())}
    delivery::atomic(path,bytes)
}

pub fn publish(c:&Configuration,bundle:&Bundle,cancelled:&impl Fn()->bool)->Result<bool> {
    c.validate()?;need(c.enabled,"Workshop delivery is disconnected")?;bundle.validate(&c.scope,c.selection["region"].as_str())?;
    inspect_destination(c)?;
    let dir=main_dir(c);let target=dir.join("Data.lua");
    let old=if target.try_exists()?{Some(delivery::read(&target,3*1024*1024)?)}else{None};
    let current=old.as_ref().map(|raw|root_header(c,raw)).transpose()?;
    if let Some((h,_))=&current {
        need(h["issuer_id"]==bundle.manifest["issuer_id"],"installed summary issuer changed; review connection")?;
        if h["market"]["server_market_id"]==bundle.manifest["market"]["server_market_id"] {
            for field in ["game","region","house_id","source_kind","server_market_id","transport_ruleset_id","realm_scope"] {
                need(h["market"][field]==bundle.manifest["market"][field],"installed market identity changed; review connection")?;
            }
        }
    }
    if let Some((h,Some(bank)))=&current {verify_bank(c,h,bank)?;if h["generation_id"]==bundle.manifest["generation_id"] {
        let toc=dir.join("TwichUI_MarketData.toc");
        if !toc.try_exists()? || delivery::read(&toc,1024)?!=delivery::SUMMARY_TOC {write_game(&toc,delivery::SUMMARY_TOC,cancelled)?;return Ok(true);}
        return Ok(false);
    }}
    need(!delivery::game_running()?,"Waiting for World of Warcraft to close.")?;
    let bank=if current.as_ref().is_some_and(|(_,b)|b.as_deref()==Some("A")){"B"}else{"A"};
    let addons=c.installation.join("Interface/AddOns");
    // Preflight every intended child before any replacement. Unknown folders
    // are never silently adopted, deleted, or executed.
    for p in bundle.manifest["partitions"].as_array().unwrap() {
        let name=part_name(bank,p["bucket"].as_u64().unwrap() as u8);let part=addons.join(&name);
        if part.try_exists()? {folder(&part,&[&format!("{name}.toc"),"Data.lua",".twichui-delivery.json"])?;
            need(part.join(".twichui-delivery.json").is_file(),"unowned summary partition folder")?;marker(c,&part)?;}
    }
    let total=bundle.parts.values().map(Vec::len).sum::<usize>();
    need(delivery::free_space(&c.installation)?>=(32*1024*1024+8*total) as u64,"insufficient recoverable Workshop disk space")?;
    if !dir.exists(){fs::create_dir(&dir)?;}
    let owner=bridge::canonical(&identity(c)?)?;
    write_game(&dir.join(".twichui-delivery.json"),&owner,cancelled)?;
    for (&bucket,raw) in &bundle.parts {
        let name=part_name(bank,bucket);let part=addons.join(&name);if !part.exists(){fs::create_dir(&part)?;}
        write_game(&part.join(".twichui-delivery.json"),&owner,cancelled)?;
        let bytes=part_artifact(bank,bucket,raw);
        write_game(&part.join("Data.lua"),&bytes,cancelled)?;
        need(delivery::read(&part.join("Data.lua"),PART_MAX)?==bytes,"summary part readback")?;
        write_game(&part.join(format!("{name}.toc")),part_toc(),cancelled)?;
    }
    verify_bank(c,&bundle.manifest,bank)?;
    let receipt=json!({"schema_version":1,"generation_id":bundle.manifest["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)});
    let bytes=root_artifact(&bundle.manifest,bank,&receipt)?;inspect_root(&bytes,&c.scope,c.selection["region"].as_str())?;
    if let Some(raw)=&old {write_game(&dir.join("Previous.lua"),raw,cancelled)?;}
    write_game(&target,&bytes,cancelled)?;
    if delivery::read(&target,ROOT_MAX)?!=bytes {if let Some(raw)=&old{write_game(&target,raw,cancelled)?;}return Err(Error::Invalid("summary root readback; previous preserved"));}
    let toc=dir.join("TwichUI_MarketData.toc");if !toc.try_exists()? || delivery::read(&toc,1024)?!=delivery::SUMMARY_TOC {write_game(&toc,delivery::SUMMARY_TOC,cancelled)?;}
    Ok(true)
}

pub fn rollback(c:&Configuration)->Result<()> {
    crate::installation::validate(&c.installation)?;let dir=main_dir(c);
    folder(&dir,&["TwichUI_MarketData.toc","Data.lua","Previous.lua",".twichui-delivery.json"])?;marker(c,&dir)?;
    let raw=delivery::read(&dir.join("Previous.lua"),3*1024*1024)?;let(h,bank)=root_header(c,&raw)?;
    need(h["market"]["server_market_id"]==c.scope.market_id&&h["market"]["region"]==c.selection["region"],"Select the previous generation's market before restoring it")?;
    if let Some(bank)=bank {verify_bank(c,&h,&bank)?;}
    write_game(&dir.join("Data.lua"),&raw,&||false)?;
    let toc=if bank.is_some(){delivery::SUMMARY_TOC}else{delivery::TOC};
    write_game(&dir.join("TwichUI_MarketData.toc"),toc,&||false)?;
    need(delivery::read(&dir.join("Data.lua"),3*1024*1024)?==raw,"summary rollback readback")
}
pub fn restore_previous(base:&Path,c:&Configuration)->Result<Status> {
    need(!c.enabled,"Disconnect Workshop before restoring previous data")?;
    rollback(c)?;let(h,_)=root_header(c,&delivery::read(&main_dir(c).join("Data.lua"),3*1024*1024)?)?;
    let mut s=delivery::status_for(base,c)?;s.published_generation=h["generation_id"].as_str().map(str::to_owned);
    s.loaded_game_generation=None;s.result="Previous market data restored. Delivery is disconnected.".into();s.error=None;
    delivery::save_status(base,&c.scope,&s)?;Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{io::{Read,Write},net::TcpListener,sync::{Arc,Mutex},thread,time::{Duration,Instant}};
    fn fixture()->Bundle {
        let value:Value=serde_json::from_str(include_str!("../../../contracts/workshop-summary/v1/fixtures/synthetic.json")).unwrap();
        Bundle{manifest:value["manifest"].clone(),parts:value["parts"].as_object().unwrap().iter().map(|(k,v)|(k.parse().unwrap(),v.as_str().unwrap().as_bytes().to_vec())).collect()}
    }
    fn seal(b:&mut Bundle) {
        let mut total=0;let parts=b.parts.iter().map(|(&bucket,raw)|{let n:Value=serde_json::from_slice(raw).unwrap();let count=n.as_array().unwrap().len();total+=count;
            json!({"bucket":bucket,"bytes":raw.len(),"record_count":count,"sha256":sha(raw)})}).collect::<Vec<_>>();
        b.manifest["partitions"]=parts.into();b.manifest["record_count"]=total.into();
        b.manifest["coverage"]["source_records"]=total.into();b.manifest["coverage"]["delivered_records"]=total.into();
        reseal(&mut b.manifest);
    }
    fn reseal(h:&mut Value){h.as_object_mut().unwrap().remove("generation_id");h["generation_id"]=sha(&bridge::canonical(h).unwrap()).into();}
    #[cfg(unix)]
    use std::sync::atomic::{AtomicUsize,Ordering};
    fn config(base:&Path,b:&Bundle)->Configuration {Configuration{version:2,enabled:true,scope:Scope{server:"http://127.0.0.1:18888/".into(),account_id:1,market_id:b.manifest["market"]["server_market_id"].as_u64().unwrap() as u32,algorithm:"twichui-pricing-v1".into()},installation:base.join("Forever"),selection:json!({"kind":"broad_summary","market_id":b.manifest["market"]["server_market_id"],"region":b.manifest["market"]["region"]}),history_days:0}}
    fn alternate(b:&Bundle)->Bundle {let mut b=b.clone();let raw=b.parts.values_mut().next().unwrap();let mut rows:Value=serde_json::from_slice(raw).unwrap();rows[0][3]="121".into();*raw=bridge::canonical(&rows).unwrap();
        b.manifest["source_watermark"]="999999".into();b.manifest["source_observation"]["observation_id"]="999999".into();seal(&mut b);b}
    #[test]
    fn fixed_contract_values_identity_and_assignment_only_transport() {
        let b=fixture();let d=tempfile::tempdir().unwrap();let c=config(d.path(),&b);b.validate(&c.scope,Some("us")).unwrap();
        let rows:Value=serde_json::from_slice(b.parts.values().next().unwrap()).unwrap();
        assert_eq!(&rows[0].as_array().unwrap()[3..6],&[json!("120"),json!("100"),json!("120")]);
        let receipt=json!({"schema_version":1,"generation_id":b.manifest["generation_id"],"desktop_build":"synthetic-test","completed_at":"2026-11-17T12:00:00Z"});
        let root=root_artifact(&b.manifest,"A",&receipt).unwrap();assert_eq!(inspect_root(&root,&c.scope,Some("us")).unwrap().0,b.manifest);
        let mut malicious=root.clone();malicious.extend_from_slice(b"os.execute('never')");assert!(inspect_root(&malicious,&c.scope,Some("us")).is_err());
        assert!(inspect_root(&root,&Scope{account_id:2,..c.scope.clone()},Some("eu")).is_err());
        assert!(bridge::parse(br#"{"manifest":1,"manifest":2}"#,100).is_err());
        assert_ne!(review_nonce().unwrap(),review_nonce().unwrap());
    }
    #[test]
    fn rehashed_manifest_semantics_and_wrong_sources_are_refused() {
        let b=fixture();let d=tempfile::tempdir().unwrap();let c=config(d.path(),&b);
        for mutation in 0..13 {let mut h=b.manifest.clone();match mutation {
            0=>h["schema_version"]=2.into(),1=>h["can_satisfy_local_competition"]=true.into(),2=>h["market"]["region"]="eu".into(),
            3=>h["market"]["game"]="wow-retail".into(),4=>h["market"]["mapping_verified"]=false.into(),5=>h["coverage"]["complete"]=false.into(),
            6=>h["coverage"]["delivered_records"]=0.into(),7=>h["source_watermark"]="1".into(),8=>h["partitioning"]["max_total_bytes"]=999999999.into(),
            9=>h["partitions"][0]["bucket"]=64.into(),10=>h["partitions"][0]["bytes"]=(MAX_PART+1).into(),
            11=>h["market"]["unapproved_field"]="unknown".into(),_=>h["issuer_id"]="not-an-issuer".into()}
            reseal(&mut h);assert!(validate_manifest(&h,&c.scope,Some("us")).is_err(),"mutation {mutation}");
        }
    }
    #[test]
    fn rehashed_row_corruption_cannot_become_supported_evidence() {
        let b=fixture();let d=tempfile::tempdir().unwrap();let c=config(d.path(),&b);
        for mutation in 0..12 {let mut bad=b.clone();let raw=bad.parts.values_mut().next().unwrap();let mut rows:Value=serde_json::from_slice(raw).unwrap();
            match mutation {0=>rows[0][1]="a".repeat(63).into(),1=>rows[0][3]="100000000000".into(),2=>rows[0][4]="0".into(),3=>rows[0][5]=100.into(),
                4=>rows[0][6]=(-1).into(),5=>rows[0][7]=1.into(),6=>rows[0][8]=1.into(),7=>rows[0][9]="110".into(),8=>rows[0][10]=61.into(),
                9=>rows[0][2]=3.into(),10=>{let copy=rows[0].clone();rows.as_array_mut().unwrap().push(copy);},_=>rows[0][0]=1.into()}
            *raw=bridge::canonical(&rows).unwrap();seal(&mut bad);assert!(bad.validate(&c.scope,Some("us")).is_err(),"mutation {mutation}");
        }
    }
    #[cfg(unix)]
    fn installation(c:&Configuration) {
        let addon=c.installation.join("Interface/AddOns/TwichUI_Workshop");fs::create_dir_all(&addon).unwrap();
        let core=c.installation.join("Interface/AddOns/!!!TwichUI");fs::create_dir_all(&core).unwrap();fs::write(core.join("!!!TwichUI.toc"),b"## Interface: 16001\n").unwrap();
        fs::write(c.installation.join("Wow.exe"),b"TWICHUI SYNTHETIC FOREVER 1.60.1").unwrap();
        fs::write(addon.join("TwichUI_Workshop.toc"),b"## Interface: 16001\nSummary.lua\nBridge.lua\n").unwrap();
        for name in ["Summary.lua","Bridge.lua"]{fs::write(addon.join(name),b"-- Synthetic installed-file fixture only\n").unwrap();}
        fs::write(addon.join("MarketDelivery.json"),br#"{"format":"twichui-market-consumer","summary_delivery_version":1,"game":"wow-forever","interface":16001,"summary_partition_bytes":131072,"summary_total_bytes":8388608}"#).unwrap();
    }
    #[cfg(unix)]
    #[test]
    fn publication_banks_noop_partial_recovery_rollback_and_savedvariables() {
        let d=tempfile::tempdir().unwrap();let b=fixture();let mut c=config(d.path(),&b);installation(&c);
        let saved=c.installation.join("WTF/Account/Synthetic/SavedVariables");fs::create_dir_all(&saved).unwrap();fs::write(saved.join("TwichUI.lua"),b"synthetic player data remains byte-identical").unwrap();
        c.save_confirmed(d.path(),true).unwrap();assert!(publish(&c,&b,&||false).unwrap());
        let path=main_dir(&c).join("Data.lua");let before=fs::read(&path).unwrap();let modified=fs::metadata(&path).unwrap().modified().unwrap();
        assert!(!publish(&c,&b,&||false).unwrap());assert_eq!(fs::metadata(&path).unwrap().modified().unwrap(),modified);
        // Interrupted first activation resumes by writing only its missing TOC.
        fs::remove_file(main_dir(&c).join("TwichUI_MarketData.toc")).unwrap();assert!(publish(&c,&b,&||false).unwrap());assert_eq!(fs::read(&path).unwrap(),before);
        let next=alternate(&b);let calls=AtomicUsize::new(0);
        assert!(publish(&c,&next,&||calls.fetch_add(1,Ordering::SeqCst)>=3).is_err());assert_eq!(fs::read(&path).unwrap(),before);
        assert!(publish(&c,&next,&||false).unwrap());let(h,bank,_)=inspect_root(&fs::read(&path).unwrap(),&c.scope,Some("us")).unwrap();assert_eq!(bank,"B");assert_eq!(h,next.manifest);
        assert_eq!(fs::read(main_dir(&c).join("Previous.lua")).unwrap(),before);
        assert!(restore_previous(d.path(),&c).is_err());c.enabled=false;c.save_confirmed(d.path(),false).unwrap();let status=restore_previous(d.path(),&c).unwrap();assert!(status.loaded_game_generation.is_none());assert_eq!(fs::read(path).unwrap(),before);
        assert_eq!(fs::read(saved.join("TwichUI.lua")).unwrap(),b"synthetic player data remains byte-identical");assert!(!d.path().join("history-archive-v1.sqlite").exists());
    }
    #[cfg(unix)]
    #[test]
    fn discovery_and_destination_security_refuse_other_accounts_links_and_unknown_files() {
        use std::os::unix::fs::symlink;
        let d=tempfile::tempdir().unwrap();let b=fixture();let c=config(d.path(),&b);installation(&c);
        assert_eq!(crate::installation::candidates(None,vec![c.installation.clone(),c.installation.clone()]),vec![c.installation.clone()]);
        let moved=d.path().join("Moved");fs::rename(&c.installation,&moved).unwrap();assert_eq!(crate::installation::candidates(Some(&c.installation),vec![moved.clone()]),vec![moved.clone()]);fs::rename(&moved,&c.installation).unwrap();
        let other=d.path().join("Other");fs::create_dir_all(other.join("Interface/AddOns")).unwrap();fs::write(other.join("Wow.exe"),b"not Forever").unwrap();assert!(crate::installation::candidates(None,vec![other]).is_empty());
        publish(&c,&b,&||false).unwrap();let before=fs::read(main_dir(&c).join("Data.lua")).unwrap();
        let mut wrong=c.clone();wrong.scope.account_id=2;assert!(publish(&wrong,&b,&||false).is_err());
        let linked=d.path().join("Link");symlink(&c.installation,&linked).unwrap();wrong=c.clone();wrong.installation=linked;assert!(inspect_destination(&wrong).is_err());
        let next=alternate(&b);let p=next.manifest["partitions"][0]["bucket"].as_u64().unwrap() as u8;
        let unowned=c.installation.join("Interface/AddOns").join(part_name("B",p));fs::create_dir(&unowned).unwrap();fs::write(unowned.join("unrelated.lua"),b"unrelated").unwrap();assert!(publish(&c,&next,&||false).is_err());
        assert_eq!(fs::read(main_dir(&c).join("Data.lua")).unwrap(),before);
    }
    #[cfg(unix)]
    #[test]
    fn moved_owned_installation_requires_new_confirmation_and_retains_bank_ownership() {
        let d=tempfile::tempdir().unwrap();let b=fixture();let c=config(d.path(),&b);installation(&c);publish(&c,&b,&||false).unwrap();
        let moved=d.path().join("Moved-Forever");fs::rename(&c.installation,&moved).unwrap();let mut relocated=c.clone();relocated.installation=moved;
        assert!(inspect_destination(&relocated).is_err());
        relocated.selection["previous_installation"]=c.installation.to_string_lossy().into_owned().into();
        assert!(relocated.save_confirmed(d.path(),false).is_err());relocated.save_confirmed(d.path(),true).unwrap();
        assert!(publish(&relocated,&alternate(&b),&||false).unwrap());
        let other=d.path().join("Second-Forever");let mut second=relocated.clone();second.installation=other.clone();installation(&second);
        assert_eq!(crate::installation::candidates(None,vec![relocated.installation.clone(),other.clone()]).len(),2);
        assert_eq!(crate::installation::candidates(Some(&relocated.installation),vec![other]),vec![relocated.installation]);
    }
    #[cfg(unix)]
    #[test]
    fn existing_account_market_choice_retargets_without_reauthorizing_another_account() {
        let d=tempfile::tempdir().unwrap();let b=fixture();let c=config(d.path(),&b);installation(&c);c.save_confirmed(d.path(),true).unwrap();publish(&c,&b,&||false).unwrap();
        let original=fs::read(main_dir(&c).join("Data.lua")).unwrap();let new_id=c.scope.market_id+1;
        let mut next=alternate(&b);next.manifest["market"]["server_market_id"]=new_id.into();next.manifest["market"]["house_id"]=115.into();next.manifest["market"]["region"]="eu".into();seal(&mut next);
        let selected=c.follow_selected_market(d.path(),new_id,"eu").unwrap();
        let mut corrupt=next.clone();corrupt.parts.values_mut().next().unwrap().push(b' ');assert!(publish(&selected,&corrupt,&||false).is_err());assert_eq!(fs::read(main_dir(&c).join("Data.lua")).unwrap(),original);
        assert!(publish(&selected,&next,&||false).unwrap());assert!(rollback(&selected).is_err());
        let mut wrong=selected.clone();wrong.scope.account_id+=1;assert!(wrong.follow_selected_market(d.path(),new_id,"eu").is_err());assert!(publish(&wrong,&next,&||false).is_err());
        let mut original_market=selected.follow_selected_market(d.path(),c.scope.market_id,"us").unwrap();original_market.enabled=false;original_market.save_confirmed(d.path(),false).unwrap();restore_previous(d.path(),&original_market).unwrap();assert_eq!(fs::read(main_dir(&c).join("Data.lua")).unwrap(),original);
    }
    fn serve(responses:Vec<(u16,Vec<u8>,bool)>)->(String,thread::JoinHandle<()>,Arc<Mutex<Vec<String>>>) {
        let listener=TcpListener::bind("127.0.0.1:0").unwrap();let origin=format!("http://{}/",listener.local_addr().unwrap());let requests=Arc::new(Mutex::new(Vec::new()));let seen=requests.clone();
        let task=thread::spawn(move||{listener.set_nonblocking(true).unwrap();for(status,body,truncated) in responses {
            let deadline=Instant::now()+Duration::from_secs(10);let(mut stream,_)=loop {match listener.accept(){Ok(v)=>break v,Err(e) if e.kind()==std::io::ErrorKind::WouldBlock&&Instant::now()<deadline=>thread::sleep(Duration::from_millis(5)),Err(e)=>panic!("missing summary test request: {e}")}};
            stream.set_nonblocking(false).unwrap();stream.set_read_timeout(Some(Duration::from_secs(5))).unwrap();let mut request=Vec::new();while !request.ends_with(b"\r\n\r\n") {let mut byte=[0];assert_eq!(stream.read(&mut byte).unwrap(),1);request.push(byte[0]);assert!(request.len()<8192);}
            let request=String::from_utf8(request).unwrap();assert!(request.to_lowercase().contains("authorization: bearer synthetic-workshop-connection"));seen.lock().unwrap().push(request);
            write!(stream,"HTTP/1.1 {status} Test\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",body.len()+if truncated{100}else{0}).unwrap();stream.write_all(&body).unwrap();
        }});(origin,task,requests)
    }
    fn envelope(b:&Bundle,account:u32)->Vec<u8>{serde_json::to_vec(&json!({"account_id":account,"manifest":b.manifest})).unwrap()}
    #[test]
    fn partial_download_restart_content_reuse_304_and_no_history_archive() {
        let d=tempfile::tempdir().unwrap();let mut b=fixture();let raw=b.parts.values().next().unwrap();let mut row:Value=serde_json::from_slice::<Value>(raw).unwrap()[0].clone();row[0]=2590.into();row[1]="b".repeat(64).into();b.parts.insert(30,bridge::canonical(&json!([row])).unwrap());seal(&mut b);
        let values=b.parts.values().cloned().collect::<Vec<_>>();let responses=vec![(200,envelope(&b,1),false),(200,values[0].clone(),false),(503,b"{}".to_vec(),false),(200,envelope(&b,1),false),(200,values[1].clone(),false),(304,vec![],false)];
        let(origin,task,requests)=serve(responses);let mut c=config(d.path(),&b);c.scope.server=origin;let client=MarketClient::new(&c.scope.server,"synthetic-workshop-connection".into()).unwrap();
        assert!(download(d.path(),&client,&c,&||false).is_err());let(bundle,_,count)=download(d.path(),&client,&c,&||false).unwrap();assert_eq!(count,2);assert_eq!(bundle.manifest,b.manifest);
        let(_,bytes,count)=download(d.path(),&client,&c,&||false).unwrap();assert_eq!((bytes,count),(0,1));task.join().unwrap();let seen=requests.lock().unwrap();assert_eq!(seen.len(),6);assert!(seen.last().unwrap().to_lowercase().contains("if-none-match:"));assert!(!d.path().join("history-archive-v1.sqlite").exists());
    }
    #[test]
    fn wrong_account_and_truncated_metadata_never_replace_a_completed_cache() {
        let d=tempfile::tempdir().unwrap();let b=fixture();let mut responses=vec![(200,envelope(&b,1),false)];responses.extend(b.parts.values().map(|v|(200,v.clone(),false)));responses.extend([(200,envelope(&b,2),false),(200,envelope(&b,1),true)]);
        let(origin,task,_)=serve(responses);let mut c=config(d.path(),&b);c.scope.server=origin;let client=MarketClient::new(&c.scope.server,"synthetic-workshop-connection".into()).unwrap();download(d.path(),&client,&c,&||false).unwrap();
        let root=cache_dir(d.path(),&c.scope).unwrap();let before=fs::read(root.join("current.json")).unwrap();assert!(download(d.path(),&client,&c,&||false).is_err());assert!(download(d.path(),&client,&c,&||false).is_err());assert_eq!(fs::read(root.join("current.json")).unwrap(),before);task.join().unwrap();
    }
}
pub fn synchronize(base:&Path,client:&MarketClient,c:&Configuration,cancelled:impl Fn()->bool)->Result<Status> {
    let mut s=delivery::status_for(base,c)?;s.installation=Some(c.installation.clone());
    s.last_attempt=Some(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs,true));s.loaded_game_generation=None;
    let result=(||->Result<()> {
        let(bundle,bytes,requests)=download(base,client,c,&cancelled)?;
        s.validated_generation=bundle.manifest["generation_id"].as_str().map(str::to_owned);
        s.canonical_bytes=Some(bundle.parts.values().map(|r|r.len() as u64).sum());s.archive_checkpoint=None;
        s.download_bytes=Some(bytes);s.download_requests=Some(requests);s.summary_records=bundle.manifest["record_count"].as_u64();
        let live=Configuration::load(base)?.ok_or(Error::Cancelled)?;
        need(live.enabled&&live.version==2&&live.scope==c.scope&&live.installation==c.installation&&live.selection==c.selection,"Workshop connection changed; previous files preserved")?;
        let changed=publish(c,&bundle,&cancelled)?;
        s.published_generation=s.validated_generation.clone();s.error=None;
        if changed {s.last_successful_write=Some(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs,true));}
        s.result=if changed{"Market data updated. Available on your next game login or reload."}else{"Up to date."}.into();Ok(())
    })();
    if let Err(error)=result {
        s.result=if matches!(&error,Error::SummaryPreparing(_)){"Preparing market data."}else if matches!(&error,Error::Invalid("Waiting for World of Warcraft to close.")){"Waiting for World of Warcraft to close."}else{"Update failed. Your previous market data is safe."}.into();
        s.error=Some(error.to_string());delivery::save_status(base,&c.scope,&s)?;return Err(error);
    }
    delivery::save_status(base,&c.scope,&s)?;Ok(s)
}
