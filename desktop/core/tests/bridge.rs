use chrono::Utc;
use serde_json::{json,Value};
use sha2::{Digest,Sha256};
use twichui_market_core::bridge::{self,BridgeCache,Scope};
fn fixture(name:&str)->Value{let root=std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../contracts/bridge/v1");bridge::parse(&std::fs::read(root.join(name)).unwrap(),bridge::MAX_BYTES).unwrap()}
fn scope()->Scope{Scope{server:"http://127.0.0.1:8899/".into(),account_id:1,market_id:2,algorithm:"twichui-pricing-v1".into()}}
fn envelope(g:&Value)->Vec<u8>{let mut h=g.clone();h.as_object_mut().unwrap().remove("records");serde_json::to_vec(&json!({"format":"twichui-market-bridge-manifest","contract_version":1,"transport_version":1,"account_id":1,"manifest":h,"cursor":"first"})).unwrap()}
fn page(g:&Value,offset:usize,end:usize)->Vec<u8>{let rows=g["records"].as_array().unwrap();let more=end<rows.len();serde_json::to_vec(&json!({"format":"twichui-market-bridge-page","contract_version":1,"transport_version":1,"account_id":1,"market_id":2,"generation_id":g["generation_id"],"offset":offset,"records":rows[offset..end],"has_more":more,"next_cursor":if more{Some("next")}else{None}})).unwrap()}
fn complete(c:&mut BridgeCache,s:&Scope,g:&Value){c.start(s,&envelope(g)).unwrap();c.apply(s,"first",&page(g,0,g["records"].as_array().unwrap().len()),Utc::now()).unwrap();}
fn seal(g:&mut Value){let mut body=g.clone();body.as_object_mut().unwrap().remove("generation_id");body.as_object_mut().unwrap().remove("integrity");let hash=|v:&Value|format!("{:x}",Sha256::digest(bridge::canonical(v).unwrap()));let records=body["records"].clone();let mut m=body.clone();m.as_object_mut().unwrap().remove("records");g["generation_id"]=hash(&body).into();g["integrity"]=json!({"records_bytes":bridge::canonical(&records).unwrap().len(),"records_sha256":hash(&records),"manifest_sha256":hash(&m)});}
#[test]
fn schema1_schema2_and_exact_unicode_encoding(){
 for name in ["canonical-generation.json","provisional-generation.json","source-canonical-generation.json","source-provisional-generation.json","fractional-close-generation.json","partial-unknown-generation.json"]{bridge::validate(&fixture(name)).unwrap();}
 let v=json!({"control":"\n\u{007f}","unicode":"é😀","money":"9223372036854775807"});
 assert_eq!(String::from_utf8(bridge::canonical(&v).unwrap()).unwrap(),"{\"control\":\"\\n\\u007f\",\"money\":\"9223372036854775807\",\"unicode\":\"\\u00e9\\ud83d\\ude00\"}");
 assert!(bridge::parse(br#"{"a":1,"a":2}"#,1024).is_err());assert!(bridge::parse(b"1.0",1024).is_err());assert!(bridge::parse(b"9007199254740992",1024).is_err());
}
#[test]
fn rejects_rehashed_semantic_corruption_and_unsupported_versions(){
 for mutation in 0..13{let mut g=fixture("source-canonical-generation.json");match mutation{
  0=>g["schema_version"]=3.into(),1=>g["contract_version"]=2.into(),2=>g["pricing_algorithm"]="future".into(),3=>g["history_basis"]="legacy-local".into(),4=>g["coverage"]["generation_complete"]=false.into(),5=>g["observations"][0]["synthetic"]=true.into(),6=>g["records"][1]["variant_key"]="a".repeat(64).into(),7=>g["records"][1]["daily"][0]["observation_ref"]=60.into(),8=>g["records"][0]["current"]["supply"]=1.into(),9=>g["records"][1]["current"]["metrics"]["historical_value_copper"]="100".into(),10=>g["records"][1]["distribution"]["tiers"][0]["quantity"]=999.into(),11=>g["record_count"]=1.into(),_=>g["observations"][0]["observed_at"]="2026-11-14t12:00:00Z".into()}
  if mutation==5{g["synthetic"]=false.into()};seal(&mut g);assert!(bridge::validate(&g).is_err(),"mutation {mutation}");}
}
#[test]
fn transactional_promotion_resume_rejection_and_previous(){
 let d=tempfile::tempdir().unwrap();let path=d.path().join("bridge.sqlite");let s=scope();let g=fixture("source-canonical-generation.json");let mut c=BridgeCache::open(&path).unwrap();complete(&mut c,&s,&g);let first=c.completed(&s).unwrap().unwrap();
 c.start(&s,&envelope(&g)).unwrap();assert!(c.apply(&s,"first",&page(&g,0,1),Utc::now()).unwrap());drop(c);
 let mut c=BridgeCache::open(&path).unwrap();let(_,cursor)=c.pending(&s).unwrap().unwrap();assert_eq!(cursor,"next");assert_eq!(c.completed(&s).unwrap().unwrap().0,g);
 let mut corrupt:Value=serde_json::from_slice(&page(&g,1,2)).unwrap();corrupt["records"][0]["current"]["metrics"]["quantity_weighted_ask_copper"]="121".into();
 assert!(c.apply(&s,"next",&serde_json::to_vec(&corrupt).unwrap(),Utc::now()).is_err());assert_eq!(c.completed(&s).unwrap().unwrap(),first);
 assert!(!c.apply(&s,"next",&page(&g,1,2),Utc::now()).unwrap());assert_eq!(c.previous(&s).unwrap().unwrap(),first);
 let mut other=s.clone();other.account_id=2;assert!(c.completed(&other).unwrap().is_none());assert!(c.start(&other,&envelope(&g)).is_err());other=s.clone();other.market_id=99;assert!(c.start(&other,&envelope(&g)).is_err());
 c.start(&s,&envelope(&g)).unwrap();let mut wrong:Value=serde_json::from_slice(&page(&g,0,1)).unwrap();wrong["offset"]=1.into();assert!(c.apply(&s,"first",&serde_json::to_vec(&wrong).unwrap(),Utc::now()).is_err());assert_eq!(c.pending(&s).unwrap().unwrap().1,"first");
}
#[test]
fn deterministic_assignment_only_lua_and_safe_staging(){
 let d=tempfile::tempdir().unwrap();let mut c=BridgeCache::memory().unwrap();let s=scope();let mut g=fixture("source-canonical-generation.json");
 let descriptor=String::from_utf8(bridge::canonical(&json!({"id":2589,"text":"\"; os.execute('bad')\n😀"})).unwrap()).unwrap();g["records"][1]["variant_json"]=descriptor.clone().into();g["records"][1]["variant_key"]=format!("{:x}",Sha256::digest(descriptor.as_bytes())).into();seal(&mut g);complete(&mut c,&s,&g);
 let p=bridge::export_staging(&c,&s,d.path()).unwrap();let bytes=std::fs::read(&p).unwrap();assert!(!String::from_utf8_lossy(&bytes).contains("os.execute"));assert_eq!(bridge::inspect_artifact(&bytes).unwrap().0,g);
 assert_eq!(std::fs::read(bridge::export_staging(&c,&s,d.path()).unwrap()).unwrap(),bytes);assert_eq!(std::fs::read(p.parent().unwrap().join("Previous.lua")).unwrap(),bytes);
 let mut bad=bytes.clone();bad.extend_from_slice(b"print('bad')");assert!(bridge::inspect_artifact(&bad).is_err());
 let unsafe_root=d.path().join("SavedVariables");std::fs::create_dir(&unsafe_root).unwrap();assert!(bridge::export_staging(&c,&s,&unsafe_root).is_err());
 let mut other=s.clone();other.account_id=2;assert!(c.start(&other,&envelope(&g)).is_err());assert!(bridge::export_staging(&c,&other,d.path()).is_err());assert_eq!(std::fs::read(p).unwrap(),bytes);
}
#[cfg(unix)]
#[test]
fn symlink_escape_and_ambiguous_permissions_refused(){
 use std::os::unix::{fs::symlink,fs::PermissionsExt};let d=tempfile::tempdir().unwrap();let c=BridgeCache::memory().unwrap();let link=d.path().join("linked");symlink(d.path(),&link).unwrap();assert!(bridge::export_staging(&c,&scope(),&link).is_err());std::fs::set_permissions(d.path(),std::fs::Permissions::from_mode(0o777)).unwrap();assert!(bridge::export_staging(&c,&scope(),d.path()).is_err());std::fs::set_permissions(d.path(),std::fs::Permissions::from_mode(0o700)).unwrap();
}
