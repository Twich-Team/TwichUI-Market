use super::{canonical,parse,validate,validate_header,validate_record,MAX_BYTES};
use crate::{client::server_url,Error,Result};
use chrono::{DateTime,Utc};
use rusqlite::{params,Connection,OptionalExtension};
use serde::{Deserialize,Serialize};
use serde_json::Value;
use sha2::{Digest,Sha256};
use std::path::Path;

#[derive(Clone,Debug,Serialize,Deserialize,PartialEq,Eq)]
#[serde(deny_unknown_fields)]
pub struct Scope {pub server:String,pub account_id:u32,pub market_id:u32,pub algorithm:String}
impl Scope {
 pub fn key(&self)->Result<String>{if server_url(&self.server)?.as_str()!=self.server||self.account_id==0||self.market_id==0||self.market_id>i32::MAX as u32||!matches!(self.algorithm.as_str(),"twichui-pricing-v1"|"asking-v1-provisional"){return Err(Error::Invalid("bridge account/market scope"))}Ok(format!("{:x}",Sha256::digest(serde_json::to_vec(self)?)))}
 fn header(&self,h:&Value)->Result<()>{self.key()?;validate_header(h)?;if h["market"]["server_market_id"]!=self.market_id||h["pricing_algorithm"]!=self.algorithm{return Err(Error::Invalid("bridge market/algorithm scope"))}Ok(())}
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct ManifestEnvelope {format:String,contract_version:u32,transport_version:u32,account_id:u32,manifest:Value,cursor:String}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Page {format:String,contract_version:u32,transport_version:u32,account_id:u32,market_id:u32,generation_id:String,offset:u64,records:Vec<Value>,has_more:bool,next_cursor:Option<String>}

pub struct BridgeCache {db:Connection}
impl BridgeCache {
 pub fn open(path:&Path)->Result<Self>{Self::initialize(Connection::open(path)?)}
 pub fn memory()->Result<Self>{Self::initialize(Connection::open_in_memory()?)}
 fn initialize(db:Connection)->Result<Self>{
  let version:u32=db.pragma_query_value(None,"user_version",|r|r.get(0))?;if version>1{return Err(Error::Invalid("newer bridge cache schema"))}
  db.busy_timeout(std::time::Duration::from_secs(5))?;
  db.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA max_page_count=65536;
   CREATE TABLE IF NOT EXISTS bridge_generations(scope TEXT NOT NULL,slot TEXT NOT NULL,manifest TEXT NOT NULL,cursor TEXT,next_position INTEGER NOT NULL,completed_at TEXT,PRIMARY KEY(scope,slot));
   CREATE TABLE IF NOT EXISTS bridge_records(scope TEXT NOT NULL,slot TEXT NOT NULL,position INTEGER NOT NULL,value TEXT NOT NULL,PRIMARY KEY(scope,slot,position));")?;
  db.pragma_update(None,"user_version",1)?;Ok(Self{db})
 }
 pub fn pending(&self,scope:&Scope)->Result<Option<(Value,String)>>{
  let row:Option<(String,String)>=self.db.query_row("SELECT manifest,cursor FROM bridge_generations WHERE scope=?1 AND slot='staging'",[scope.key()?],|r|Ok((r.get(0)?,r.get(1)?))).optional()?;
  row.map(|(h,c)|{let h=parse(h.as_bytes(),65536)?;scope.header(&h)?;Ok((h,c))}).transpose()
 }
 pub fn start(&mut self,scope:&Scope,raw:&[u8])->Result<()>{
  let envelope:ManifestEnvelope=serde_json::from_value(parse(raw,70*1024)?)?;
  if envelope.format!="twichui-market-bridge-manifest"||envelope.contract_version!=1||envelope.transport_version!=1||envelope.account_id!=scope.account_id||envelope.cursor.is_empty()||envelope.cursor.len()>2048{return Err(Error::Invalid("bridge manifest envelope"))}
  scope.header(&envelope.manifest)?;let key=scope.key()?;let tx=self.db.transaction()?;
  tx.execute("DELETE FROM bridge_records WHERE scope=?1 AND slot='staging'",[&key])?;
  tx.execute("INSERT INTO bridge_generations(scope,slot,manifest,cursor,next_position,completed_at) VALUES(?1,'staging',?2,?3,0,NULL) ON CONFLICT(scope,slot) DO UPDATE SET manifest=excluded.manifest,cursor=excluded.cursor,next_position=0,completed_at=NULL",params![key,String::from_utf8(canonical(&envelope.manifest)?).unwrap(),envelope.cursor])?;
  tx.commit()?;Ok(())
 }
 pub fn abandon_pending(&mut self,scope:&Scope)->Result<()>{let tx=self.db.transaction()?;let key=scope.key()?;tx.execute("DELETE FROM bridge_records WHERE scope=?1 AND slot='staging'",[&key])?;tx.execute("DELETE FROM bridge_generations WHERE scope=?1 AND slot='staging'",[&key])?;tx.commit()?;Ok(())}
 pub fn apply(&mut self,scope:&Scope,requested_cursor:&str,raw:&[u8],completed_at:DateTime<Utc>)->Result<bool>{
  let page:Page=serde_json::from_value(parse(raw,1024*1024)?)?;let key=scope.key()?;
  let tx=self.db.transaction()?;
  let(h,cursor,offset):(String,String,u32)=tx.query_row("SELECT manifest,cursor,next_position FROM bridge_generations WHERE scope=?1 AND slot='staging'",[&key],|r|Ok((r.get(0)?,r.get(1)?,r.get(2)?)))?;
  let header=parse(h.as_bytes(),65536)?;scope.header(&header)?;
  let total=header["record_count"].as_u64().unwrap();let end=offset.checked_add(page.records.len() as u32).ok_or(Error::Invalid("bridge page count"))?;
  if cursor!=requested_cursor||page.format!="twichui-market-bridge-page"||page.contract_version!=1||page.transport_version!=1||page.account_id!=scope.account_id||page.market_id!=scope.market_id||page.generation_id!=header["generation_id"].as_str().unwrap()||page.offset!=u64::from(offset)||page.records.len()>100||u64::from(end)>total||page.has_more!=(u64::from(end)<total)||page.has_more&&(page.records.is_empty()||page.next_cursor.as_ref().is_none_or(|c|c.is_empty()||c.len()>2048))||!page.has_more&&page.next_cursor.is_some(){return Err(Error::Invalid("bridge page sequence/scope"))}
  let last:Option<String>=tx.query_row("SELECT value FROM bridge_records WHERE scope=?1 AND slot='staging' ORDER BY position DESC LIMIT 1",[&key],|r|r.get(0)).optional()?;
  let mut previous=last.map(|s|parse(s.as_bytes(),65536)).transpose()?;
  for (i,r) in page.records.iter().enumerate(){validate_record(&header,r)?;if previous.as_ref().is_some_and(|p|(r["item_id"].as_u64().unwrap(),r["variant_key"].as_str().unwrap())<=(p["item_id"].as_u64().unwrap(),p["variant_key"].as_str().unwrap())){return Err(Error::Invalid("duplicate/unordered bridge identity"))}
   tx.execute("INSERT INTO bridge_records(scope,slot,position,value) VALUES(?1,'staging',?2,?3)",params![key,offset+i as u32,String::from_utf8(canonical(r)?).unwrap()])?;previous=Some(r.clone());}
  if page.has_more{tx.execute("UPDATE bridge_generations SET cursor=?2,next_position=?3 WHERE scope=?1 AND slot='staging'",params![key,page.next_cursor,end])?;}
  else {
   let mut generation=header.clone();let mut statement=tx.prepare("SELECT position,value FROM bridge_records WHERE scope=?1 AND slot='staging' ORDER BY position")?;
   let rows=statement.query_map([&key],|r|Ok((r.get::<_,u32>(0)?,r.get::<_,String>(1)?)))?;
   let mut records=Vec::new();let mut bytes=canonical(&header)?.len();for row in rows{let(i,s)=row?;if i!=records.len() as u32{return Err(Error::Invalid("incomplete bridge staging"))}bytes+=s.len()+1;if bytes>MAX_BYTES{return Err(Error::Invalid("bridge cache size"))}records.push(parse(s.as_bytes(),65536)?)}drop(statement);
   generation.as_object_mut().unwrap().insert("records".into(),records.into());validate(&generation)?;
   // Promotion and previous-generation retention are one SQLite transaction.
   tx.execute("DELETE FROM bridge_records WHERE scope=?1 AND slot='previous'",[&key])?;
   tx.execute("DELETE FROM bridge_generations WHERE scope=?1 AND slot='previous'",[&key])?;
   tx.execute("UPDATE bridge_records SET slot='previous' WHERE scope=?1 AND slot='active'",[&key])?;
   tx.execute("UPDATE bridge_generations SET slot='previous' WHERE scope=?1 AND slot='active'",[&key])?;
   tx.execute("UPDATE bridge_records SET slot='active' WHERE scope=?1 AND slot='staging'",[&key])?;
   tx.execute("UPDATE bridge_generations SET slot='active',cursor=NULL,next_position=?2,completed_at=?3 WHERE scope=?1 AND slot='staging'",params![key,end,completed_at.to_rfc3339_opts(chrono::SecondsFormat::Micros,true)])?;
  }
  tx.commit()?;Ok(page.has_more)
 }
 pub fn completed(&self,scope:&Scope)->Result<Option<(Value,Value)>>{self.completed_slot(scope,"active")}
 pub fn previous(&self,scope:&Scope)->Result<Option<(Value,Value)>>{self.completed_slot(scope,"previous")}
 fn completed_slot(&self,scope:&Scope,slot:&str)->Result<Option<(Value,Value)>>{
  let key=scope.key()?;let row:Option<(String,String)>=self.db.query_row("SELECT manifest,completed_at FROM bridge_generations WHERE scope=?1 AND slot=?2",params![key,slot],|r|Ok((r.get(0)?,r.get(1)?))).optional()?;
  let Some((header,completed_at))=row else{return Ok(None)};let mut g=parse(header.as_bytes(),65536)?;scope.header(&g)?;
  let mut statement=self.db.prepare("SELECT position,value FROM bridge_records WHERE scope=?1 AND slot=?2 ORDER BY position")?;let rows=statement.query_map(params![key,slot],|r|Ok((r.get::<_,u32>(0)?,r.get::<_,String>(1)?)))?;
  let mut records=Vec::new();let mut bytes=header.len();for row in rows{let(i,s)=row?;if i!=records.len() as u32{return Err(Error::Invalid("incomplete completed bridge"))}bytes+=s.len()+1;if bytes>MAX_BYTES{return Err(Error::Invalid("bridge cache size"))}records.push(parse(s.as_bytes(),65536)?)}
  g.as_object_mut().unwrap().insert("records".into(),records.into());validate(&g)?;
  let receipt=serde_json::json!({"schema_version":1,"generation_id":g["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":completed_at});
  Ok(Some((g,receipt)))
 }
}

#[cfg(test)]
mod tests {
 use super::*;
 use serde_json::json;
 #[test]
 fn sqlite_full_rolls_back_page_and_preserves_completed_generation(){
  let g:Value=serde_json::from_str(include_str!("../../../../contracts/bridge/v1/source-canonical-generation.json")).unwrap();
  let mut h=g.clone();h.as_object_mut().unwrap().remove("records");
  let s=Scope{server:"http://127.0.0.1:8899/".into(),account_id:1,market_id:2,algorithm:"twichui-pricing-v1".into()};
  let envelope=serde_json::to_vec(&json!({"format":"twichui-market-bridge-manifest","contract_version":1,"transport_version":1,"account_id":1,"manifest":h,"cursor":"first"})).unwrap();
  let page=serde_json::to_vec(&json!({"format":"twichui-market-bridge-page","contract_version":1,"transport_version":1,"account_id":1,"market_id":2,"generation_id":g["generation_id"],"offset":0,"records":g["records"],"has_more":false,"next_cursor":null})).unwrap();
  let mut c=BridgeCache::memory().unwrap();c.start(&s,&envelope).unwrap();c.apply(&s,"first",&page,Utc::now()).unwrap();let good=c.completed(&s).unwrap();
  c.start(&s,&envelope).unwrap();c.db.execute_batch("CREATE TABLE quota(value BLOB)").unwrap();let count:u32=c.db.pragma_query_value(None,"page_count",|r|r.get(0)).unwrap();c.db.pragma_update(None,"max_page_count",count).unwrap();
  let error=loop{match c.db.execute("INSERT INTO quota VALUES(zeroblob(4096))",[]){Ok(_)=>{},Err(e)=>break e}};
  assert!(matches!(error,rusqlite::Error::SqliteFailure(e,_) if e.code==rusqlite::ErrorCode::DiskFull));
  assert!(c.apply(&s,"first",&page,Utc::now()).is_err());assert_eq!(c.completed(&s).unwrap(),good);assert_eq!(c.pending(&s).unwrap().unwrap().1,"first");
  c.db.pragma_update(None,"max_page_count",65536).unwrap();c.db.execute_batch("DROP TABLE quota").unwrap();c.apply(&s,"first",&page,Utc::now()).unwrap();assert_eq!(c.previous(&s).unwrap(),good);
 }
}
