use crate::{Error,Result};
use chrono::{DateTime,NaiveDate,Utc};
use serde::de::{self,Deserialize,Deserializer,MapAccess,SeqAccess,Visitor};
use serde_json::{Map,Value};
use sha2::{Digest,Sha256};
use std::{collections::HashSet,fmt,sync::OnceLock};
pub const MAX_BYTES:usize=32*1024*1024;
pub const MAX_RECORD_BYTES:usize=64*1024;
const SAFE:u64=9_007_199_254_740_991;
fn bad<T>() -> Result<T>{Err(Error::Invalid("bridge schema, identity or integrity"))}
struct Strict(Value);
impl<'de> Deserialize<'de> for Strict {
 fn deserialize<D:Deserializer<'de>>(d:D)->std::result::Result<Self,D::Error>{
  struct V;
  impl<'de> Visitor<'de> for V {
   type Value=Strict;
   fn expecting(&self,f:&mut fmt::Formatter)->fmt::Result{f.write_str("bounded exact JSON without duplicate keys")}
   fn visit_bool<E:de::Error>(self,v:bool)->std::result::Result<Strict,E>{Ok(Strict(v.into()))}
   fn visit_unit<E:de::Error>(self)->std::result::Result<Strict,E>{Ok(Strict(Value::Null))}
   fn visit_i64<E:de::Error>(self,v:i64)->std::result::Result<Strict,E>{if v.unsigned_abs()>SAFE{return Err(E::custom("integer range"))}Ok(Strict(v.into()))}
   fn visit_u64<E:de::Error>(self,v:u64)->std::result::Result<Strict,E>{if v>SAFE{return Err(E::custom("integer range"))}Ok(Strict(v.into()))}
   fn visit_f64<E:de::Error>(self,_:f64)->std::result::Result<Strict,E>{Err(E::custom("floating point"))}
   fn visit_str<E:de::Error>(self,v:&str)->std::result::Result<Strict,E>{Ok(Strict(v.into()))}
   fn visit_string<E:de::Error>(self,v:String)->std::result::Result<Strict,E>{Ok(Strict(v.into()))}
   fn visit_seq<A:SeqAccess<'de>>(self,mut a:A)->std::result::Result<Strict,A::Error>{let mut v=Vec::new();while let Some(x)=a.next_element::<Strict>()?{v.push(x.0)}Ok(Strict(v.into()))}
   fn visit_map<A:MapAccess<'de>>(self,mut a:A)->std::result::Result<Strict,A::Error>{let mut v=Map::new();while let Some((k,x))=a.next_entry::<String,Strict>()?{if v.insert(k,x.0).is_some(){return Err(de::Error::custom("duplicate key"))}}Ok(Strict(v.into()))}
  }
  d.deserialize_any(V)
 }
}
pub fn parse(raw:&[u8],maximum:usize)->Result<Value>{
 let _parse=crate::performance::measure(crate::performance::Stage::JsonParse);
 if raw.len()>maximum{return bad()}
 let mut d=serde_json::Deserializer::from_slice(raw);let v=Strict::deserialize(&mut d)?.0;d.end()?;
 canonical(&v)?;Ok(v)
}
fn quoted(s:&str,out:&mut String){
 out.push('"');for c in s.chars(){match c {'"'=>out.push_str("\\\""),'\\'=>out.push_str("\\\\"),'\x08'=>out.push_str("\\b"),'\x0c'=>out.push_str("\\f"),'\n'=>out.push_str("\\n"),'\r'=>out.push_str("\\r"),'\t'=>out.push_str("\\t"),c if (' '..='~').contains(&c)=>out.push(c),c=>{use std::fmt::Write;let n=c as u32;if n<=0xffff{write!(out,"\\u{n:04x}").unwrap()}else{let n=n-0x10000;write!(out,"\\u{:04x}\\u{:04x}",0xd800+(n>>10),0xdc00+(n&1023)).unwrap()}}}}out.push('"');
}
pub fn canonical(v:&Value)->Result<Vec<u8>>{
 fn emit(v:&Value,out:&mut String,depth:usize)->Result<()>{if depth>12{return bad()}match v{
  Value::Null=>out.push_str("null"),Value::Bool(b)=>out.push_str(if *b{"true"}else{"false"}),
  Value::Number(n)=>{if !(n.is_i64()||n.is_u64())||n.as_i64().map(|n|n.unsigned_abs()>SAFE).unwrap_or_else(||n.as_u64().unwrap_or(u64::MAX)>SAFE){return bad()}out.push_str(&n.to_string())},
  Value::String(s)=>quoted(s,out),Value::Array(a)=>{out.push('[');for(i,x)in a.iter().enumerate(){if i>0{out.push(',')}emit(x,out,depth+1)?}out.push(']')},
  Value::Object(m)=>{out.push('{');let mut keys=m.keys().collect::<Vec<_>>();keys.sort();for(i,k)in keys.iter().enumerate(){if i>0{out.push(',')}quoted(k,out);out.push(':');emit(&m[*k],out,depth+1)?}out.push('}')}
 }Ok(())}let mut out=String::new();emit(v,&mut out,0)?;Ok(out.into_bytes())
}
pub(crate) fn hash(v:&Value)->Result<String>{let _hash=crate::performance::measure(crate::performance::Stage::HashVerification);Ok(format!("{:x}",Sha256::digest(canonical(v)?)))}
fn integer(v:&Value)->Option<u64>{v.as_u64().filter(|n|*n<=SAFE)}
fn money(v:&Value,positive:bool)->bool{v.as_str().is_some_and(|s|!s.is_empty()&&s.len()<=19&&s.bytes().all(|c|c.is_ascii_digit())&&(s=="0"||!s.starts_with('0'))&&s.parse::<u64>().is_ok_and(|n|n<=i64::MAX as u64&&(!positive||n>0)))}
fn hex(s:&str)->bool{s.len()==64&&s.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))}
pub(crate) fn time(v:&Value)->Result<DateTime<Utc>>{let s=v.as_str().ok_or(Error::Invalid("bridge timestamp"))?;if !s.ends_with('Z')||s.get(10..11)!=Some("T")||s.get(17..19).and_then(|s|s.parse::<u8>().ok()).is_none_or(|n|n>=60){return bad()}DateTime::parse_from_rfc3339(s).map(|d|d.with_timezone(&Utc)).map_err(|_|Error::Invalid("bridge timestamp"))}
fn date(v:&Value)->Result<NaiveDate>{NaiveDate::parse_from_str(v.as_str().unwrap_or(""),"%Y-%m-%d").map_err(|_|Error::Invalid("bridge UTC day"))}
fn pattern(p:&str,s:&str)->bool{
 match p {
  "^[0-9a-f]{64}$"=>hex(s),"^(0|[1-9][0-9]{0,18})$"=>money(&Value::String(s.into()),false),"^[1-9][0-9]{0,18}$"=>money(&Value::String(s.into()),true),
  "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"=>s.len()==10&&date(&s.into()).is_ok(),
  p if p.contains("T[0-9]")=>{let fraction=s.split_once('.').map(|(_,s)|s.trim_end_matches('Z'));s.len()>=20&&time(&s.into()).is_ok()&&fraction.is_none_or(|f|!p.contains("\\\\.")&&!f.is_empty()&&f.len()<=6&&f.bytes().all(|b|b.is_ascii_digit()))},_=>false
 }
}
pub(crate) fn schema_check(s:&Value,v:&Value)->Result<()>{
 if let Some(t)=s.get("type") {let types=t.as_array().map(|a|a.iter().collect::<Vec<_>>()).unwrap_or_else(||vec![t]);if !types.iter().any(|t|match t.as_str(){Some("null")=>v.is_null(),Some("object")=>v.is_object(),Some("array")=>v.is_array(),Some("string")=>v.is_string(),Some("boolean")=>v.is_boolean(),Some("integer")=>v.is_i64()||v.is_u64(),_=>false}){return bad()}}
 if s.get("const").is_some_and(|x|x!=v)||s.get("enum").and_then(Value::as_array).is_some_and(|a|!a.contains(v)){return bad()}
 if let Some(a)=s.get("anyOf").and_then(Value::as_array){if !a.iter().any(|s|schema_check(s,v).is_ok()){return bad()}}
 if let Some(a)=s.get("allOf").and_then(Value::as_array){for s in a{schema_check(s,v)?}}
 if let Some(condition)=s.get("if"){if schema_check(condition,v).is_ok(){if let Some(s)=s.get("then"){schema_check(s,v)?}}else if let Some(s)=s.get("else"){schema_check(s,v)?}}
 if let Some(m)=v.as_object(){
  if let Some(r)=s.get("required").and_then(Value::as_array){if r.iter().any(|k|!m.contains_key(k.as_str().unwrap_or(""))){return bad()}}
  if let Some(p)=s.get("properties").and_then(Value::as_object){for(k,v)in m{if let Some(s)=p.get(k){schema_check(s,v)?}else if s["additionalProperties"]==false{return bad()}}}
 }
 if let Some(a)=v.as_array(){if integer(&s["minItems"]).is_some_and(|n|a.len()<(n as usize))||integer(&s["maxItems"]).is_some_and(|n|a.len()>(n as usize)){return bad()}if s["uniqueItems"]==true{let mut seen=HashSet::new();for x in a{if !seen.insert(canonical(x)?){return bad()}}}if let Some(s)=s.get("items"){for x in a{schema_check(s,x)?}}}
 if let Some(t)=v.as_str(){let n=t.chars().count();if integer(&s["minLength"]).is_some_and(|x|n<(x as usize))||integer(&s["maxLength"]).is_some_and(|x|n>(x as usize)){return bad()}if let Some(p)=s["pattern"].as_str(){if !pattern(p,t){return bad()}}if let Some(f)=s["format"].as_str(){let valid=match f{"copper-i64"=>money(v,false),"positive-i64"=>money(v,true),"date"=>date(v).is_ok(),"date-time"=>time(v).is_ok(),"uuid"=>t.len()==36&&t.bytes().enumerate().all(|(i,b)|if [8,13,18,23].contains(&i){b==b'-'}else{b.is_ascii_hexdigit()}),_=>false};if !valid{return bad()}}}
 if v.is_number(){let n=v.as_i64().ok_or(Error::Invalid("bridge integer"))?;if s["minimum"].as_i64().is_some_and(|min|n<min)||s["maximum"].as_i64().is_some_and(|max|n>max){return bad()}}
 Ok(())
}
fn schema(version:u64)->Result<&'static Value>{static ONE:OnceLock<Value>=OnceLock::new();static TWO:OnceLock<Value>=OnceLock::new();match version{1=>Ok(ONE.get_or_init(||serde_json::from_str(include_str!("../../../../contracts/bridge/v1/generation.schema.json")).unwrap())),2=>Ok(TWO.get_or_init(||serde_json::from_str(include_str!("../../../../contracts/bridge/v1/generation-schema2.schema.json")).unwrap())),_=>bad()}}
fn body(g:&Value)->Value{let mut b=g.clone();b.as_object_mut().unwrap().remove("generation_id");b.as_object_mut().unwrap().remove("integrity");b}
fn manifest(g:&Value)->Value{let mut b=body(g);b.as_object_mut().unwrap().remove("records");b}
pub fn validate_header(header:&Value)->Result<()>{let mut g=header.clone();if g.get("records").is_some(){return bad()}g.as_object_mut().ok_or(Error::Invalid("bridge manifest"))?.insert("records".into(),Value::Array(vec![]));schema_check(schema(integer(&g["schema_version"]).unwrap_or(0))?,&g)?;if canonical(header)?.len()>MAX_RECORD_BYTES||canonical(&manifest(&g))?.len()>MAX_RECORD_BYTES{return bad()}
 if header["coverage"]["generation_complete"]!=true||header["integrity"]["manifest_sha256"]!=hash(&manifest(&g))?{return bad()}
 let at=time(&g["generated_at"])?;if !g["desktop_sync_completed_at"].is_null()&&time(&g["desktop_sync_completed_at"])? >at{return bad()}if !g["server_checked_at"].is_null()&&time(&g["server_checked_at"])? >at{return bad()}
 if date(&g["as_of_utc_day"])? >at.date_naive(){return bad()}
 let cov=&g["coverage"];if date(&cov["history_from_day"])? >date(&cov["history_through_day"])?||date(&cov["history_through_day"])? >date(&g["as_of_utc_day"])?||!(0..60).contains(&(date(&g["as_of_utc_day"])?-date(&cov["history_from_day"])?).num_days()){return bad()}
 if cov["delivered_observed_days"].as_u64()>cov["available_observed_days"].as_u64()||cov["history_complete"]==true&&(cov["history_truncated"]==true||cov["delivered_observed_days"]!=cov["available_observed_days"]){return bad()}
 if cov["history_truncated"]==true&&!cov["omitted_sections"].as_array().unwrap().contains(&Value::String("older_daily_history".into())){return bad()}
 if (g["market"]["source_kind"]=="auctions")!=(cov["scope"]=="house_auctions"){return bad()}
 if g["market"]["mapping_verified"]==true&&(g["market"]["player_ruleset"].is_null()||g["market"]["mapping_evidence_sha256"].is_null()){return bad()}
 let observations=g["observations"].as_array().unwrap();let mut ids=HashSet::new();let mut delivered=HashSet::new();let mut latest=None;
 for(i,o)in observations.iter().enumerate(){let id=o["observation_id"].as_str().unwrap().parse::<u64>().unwrap();let t=time(&o["observed_at"])?;if !ids.insert(id)||id>g["watermark_observation_id"].as_str().unwrap().parse::<u64>().unwrap()||t>at||t.date_naive()!=date(&o["utc_day"])?||o["synthetic"]==true&&g["synthetic"]!=true{return bad()}if !o["upstream_updated_at"].is_null()&&time(&o["upstream_updated_at"])? >at{return bad()}let day=o["utc_day"].as_str().unwrap();if day>=cov["history_from_day"].as_str().unwrap()&&day<=cov["history_through_day"].as_str().unwrap(){delivered.insert(day);}let k=(t,id,i);if latest.is_none_or(|old|k>old){latest=Some(k)}}
 if delivered.len() as u64!=cov["delivered_observed_days"].as_u64().unwrap(){return bad()}
 if let Some(index)=g["current_observation_ref"].as_u64(){let o=observations.get(index as usize).ok_or(Error::Invalid("bridge reference"))?;if latest.map(|x|x.2)!=Some(index as usize)||o["scope_complete"]!=cov["current_complete"]{return bad()}}else if g["record_count"]!=0{return bad()}
 Ok(())
}
fn observation<'a>(g:&'a Value,r:&Value)->Result<&'a Value>{g["observations"].as_array().and_then(|a|r.as_u64().and_then(|i|a.get(i as usize))).ok_or(Error::Invalid("bridge observation reference"))}
fn counts(x:&Value,prices:&[&Value],source:&Value,canonical_model:bool)->Result<()>{
 let state=x["state"].as_str().unwrap();let count_fields=["supply","priced_supply","listing_count"];
 if state=="unknown" {if count_fields.iter().any(|k|!x[*k].is_null())||prices.iter().any(|v|!v.is_null()){return bad()}}
 else{if count_fields.iter().any(|k|integer(&x[*k]).is_none())||x["priced_supply"].as_u64()>x["supply"].as_u64(){return bad()}if state=="absent"&&(source["scope_complete"]!=true||count_fields.iter().any(|k|x[*k]!=0)||prices.iter().any(|v|!v.is_null())){return bad()}if x["priced_supply"]==0&&prices.iter().any(|v|!v.is_null()){return bad()}}
 if x["arithmetic_status"]=="unsupported"&&prices.iter().any(|v|!v.is_null()){return bad()}
 if canonical_model&&prices.iter().any(|v|!v.is_null()&&!v.as_str().and_then(|s|s.parse::<u64>().ok()).is_some_and(|n|(1..=99_999_999_999).contains(&n))){return bad()}
 Ok(())
}
pub fn validate_record(g:&Value,r:&Value)->Result<()>{
 schema_check(&schema(integer(&g["schema_version"]).unwrap_or(0))?["properties"]["records"]["items"],r)?;if canonical(r)?.len()>MAX_RECORD_BYTES{return bad()}
 if r["identity_basis"]=="exact_upstream" {let text=r["variant_json"].as_str().ok_or(Error::Invalid("variant descriptor"))?;let d=parse(text.as_bytes(),4096)?;if !d.is_object()||d["id"]!=r["item_id"]||canonical(&d)?!=text.as_bytes()||r["variant_key"]!=format!("{:x}",Sha256::digest(text.as_bytes())){return bad()}}else if !r["variant_json"].is_null(){return bad()}
 let model=g["pricing_algorithm"]=="twichui-pricing-v1";let c=&r["current"];let obs=observation(g,&c["observation_ref"])?;
 if c["observation_ref"]!=g["current_observation_ref"]||c["algorithm"]!=g["pricing_algorithm"]||c["metric_basis"]!=if model{"lower_band_mean"}else{"quantity_weighted_mean"}||c["complete"]==true&&obs["scope_complete"]!=true{return bad()}
 counts(c,&[&c["metrics"]["minimum_copper"],&c["metrics"]["recent_copper"]],obs,model)?;
 let coverage=&c["coverage"];let n14=coverage["priced_days_14"].as_u64().unwrap();let n60=coverage["priced_days_60"].as_u64().unwrap();if n14>n60||n60>coverage["observed_days_60"].as_u64().unwrap()||model&&(n14>14||n60>60){return bad()}
 if model {for k in ["minimum_copper","recent_copper","market_value_copper","historical_value_copper"]{let v=&c["metrics"][k];if !v.is_null()&&!v.as_str().and_then(|s|s.parse::<u64>().ok()).is_some_and(|n|(1..=99_999_999_999).contains(&n)){return bad()}}if !c["metrics"]["historical_value_copper"].is_null()&&n60<3{return bad()}}
 let mut last="";for d in r["daily"].as_array().unwrap(){let o=observation(g,&d["observation_ref"])?;let day=o["utc_day"].as_str().unwrap();if day<=last||day<g["coverage"]["history_from_day"].as_str().unwrap()||day>g["coverage"]["history_through_day"].as_str().unwrap()||d["algorithm"]!=g["pricing_algorithm"]{return bad()}last=day;
 if model {if o["scope_complete"]!=true{return bad()}let close=g["observations"].as_array().unwrap().iter().filter(|x|x["utc_day"]==o["utc_day"]&&x["scope_complete"]==true).max_by_key(|x|(time(&x["observed_at"]).unwrap(),x["observation_id"].as_str().unwrap().parse::<u64>().unwrap())).unwrap();if o!=close{return bad()}}
 counts(d,&[&d["minimum_copper"],&d["recent_copper"]],o,model)?;}
 if g["coverage"]["history_complete"]==true {
  let eligible=g["observations"].as_array().unwrap().iter().filter(|o|o["utc_day"].as_str().unwrap()>=g["coverage"]["history_from_day"].as_str().unwrap()&&o["utc_day"].as_str().unwrap()<=g["coverage"]["history_through_day"].as_str().unwrap()&&(!model||o["scope_complete"]==true)).map(|o|o["utc_day"].as_str().unwrap()).collect::<HashSet<_>>();
  let actual=r["daily"].as_array().unwrap().iter().map(|d|observation(g,&d["observation_ref"]).unwrap()["utc_day"].as_str().unwrap()).collect::<HashSet<_>>();if eligible!=actual{return bad()}
 }
 let dist=&r["distribution"];if (!dist.is_null())!=(r["distribution_status"]=="available"){return bad()}if g["coverage"]["distribution_complete"]==true&&c["priced_supply"].as_u64().unwrap_or(0)>0&&dist.is_null(){return bad()}
 if !dist.is_null(){if c["state"]!="listed"||dist["algorithm"]!=if model{"canonical-tiers-v1"}else{"linear-unit-price-bands-v1"}||dist["priced_supply"]!=c["priced_supply"]||dist["priced_supply"].as_u64().unwrap()+dist["unpriced_supply"].as_u64().unwrap()!=c["supply"].as_u64().unwrap()||dist["priced_listing_count"].as_u64().unwrap()+dist["unpriced_listing_count"].as_u64().unwrap()!=c["listing_count"].as_u64().unwrap()||dist["complete"]==true&&dist["truncated"]==true{return bad()}
 if model {let q=&dist["quartiles"];if q.is_null()||!dist["bands"].as_array().unwrap().is_empty(){return bad()}let price=|k:&str|q[k].as_str().and_then(|x|x.parse::<u64>().ok()).unwrap_or(0);let quartiles=[price("q25_copper"),price("q50_copper"),price("q75_copper"),price("high_copper")];if quartiles.iter().any(|n|!(1..=99_999_999_999).contains(n))||quartiles.windows(2).any(|w|w[0]>w[1])||price("anchor_copper")<quartiles[0]||price("anchor_copper")>quartiles[1]{return bad()}let minimum=c["metrics"]["minimum_copper"].as_str().and_then(|x|x.parse::<u64>().ok()).unwrap_or(0);let recent=c["metrics"]["recent_copper"].as_str().and_then(|x|x.parse::<u64>().ok()).unwrap_or(0);if minimum==0||minimum>recent||recent>quartiles[1]{return bad()}let(mut prev,mut quantity,mut listings)=(0,dist["tail_quantity"].as_u64().unwrap(),dist["tail_listing_count"].as_u64().unwrap());for t in dist["tiers"].as_array().unwrap(){let p=t["unit_copper"].as_str().unwrap().parse::<u64>().unwrap();if p<=prev||p>99_999_999_999||t["listing_count"].as_u64()>t["quantity"].as_u64()||t["largest_listing"].as_u64()>t["quantity"].as_u64(){return bad()}prev=p;quantity+=t["quantity"].as_u64().unwrap();listings+=t["listing_count"].as_u64().unwrap()}if quantity!=dist["priced_supply"].as_u64().unwrap()||listings!=dist["priced_listing_count"].as_u64().unwrap(){return bad()}}
 else{if !dist["quartiles"].is_null()||!dist["tiers"].as_array().unwrap().is_empty()||dist["tail_quantity"]!=0||dist["tail_listing_count"]!=0{return bad()}let(mut q,mut n)=(0,0);for b in dist["bands"].as_array().unwrap(){if b["minimum_copper"].as_str().unwrap().parse::<u64>().unwrap()>b["maximum_copper"].as_str().unwrap().parse::<u64>().unwrap(){return bad()}q+=b["supply"].as_u64().unwrap();n+=b["listing_count"].as_u64().unwrap()}if q!=dist["priced_supply"].as_u64().unwrap()||n!=dist["priced_listing_count"].as_u64().unwrap(){return bad()}}}
 Ok(())
}
pub fn validate(g:&Value)->Result<()>{
 if canonical(g)?.len()>MAX_BYTES{return bad()}let records=g["records"].as_array().ok_or(Error::Invalid("bridge records"))?;let mut header=g.clone();header.as_object_mut().ok_or(Error::Invalid("bridge generation"))?.remove("records");validate_header(&header)?;
 if records.len() as u64!=g["record_count"].as_u64().unwrap()||g["integrity"]["records_bytes"]!=canonical(&g["records"])?.len()||g["integrity"]["records_sha256"]!=hash(&g["records"])?||g["generation_id"]!=hash(&body(g))?{return bad()}
 let mut last=None;for r in records{validate_record(g,r)?;let k=(r["item_id"].as_u64().unwrap(),r["variant_key"].as_str().unwrap());if last.is_some_and(|old|k<=old){return bad()}last=Some(k)}Ok(())
}
