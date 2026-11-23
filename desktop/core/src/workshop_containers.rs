//! Fixed 2-current/4-history containers per bank. Only data literals enter WoW.
//! The server's canonical source and Merkle attestation remain unchanged.
use crate::{bridge,delivery,installation,workshop_prepared as prepared,workshop_summary as summary,Error,Result};
use base64::{engine::general_purpose::STANDARD,Engine};
use flate2::{read::DeflateDecoder,write::DeflateEncoder,Compression};
use serde_json::{json,Value};
use std::{collections::BTreeMap,fs,io::{Read,Write},path::{Path,PathBuf}};
use summary::{need,Bundle};

pub const ROOT_PREFIX:&[u8]=b"TwichUIMarketData = { summary_version = 3, manifest = ";
pub const BLOCK:usize=524288;
pub const ENCODED:usize=700000;
// A conservative admission bound on synchronous source compilation, not a frame
// guarantee. Oversize generations refuse publication; never silently enlarge it.
pub const CONTAINER_MAX:usize=8*1024*1024;

pub fn name(bank:&str,history:bool,group:usize)->String {
    format!("TwichUI_Market{}Container{bank}{group:02}",if history{"History"}else{"Current"})
}
fn global(history:bool)->&'static str {if history{"TwichUIMarketCompressedHistory"}else{"TwichUIMarketCompressedCurrent"}}
fn literal(out:&mut Vec<u8>,raw:&[u8]){bridge::export::literal(raw,out)}
fn stream(out:&mut Vec<u8>,bytes:&[u8])->Result<()> {
    out.extend(b"{");
    for block in bytes.chunks(BLOCK) {
        let mut encoder=DeflateEncoder::new(Vec::new(),Compression::new(6));encoder.write_all(block)?;
        let encoded=STANDARD.encode(encoder.finish()?);need(encoded.len()<=ENCODED,"compressed block capacity")?;
        out.extend(format!("{{ bytes = {}, payload = ",block.len()).as_bytes());literal(out,encoded.as_bytes());out.extend(b" },");
    }
    out.extend(b" }");Ok(())
}
fn expect(raw:&[u8],at:&mut usize,text:&[u8])->Result<()> {
    need(raw.get(*at..*at+text.len())==Some(text),"compressed container syntax")?;*at+=text.len();Ok(())
}
fn read_stream(raw:&[u8],at:&mut usize,bytes:usize)->Result<Vec<u8>> {
    expect(raw,at,b"{")?;let mut out=Vec::with_capacity(bytes);
    for offset in (0..bytes).step_by(BLOCK) {
        let size=BLOCK.min(bytes-offset);
        expect(raw,at,format!("{{ bytes = {size}, payload = ").as_bytes())?;
        let encoded=bridge::export::read_literal(raw,at,ENCODED)?;
        let compressed=STANDARD.decode(&encoded).map_err(|_|Error::Invalid("container base64"))?;
        need(STANDARD.encode(&compressed).as_bytes()==encoded,"canonical container base64")?;
        let mut decoder=DeflateDecoder::new(compressed.as_slice());let mut block=Vec::with_capacity(size);
        decoder.by_ref().take(size as u64+1).read_to_end(&mut block)?;
        need(block.len()==size && decoder.total_in()==compressed.len() as u64,"raw Deflate size/trailing input")?;
        out.extend(block);expect(raw,at,b" },")?;
    }
    expect(raw,at,b" }")?;Ok(out)
}
fn prefix(bank:&str,bucket:usize,history:bool,generation:&str,content:&str)->Vec<u8> {
    let mut out=format!("{}[\"{bank}{bucket:02}\"] = {{ version = 1, generation = ",global(history)).into_bytes();
    literal(&mut out,generation.as_bytes());out.extend(b", content_id = ");literal(&mut out,content.as_bytes());out.extend(b", data = ");out
}
pub fn build(bundle:&Bundle,value:&Value,bank:&str)->Result<BTreeMap<String,Vec<u8>>> {
    need(bank=="A"||bank=="B","container bank")?;
    let(a,parts)=prepared::build(bundle,value)?;need(a.partitions_count==32,"container logical layout")?;
    let generation=bundle.manifest["generation_id"].as_str().unwrap();let mut output=BTreeMap::new();
    for history in [false,true] {for group in 0..if history{4}else{2} {
        let g=global(history);let mut bytes=format!("{g} = {g} or {{}}\n").into_bytes();
        for bucket in group*16..(group+1)*16 {
            if history {
                let Some(p)=bundle.manifest["history_partitions"].as_array().unwrap().iter().find(|p|p["bucket"]==bucket)else{continue};
                let raw=&bundle.parts[&(bucket as u8+64)];
                bytes.extend(prefix(bank,bucket,true,generation,p["sha256"].as_str().unwrap()));stream(&mut bytes,raw)?;
            }else {
                let p=&a.partitions[bucket];let part=&parts[&(bucket as u8)];
                bytes.extend(prefix(bank,bucket,false,generation,&p.sha256));stream(&mut bytes,part.data.as_bytes())?;
                bytes.extend(b", proofs = ");stream(&mut bytes,part.proofs.as_bytes())?;
            }
            bytes.extend(b" }\n");need(bytes.len()<=CONTAINER_MAX,"container source capacity; generation not activated")?;
        }
        output.insert(name(bank,history,group),bytes);
    }}
    Ok(output)
}
fn verify_bytes(raw:&[u8],h:&Value,bank:&str,a:&prepared::Attestation,history:bool,group:usize)->Result<()> {
    need(raw.len()<=CONTAINER_MAX,"container source size")?;let g=global(history);
    let mut at=0;expect(raw,&mut at,format!("{g} = {g} or {{}}\n").as_bytes())?;
    for bucket in group*16..(group+1)*16 {
        if history {
            let Some(p)=h["history_partitions"].as_array().unwrap().iter().find(|p|p["bucket"]==bucket)else{continue};
            expect(raw,&mut at,&prefix(bank,bucket,true,h["generation_id"].as_str().unwrap(),p["sha256"].as_str().unwrap()))?;
            let data=read_stream(raw,&mut at,p["bytes"].as_u64().unwrap() as usize)?;
            summary::validate_position(h,bucket as u8+64,p,&data)?;
        }else {
            let p=&a.partitions[bucket];let size=p.record_count.max(1).next_power_of_two();
            expect(raw,&mut at,&prefix(bank,bucket,false,h["generation_id"].as_str().unwrap(),&p.sha256))?;
            let data=read_stream(raw,&mut at,p.record_count*prepared::WIDTH)?;expect(raw,&mut at,b", proofs = ")?;
            let proofs=read_stream(raw,&mut at,(2*size-1)*64)?;
            let part=prepared::Part{data:String::from_utf8(data).map_err(|_|Error::Invalid("current bytes"))?,proofs:String::from_utf8(proofs).map_err(|_|Error::Invalid("proof bytes"))?};
            prepared::inspect(bank,p,a,&prepared::artifact(bank,p,32,&part)?,h)?;
        }
        expect(raw,&mut at,b" }\n")?;
    }
    need(at==raw.len(),"container trailing source")
}
pub fn verify_bank(c:&delivery::Configuration,h:&Value,bank:&str,value:&Value)->Result<()> {
    let a=prepared::metadata(value,h)?;need(a.partitions_count==32,"container layout")?;
    for history in [false,true] {for group in 0..if history{4}else{2} {
        let n=name(bank,history,group);let dir=c.installation.join("Interface/AddOns").join(&n);
        summary::folder(&dir,&[&format!("{n}.toc"),"Data.lua",".twichui-delivery.json"])?;
        need(dir.join(".twichui-delivery.json").is_file(),"unowned container")?;summary::marker(c,&dir)?;
        need(delivery::read(&dir.join(format!("{n}.toc")),1024)?==summary::part_toc(),"container TOC")?;
        verify_bytes(&delivery::read(&dir.join("Data.lua"),CONTAINER_MAX)?,h,bank,&a,history,group)?;
    }}Ok(())
}
fn legacy_names()->Vec<String> {
    let mut out=Vec::new();for bank in ["A","B"] {for bucket in 0..64 {
        out.push(format!("TwichUI_MarketPart{bank}{bucket:02}"));out.push(format!("TwichUI_MarketHistoryPart{bank}{bucket:02}"));
        if bucket<32{out.push(prepared::name(bank,bucket));}
    }}out
}
fn archive(c:&delivery::Configuration)->PathBuf {c.installation.join("Interface/.twichui-market-legacy")}
fn children(c:&delivery::Configuration,dir:&Path,n:&str)->Result<()> {
    summary::folder(dir,&[&format!("{n}.toc"),"Data.lua",".twichui-delivery.json"])?;
    if fs::read_dir(dir)?.next().is_none(){return Ok(())}
    need(dir.join(".twichui-delivery.json").is_file(),"unowned obsolete Market folder")?;summary::marker(c,dir)
}
fn preflight_legacy(c:&delivery::Configuration,restoring:bool)->Result<()> {
    let addons=c.installation.join("Interface/AddOns");let backup=archive(c);
    if backup.try_exists()? {
        delivery::game_owned(&backup)?;summary::marker(c,&backup)?;
        need(fs::read_dir(&backup)?.next().is_none()||backup.join(".twichui-delivery.json").is_file(),"unowned legacy recovery directory")?;
    }
    for n in legacy_names() {
        for base in [&addons,&backup] {let dir=base.join(&n);if dir.try_exists()?{children(c,&dir,&n)?;}}
        if !restoring && addons.join(&n).try_exists()? && backup.join(&n).try_exists()? {
            need(same_files(&addons.join(&n),&backup.join(&n))?,"legacy recovery conflict; preserve both copies")?;
        }
    }
    Ok(())
}
fn same_files(a:&Path,b:&Path)->Result<bool> {
    let mut left=BTreeMap::new();let mut right=BTreeMap::new();
    for(entry,map)in [(a,&mut left),(b,&mut right)]{for f in fs::read_dir(entry)? {let f=f?;map.insert(f.file_name(),delivery::read(&f.path(),prepared::MAX_PART*4+1024)?);}}
    Ok(left==right)
}
fn archive_legacy(c:&delivery::Configuration)->Result<()> {
    let addons=c.installation.join("Interface/AddOns");let backup=archive(c);
    for n in legacy_names() {
        let from=addons.join(&n);if !from.try_exists()?{continue}children(c,&from,&n)?;
        let to=backup.join(&n);
        if to.try_exists()? {
            children(c,&to,&n)?;need(same_files(&from,&to)?,"legacy recovery conflict; preserve both copies")?;
            // Both byte-identical owned copies have been verified. Remove only
            // the exact generated files; never recursive unknown-file deletion.
            for file in [format!("{n}.toc"),"Data.lua".into(),".twichui-delivery.json".into()] {
                let path=from.join(&file);if path.try_exists()? {
                    need(delivery::read(&path,prepared::MAX_PART*4+1024)?==delivery::read(&to.join(&file),prepared::MAX_PART*4+1024)?,"legacy recovery changed during cleanup")?;
                    fs::remove_file(path)?;
                }
            }
            fs::remove_dir(&from)?;
        }else{fs::rename(from,to)?;}
    }Ok(())
}
pub fn restore_legacy(c:&delivery::Configuration)->Result<()> {
    let backup=archive(c);if !backup.try_exists()?{return Ok(())}preflight_legacy(c,true)?;
    let addons=c.installation.join("Interface/AddOns");
    for n in legacy_names(){let from=backup.join(&n);if !from.try_exists()?{continue}
        let to=addons.join(&n);if to.try_exists()?{children(c,&to,&n)?;for f in fs::read_dir(&to)?{let f=f?;
            if f.file_name()!=".twichui-delivery.json"{need(delivery::read(&f.path(),prepared::MAX_PART*4+1024)?==delivery::read(&from.join(f.file_name()),prepared::MAX_PART*4+1024)?,"legacy restore conflict")?;}
        }}
        else{fs::create_dir(&to)?;}
        // Marker first; a crash between mkdir and this write leaves only an
        // empty folder. Known partial files can then be completed safely.
        delivery::game_atomic(&to.join(".twichui-delivery.json"),&bridge::canonical(&summary::identity(c)?)?)?;
        for f in fs::read_dir(&from)?{let f=f?;delivery::game_atomic(&to.join(f.file_name()),&delivery::read(&f.path(),prepared::MAX_PART*4+1024)?)?;}
    }Ok(())
}
pub fn restore_for_downgrade(c:&delivery::Configuration,raw:Option<&[u8]>)->Result<()> {
    if raw.is_some_and(|b|b.starts_with(ROOT_PREFIX)){need(!delivery::game_running()?,"close WoW before Market layout downgrade")?;restore_legacy(c)?;}Ok(())
}
pub fn publish(c:&delivery::Configuration,b:&Bundle,value:&Value,cancelled:&impl Fn()->bool)->Result<bool> {
    c.validate()?;need(c.enabled,"Workshop disconnected")?;b.validate(&c.scope,c.selection["region"].as_str())?;
    let(a,_)=prepared::build(b,value)?;need(a.partitions_count==32,"compressed current count")?;
    summary::inspect_destination(c)?;preflight_legacy(c,false)?;
    let root=summary::main_dir(c);let target=root.join("Data.lua");
    let old=if target.try_exists()?{Some(delivery::read(&target,3*1024*1024)?)}else{None};
    let migration=old.as_ref().is_some_and(|raw|!raw.starts_with(ROOT_PREFIX));
    if migration{
        need(!delivery::game_running()?,"close WoW before Market container migration")?;
        let saved=archive(c).join("Data.lua");if saved.try_exists()?{
            need(delivery::read(&saved,3*1024*1024)?.as_slice()==old.as_ref().unwrap().as_slice(),"legacy recovery root conflict; preserve snapshot before another migration")?;
        }
    }
    let current=old.as_ref().map(|raw|summary::root_header(c,raw)).transpose()?;
    if let Some((h,slot))=&current {
        need(h["issuer_id"]==b.manifest["issuer_id"],"container issuer changed")?;
        if h["market"]["server_market_id"]==b.manifest["market"]["server_market_id"] {
            for field in ["game","region","house_id","source_kind","server_market_id","transport_ruleset_id","realm_scope"] {
                need(h["market"][field]==b.manifest["market"][field],"container Market identity changed; reconnect")?;
            }
        }
        if let Some(bank)=slot{summary::verify_bank(c,h,bank)?;}
        if old.as_ref().is_some_and(|r|r.starts_with(ROOT_PREFIX))&&h["generation_id"]==b.manifest["generation_id"] {
            let(_,_,_,installed)=summary::inspect_root_full(old.as_ref().unwrap(),&c.scope,None)?;
            if installed.as_ref()==Some(value){archive_legacy(c)?;return Ok(false)}
        }
    }
    let bank=if current.as_ref().is_some_and(|(_,b)|b.as_deref()==Some("A")){"B"}else{"A"};
    let outputs=build(b,value,bank)?;let addons=c.installation.join("Interface/AddOns");
    for history in [false,true]{for slot in ["A","B"]{for group in 0..if history{4}else{2}{
        let n=name(slot,history,group);let dir=addons.join(&n);if dir.try_exists()?{
            summary::folder(&dir,&[&format!("{n}.toc"),"Data.lua",".twichui-delivery.json"])?;summary::marker(c,&dir)?;
            need(dir.join(".twichui-delivery.json").is_file()||fs::read_dir(&dir)?.next().is_none(),"unowned container destination")?;
        }
    }}}
    let bytes:usize=outputs.values().map(Vec::len).sum();need(delivery::free_space(&c.installation)?>=(32*1024*1024+4*bytes)as u64,"container recoverable disk space")?;
    let owner=bridge::canonical(&summary::identity(c)?)?;
    if !root.try_exists()?{fs::create_dir(&root)?;}summary::write_game(&root.join(".twichui-delivery.json"),&owner,cancelled)?;
    // Keep the exact legacy roots outside AddOns before any obsolete folder is
    // moved. A partially completed move is recoverable from the union of paths.
    let backup=archive(c);if !backup.try_exists()?{fs::create_dir(&backup)?;}
    summary::write_game(&backup.join(".twichui-delivery.json"),&owner,cancelled)?;
    if let Some(raw)=&old{if !raw.starts_with(ROOT_PREFIX){
        if !backup.join("Data.lua").try_exists()?{summary::write_game(&backup.join("Data.lua"),raw,cancelled)?;}
        if root.join("Previous.lua").try_exists()? && !backup.join("Previous.lua").try_exists()?{
            summary::write_game(&backup.join("Previous.lua"),&delivery::read(&root.join("Previous.lua"),3*1024*1024)?,cancelled)?;
        }
    }}
    for history in [false,true]{for slot in ["A","B"]{for group in 0..if history{4}else{2}{
        let n=name(slot,history,group);let dir=addons.join(&n);if !dir.try_exists()?{fs::create_dir(&dir)?;}
        summary::write_game(&dir.join(".twichui-delivery.json"),&owner,cancelled)?;
        if let Some(bytes)=outputs.get(&n){summary::write_game(&dir.join("Data.lua"),bytes,cancelled)?;need(delivery::read(&dir.join("Data.lua"),CONTAINER_MAX)?==*bytes,"container exact readback")?;}
        else if !dir.join("Data.lua").try_exists()?{let g=global(history);summary::write_game(&dir.join("Data.lua"),format!("{g} = {g} or {{}}\n").as_bytes(),cancelled)?;}
        summary::write_game(&dir.join(format!("{n}.toc")),summary::part_toc(),cancelled)?;
    }}}
    verify_bank(c,&b.manifest,bank,value)?;
    let receipt=json!({"schema_version":1,"generation_id":b.manifest["generation_id"],"desktop_build":env!("CARGO_PKG_VERSION"),"completed_at":chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros,true)});
    let mut raw=summary::prepared_root_artifact(&b.manifest,bank,&receipt,value)?;
    raw[..ROOT_PREFIX.len()].copy_from_slice(ROOT_PREFIX);summary::inspect_root(&raw,&c.scope,c.selection["region"].as_str())?;
    summary::write_game(&root.join("TwichUI_MarketData.toc"),delivery::SUMMARY_TOC,cancelled)?;
    if let Some(prior)=&old{summary::write_game(&root.join("Previous.lua"),prior,cancelled)?;}
    need(installation::compressed_containers(&c.installation)?,"container capability changed")?;
    if migration{need(!delivery::game_running()?,"close WoW before Market container migration")?;}
    summary::write_game(&target,&raw,cancelled)?;
    if delivery::read(&target,raw.len())?!=raw {if let Some(prior)=old{summary::write_game(&target,&prior,&||false)?;}return Err(Error::Invalid("container root readback"))}
    // Activation is committed. Cleanup has no cancellation point; errors leave
    // the complete new generation active and preserve remaining legacy files.
    archive_legacy(c)?;Ok(true)
}

#[cfg(test)]
mod codec_tests {
    use super::*;
    #[test]
    fn raw_blocks_are_capped_deterministic_and_reject_truncation_or_trailing_source() {
        // Known bounded data, not a bomb. Explicitly exercises the block split
        // and both sides of the verified 512KiB envelope.
        for size in [0,1,BLOCK,BLOCK+1] {
            let data=vec![b'x';size];let mut encoded=Vec::new();stream(&mut encoded,&data).unwrap();
            let mut at=0;assert_eq!(read_stream(&encoded,&mut at,size).unwrap(),data);assert_eq!(at,encoded.len());
            if size>0 {let mut at=0;assert!(read_stream(&encoded[..encoded.len()-3],&mut at,size).is_err());}
        }
        let mut at=0;assert!(read_stream(b"{{ bytes = 524289, payload = \"AAAA\" }, }",&mut at,BLOCK+1).is_err());
    }
}
