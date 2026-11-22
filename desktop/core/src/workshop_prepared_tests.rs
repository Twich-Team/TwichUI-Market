// Included inside workshop_summary's existing test module to reuse its actual
// HTTP, scoped configuration and disposable publication fixtures.
fn prepared_fixture(count:usize)->Bundle {
    let v:Value=serde_json::from_str(include_str!("../../../contracts/workshop-prepared/v1/fixtures/synthetic.json")).unwrap();
    Bundle{manifest:v["manifest"].clone(),parts:v["parts"].as_object().unwrap().iter().map(|(k,v)|(k.parse().unwrap(),v.as_str().unwrap().as_bytes().to_vec())).collect(),prepared:Some(v["layouts"][count.to_string()]["attestation"].clone())}
}
fn prepared_next(b:&Bundle)->Bundle {
    let mut next=b.clone();next.manifest["source_watermark"]="999999".into();reseal(&mut next.manifest);
    let value=next.prepared.as_mut().unwrap();value["source_generation_id"]=next.manifest["generation_id"].clone();
    value.as_object_mut().unwrap().remove("attestation_id");value["attestation_id"]=sha(&bridge::canonical(value).unwrap()).into();next
}
#[cfg(unix)]
fn prepared_installation(c:&Configuration,count:usize) {
    installation(c);let dir=c.installation.join("Interface/AddOns/TwichUI_Workshop");
    let mut cap:Value=serde_json::from_slice(&fs::read(dir.join("MarketDelivery.json")).unwrap()).unwrap();
    for (key,value) in [("summary_current_contract",3),("summary_current_partition_bytes",1048576),("summary_current_total_bytes",33554432),
        ("summary_history_contract",2),("summary_history_partition_bytes",1048576),("summary_history_total_bytes",67108864),
        ("prepared_current_version",1),("prepared_current_partitions",count),("prepared_current_part_bytes",4194304),("prepared_current_total_bytes",33554432)] {cap[key]=json!(value);}
    fs::write(dir.join("MarketDelivery.json"),bridge::canonical(&cap).unwrap()).unwrap();
    fs::write(dir.join("Prepared.lua"),b"-- Synthetic reader capability fixture\n").unwrap();
    fs::write(dir.join("TwichUI_Workshop.toc"),b"## Interface: 16001\nPrepared.lua\nSummary.lua\nBridge.lua\n").unwrap();
}
#[test]
fn prepared_native_matches_authoritative_python_vectors_and_refuses_source_injection() {
    let vector:Value=serde_json::from_str(include_str!("../../../contracts/workshop-prepared/v1/fixtures/synthetic.json")).unwrap();
    for count in [16,32] {
        let b=prepared_fixture(count);let d=tempfile::tempdir().unwrap();let c=config(d.path(),&b);b.validate(&c.scope,Some("us")).unwrap();
        let (a,parts)=crate::workshop_prepared::build(&b,b.prepared.as_ref().unwrap()).unwrap();
        for p in &a.partitions {
            let part=&parts[&(p.bucket as u8)];let expected=&vector["layouts"][count.to_string()]["payloads"][p.bucket.to_string()];
            assert_eq!(part.data,expected[0]);assert_eq!(part.proofs,expected[1]);
            let bytes=crate::workshop_prepared::artifact("A",p,count,part).unwrap();
            crate::workshop_prepared::inspect("A",p,&a,&bytes,&b.manifest).unwrap();
            let mut injected=bytes.clone();injected.extend(b"os.execute('untrusted')\n");
            assert!(crate::workshop_prepared::inspect("A",p,&a,&injected,&b.manifest).is_err());
            if p.record_count>0 {
                let mut damaged=part.clone();damaged.data.replace_range(73..83,"0000000001");
                let bytes=crate::workshop_prepared::artifact("A",p,count,&damaged).unwrap();
                assert!(crate::workshop_prepared::inspect("A",p,&a,&bytes,&b.manifest).is_err());
            }
        }
    }
}
#[test]
fn prepared_metadata_and_source_cannot_be_rehashed_into_different_prices_or_false_counts() {
    let b=prepared_fixture(16);
    for mutation in 0..5 {
        let mut next=b.clone();let a=next.prepared.as_mut().unwrap();
        match mutation {0=>a["source_generation_id"]="f".repeat(64).into(),1=>a["record_count"]=999.into(),
            2=>a["partitions"][0]["record_count"]=1.into(),3=>a["partitions"][13]["merkle_root"]="f".repeat(64).into(),
            _=>a["unexpected"]=true.into()};
        a.as_object_mut().unwrap().remove("attestation_id");a["attestation_id"]=sha(&bridge::canonical(a).unwrap()).into();
        let value=a.clone();assert!(crate::workshop_prepared::build(&next,&value).is_err(),"mutation {mutation}");
    }
    let mut changed=b.clone();changed.parts.values_mut().next().unwrap().push(b' ');
    assert!(crate::workshop_prepared::build(&changed,changed.prepared.as_ref().unwrap()).is_err());
    let next=prepared_next(&b);
    let (_,old)=crate::workshop_prepared::build(&b,b.prepared.as_ref().unwrap()).unwrap();
    let (_,new)=crate::workshop_prepared::build(&next,next.prepared.as_ref().unwrap()).unwrap();assert_eq!(old,new);
}
#[cfg(unix)]
#[test]
fn prepared_atomic_publication_noop_corruption_ownership_and_legacy_downgrade() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(16);let c=config(d.path(),&b);prepared_installation(&c,16);
    assert!(publish(&c,&b,&||false).unwrap());let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();
    assert!(before.starts_with(crate::workshop_prepared::ROOT_PREFIX));verify_bank(&c,&b.manifest,"A").unwrap();
    assert!(!c.installation.join("Interface/AddOns/TwichUI_MarketPartA29").exists());
    assert!(!publish(&c,&b,&||false).unwrap());
    let file=c.installation.join("Interface/AddOns/TwichUI_MarketCurrentPartA13/Data.lua");let bytes=fs::read(&file).unwrap();
    fs::write(&file,b"invalid").unwrap();assert!(publish(&c,&b,&||false).is_err());assert_eq!(fs::read(&root).unwrap(),before);
    fs::write(&file,bytes).unwrap();
    let dir=c.installation.join("Interface/AddOns/TwichUI_Workshop");let mut cap:Value=serde_json::from_slice(&fs::read(dir.join("MarketDelivery.json")).unwrap()).unwrap();
    for key in ["prepared_current_version","prepared_current_partitions","prepared_current_part_bytes","prepared_current_total_bytes"] {cap.as_object_mut().unwrap().remove(key);}
    fs::write(dir.join("MarketDelivery.json"),bridge::canonical(&cap).unwrap()).unwrap();
    assert!(publish(&c,&b,&||false).unwrap());let raw=fs::read(&root).unwrap();assert!(raw.starts_with(ROOT_PREFIX));
    let (_,bank,_)=inspect_root(&raw,&c.scope,Some("us")).unwrap();verify_source_bank(&c,&b.manifest,&bank,false).unwrap();
    assert!(rollback(&c).is_err(),"legacy addon restored incompatible prepared root");
    assert_eq!(fs::read(&root).unwrap(),raw);
}
#[cfg(unix)]
#[test]
fn prepared_cancelled_publication_keeps_last_good_and_supports_layout_switch_rollback() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(16);let c=config(d.path(),&b);prepared_installation(&c,16);
    publish(&c,&b,&||false).unwrap();let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();let next=prepared_next(&b);
    for stop in [0,2,6,16,32,48] {
        let n=AtomicUsize::new(0);assert!(publish(&c,&next,&||n.fetch_add(1,Ordering::SeqCst)>=stop).is_err());
        assert_eq!(fs::read(&root).unwrap(),before);verify_bank(&c,&b.manifest,"A").unwrap();
    }
    publish(&c,&next,&||false).unwrap();rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),before);
    prepared_installation(&c,32);let newer=prepared_fixture(32);publish(&c,&newer,&||false).unwrap();
    rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),before);
}
#[cfg(unix)]
#[test]
fn prepared_http_negotiation_validated_cache_reuse_and_unavailable_legacy_fallback() {
    for unavailable in [false,true] {
        let d=tempfile::tempdir().unwrap();let b=prepared_fixture(16);let mut c=config(d.path(),&b);prepared_installation(&c,16);
        let mut responses=vec![(200,envelope(&b,1),false)];
        for (key,_) in part_specs(&b.manifest) {responses.push((200,b.parts[&key].clone(),false));}
        responses.push(if unavailable {(404,b"{}".to_vec(),false)}else{(200,serde_json::to_vec(&json!({"account_id":1,"attestation":b.prepared})).unwrap(),false)});
        if !unavailable {responses.push((304,vec![],false));}
        let (origin,task,requests)=serve(responses);c.scope.server=origin;
        let client=MarketClient::new(&c.scope.server,"synthetic-workshop-connection".into()).unwrap();
        let (received,_,queries)=download(d.path(),&client,&c,&||false).unwrap();assert_eq!(queries as usize,2+b.parts.len());
        assert_eq!(received.prepared.is_some(),!unavailable);publish(&c,&received,&||false).unwrap();
        if !unavailable {let (_,bytes,count)=download(d.path(),&client,&c,&||false).unwrap();assert_eq!((bytes,count),(0,1));}
        task.join().unwrap();let seen=requests.lock().unwrap();assert!(seen.iter().any(|r|r.contains("/prepared/1/16")));
        assert_eq!(seen.iter().filter(|r|r.contains("/prepared/1/")).count(),1);
    }
}
#[cfg(unix)]
#[test]
fn prepared_unknown_files_wrong_accounts_and_mid_publication_capability_changes_preserve_root() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(16);let c=config(d.path(),&b);prepared_installation(&c,16);
    publish(&c,&b,&||false).unwrap();let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();let next=prepared_next(&b);
    let dir=c.installation.join("Interface/AddOns/TwichUI_MarketCurrentPartB13");fs::create_dir(&dir).unwrap();fs::write(dir.join("unrelated.lua"),b"keep").unwrap();
    assert!(publish(&c,&next,&||false).is_err());assert_eq!(fs::read(&root).unwrap(),before);assert_eq!(fs::read(dir.join("unrelated.lua")).unwrap(),b"keep");
    fs::remove_file(dir.join("unrelated.lua")).unwrap();fs::remove_dir(dir).unwrap();
    let mut other=c.clone();other.scope.account_id+=1;assert!(publish(&other,&next,&||false).is_err());
    let n=AtomicUsize::new(0);let cap=c.installation.join("Interface/AddOns/TwichUI_Workshop/MarketDelivery.json");
    assert!(publish(&c,&next,&||{if n.fetch_add(1,Ordering::SeqCst)==2 {
        let mut value:Value=serde_json::from_slice(&fs::read(&cap).unwrap()).unwrap();value["prepared_current_partitions"]=32.into();
        fs::write(&cap,bridge::canonical(&value).unwrap()).unwrap();
    }false}).is_err());assert_eq!(fs::read(&root).unwrap(),before);
}
