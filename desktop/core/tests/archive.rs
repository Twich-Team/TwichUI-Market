use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use twichui_market_core::{
    archive::{normalize_selection, project, validate_scoped, ArchiveStore, DeliveryBudget},
    bridge::{self, Scope},
    Error,
};
fn encoded(v: &Value) -> Vec<u8> {
    bridge::canonical(v).unwrap()
}
fn sha(v: &Value) -> String {
    format!("{:x}", Sha256::digest(encoded(v)))
}
fn scope() -> Scope {
    Scope {
        server: "http://127.0.0.1:43321/".into(),
        account_id: 1,
        market_id: 2,
        algorithm: "twichui-pricing-v1".into(),
    }
}
fn source() -> Value {
    serde_json::from_str(include_str!(
        "../../../contracts/bridge/v1/source-canonical-generation.json"
    ))
    .unwrap()
}
fn fixture(cp: &str) -> (Value, Vec<Value>, Value) {
    let g = source();
    let obs = g["observations"]
        .as_array()
        .unwrap()
        .iter()
        .map(|o| json!({"kind":"observation","observation":o}))
        .collect::<Vec<_>>();
    let mut snapshots = Vec::new();
    let mut variants = Vec::new();
    for (i, o) in g["observations"].as_array().unwrap().iter().enumerate() {
        let sid = o["snapshot_id"].as_str().unwrap();
        let mut group = Vec::new();
        for r in g["records"].as_array().unwrap() {
            if let Some(d) = r["daily"]
                .as_array()
                .unwrap()
                .iter()
                .find(|d| d["observation_ref"] == i && d["state"] == "listed")
            {
                group.push(json!({"kind":"variant","snapshot_id":sid,"item_id":r["item_id"],"variant_key":r["variant_key"],
                    "value":{"variant_json":r["variant_json"],"summary":{"state":if d["priced_supply"]==0{"unpriced"}else{"priced"},
                        "supply":d["supply"],"priced_supply":d["priced_supply"],"listing_count":d["listing_count"],
                        "minimum_listing_copper":d["minimum_copper"],"recent_copper":d["recent_copper"],"quantity_weighted_ask_copper":d["recent_copper"]}}}));
            }
        }
        let raw = group
            .iter()
            .flat_map(|v| {
                let mut r = encoded(v);
                r.push(b'\n');
                r
            })
            .collect::<Vec<_>>();
        snapshots.push(json!({"kind":"snapshot","snapshot_id":sid,"content_sha256":o["snapshot_content_sha256"],"record_count":group.len(),"records_sha256":format!("{:x}",Sha256::digest(&raw)),"records_bytes":raw.len()}));
        variants.extend(group);
    }
    let meta = obs
        .iter()
        .chain(&snapshots)
        .flat_map(|v| {
            let mut r = encoded(v);
            r.push(b'\n');
            r
        })
        .collect::<Vec<_>>();
    let entries = obs
        .iter()
        .chain(&snapshots)
        .chain(&variants)
        .cloned()
        .collect::<Vec<_>>();
    let header = json!({"format":"twichui-history-archive","protocol_version":1,"checkpoint_id":cp.repeat(64),"account_id":1,
        "issuer_id":g["issuer_id"],"market":g["market"],"pricing_algorithm":g["pricing_algorithm"],"history_basis":g["history_basis"],"evidence_revision":1,
        "watermark_observation_id":g["watermark_observation_id"],"base_checkpoint_id":null,"base_watermark_observation_id":"0",
        "generated_at":g["generated_at"],"expires_at":"2026-11-16T12:02:00Z","server_checked_at":g["server_checked_at"],"server_build":"synthetic-archive",
        "retention_basis":"all_retained_observations_and_snapshot_summaries","archive_complete":true,
        "total_observations":obs.len(),"total_snapshots":snapshots.len(),"total_records":variants.len(),"transfer_observations":obs.len(),"transfer_snapshots":snapshots.len(),"transfer_records":variants.len(),
        "transfer_bytes":entries.iter().map(|v|encoded(v).len()+1).sum::<usize>(),"metadata_sha256":format!("{:x}",Sha256::digest(meta))});
    let mut pages = Vec::new();
    let mut chain = vec![0u8; 32];
    let mut offset = 0;
    for (i, part) in entries.chunks(2).enumerate() {
        let value = Value::Array(part.to_vec());
        let prev = format!("{:x}", Hex(&chain));
        let mut h = Sha256::new();
        h.update(&chain);
        h.update(encoded(&value));
        chain = h.finalize().to_vec();
        let more = offset + part.len() < entries.len();
        pages.push(json!({"format":"twichui-history-archive-page","protocol_version":1,"checkpoint_id":header["checkpoint_id"],"account_id":1,"market_id":2,
            "offset":offset,"entries":value,"previous_sha256":prev,"page_sha256":sha(&value),"chain_sha256":format!("{:x}",Hex(&chain)),
            "has_more":more,"next_cursor":if more{Some(format!("page{}",i+1))}else{None}}));
        offset += part.len();
    }
    let request = json!({"format":"twichui-market-selection","contract_version":1,"expected_schema_version":3,"issuer_id":g["issuer_id"],"market":g["market"],"scope_type":"explicit_variants",
        "variants":g["records"].as_array().unwrap().iter().map(|r|json!({"item_id":r["item_id"],"variant_key":r["variant_key"]})).collect::<Vec<_>>(),
        "history_from_day":"2026-11-14","history_through_day":"2026-11-15","pricing_algorithm":"twichui-pricing-v1","history_basis":"canonical_complete_scope_close","profile":"daily_research_v1"});
    (json!({"header":header,"cursor":"page0"}), pages, request)
}
struct Hex<'a>(&'a [u8]);
impl std::fmt::LowerHex for Hex<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        for b in self.0 {
            write!(f, "{b:02x}")?;
        }
        Ok(())
    }
}
fn accept(s: &mut ArchiveStore, e: &Value, pages: &[Value]) {
    s.begin(&scope(), &encoded(e)).unwrap();
    for (i, p) in pages.iter().enumerate() {
        assert_eq!(
            s.apply(&scope(), &format!("page{i}"), &encoded(p)).unwrap(),
            i + 1 < pages.len()
        );
    }
}
#[test]
fn actual_l1_contract_fixtures_and_negative_membership() {
    for name in [
        "scoped.json",
        "unknown-scoped.json",
        "short-window-scoped.json",
        "large-money-scoped.json",
    ] {
        let p = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../contracts/bridge/scoped-l1/fixtures")
            .join(name);
        let g: Value = serde_json::from_slice(&std::fs::read(p).unwrap()).unwrap();
        validate_scoped(&g, None).unwrap();
        assert!(
            bridge::validate(&g).is_err(),
            "legacy reader accepted scoped subset"
        );
        let mut bad = g.clone();
        bad["generation_id"] = "0".repeat(64).into();
        assert!(validate_scoped(&bad, None).is_err());
    }
}
#[test]
fn interrupted_bootstrap_resume_exact_projection_and_publication() {
    let d = tempfile::tempdir().unwrap();
    let path = d.path().join("archive.sqlite");
    let (e, pages, request) = fixture("1");
    let mut s = ArchiveStore::open(&path, 64 * 1024 * 1024).unwrap();
    s.begin(&scope(), &encoded(&e)).unwrap();
    assert!(s.apply(&scope(), "page0", &encoded(&pages[0])).unwrap());
    assert!(s.active(&scope()).unwrap().is_none());
    drop(s);
    let mut s = ArchiveStore::open(&path, 64 * 1024 * 1024).unwrap();
    assert_eq!(s.pending(&scope()).unwrap().unwrap().1, "page1");
    assert!(
        s.apply(&scope(), "page0", &encoded(&pages[0])).is_err(),
        "duplicate page advanced"
    );
    for (i, p) in pages.iter().enumerate().skip(1) {
        s.apply(&scope(), &format!("page{i}"), &encoded(p)).unwrap();
    }
    let (g, r, sizes) = project(&s, &scope(), &request, &DeliveryBudget::default()).unwrap();
    assert_eq!(g["records"][0]["current"]["state"], "absent");
    assert_eq!(g["records"][0]["daily"][0]["recent_copper"], "50");
    let priced = g["records"]
        .as_array()
        .unwrap()
        .iter()
        .find(|v| v["item_id"] == 2589)
        .unwrap();
    assert_eq!(priced["current"]["metrics"]["recent_copper"], "120");
    assert!(!g["coverage"]["generation_complete"].as_bool().unwrap());
    assert_eq!(g["scope"]["scope_complete"], true);
    let root = bridge::staging_directory(d.path(), &scope()).unwrap();
    let out =
        bridge::export_generation(&scope(), &root, &g, &r, &DeliveryBudget::default()).unwrap();
    let raw = std::fs::read(&out).unwrap();
    assert_eq!(raw.len() as u64, sizes.lua_bytes);
    assert_eq!(bridge::inspect_artifact(&raw).unwrap().0, g);
    let before = raw;
    let tiny = DeliveryBudget {
        canonical_bytes: 1,
        ..DeliveryBudget::default()
    };
    assert!(matches!(
        project(&s, &scope(), &request, &tiny),
        Err(Error::Capacity { .. })
    ));
    assert_eq!(std::fs::read(out).unwrap(), before);
    s.save_selection(&scope(), &request).unwrap();
    assert_eq!(s.selection(&scope()).unwrap().unwrap(), request);
}
#[test]
fn failed_candidate_and_disk_budget_preserve_previous_archive() {
    let mut s = ArchiveStore::memory(64 * 1024 * 1024).unwrap();
    let (e, pages, request) = fixture("1");
    accept(&mut s, &e, &pages);
    let (first, _, _) = project(&s, &scope(), &request, &DeliveryBudget::default()).unwrap();
    let (new, np, _) = fixture("2");
    s.begin(&scope(), &encoded(&new)).unwrap();
    let mut corrupt = np[0].clone();
    corrupt["chain_sha256"] = "0".repeat(64).into();
    assert!(s.apply(&scope(), "page0", &encoded(&corrupt)).is_err());
    assert_eq!(
        s.active(&scope()).unwrap().unwrap().checkpoint_id,
        "1".repeat(64)
    );
    assert_eq!(
        project(&s, &scope(), &request, &DeliveryBudget::default())
            .unwrap()
            .0,
        first
    );
    s.abandon_pending(&scope()).unwrap();
    accept(&mut s, &new, &np);
    assert_eq!(
        s.previous(&scope()).unwrap().unwrap().checkpoint_id,
        "1".repeat(64)
    );
    let mut tiny = ArchiveStore::memory(65536).unwrap();
    let mut large = e.clone();
    large["header"]["transfer_bytes"] = 65536.into();
    assert!(matches!(
        tiny.begin(&scope(), &encoded(&large)),
        Err(Error::Capacity { .. })
    ));
}
#[test]
fn unknown_future_wrong_scope_selection_and_cache_corruption_refuse() {
    let d = tempfile::tempdir().unwrap();
    let path = d.path().join("history.sqlite");
    let (e, pages, mut request) = fixture("1");
    let mut s = ArchiveStore::open(&path, 64 * 1024 * 1024).unwrap();
    let mut bad = e.clone();
    bad["header"]["protocol_version"] = 2.into();
    assert!(s.begin(&scope(), &encoded(&bad)).is_err());
    bad = e.clone();
    bad["header"]["account_id"] = 2.into();
    assert!(s.begin(&scope(), &encoded(&bad)).is_err());
    accept(&mut s, &e, &pages);
    request["variants"].as_array_mut().unwrap().reverse();
    let normalized = normalize_selection(request.clone()).unwrap();
    assert!(project(&s, &scope(), &request, &DeliveryBudget::default()).is_err());
    request = normalized;
    let duplicate = request["variants"][0].clone();
    request["variants"].as_array_mut().unwrap().push(duplicate);
    assert!(normalize_selection(request).is_err());
    let db = rusqlite::Connection::open(&path).unwrap();
    db.execute("UPDATE history_entries SET value='{}' WHERE phase=2", [])
        .unwrap();
    let (_, _, request) = fixture("1");
    assert!(project(&s, &scope(), &request, &DeliveryBudget::default()).is_err());
}

// Independently reseal test transport envelopes after altering synthetic source
// metadata. Does not invoke either production producer or reader hash routines.
fn repack(mut envelope: Value, entries: Vec<Value>) -> (Value, Vec<Value>) {
    let h = &mut envelope["header"];
    for (kind, total, transfer) in [
        ("observation", "total_observations", "transfer_observations"),
        ("snapshot", "total_snapshots", "transfer_snapshots"),
        ("variant", "total_records", "transfer_records"),
    ] {
        let n = entries.iter().filter(|e| e["kind"] == kind).count();
        h[total] = n.into();
        h[transfer] = n.into();
    }
    h["transfer_bytes"] = entries
        .iter()
        .map(|v| encoded(v).len() + 1)
        .sum::<usize>()
        .into();
    h["metadata_sha256"] = format!(
        "{:x}",
        Sha256::digest(
            entries
                .iter()
                .filter(|e| e["kind"] != "variant")
                .flat_map(|v| {
                    let mut x = encoded(v);
                    x.push(b'\n');
                    x
                })
                .collect::<Vec<_>>()
        )
    )
    .into();
    let v = Value::Array(entries);
    let mut hasher = Sha256::new();
    hasher.update([0u8; 32]);
    hasher.update(encoded(&v));
    let p = json!({"format":"twichui-history-archive-page","protocol_version":1,"checkpoint_id":h["checkpoint_id"],"account_id":1,"market_id":2,"offset":0,
        "entries":v,"previous_sha256":"0".repeat(64),"page_sha256":sha(&v),"chain_sha256":format!("{:x}",hasher.finalize()),"has_more":false,"next_cursor":null});
    (envelope, vec![p])
}
#[test]
fn full_rebootstrap_after_source_retention_keeps_previous_evidence_separate() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("archive.sqlite");
    let mut s = ArchiveStore::open(&path, 64 * 1024 * 1024).unwrap();
    let (e, pages, request) = fixture("1");
    accept(&mut s, &e, &pages);
    let db = rusqlite::Connection::open(&path).unwrap();
    let before: i64 = db
        .query_row("SELECT count(*) FROM history_entries", [], |r| r.get(0))
        .unwrap();
    let (new, np, _) = fixture("2");
    let entries = np
        .iter()
        .flat_map(|p| p["entries"].as_array().unwrap().clone())
        .collect::<Vec<_>>();
    let sid = entries.iter().find(|e| e["kind"] == "observation").unwrap()["observation"]
        ["snapshot_id"]
        .clone();
    let oid = entries.iter().find(|e| e["kind"] == "observation").unwrap()["observation"]
        ["observation_id"]
        .clone();
    let entries = entries
        .into_iter()
        .filter(|e| {
            if e["kind"] == "observation" {
                e["observation"]["observation_id"] != oid
            } else {
                e["snapshot_id"] != sid
            }
        })
        .collect();
    let (new, np) = repack(new, entries);
    accept(&mut s, &new, &np);
    assert_eq!(
        s.previous(&scope()).unwrap().unwrap().checkpoint_id,
        "1".repeat(64)
    );
    let after: i64 = db
        .query_row("SELECT count(*) FROM history_entries", [], |r| r.get(0))
        .unwrap();
    assert_eq!(before, after, "complete old evidence was deleted");
    assert!(
        project(&s, &scope(), &request, &DeliveryBudget::default()).is_err(),
        "unretained identity must not be satisfied from another checkpoint"
    );
    let mut bounded = request.clone();
    bounded["variants"]
        .as_array_mut()
        .unwrap()
        .retain(|r| r["item_id"] == 2589);
    let (g, _, _) = project(&s, &scope(), &bounded, &DeliveryBudget::default()).unwrap();
    assert_eq!(g["observations"].as_array().unwrap().len(), 1);
    assert_eq!(
        g["scope"]["date_coverage"][0]["state"], "no_observation",
        "pruned source evidence leaked into the new checkpoint"
    );
    assert_eq!(g["records"][0]["identity_basis"], "exact_upstream");
}
#[test]
fn incomplete_observation_stays_unknown_and_deleted_cache_row_is_not_absence() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("archive.sqlite");
    let mut s = ArchiveStore::open(&path, 64 * 1024 * 1024).unwrap();
    let (e, pages, request) = fixture("1");
    let mut entries = pages
        .iter()
        .flat_map(|p| p["entries"].as_array().unwrap().clone())
        .collect::<Vec<_>>();
    let current = entries
        .iter_mut()
        .filter(|e| e["kind"] == "observation")
        .last()
        .unwrap();
    current["observation"]["scope_complete"] = false.into();
    let (e, pages) = repack(e, entries);
    accept(&mut s, &e, &pages);
    let (g, _, _) = project(&s, &scope(), &request, &DeliveryBudget::default()).unwrap();
    assert_eq!(g["records"][0]["current"]["state"], "unknown");
    assert!(g["records"][0]["current"]["metrics"]["recent_copper"].is_null());
    assert_eq!(g["scope"]["date_coverage"][1]["state"], "incomplete_only");
    let db = rusqlite::Connection::open(&path).unwrap();
    db.execute(
        "DELETE FROM history_entries WHERE phase=2 AND item_id=2589",
        [],
    )
    .unwrap();
    assert!(project(&s, &scope(), &request, &DeliveryBudget::default()).is_err());
}
