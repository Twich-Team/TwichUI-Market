use crate::runtime::Runtime;
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager,
};
use twichui_market_core::{scheduler::Phase, worker::State};
struct TrayControls {
    status: MenuItem<tauri::Wry>,
    sync: MenuItem<tauri::Wry>,
    pause: MenuItem<tauri::Wry>,
}
fn label(phase: Phase) -> &'static str {
    match phase {
        Phase::NotConnected => "Not connected",
        Phase::ChooseMarket => "Choose a market",
        Phase::Ready => "Up to date",
        Phase::Synchronizing => "Synchronizing",
        Phase::Cancelling => "Cancelling",
        Phase::Paused => "Automatic sync paused",
        Phase::Offline => "Cannot reach server",
        Phase::ServerUnavailable => "Server unavailable",
        Phase::SignInRequired => "Sign in again",
        Phase::RecoverableError => "Sync needs attention",
        Phase::Stopped => "Closing companion",
    }
}
pub fn restore(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}
pub fn create_tray(app: &AppHandle) -> tauri::Result<()> {
    let status = MenuItem::with_id(app, "status", "Not connected", false, None::<&str>)?;
    let open = MenuItem::with_id(app, "open", "Open companion", true, None::<&str>)?;
    let sync = MenuItem::with_id(app, "sync", "Sync now", false, None::<&str>)?;
    let pause = MenuItem::with_id(app, "pause", "Pause automatic sync", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "Settings…", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let menu = Menu::with_items(
        app,
        &[&status, &separator, &open, &sync, &pause, &settings, &quit],
    )?;
    let mut tray = TrayIconBuilder::with_id("companion")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .tooltip("TwichUI Market Companion — Not connected")
        .on_menu_event(|app, event| {
            let runtime = app.state::<Arc<Runtime>>();
            let result = match event.id.as_ref() {
                "open" => {
                    restore(app);
                    Ok(())
                }
                "settings" => {
                    restore(app);
                    let _ = app.emit("open-settings", ());
                    Ok(())
                }
                "sync" => runtime
                    .worker
                    .sync_now()
                    .map(|_| ())
                    .map_err(|e| e.to_string()),
                "pause" => {
                    if runtime
                        .worker
                        .snapshot()
                        .is_ok_and(|state| state.sync.automatic_sync)
                    {
                        runtime.pause()
                    } else {
                        runtime.resume()
                    }
                }
                "quit" => {
                    runtime.request_quit();
                    Ok(())
                }
                _ => Ok(()),
            };
            if let Err(error) = result {
                let _ = app.emit("companion-error", error);
                restore(app);
            }
        })
        .on_tray_icon_event(|tray, event| {
            if matches!(
                event,
                TrayIconEvent::DoubleClick {
                    button: MouseButton::Left,
                    ..
                } | TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                }
            ) {
                restore(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        tray = tray.icon(icon.clone());
    }
    tray.build(app)?;
    app.manage(TrayControls {
        status,
        sync,
        pause,
    });
    Ok(())
}
pub fn update_tray(app: &AppHandle, state: &State) {
    if let Some(controls) = app.try_state::<TrayControls>() {
        let text = label(state.sync.phase);
        let _ = controls.status.set_text(text);
        let _ = controls.sync.set_enabled(
            !state.sync.running
                && state.sync.selected_market.is_some()
                && !matches!(
                    state.sync.phase,
                    Phase::NotConnected | Phase::SignInRequired | Phase::Stopped
                ),
        );
        let _ = controls.pause.set_text(if state.sync.automatic_sync {
            "Pause automatic sync"
        } else {
            "Resume automatic sync"
        });
        if let Some(tray) = app.tray_by_id("companion") {
            let _ = tray.set_tooltip(Some(format!("TwichUI Market Companion — {text}")));
        }
    }
}
