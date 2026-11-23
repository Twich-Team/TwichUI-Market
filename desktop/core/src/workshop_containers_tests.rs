// Uses the existing disposable publication fixtures, never installed user files.
#[cfg(unix)]
fn containers_installation(c:&Configuration) {
    prepared_installation(c,32);let dir=c.installation.join("Interface/AddOns/TwichUI_Workshop");
    let mut cap:Value=serde_json::from_slice(&fs::read(dir.join("MarketDelivery.json")).unwrap()).unwrap();
    for(k,v)in [("container_packaging_version",json!(1)),("container_codec",json!("raw-deflate-base64")),
        ("container_block_bytes",json!(524288)),("current_containers",json!(2)),("history_containers",json!(4))]{cap[k]=v;}
    fs::write(dir.join("MarketDelivery.json"),bridge::canonical(&cap).unwrap()).unwrap();
    fs::write(dir.join("Containers.lua"),b"-- Synthetic capability file\n").unwrap();
    fs::write(dir.join("TwichUI_Workshop.toc"),b"## Interface: 16001\nContainers.lua\nPrepared.lua\nSummary.lua\nBridge.lua\n").unwrap();
}
#[test]
fn containers_external_format_exact_source_and_malformed_refusal() {
    let b=prepared_fixture(32);let value=b.prepared.as_ref().unwrap();
    let first=crate::workshop_containers::build(&b,value,"A").unwrap();
    assert_eq!(first,crate::workshop_containers::build(&b,value,"A").unwrap());assert_eq!(first.len(),6);
    assert!(crate::workshop_containers::build(&prepared_fixture(16),prepared_fixture(16).prepared.as_ref().unwrap(),"A").is_err());
}
#[cfg(unix)]
fn market_folder_count(c:&Configuration)->usize {
    fs::read_dir(c.installation.join("Interface/AddOns")).unwrap().filter(|e|e.as_ref().unwrap().file_name().to_string_lossy().starts_with("TwichUI_Market")).count()
}
#[cfg(unix)]
#[test]
fn containers_fresh_thirteen_banks_noop_corruption_and_safe_rollback() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);containers_installation(&c);
    assert!(publish(&c,&b,&||false).unwrap());assert_eq!(market_folder_count(&c),13);
    let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();assert!(before.starts_with(crate::workshop_containers::ROOT_PREFIX));
    verify_bank(&c,&b.manifest,"A").unwrap();assert!(!publish(&c,&b,&||false).unwrap());
    let mut unavailable=b.clone();unavailable.prepared=None;assert!(matches!(publish(&c,&unavailable,&||false),Err(Error::PreparedUnavailable)));
    assert_eq!(fs::read(&root).unwrap(),before);assert_eq!(market_folder_count(&c),13);
    let next=prepared_next(&b);publish(&c,&next,&||false).unwrap();verify_bank(&c,&next.manifest,"B").unwrap();
    rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),before);assert_eq!(market_folder_count(&c),13);
    let data=c.installation.join("Interface/AddOns/TwichUI_MarketCurrentContainerA01/Data.lua");let original=fs::read(&data).unwrap();
    for damaged in [b"invalid".to_vec(),[original.clone(),b"os.execute('untrusted')".to_vec()].concat()] {
        fs::write(&data,damaged).unwrap();assert!(publish(&c,&next,&||false).is_err());assert_eq!(fs::read(&root).unwrap(),before);
    }
    fs::write(data,original).unwrap();
}
#[cfg(unix)]
#[test]
fn containers_interrupted_writes_resume_with_unchanged_active_generation() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);containers_installation(&c);
    publish(&c,&b,&||false).unwrap();let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();let next=prepared_next(&b);
    let probe=tempfile::tempdir().unwrap();let pc=config(probe.path(),&b);containers_installation(&pc);publish(&pc,&b,&||false).unwrap();
    let points=AtomicUsize::new(0);publish(&pc,&next,&||{points.fetch_add(1,Ordering::SeqCst);false}).unwrap();
    // Every actual cancellation point, not a guessed count beyond activation.
    for stop in 0..points.load(Ordering::SeqCst) {
        let n=AtomicUsize::new(0);assert!(publish(&c,&next,&||n.fetch_add(1,Ordering::SeqCst)>=stop).is_err());
        assert_eq!(fs::read(&root).unwrap(),before);verify_bank(&c,&b.manifest,"A").unwrap();
    }
    assert!(publish(&c,&next,&||false).unwrap());assert_eq!(market_folder_count(&c),13);
}
#[cfg(unix)]
#[test]
fn containers_migration_preserves_257_owned_folders_and_downgrade_bytes() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);prepared_installation(&c,32);
    // Existing Contract 3 (pre-prepared) installation, padded with inactive
    // owned folders to exercise the full former 257 physical-addon footprint.
    let mut legacy=b.clone();legacy.prepared=None;publish(&c,&legacy,&||false).unwrap();
    let addons=c.installation.join("Interface/AddOns");let owner=bridge::canonical(&identity(&c).unwrap()).unwrap();
    for slot in ["A","B"]{for b in 0..128{let n=part_name(slot,b);let dir=addons.join(&n);if !dir.exists(){fs::create_dir(&dir).unwrap();
        fs::write(dir.join(".twichui-delivery.json"),&owner).unwrap();fs::write(dir.join(format!("{n}.toc")),part_toc()).unwrap();fs::write(dir.join("Data.lua"),b"-- retained inactive bytes\n").unwrap();
    }}}
    assert_eq!(market_folder_count(&c),257);
    let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();containers_installation(&c);
    assert!(publish(&c,&b,&||false).unwrap());assert_eq!(market_folder_count(&c),13);
    assert_eq!(fs::read(c.installation.join("Interface/.twichui-market-legacy/Data.lua")).unwrap(),before);
    rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),before);verify_bank(&c,&b.manifest,"A").unwrap();
    assert_eq!(fs::read(addons.join("TwichUI_MarketPartB63/Data.lua")).unwrap(),b"-- retained inactive bytes\n");
    publish(&c,&b,&||false).unwrap();assert_eq!(market_folder_count(&c),13);
    // A legacy addon with this Companion safely gets legacy publication, while
    // its compatible previous compressed generation cannot be reactivated.
    prepared_installation(&c,32);publish(&c,&b,&||false).unwrap();assert!(fs::read(&root).unwrap().starts_with(crate::workshop_prepared::ROOT_PREFIX));
    let committed=fs::read(&root).unwrap();assert!(rollback(&c).is_err());assert_eq!(fs::read(&root).unwrap(),committed);
}
#[cfg(unix)]
#[test]
fn containers_preflight_refuses_unrelated_or_wrong_owner_before_activation() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);prepared_installation(&c,32);publish(&c,&b,&||false).unwrap();
    let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();
    let unknown=c.installation.join("Interface/AddOns/TwichUI_MarketCurrentPartA13/unrelated.txt");fs::write(&unknown,b"keep").unwrap();containers_installation(&c);
    assert!(publish(&c,&b,&||false).is_err());assert_eq!(fs::read(&unknown).unwrap(),b"keep");assert_eq!(fs::read(&root).unwrap(),before);
    fs::remove_file(unknown).unwrap();let mut other=c.clone();other.scope.account_id+=1;assert!(publish(&other,&b,&||false).is_err());assert_eq!(fs::read(&root).unwrap(),before);
}
#[cfg(unix)]
#[test]
fn containers_prepared_193_migration_and_partial_move_restore_are_resumable() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);prepared_installation(&c,32);publish(&c,&b,&||false).unwrap();
    let addons=c.installation.join("Interface/AddOns");let owner=bridge::canonical(&identity(&c).unwrap()).unwrap();
    for slot in ["A","B"]{for history in [false,true]{for bucket in 0..if history{64}else{32}{
        let n=if history{part_name(slot,bucket+64)}else{crate::workshop_prepared::name(slot,bucket)};let dir=addons.join(&n);
        if !dir.exists(){fs::create_dir(&dir).unwrap();fs::write(dir.join(".twichui-delivery.json"),&owner).unwrap();
            fs::write(dir.join(format!("{n}.toc")),part_toc()).unwrap();fs::write(dir.join("Data.lua"),b"-- inactive retained fixture\n").unwrap();}
    }}}
    assert_eq!(market_folder_count(&c),193);let root=main_dir(&c).join("Data.lua");let old=fs::read(&root).unwrap();
    containers_installation(&c);publish(&c,&b,&||false).unwrap();assert_eq!(market_folder_count(&c),13);
    let recovery=c.installation.join("Interface/.twichui-market-legacy");
    // Recreate a crash between individual post-activation folder moves. Resume
    // finishes cleanup before the no-op result, with all snapshot bytes intact.
    let n="TwichUI_MarketCurrentPartA13";fs::rename(recovery.join(n),addons.join(n)).unwrap();
    assert!(!publish(&c,&b,&||false).unwrap());assert_eq!(market_folder_count(&c),13);
    // Recreate a partial restore after mkdir/marker. Restoration completes only
    // matching known files, never adopting an unrelated preexisting payload.
    let target=addons.join(n);fs::create_dir(&target).unwrap();fs::write(target.join(".twichui-delivery.json"),&owner).unwrap();
    rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),old);verify_bank(&c,&b.manifest,"A").unwrap();
    assert_eq!(fs::read(target.join("Data.lua")).unwrap(),fs::read(recovery.join(n).join("Data.lua")).unwrap());
}

#[cfg(unix)]
#[test]
fn containers_confirmed_market_switch_and_previous_market_rollback_keep_exact_identity() {
    let d=tempfile::tempdir().unwrap();let b=prepared_fixture(32);let c=config(d.path(),&b);containers_installation(&c);publish(&c,&b,&||false).unwrap();
    let root=main_dir(&c).join("Data.lua");let before=fs::read(&root).unwrap();let mut next=b.clone();
    next.manifest["market"]["server_market_id"]=json!(c.scope.market_id+1);reseal(&mut next.manifest);
    let a=next.prepared.as_mut().unwrap();a["source_generation_id"]=next.manifest["generation_id"].clone();
    a.as_object_mut().unwrap().remove("attestation_id");a["attestation_id"]=sha(&bridge::canonical(a).unwrap()).into();
    let mut selected=c.clone();selected.scope.market_id+=1;selected.selection["market_id"]=json!(selected.scope.market_id);
    publish(&selected,&next,&||false).unwrap();let active=fs::read(&root).unwrap();assert!(rollback(&selected).is_err());assert_eq!(fs::read(&root).unwrap(),active);
    rollback(&c).unwrap();assert_eq!(fs::read(&root).unwrap(),before);
}
