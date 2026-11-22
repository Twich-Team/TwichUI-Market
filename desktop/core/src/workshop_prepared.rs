//! Source-authenticated fixed current records. Never executes generated Lua.
use crate::{bridge, workshop_summary::{self as summary, Bundle}, Error, Result};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

pub const WIDTH: usize = 135;
pub const MAX_PART: usize = 4 * 1024 * 1024;
pub const MAX_TOTAL: usize = 32 * 1024 * 1024;
pub const ROOT_PREFIX: &[u8] = b"TwichUIMarketData = { summary_version = 2, manifest = ";
const WIDTHS: [usize; 13] = [8,64,1,10,10,10,14,1,1,10,2,2,2];
fn need(ok: bool, why: &'static str) -> Result<()> { if ok { Ok(()) } else { Err(Error::Invalid(why)) } }
fn sha(raw: &[u8]) -> String { format!("{:x}", Sha256::digest(raw)) }
fn hex(s: &str) -> bool { s.len()==64 && s.bytes().all(|b|b.is_ascii_hexdigit() && !b.is_ascii_uppercase()) }

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Descriptor {pub bucket:usize,pub record_count:usize,pub bytes:usize,pub sha256:String,pub merkle_root:String}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Attestation {
    pub format:String,pub version:u64,pub source_generation_id:String,pub partitions_count:usize,
    pub record_width:usize,pub hash_algorithm:String,pub record_count:usize,
    pub partitions:Vec<Descriptor>,pub attestation_id:String,
}
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Part {pub data:String,pub proofs:String}

pub fn metadata(value:&Value, h:&Value)->Result<Attestation> {
    let a:Attestation=serde_json::from_value(value.clone())?;
    need(h["contract_version"]==3 && a.format=="twichui-workshop-prepared-current" && a.version==1
         && [16,32].contains(&a.partitions_count) && a.record_width==WIDTH
         && a.hash_algorithm=="sha256-canonical-13-v1" && hex(&a.attestation_id)
         && a.source_generation_id==h["generation_id"] && a.record_count<=150000
         && a.record_count as u64==h["record_count"].as_u64().unwrap_or(u64::MAX)
         && a.partitions.len()==a.partitions_count,"prepared source/contract")?;
    let mut body=value.clone();body.as_object_mut().ok_or(Error::Invalid("prepared object"))?.remove("attestation_id");
    need(sha(&bridge::canonical(&body)?)==a.attestation_id,"prepared attestation digest")?;
    let mut total=0;let mut records=0;
    for (bucket,p) in a.partitions.iter().enumerate() {
        need(p.bucket==bucket && p.record_count<=150000 && p.bytes>=2 && p.bytes<=MAX_PART
             && hex(&p.sha256) && hex(&p.merkle_root),"prepared descriptor")?;
        let size=p.record_count.max(1).next_power_of_two();
        let bytes=WIDTH*p.record_count+(2*size-1)*64;total+=bytes;records+=p.record_count;
        need(bytes<=MAX_PART && total<=MAX_TOTAL,"prepared capacity")?;
        if p.record_count==0 {need(p.sha256==sha(b"[]") && p.merkle_root==sha(b"empty\0") && p.bytes==2,"prepared empty bucket")?;}
    }
    need(records==a.record_count,"prepared count")?;Ok(a)
}
fn nodes(rows:&[Value])->Result<Vec<String>> {
    let size=rows.len().max(1).next_power_of_two();let mut out=vec![String::new();2*size];
    for i in 0..size {out[size+i]=if let Some(row)=rows.get(i) {let mut bytes=b"row\0".to_vec();bytes.extend(bridge::canonical(row)?);sha(&bytes)} else {sha(b"empty\0")};}
    for i in (1..size).rev() {let mut bytes=b"node\0".to_vec();bytes.extend(out[i*2].as_bytes());bytes.extend(out[i*2+1].as_bytes());out[i]=sha(&bytes);}
    Ok(out.into_iter().skip(1).collect())
}
fn encode(rows:&[Value])->Result<String> {
    let mut out=String::with_capacity(rows.len()*WIDTH);
    for row in rows {
        let row=row.as_array().ok_or(Error::Invalid("prepared row"))?;need(row.len()==13,"prepared columns")?;
        for (i,width) in WIDTHS.iter().enumerate() {
            let word=if row[i].is_null() {need([3,4,5,6,9].contains(&i),"prepared null")?;"z".repeat(*width)}
            else if i==1 {let key=row[i].as_str().ok_or(Error::Invalid("prepared variant"))?;need(hex(key),"prepared variant")?;key.to_string()}
            else {let n=if [3,4,5,9].contains(&i) {row[i].as_str().and_then(|s|s.parse::<u64>().ok())} else {row[i].as_u64()}.ok_or(Error::Invalid("prepared integer"))?;
                format!("{n:0width$x}")};
            need(word.len()==*width,"prepared width")?;out.push_str(&word);
        }
    }Ok(out)
}
fn decode(data:&str)->Result<Vec<Value>> {
    need(data.len()%WIDTH==0 && data.bytes().all(|b|b.is_ascii_digit() || (b'a'..=b'f').contains(&b) || b==b'z'),"prepared data syntax")?;
    let mut rows=Vec::with_capacity(data.len()/WIDTH);
    for bytes in data.as_bytes().chunks_exact(WIDTH) {
        let mut row=Vec::new();let mut at=0;
        for (i,width) in WIDTHS.iter().enumerate() {
            let word=std::str::from_utf8(&bytes[at..at+width]).map_err(|_|Error::Invalid("prepared word"))?;at+=width;
            let value=if i==1 {need(hex(word),"prepared exact variant")?;json!(word)}
            else if word.bytes().all(|b|b==b'z') {need([3,4,5,6,9].contains(&i),"prepared unavailable")?;Value::Null}
            else {let n=u64::from_str_radix(word,16).map_err(|_|Error::Invalid("prepared number"))?;
                if [3,4,5,9].contains(&i) {json!(n.to_string())} else {json!(n)}};
            row.push(value);
        }rows.push(Value::Array(row));
    }Ok(rows)
}
fn descriptor(rows:&[Value],p:&Descriptor)->Result<Part> {
    let raw=bridge::canonical(&Value::Array(rows.to_vec()))?;let nodes=nodes(rows)?;
    need(rows.len()==p.record_count && raw.len()==p.bytes && sha(&raw)==p.sha256 && nodes[0]==p.merkle_root,"prepared authoritative content")?;
    Ok(Part{data:encode(rows)?,proofs:nodes.concat()})
}
pub fn build(bundle:&Bundle,value:&Value)->Result<(Attestation,BTreeMap<u8,Part>)> {
    let a=metadata(value,&bundle.manifest)?;let mut groups=vec![Vec::<Value>::new();a.partitions_count];
    for p in bundle.manifest["partitions"].as_array().ok_or(Error::Invalid("prepared source parts"))? {
        let b=p["bucket"].as_u64().ok_or(Error::Invalid("prepared source bucket"))? as u8;
        let raw=bundle.parts.get(&b).ok_or(Error::Invalid("prepared missing source"))?;
        summary::validate_part(&bundle.manifest,p,raw)?;
        for row in bridge::parse(raw,summary::HISTORY_PART)?.as_array().unwrap() {
            groups[row[0].as_u64().unwrap() as usize%a.partitions_count].push(row.clone());
        }
    }
    let mut parts=BTreeMap::new();
    for (bucket,rows) in groups.iter_mut().enumerate() {
        rows.sort_by(|a,b|a[0].as_u64().cmp(&b[0].as_u64()).then_with(||a[1].as_str().cmp(&b[1].as_str())));
        parts.insert(bucket as u8,descriptor(rows,&a.partitions[bucket])?);
    }Ok((a,parts))
}
pub fn name(bank:&str,bucket:u8)->String {format!("TwichUI_MarketCurrentPart{bank}{bucket:02}")}
fn prefix(bank:&str,p:&Descriptor,count:usize)->Result<String> {
    need(["A","B"].contains(&bank) && [16,32].contains(&count) && p.bucket<count && hex(&p.sha256),"prepared artifact identity")?;
    Ok(format!("TwichUIMarketCurrentParts = TwichUIMarketCurrentParts or {{}}\nTwichUIMarketCurrentParts[\"{bank}{:02}\"] = {{ version = 1, layout = {count}, content_id = \"{}\", data = \"",p.bucket,p.sha256))
}
pub fn artifact(bank:&str,p:&Descriptor,count:usize,part:&Part)->Result<Vec<u8>> {
    need(part.data.len()==p.record_count*WIDTH && part.data.len()+part.proofs.len()<=MAX_PART
         && part.data.bytes().all(|b|b.is_ascii_digit() || (b'a'..=b'f').contains(&b) || b==b'z')
         && part.proofs.bytes().all(|b|b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),"prepared literal grammar")?;
    Ok(format!("{}{}\", proofs = \"{}\" }}\n",prefix(bank,p,count)?,part.data,part.proofs).into_bytes())
}
pub fn inspect(bank:&str,p:&Descriptor,a:&Attestation,raw:&[u8],h:&Value)->Result<()> {
    let prefix=prefix(bank,p,a.partitions_count)?;need(raw.len()<=MAX_PART+1024 && raw.starts_with(prefix.as_bytes()),"prepared transport")?;
    let text=std::str::from_utf8(&raw[prefix.len()..]).map_err(|_|Error::Invalid("prepared source syntax"))?;
    let (data,tail)=text.split_once("\", proofs = \"").ok_or(Error::Invalid("prepared source fields"))?;
    let proofs=tail.strip_suffix("\" }\n").ok_or(Error::Invalid("prepared source tail"))?;
    let rows=decode(data)?;let expected=descriptor(&rows,p)?;
    need(expected.data==data && expected.proofs==proofs,"prepared byte integrity")?;
    // Independently rebind the installed rows to all original modulo-64 source
    // descriptors. This also reuses the complete existing typed row validator.
    for b in (p.bucket..64).step_by(a.partitions_count) {
        let group=Value::Array(rows.iter().filter(|r|r[0].as_u64().is_some_and(|id|id%64==b as u64)).cloned().collect());
        if let Some(original)=h["partitions"].as_array().unwrap().iter().find(|d|d["bucket"]==b) {
            summary::validate_part(h,original,&bridge::canonical(&group)?)?;
        } else {need(group.as_array().unwrap().is_empty(),"prepared unexpected source rows")?;}
    }Ok(())
}
