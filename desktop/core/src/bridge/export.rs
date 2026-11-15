//! Fixed assignment-only Lua transport, manual staging only. Never discovers a game installation.
use super::{canonical,parse,validate,BridgeCache,Scope,MAX_BYTES};
use crate::{Error,Result};
use serde_json::Value;
use std::{fs,io::{Read,Write},path::{Component,Path,PathBuf}};
const MAX_ARTIFACT:usize=MAX_BYTES*4+2*1024*1024;
const PREFIX:&str="TwichUIMarketData = { transport_version = 1, manifest = ";
const TOC:&str="## Interface: 16001\n## Title: TwichUI Market Data\n## Notes: Companion-generated market observations. No local scans or SavedVariables.\n## LoadOnDemand: 1\nData.lua\n";
fn refuse<T>()->Result<T>{Err(Error::Invalid("use an owned companion staging directory outside game files"))}
fn no_links(path:&Path)->Result<()>{
 let mut p=PathBuf::new();for part in path.components(){if matches!(part,Component::ParentDir|Component::CurDir){return refuse()}p.push(part);if let Ok(meta)=fs::symlink_metadata(&p){if meta.file_type().is_symlink(){return refuse()}#[cfg(windows)]{use std::os::windows::fs::MetadataExt;if meta.file_attributes()&0x400!=0{return refuse()}}}}
 Ok(())
}
fn safe_root(root:&Path)->Result<()>{
 if !root.is_absolute()||!root.is_dir(){return refuse()}no_links(root)?;
 #[cfg(windows)]super::windows_owner::check(root)?;
 for part in root.components(){if ["savedvariables","wtf","interface","addons"].contains(&part.as_os_str().to_string_lossy().to_ascii_lowercase().as_str()){return refuse()}}
 for p in root.ancestors(){if p.join("WTF").exists()||p.join("Interface").join("AddOns").exists(){return refuse()}}
 #[cfg(unix)]{use std::os::unix::fs::PermissionsExt;if fs::metadata(root)?.permissions().mode()&0o022!=0{return refuse()}}
 Ok(())
}
fn literal(raw:&[u8],out:&mut Vec<u8>){out.push(b'"');for b in raw{out.extend_from_slice(format!("\\{b:03}").as_bytes())}out.push(b'"')}
pub(crate) fn artifact(g:&Value,receipt:&Value)->Result<Vec<u8>>{
 validate(g)?;let mut h=g.clone();let records=h.as_object_mut().unwrap().remove("records").unwrap();let header=canonical(&h)?;if header.len()>65536{return refuse()}
 let mut out=PREFIX.as_bytes().to_vec();literal(&header,&mut out);out.extend_from_slice(b", records = {\n");
 for r in records.as_array().unwrap(){let raw=canonical(r)?;if raw.len()>65536{return refuse()}literal(&raw,&mut out);out.extend_from_slice(b",\n")}
 out.extend_from_slice(b"}, receipt = ");let raw=canonical(receipt)?;if raw.len()>4096{return refuse()}literal(&raw,&mut out);out.extend_from_slice(b" }\n");if out.len()>MAX_ARTIFACT{return refuse()}Ok(out)
}
/// Decode our fixed template for readback/rollback. No Lua interpreter or dynamic code evaluation.
pub fn inspect_artifact(bytes:&[u8])->Result<(Value,Value)>{
 if bytes.len()>MAX_ARTIFACT{return refuse()}
 struct Reader<'a>{b:&'a[u8],i:usize}
 impl Reader<'_>{fn exact(&mut self,s:&[u8])->Result<()>{if self.b.get(self.i..self.i+s.len())!=Some(s){return refuse()}self.i+=s.len();Ok(())}fn string(&mut self,max:usize)->Result<Vec<u8>>{self.exact(b"\"")?;let mut out=Vec::new();while self.b.get(self.i)!=Some(&b'"'){self.exact(b"\\")?;let digits=self.b.get(self.i..self.i+3).ok_or(Error::Invalid("bridge Lua escape"))?;if !digits.iter().all(u8::is_ascii_digit){return refuse()}let n=(digits[0]-b'0') as u16*100+(digits[1]-b'0') as u16*10+(digits[2]-b'0') as u16;if n>255||out.len()>=max{return refuse()}out.push(n as u8);self.i+=3;}self.exact(b"\"")?;Ok(out)}}
 let mut r=Reader{b:bytes,i:0};r.exact(PREFIX.as_bytes())?;let mut g=parse(&r.string(65536)?,65536)?;r.exact(b", records = {\n")?;let mut records=Vec::new();let mut size=0;
 while r.b.get(r.i)==Some(&b'"'){let raw=r.string(65536)?;size+=raw.len()+1;if size>MAX_BYTES||records.len()>=150000{return refuse()}records.push(parse(&raw,65536)?);r.exact(b",\n")?}
 r.exact(b"}, receipt = ")?;let receipt=parse(&r.string(4096)?,4096)?;r.exact(b" }\n")?;if r.i!=bytes.len(){return refuse()}g.as_object_mut().ok_or(Error::Invalid("bridge Lua manifest"))?.insert("records".into(),records.into());validate(&g)?;
 if receipt["schema_version"]!=1||receipt["generation_id"]!=g["generation_id"]||receipt.as_object().is_none_or(|o|o.len()!=4)||receipt["desktop_build"].as_str().is_none_or(|s|s.is_empty()||s.len()>80)||super::validation::time(&receipt["completed_at"]).is_err(){return refuse()}Ok((g,receipt))
}
fn read(path:&Path,maximum:usize)->Result<Vec<u8>>{no_links(path)?;let mut data=Vec::new();fs::File::open(path)?.take(maximum as u64+1).read_to_end(&mut data)?;if data.len()>maximum{return refuse()}Ok(data)}
fn atomic(path:&Path,bytes:&[u8])->Result<()>{let parent=path.parent().ok_or(Error::Invalid("bridge staging parent"))?;no_links(parent)?;no_links(path)?;let mut f=tempfile::NamedTempFile::new_in(parent)?;f.write_all(bytes)?;f.flush()?;f.as_file().sync_all()?;
 #[cfg(unix)]{use std::os::unix::fs::MetadataExt;if f.as_file().metadata()?.uid()!=fs::metadata(parent)?.uid(){return refuse()}}
 f.persist(path).map_err(|e|Error::Io(e.error))?;#[cfg(unix)]fs::File::open(parent)?.sync_all()?;Ok(())}

/// Creates only fixed, account-scoped children of an already safe companion directory.
pub fn staging_directory(base:&Path,scope:&Scope)->Result<PathBuf>{
 safe_root(base)?;let mut root=base.to_path_buf();
 for name in ["workshop-testing".to_owned(),scope.key()?]{root.push(name);no_links(&root)?;if !root.exists(){fs::create_dir(&root)?}safe_root(&root)?;}
 Ok(root)
}

pub fn export_staging(cache:&BridgeCache,scope:&Scope,root:&Path)->Result<PathBuf>{publish(cache,scope,root,|p,b|atomic(p,b))}
fn publish(cache:&BridgeCache,scope:&Scope,root:&Path,replace:impl FnOnce(&Path,&[u8])->Result<()>)->Result<PathBuf>{
 safe_root(root)?;let(g,receipt)=cache.completed(scope)?.ok_or(Error::Invalid("complete a bridge download before export"))?;let bytes=artifact(&g,&receipt)?;inspect_artifact(&bytes)?;
 let marker=root.join(".twichui-bridge-scope");let key=scope.key()?;if marker.exists(){if read(&marker,128)?!=key.as_bytes(){return refuse()}}else{atomic(&marker,key.as_bytes())?}
 let folder=root.join("TwichUI_MarketData");no_links(&folder)?;if !folder.exists(){fs::create_dir(&folder)?}if !folder.is_dir(){return refuse()}
 for entry in fs::read_dir(&folder)?{let path=entry?.path();no_links(&path)?;#[cfg(unix)]{use std::os::unix::fs::MetadataExt;if fs::metadata(&path)?.uid()!=fs::metadata(&folder)?.uid(){return refuse()}}
 #[cfg(windows)]super::windows_owner::check(&path)?;
 let name=path.file_name().unwrap().to_string_lossy();if !["TwichUI_MarketData.toc","Data.lua","Previous.lua"].contains(&name.as_ref())||!path.is_file(){return refuse()}}
 let toc=folder.join("TwichUI_MarketData.toc");if toc.exists(){if read(&toc,1024)?!=TOC.as_bytes(){return refuse()}}else{atomic(&toc,TOC.as_bytes())?}
 let target=folder.join("Data.lua");let previous=folder.join("Previous.lua");let old=if target.exists(){let b=read(&target,MAX_ARTIFACT)?;inspect_artifact(&b)?;Some(b)}else{None};
 if let Some(b)=&old{atomic(&previous,b)?;inspect_artifact(&read(&previous,MAX_ARTIFACT)?)?;}
 if let Err(error)=replace(&target,&bytes){if let Some(b)=&old{atomic(&target,b)?}return Err(error)}
 let result=read(&target,MAX_ARTIFACT).and_then(|published|{if published!=bytes{return refuse()}inspect_artifact(&published).map(|_|())});
 if let Err(error)=result{if let Some(b)=&old{atomic(&target,b)?}else if target.is_file(){fs::remove_file(&target)?}return Err(error)}
 Ok(target)
}

#[cfg(test)]
mod tests {
 use super::*;use chrono::Utc;use serde_json::json;
 fn completed()->(BridgeCache,Scope){let g:Value=serde_json::from_str(include_str!("../../../../contracts/bridge/v1/source-canonical-generation.json")).unwrap();let mut h=g.clone();h.as_object_mut().unwrap().remove("records");let s=Scope{server:"http://127.0.0.1:8899/".into(),account_id:1,market_id:2,algorithm:"twichui-pricing-v1".into()};let mut c=BridgeCache::memory().unwrap();c.start(&s,&serde_json::to_vec(&json!({"format":"twichui-market-bridge-manifest","contract_version":1,"transport_version":1,"account_id":1,"manifest":h,"cursor":"first"})).unwrap()).unwrap();c.apply(&s,"first",&serde_json::to_vec(&json!({"format":"twichui-market-bridge-page","contract_version":1,"transport_version":1,"account_id":1,"market_id":2,"generation_id":g["generation_id"],"offset":0,"records":g["records"],"has_more":false,"next_cursor":null})).unwrap(),Utc::now()).unwrap();(c,s)}
 #[test]fn failed_replace_and_bad_readback_restore_previous(){let(c,s)=completed();let root=tempfile::tempdir().unwrap();let p=export_staging(&c,&s,root.path()).unwrap();let old=fs::read(&p).unwrap();assert!(publish(&c,&s,root.path(),|_,_|Err(Error::Io(std::io::Error::other("injected replace failure")))).is_err());assert_eq!(fs::read(&p).unwrap(),old);assert!(publish(&c,&s,root.path(),|p,_|{fs::write(p,b"corrupt")?;Ok(())}).is_err());assert_eq!(fs::read(&p).unwrap(),old);assert_eq!(fs::read(p.parent().unwrap().join("Previous.lua")).unwrap(),old);}
}
