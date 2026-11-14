#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde::{Deserialize, Serialize};
use std::{io::Write, path::PathBuf, sync::Mutex};
use tauri::{AppHandle, Manager};
use twichui_market_core::{
    cache::{Cache, Status},
    client::{server_url, MarketClient},
    vault,
};

struct OperationLock(Mutex<()>);
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct Config {
    server: String,
}

fn directory(app: &AppHandle) -> Result<PathBuf, String> {
    let path = app
        .path()
        .app_data_dir()
        .map_err(|_| "Application data directory unavailable")?;
    std::fs::create_dir_all(&path).map_err(|_| "Could not create application data directory")?;
    Ok(path)
}
fn config(path: &std::path::Path) -> Result<Config, String> {
    let bytes =
        std::fs::read(path.join("connection.json")).map_err(|_| "Connect a server first")?;
    serde_json::from_slice(&bytes)
        .map_err(|_| "Connection settings are invalid; connect again".into())
}
fn cache(path: &std::path::Path) -> Result<Cache, String> {
    Cache::open(&path.join("market-v1.sqlite")).map_err(|error| error.to_string())
}
async fn operation<T: Send + 'static>(
    app: AppHandle,
    job: impl FnOnce(PathBuf) -> Result<T, String> + Send + 'static,
) -> Result<T, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let state = app.state::<OperationLock>();
        let _guard = state
            .0
            .lock()
            .map_err(|_| "An operation failed; restart the companion")?;
        job(directory(&app)?)
    })
    .await
    .map_err(|_| "Companion operation failed".to_string())?
}

#[tauri::command]
async fn connection(app: AppHandle) -> Result<Option<String>, String> {
    operation(app, |path| {
        if !path.join("connection.json").exists() {
            return Ok(None);
        }
        Ok(Some(config(&path)?.server))
    })
    .await
}
#[tauri::command]
async fn connect(app: AppHandle, server: String, token: String) -> Result<String, String> {
    operation(app, move |path| {
        let server = server_url(&server).map_err(|e| e.to_string())?.to_string();
        let client = MarketClient::new(&server, token.clone()).map_err(|e| e.to_string())?;
        client.authenticate().map_err(|e| e.to_string())?;
        vault::save(&server, &token).map_err(|e| e.to_string())?;
        let mut temporary = tempfile::NamedTempFile::new_in(&path)
            .map_err(|_| "Could not save connection settings")?;
        serde_json::to_writer(
            &mut temporary,
            &Config {
                server: server.clone(),
            },
        )
        .map_err(|_| "Could not save connection settings")?;
        temporary
            .flush()
            .map_err(|_| "Could not save connection settings")?;
        temporary
            .as_file()
            .sync_all()
            .map_err(|_| "Could not save connection settings")?;
        temporary
            .persist(path.join("connection.json"))
            .map_err(|_| "Could not save connection settings")?;
        Ok(server)
    })
    .await
}
#[tauri::command]
async fn status(app: AppHandle, market: u32) -> Result<Status, String> {
    operation(app, move |path| {
        cache(&path)?
            .status(&config(&path)?.server, market)
            .map_err(|e| e.to_string())
    })
    .await
}
#[derive(Serialize)]
struct SyncResult {
    has_more: bool,
    status: Status,
}
#[tauri::command]
async fn sync_page(app: AppHandle, market: u32) -> Result<SyncResult, String> {
    operation(app, move |path| {
        let server = config(&path)?.server;
        let token = vault::load(&server).map_err(|e| e.to_string())?;
        let client = MarketClient::new(&server, token).map_err(|e| e.to_string())?;
        let mut cache = cache(&path)?;
        let has_more = client
            .synchronize_page(&mut cache, market)
            .map_err(|e| e.to_string())?;
        Ok(SyncResult {
            has_more,
            status: cache.status(&server, market).map_err(|e| e.to_string())?,
        })
    })
    .await
}
#[tauri::command]
async fn reset_market(app: AppHandle, market: u32) -> Result<(), String> {
    operation(app, move |path| {
        cache(&path)?
            .reset(&config(&path)?.server, market)
            .map_err(|e| e.to_string())
    })
    .await
}
#[tauri::command]
async fn export_market(app: AppHandle, market: u32) -> Result<String, String> {
    operation(app, move |path| {
        let exports = path.join("exports");
        std::fs::create_dir_all(&exports).map_err(|_| "Could not create export directory")?;
        let output = cache(&path)?
            .export(&config(&path)?.server, market, &exports)
            .map_err(|e| e.to_string())?;
        Ok(output.to_string_lossy().into_owned())
    })
    .await
}
#[tauri::command]
async fn disconnect(app: AppHandle) -> Result<(), String> {
    operation(app, |path| {
        let server = config(&path)?.server;
        vault::remove(&server).map_err(|e| e.to_string())?;
        std::fs::remove_file(path.join("connection.json"))
            .map_err(|_| "Could not remove connection settings")?;
        Ok(())
    })
    .await
}

fn main() {
    tauri::Builder::default()
        .manage(OperationLock(Mutex::new(())))
        .invoke_handler(tauri::generate_handler![
            connection,
            connect,
            status,
            sync_page,
            reset_market,
            export_market,
            disconnect
        ])
        .run(tauri::generate_context!())
        .expect("TwichUI Market Companion could not start");
}
