//! No update network request without a build-pinned owner key. All install intent
//! comes from an explicit confirmation; the WebView never receives package bytes.
use crate::runtime::Runtime;
use serde::Serialize;
use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Condvar, Mutex,
    },
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Listener, Manager};
use tauri_plugin_updater::{Update, UpdaterExt};
use twichui_market_core::{
    scheduler::{Clock, SystemClock},
    update::{self, Package},
};
pub const PUBLIC_KEY: &str = include_str!("../updater-public-key.txt");
type Result<T> = std::result::Result<T, String>;
#[derive(Clone, Serialize)]
pub struct View {
    pub status: &'static str,
    pub version: Option<String>,
    pub available_version: Option<String>,
    pub message: String,
    pub notes: Option<String>,
    pub restart_required: bool,
    pub verification_key_sha256: String,
}
impl View {
    fn new(status: &'static str, message: &str) -> Self {
        Self {
            status,
            version: None,
            available_version: None,
            message: message.into(),
            notes: None,
            restart_required: false,
            verification_key_sha256: update::public_key_fingerprint(PUBLIC_KEY),
        }
    }
}
struct Pending {
    package: Package,
    update: Update,
    checked: Instant,
}
pub struct Updates {
    busy: AtomicBool,
    pending: Mutex<Option<Pending>>,
    view: Mutex<View>,
    background: Arc<(Mutex<Background>, Condvar)>,
}
#[derive(Default)]
struct Background {
    schedule: update::CheckSchedule,
    stopped: bool,
    connected: bool,
}
impl Default for Updates {
    fn default() -> Self {
        Self {
            busy: AtomicBool::new(false),
            pending: Mutex::new(None),
            view: Mutex::new(View::new(
                "idle",
                "Updates are checked automatically. Installing always needs your confirmation.",
            )),
            background: Arc::new((Mutex::new(Background::default()), Condvar::new())),
        }
    }
}
struct Busy<'a>(&'a AtomicBool);
impl Drop for Busy<'_> {
    fn drop(&mut self) {
        self.0.store(false, Ordering::Release);
    }
}
impl Updates {
    fn claim(&self) -> Result<Busy<'_>> {
        if self.busy.swap(true, Ordering::AcqRel) {
            return Err("An update operation is already running.".into());
        }
        Ok(Busy(&self.busy))
    }
    fn set(&self, app: &AppHandle, mut view: View) -> Result<View> {
        {
            let mut previous=self.view.lock().map_err(|_|"Update status is unavailable")?;
            view.available_version=match view.status {
                "available"=>view.version.clone(),
                "current"=>None,
                _=>previous.available_version.clone(),
            };
            *previous=view.clone();
        }
        let _=app.emit("companion-update",&view);
        crate::shell::update_notice(app,&view);
        if view.status=="available" {
            if let Some(version)=view.version.as_deref() {
                let background=app.get_webview_window("main").is_some_and(|window|
                    window.is_visible().ok()==Some(false)||window.is_minimized().ok()==Some(true));
                if app.state::<Arc<Runtime>>().claim_update_notice(version,background).unwrap_or(false) {
                    use tauri_plugin_notification::NotificationExt;
                    let _=app.notification().builder().title("Companion update available")
                        .body(format!("Companion {version} is available. Open the Companion to review it; installation requires your confirmation."))
                        .show();
                }
            }
        }
        Ok(view)
    }
}
pub fn stop_background(app: &AppHandle) {
    if let Some(updates) = app.try_state::<Arc<Updates>>() {
        if let Ok(mut state) = updates.background.0.lock() {
            state.stopped = true;
        }
        updates.background.1.notify_all();
    }
}
pub fn start_background(app: AppHandle) -> Result<()> {
    if cfg!(feature = "private-dev") { return Ok(()); }
    let updates = app.state::<Arc<Updates>>().inner().clone();
    if let Ok(mut state) = updates.background.0.lock() {
        state.connected = app.state::<Arc<Runtime>>().updates_eligible();
    }
    let observer = updates.clone();
    app.listen("companion-state", move |event| {
        let Ok(value) = serde_json::from_str::<serde_json::Value>(event.payload()) else {
            return;
        };
        let Some(connected) = value.get("connected").and_then(|value| value.as_bool()) else {
            return;
        };
        if let Ok(mut background) = observer.background.0.lock() {
            if !background.stopped && background.connected != connected {
                background.connected = connected;
                if connected {
                    background.schedule.connection_ready(SystemClock.now_ms());
                }
                observer.background.1.notify_one();
            }
        }
    });
    std::thread::Builder::new()
        .name("market-update-checks".into())
        .spawn(move || {
            let runtime = app.state::<Arc<Runtime>>().inner().clone();
            loop {
                if runtime.quitting() {
                    break;
                }
                let eligible = runtime.updates_eligible();
                let now = SystemClock.now_ms();
                let Ok(mut background) = updates.background.0.lock() else {
                    break;
                };
                if background.stopped {
                    break;
                }
                if background.schedule.claim(now, eligible) {
                    drop(background);
                    let _ = check(app.clone());
                } else {
                    let wait = background.schedule.wait_ms(now, eligible);
                    let Ok((guard, _)) = updates
                        .background
                        .1
                        .wait_timeout(background, Duration::from_millis(wait))
                    else {
                        break;
                    };
                    drop(guard);
                }
            }
        })
        .map_err(|_| "Automatic update checks could not start".to_string())?;
    Ok(())
}
pub fn state(app: &AppHandle) -> Result<View> {
    app.state::<Arc<Updates>>()
        .view
        .lock()
        .map(|view| view.clone())
        .map_err(|_| "Update status is unavailable".into())
}
pub fn check(app: AppHandle) -> Result<View> {
    if cfg!(feature = "private-dev") {
        return app.state::<Arc<Updates>>().set(&app, View::new("unavailable", "Automatic updates are disabled in this private DEV build."));
    }
    let updates = app.state::<Arc<Updates>>().inner().clone();
    let _busy = updates.claim()?;
    *updates
        .pending
        .lock()
        .map_err(|_| "Update status is unavailable")? = None;
    let key = PUBLIC_KEY.trim();
    let runtime = app.state::<Arc<Runtime>>().inner().clone();
    if !runtime.updates_eligible() {
        return updates.set(
            &app,
            View::new(
                "unavailable",
                "Connect to TwichUI Market to check for verified updates.",
            ),
        );
    }
    updates.set(
        &app,
        View::new("checking", "Checking for a verified update…"),
    )?;
    let result = (|| -> Result<Option<Pending>> {
        let Some((package, raw)) = runtime
            .with_update_client(|client| client.update_metadata(env!("CARGO_PKG_VERSION")))
            .map_err(|_| "Could not check updates. Your current companion keeps working.")?
        else {
            return Ok(None);
        };
        let endpoint = format!(
            "{}/api/v1/companion/private-beta/update/windows-x86_64/{}",
            update::ORIGIN,
            env!("CARGO_PKG_VERSION")
        );
        let updater = app
            .updater_builder()
            .pubkey(key.trim())
            .endpoints(vec![endpoint
                .parse()
                .map_err(|_| "Update configuration is unavailable")?])
            .map_err(|_| "Update configuration is unavailable")?
            .timeout(Duration::from_secs(120))
            .no_proxy()
            .build()
            .map_err(|_| "Update configuration is unavailable")?;
        // restore_update avoids an unbounded SDK metadata request and enforces a
        // cryptographically signed version in addition to its SemVer comparator.
        let Some(update) = updater
            .restore_update(raw)
            .map_err(|_| "This update could not be verified. Keep using your current companion.")?
        else {
            return Ok(None);
        };
        if update.version != package.version || update.download_url.as_str() != package.download_url
        {
            return Err("The update information did not match. Try checking again later.".into());
        }
        Ok(Some(Pending {
            package,
            update,
            checked: Instant::now(),
        }))
    })();
    if let Ok(mut background) = updates.background.0.lock() {
        background
            .schedule
            .completed(SystemClock.now_ms(), result.is_ok());
    }
    match result {
        Ok(Some(pending)) => {
            let view = View {
                status: "available",
                version: Some(pending.package.version.clone()),
                available_version: Some(pending.package.version.clone()),
                message: format!("Companion {} is available.", pending.package.version),
                notes: Some(pending.package.notes.clone()),
                restart_required: false,
                verification_key_sha256: update::public_key_fingerprint(PUBLIC_KEY),
            };
            *updates
                .pending
                .lock()
                .map_err(|_| "Update status is unavailable")? = Some(pending);
            updates.set(&app, view)
        }
        Ok(None) => updates.set(
            &app,
            View::new(
                "current",
                "You have the latest verified companion available to this installation.",
            ),
        ),
        Err(message) => updates.set(&app, View::new("error", &message)),
    }
}
pub fn install(app: AppHandle, version: String) -> Result<View> {
    if cfg!(feature = "private-dev") { return Err("Updates are disabled in this private DEV build.".into()); }
    let updates = app.state::<Arc<Updates>>().inner().clone();
    let _busy = updates.claim()?;
    let pending = updates
        .pending
        .lock()
        .map_err(|_| "Update status is unavailable")?
        .take()
        .filter(|pending| {
            pending.package.version == version
                && pending.checked.elapsed() < Duration::from_secs(600)
        })
        .ok_or("Check for updates again before installing.")?;
    updates.set(
        &app,
        View::new(
            "installing",
            "Downloading and verifying your update. Keep the companion open…",
        ),
    )?;
    let verified = (|| -> Result<Vec<u8>> {
        let runtime = app.state::<Arc<Runtime>>().inner().clone();
        let bytes = runtime
            .with_update_client(|client| client.download_update(&pending.package))
            .map_err(|_| {
                "The update could not be downloaded intact. Your current companion keeps working."
            })?;
        pending.update.verify(&bytes).map_err(|_|"The update signature or signed version did not match. Your current companion keeps working.")?;
        Ok(bytes)
    })();
    let bytes = match verified {
        Ok(bytes) => bytes,
        Err(message) => return updates.set(&app, View::new("error", &message)),
    };
    let runtime = app.state::<Arc<Runtime>>().inner().clone();
    if runtime.prepare_update().is_err() {
        let mut view = View::new(
            "error",
            "The companion could not prepare the update. Restart it before trying again.",
        );
        view.restart_required = true;
        return updates.set(&app, view);
    }
    // install verifies again before it launches the current-user NSIS updater.
    // On Windows a successful install launch exits this process through Tauri cleanup.
    let result = pending.update.install(bytes);
    runtime.update_failed();
    let mut view = View::new(
        "error",
        if result.is_err() {
            "The update could not finish. Restart the companion to resume synchronization."
        } else {
            "Restart the companion to finish the update."
        },
    );
    view.restart_required = true;
    updates.set(&app, view)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tauri::test::{mock_builder, mock_context, noop_assets};
    const BYTES: &[u8] = include_bytes!("../tests/fixtures/synthetic-update.txt");
    const KEY: &str = include_str!("../tests/fixtures/synthetic-public.key");
    const SIGNATURE: &str = include_str!("../tests/fixtures/synthetic-update.txt.sig");
    /// Owner-signing workflow only. The SDK exits this child after launching NSIS;
    /// its parent must verify the installed binary, reconnect and retain data.
    #[cfg(windows)]
    #[test]
    #[ignore = "Requires the owner's actual signed installer on a disposable runner"]
    fn launch_owner_signed_installer_on_disposable_runner() {
        use std::os::windows::process::CommandExt;
        use std::{
            env, fs,
            path::PathBuf,
            process::{Command, Stdio},
        };
        assert_eq!(env::var("GITHUB_ACTIONS").as_deref(), Ok("true"));
        assert_eq!(env::var("RUNNER_OS").as_deref(), Ok("Windows"));
        assert_eq!(env::var("MARKET_TEST_UPDATER_SDK").as_deref(), Ok("true"));
        let directory = PathBuf::from(env::var("MARKET_TEST_INSTALL_DIRECTORY").unwrap());
        let temporary = PathBuf::from(env::var("RUNNER_TEMP").unwrap());
        assert!(directory.starts_with(&temporary));
        assert_eq!(directory.file_name().unwrap(), "TwichMarket-Upgrade");
        let installer = PathBuf::from(env::var("MARKET_TEST_NEW_INSTALLER").unwrap());
        assert!(fs::metadata(&installer).unwrap().len() <= 64 * 1024 * 1024);
        let bytes = fs::read(&installer).unwrap();
        let signature = fs::read_to_string(format!("{}.sig", installer.display())).unwrap();
        let key = PUBLIC_KEY;
        let version = env::var("RELEASE_VERSION").unwrap();
        let mut context = mock_context(noop_assets());
        context.package_info_mut().version = "0.1.0".parse().unwrap();
        context.config_mut().plugins.0.insert(
            "updater".into(),
            json!({
                "pubkey":key.trim(),"requireSignedVersion":true,"allowDowngrades":false,
                "windows":{"installMode":"quiet"}
            }),
        );
        let app = mock_builder()
            .plugin(
                tauri_plugin_updater::Builder::new()
                    .pubkey(key.trim())
                    .build(),
            )
            .build(context)
            .unwrap();
        let updater = app
            .updater_builder()
            .pubkey(key.trim())
            .endpoints(vec![format!(
                "{}/unused-owner-test-endpoint",
                update::ORIGIN
            )
            .parse()
            .unwrap()])
            .unwrap()
            .executable_path(directory.join("twichui-market-companion.exe"))
            .installer_args(["/S".to_string(), format!("/D={}", directory.display())])
            .build()
            .unwrap();
        let payload = json!({"version":version,"url":format!("{}/api/v1/companion/releases/{}/windows-x64",update::ORIGIN,version),"signature":signature.trim()});
        let candidate = updater
            .restore_update(payload)
            .unwrap()
            .unwrap()
            .restart_after_install(false);
        let mut corrupt = bytes.clone();
        corrupt[0] ^= 1;
        assert!(candidate.verify(&corrupt).is_err());
        candidate.verify(&bytes).unwrap();
        let wrong = serde_json::json!({"version":"2.9999.9999","url":format!("{}/api/v1/companion/releases/2.9999.9999/windows-x64",update::ORIGIN),"signature":signature.trim()});
        assert!(updater
            .restore_update(wrong)
            .unwrap()
            .unwrap()
            .verify(&bytes)
            .is_err());
        let workspace = PathBuf::from(env::var("GITHUB_WORKSPACE").unwrap());
        let evidence = workspace.join("artifacts/companion-signed-update-test/sdk-crypto.json");
        fs::create_dir_all(evidence.parent().unwrap()).unwrap();
        fs::write(
            &evidence,
            serde_json::to_vec_pretty(&json!({
                "sdk_test_executed":true,"supported_sdk_signature_verified":true,
                "corrupt_payload_rejected":true,"wrong_signed_version_rejected":true,
                "version":version,"installer":installer,"expected_install_directory":directory,
                "updater_public_key_sha256":update::public_key_fingerprint(key)
            }))
            .unwrap(),
        )
        .unwrap();
        eprintln!(
            "Actual owner-key SDK crypto assertions passed; invoking the verified NSIS installer."
        );
        // Start the observer only now, after Cargo compilation and crypto checks.
        // Its bounded interval must cover installation, not compilation time.
        let _observer = Command::new("powershell.exe")
            .args(["-NoProfile", "-NonInteractive", "-File"])
            .arg(workspace.join("scripts/windows/watch-update-installer.ps1"))
            .current_dir(&workspace)
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(0x08000000)
            .spawn()
            .unwrap();
        let ready = evidence.parent().unwrap().join("installer-observer.ready");
        let deadline = Instant::now() + Duration::from_secs(15);
        while !ready.exists() && Instant::now() < deadline {
            std::thread::sleep(Duration::from_millis(25));
        }
        assert!(ready.exists(), "Installer observer did not become ready");
        candidate
            .install(bytes)
            .expect("The supported updater must launch the verified installer");
        panic!("A successful Windows SDK install launch exits this child process");
    }

    #[test]
    fn supported_updater_verifies_bytes_and_binds_the_signed_version() {
        let mut context = mock_context(noop_assets());
        context.config_mut().plugins.0.insert(
            "updater".into(),
            json!({
                "pubkey":KEY.trim(),"requireSignedVersion":true,"allowDowngrades":false
            }),
        );
        let app = mock_builder()
            .plugin(
                tauri_plugin_updater::Builder::new()
                    .pubkey(KEY.trim())
                    .build(),
            )
            .build(context)
            .unwrap();
        let updater = app
            .updater_builder()
            .endpoints(vec![format!("{}/unused-test-endpoint", update::ORIGIN)
                .parse()
                .unwrap()])
            .unwrap()
            .build()
            .unwrap();
        let manifest = json!({"version":"2.0.0","url":format!("{}/api/v1/companion/releases/2.0.0/windows-x64",update::ORIGIN),"signature":SIGNATURE.trim(),"notes":"Synthetic crypto fixture only"});
        let verified = updater.restore_update(manifest.clone()).unwrap().unwrap();
        verified.verify(BYTES).unwrap();
        let mut corrupted = BYTES.to_vec();
        corrupted[0] ^= 1;
        assert!(verified.verify(&corrupted).is_err());
        let mut inflated = manifest.clone();
        inflated["version"] = json!("2.0.1");
        assert!(updater
            .restore_update(inflated)
            .unwrap()
            .unwrap()
            .verify(BYTES)
            .is_err());
        let mut older = manifest;
        older["version"] = json!("0.1.0");
        assert!(updater.restore_update(older).unwrap().is_none());
    }
}
