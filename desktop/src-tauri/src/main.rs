#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
mod runtime;
mod shell;
mod startup;
mod updates;
use runtime::{Runtime, View};
use std::sync::Arc;
use tauri::{AppHandle, Manager};
use twichui_market_core::settings::Settings;
fn runtime(app: &AppHandle) -> Arc<Runtime> {
    app.state::<Arc<Runtime>>().inner().clone()
}
#[tauri::command]
fn update_state(app: AppHandle) -> Result<updates::View, String> {
    updates::state(&app)
}
#[tauri::command]
async fn check_update(app: AppHandle) -> Result<updates::View, String> {
    tauri::async_runtime::spawn_blocking(move || updates::check(app))
        .await
        .map_err(|_| "Update check was interrupted".to_string())?
}
#[tauri::command]
async fn install_update(app: AppHandle, version: String) -> Result<updates::View, String> {
    tauri::async_runtime::spawn_blocking(move || updates::install(app, version))
        .await
        .map_err(|_| "Update was interrupted".to_string())?
}
#[tauri::command]
async fn restart_companion(app: AppHandle) -> Result<(), String> {
    if !updates::state(&app)?.restart_required {
        return Err("A restart is not required by an update.".into());
    }
    tauri::async_runtime::spawn_blocking(move || -> Result<(), String> {
        runtime(&app).prepare_update()?;
        app.restart()
    })
    .await
    .map_err(|_| "Restart was interrupted".to_string())?
}
#[tauri::command]
fn app_state(app: AppHandle) -> Result<View, String> {
    runtime(&app).view()
}
#[tauri::command]
fn sign_in(app: AppHandle, device_name: String) -> Result<(), String> {
    runtime(&app).sign_in(device_name)
}
#[tauri::command]
fn cancel_approval(app: AppHandle) -> Result<(), String> {
    runtime(&app).cancel_approval()
}
#[tauri::command]
fn open_approval(app: AppHandle) -> Result<(), String> {
    runtime(&app).reopen_approval()
}
#[tauri::command]
fn save_settings(app: AppHandle, settings: Settings, reset_invalid: bool) -> Result<(), String> {
    runtime(&app).save_settings(settings, reset_invalid)
}
#[tauri::command]
fn sync_now(app: AppHandle) -> Result<bool, String> {
    let runtime = runtime(&app);
    let view = runtime.view()?;
    if view.approving || view.refreshing || !view.connected {
        return Err("Finish connecting before synchronizing".into());
    }
    runtime.worker.sync_now().map_err(|e| e.to_string())
}
#[tauri::command]
fn pause_sync(app: AppHandle) -> Result<(), String> {
    runtime(&app).pause()
}
#[tauri::command]
fn resume_sync(app: AppHandle) -> Result<(), String> {
    runtime(&app).resume()
}
#[tauri::command]
fn cancel_sync(app: AppHandle) -> Result<(), String> {
    runtime(&app).worker.cancel().map_err(|e| e.to_string())
}
#[tauri::command]
fn refresh_connection(app: AppHandle) -> Result<(), String> {
    runtime(&app).refresh_connection()
}
#[tauri::command]
fn disconnect(app: AppHandle) -> Result<(), String> {
    runtime(&app).disconnect()
}
#[tauri::command]
async fn export_market(app: AppHandle) -> Result<String, String> {
    let owned = runtime(&app);
    tauri::async_runtime::spawn_blocking(move || owned.export())
        .await
        .map_err(|_| "Export interrupted")?
}
#[tauri::command]
async fn export_workshop(app: AppHandle,algorithm:String) -> Result<String,String> {
    let owned=runtime(&app);
    tauri::async_runtime::spawn_blocking(move || owned.export_workshop(&algorithm)).await.map_err(|_| "Workshop test export interrupted".to_string())?
}
#[tauri::command]
async fn configure_delivery(app:AppHandle,installation:String,algorithm:String,history_days:u32,operation:String,confirmed:bool,variants:serde_json::Value)->Result<serde_json::Value,String>{
    let owned=runtime(&app);
    tauri::async_runtime::spawn_blocking(move ||owned.configure_delivery(installation,algorithm,history_days,operation,confirmed,variants)).await.map_err(|_|"Delivery setup interrupted".to_string())?
}
#[tauri::command]
async fn prepare_workshop(app:AppHandle)->Result<serde_json::Value,String>{
    let owned=runtime(&app);
    tauri::async_runtime::spawn_blocking(move ||owned.prepare_workshop()).await.map_err(|_|"Workshop setup interrupted".to_string())?
}
#[tauri::command]
async fn confirm_workshop(app:AppHandle,review_id:String)->Result<(),String>{
    let owned=runtime(&app);
    tauri::async_runtime::spawn_blocking(move ||owned.confirm_workshop(review_id)).await.map_err(|_|"Workshop setup interrupted".to_string())?
}
#[tauri::command]
fn cancel_workshop(app:AppHandle)->Result<(),String>{runtime(&app).cancel_workshop()}
#[tauri::command]
async fn archive_workshop(
    app: AppHandle,
    algorithm: String,
    disk_budget_mib: u64,
    selected: Option<serde_json::Value>,
    publish: bool,
    compatible: bool,
) -> Result<serde_json::Value, String> {
    let owned = runtime(&app).clone();
    tauri::async_runtime::spawn_blocking(move || {
        owned.archive_workshop(&algorithm, disk_budget_mib, selected, publish, compatible)
    })
    .await
    .map_err(|_| "History archive action interrupted".to_string())?
}
#[tauri::command]
fn open_exports(app: AppHandle) -> Result<(), String> {
    runtime(&app).open_exports()
}
#[tauri::command]
fn open_website(app: AppHandle, page: String) -> Result<(), String> {
    runtime(&app).open_website(&page)
}
#[tauri::command]
fn set_performance_capture(app:AppHandle,enabled:bool)->Result<(),String>{runtime(&app).set_performance_capture(enabled)}
#[tauri::command]
fn save_diagnostics(app: AppHandle) -> Result<String, String> {
    runtime(&app).diagnostics()
}
#[tauri::command]
fn quit(app: AppHandle) {
    runtime(&app).request_quit();
}
#[tauri::command]
fn hide_to_tray(app: AppHandle) -> Result<(), String> {
    if !runtime(&app).view()?.settings.onboarding_completed {
        return Err("Finish your first sync before hiding to the tray".into());
    }
    app.get_webview_window("main")
        .ok_or("Window unavailable")?
        .hide()
        .map_err(|_| "Could not hide the window".into())
}
#[tauri::command]
fn show_companion(app: AppHandle) {
    shell::restore(&app);
}
fn main() {
    let flags = tauri_plugin_window_state::StateFlags::POSITION
        | tauri_plugin_window_state::StateFlags::SIZE
        | tauri_plugin_window_state::StateFlags::MAXIMIZED;
    let app = tauri::Builder::default()
        // Must be the first plugin. A normal second launch restores the existing process.
        .plugin(tauri_plugin_single_instance::init(|app, args, _| {
            if !args.iter().any(|arg| arg == "--background") {
                shell::restore(app);
            }
        }))
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(flags)
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_updater::Builder::new()
                .pubkey(updates::PUBLIC_KEY.trim())
                .build(),
        )
        .setup(|app| {
            let path = app.path().app_data_dir()?;
            let runtime =
                Runtime::create(app.handle().clone(), path).map_err(std::io::Error::other)?;
            app.manage(runtime.clone());
            app.manage(Arc::new(updates::Updates::default()));
            shell::create_tray(app.handle())?;
            if let Some(window) = app.get_webview_window("main") {
                if runtime.should_hide_on_start() {
                    window.hide()?;
                } else {
                    window.show()?;
                }
            }
            runtime.initialize();
            updates::start_background(app.handle().clone()).map_err(std::io::Error::other)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            let app = window.app_handle();
            let Some(runtime) = app.try_state::<Arc<Runtime>>() else {
                return;
            };
            match event {
                tauri::WindowEvent::CloseRequested { api, .. } if !runtime.quitting() => {
                    api.prevent_close();
                    if runtime.hide_on_close() {
                        let _ = window.hide();
                    } else {
                        runtime.request_quit();
                    }
                }
                tauri::WindowEvent::Resized(_) if runtime.hide_on_minimize() => {
                    if window.is_minimized().unwrap_or(false) {
                        let _ = window.hide();
                    }
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![
            update_state,
            check_update,
            install_update,
            restart_companion,
            app_state,
            sign_in,
            cancel_approval,
            open_approval,
            save_settings,
            sync_now,
            pause_sync,
            resume_sync,
            cancel_sync,
            refresh_connection,
            disconnect,
            export_market,
            export_workshop,
            archive_workshop,
            configure_delivery,
            prepare_workshop,
            confirm_workshop,
            cancel_workshop,
            open_exports,
            open_website,
            save_diagnostics,
            set_performance_capture,
            quit,
            hide_to_tray,
            show_companion
        ])
        .build(tauri::generate_context!())
        .expect("TwichUI Market Companion could not start");
    app.run(|app, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            let runtime = runtime(app);
            if !runtime.quitting() {
                api.prevent_exit();
                runtime.request_quit();
            }
        }
    });
}
