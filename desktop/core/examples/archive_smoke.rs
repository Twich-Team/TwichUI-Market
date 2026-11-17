//! Disposable authenticated HTTP -> real archive -> schema-3 publisher acceptance.
//! Test token only in environment; no game installation, SavedVariables or scheduler.
use std::{path::PathBuf, time::Instant};
use twichui_market_core::{
    archive::{project, ArchiveStore, DeliveryBudget, DEFAULT_DISK_BUDGET},
    bridge::{self, Scope},
    client::MarketClient,
};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let a = std::env::args().skip(1).collect::<Vec<_>>();
    if a.len() < 6 {
        return Err("server account market archive staging action [selection-file]".into());
    }
    let scope = Scope {
        server: twichui_market_core::client::server_url(&a[0])?.to_string(),
        account_id: a[1].parse()?,
        market_id: a[2].parse()?,
        algorithm: std::env::var("TWICHUI_ARCHIVE_TEST_ALGORITHM")
            .unwrap_or_else(|_| "twichui-pricing-v1".into()),
    };
    let mut store = ArchiveStore::open(&PathBuf::from(&a[3]), DEFAULT_DISK_BUDGET)?;
    let start = Instant::now();
    match a[5].as_str() {
        "auto" => {
            // Only this synthetic acceptance executable constructs a fake game.
            let request = bridge::parse(
                &std::fs::read(a.get(6).ok_or("selection path required")?)?,
                128 * 1024,
            )?;
            let root = PathBuf::from(&a[4]);
            let base = root.join("automatic-fixture");
            std::fs::create_dir_all(&base)?;
            let installation = base.join("Forever");
            let consumer = installation.join("Interface/AddOns/TwichUI_Workshop");
            std::fs::create_dir_all(&consumer)?;
            std::fs::write(
                installation.join("Wow.exe"),
                b"synthetic fixture, not a game executable",
            )?;
            std::fs::write(consumer.join("MarketDelivery.json"),br#"{"format":"twichui-market-consumer","capability_version":1,"contract_version":1,"transport_version":1,"schema_versions":[3],"canonical_bytes":2097152,"lua_bytes":3145728}"#)?;
            let config = twichui_market_core::delivery::Configuration {
                version: 1,
                enabled: true,
                scope: scope.clone(),
                installation: installation.clone(),
                selection: request,
                history_days: 60,
            };
            config.save_confirmed(&base, true)?;
            let c = MarketClient::new(&scope.server, std::env::var("TWICHUI_ARCHIVE_TEST_TOKEN")?)?;
            let status = twichui_market_core::delivery::synchronize(&base, &c, &config, || false)?;
            let path = installation.join("Interface/AddOns/TwichUI_MarketData/Data.lua");
            let (g, _) = bridge::inspect_artifact(&std::fs::read(&path)?)?;
            if g["synthetic"] != true {
                return Err("acceptance requires synthetic observations".into());
            }
            println!(
                "{}",
                serde_json::json!({"status":status,"lua_path":path,"synthetic":true})
            );
        }
        "step" | "sync" => {
            let c = MarketClient::new(&scope.server, std::env::var("TWICHUI_ARCHIVE_TEST_TOKEN")?)?;
            let complete = if a[5] == "step" {
                c.download_archive_pages(&mut store, &scope, || false, 1)?
            } else {
                c.download_archive(&mut store, &scope, || false)?;
                true
            };
            println!(
                "{}",
                serde_json::json!({"complete":complete,"pending":store.pending(&scope)?.is_some(),"header":store.active(&scope)?,"archive_bytes":store.allocated_bytes()?,"metrics":store.metrics(),"elapsed_ms":start.elapsed().as_secs_f64()*1000.})
            );
        }
        "export" | "refuse" => {
            let request = bridge::parse(
                &std::fs::read(a.get(6).ok_or("selection path required")?)?,
                128 * 1024,
            )?;
            let budget = if a[5] == "refuse" {
                DeliveryBudget {
                    canonical_bytes: 1,
                    ..DeliveryBudget::default()
                }
            } else {
                DeliveryBudget::default()
            };
            let (g, r, s) = project(&store, &scope, &request, &budget)?;
            store.save_selection(&scope, &request)?;
            let root = PathBuf::from(&a[4]);
            let path = bridge::export_generation(&scope, &root, &g, &r, &budget)?;
            let readback = bridge::inspect_artifact(&std::fs::read(&path)?)?;
            if readback.0 != g {
                return Err("readback differs".into());
            }
            let generation_path = root.join("generation.json");
            std::fs::write(&generation_path, bridge::canonical(&g)?)?;
            println!(
                "{}",
                serde_json::json!({"generation_id":g["generation_id"],"checkpoint_id":store.active(&scope)?.unwrap().checkpoint_id,"sizes":s,"receipt":r,"lua_path":path,"generation_path":generation_path,"archive_bytes":store.allocated_bytes()?,"metrics":store.metrics(),"elapsed_ms":start.elapsed().as_secs_f64()*1000.})
            );
        }
        _ => return Err("unsupported acceptance action".into()),
    }
    Ok(())
}
