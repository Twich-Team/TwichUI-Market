//! Native process ownership. The WebView renders state and sends intent only.
use chrono::Utc;
use serde::Serialize;
use std::{
    io::Write,
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread::{self, JoinHandle},
    time::Duration,
};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_opener::OpenerExt;
use twichui_market_core::{
    authorization::{ApprovalInfo, AuthorizationClient, CredentialStore},
    cache::{Cache, Status},
    client::{server_url, MarketClient},
    connection::Bootstrap,
    profile::{Mode, Profile, RememberedMarket},
    scheduler::{Run, SystemClock},
    settings::Settings,
    synchronizer,
    vault::{self, NativeCredentialStore},
    worker::{Execution, Executor, State, Worker},
    Error,
};

type Result<T> = std::result::Result<T, String>;
fn setup_core(stage:&str,error:Error)->String {
    serde_json::to_string(&twichui_market_core::workshop_setup::Failure::from_error(stage,error))
        .unwrap_or_else(|_|"Workshop setup interrupted".into())
}
fn friendly(error: impl std::fmt::Display) -> String {
    error.to_string()
}
#[derive(Serialize, Clone)]
pub struct View {
    pub version: String,
    pub settings: Settings,
    pub mode: Mode,
    pub connected: bool,
    pub account: Option<twichui_market_core::connection::Account>,
    pub bootstrap: Option<Bootstrap>,
    pub offline_market: Option<RememberedMarket>,
    pub sync: State,
    pub cache: Option<StatusView>,
    pub approval: Option<ApprovalInfo>,
    pub approving: bool,
    pub refreshing: bool,
    pub error: Option<String>,
    pub settings_valid: bool,
    pub autostart_enabled: bool,
    pub quitting: bool,
    pub window_visible: bool,
    pub delivery: serde_json::Value,
    pub sync_progress: twichui_market_core::performance::Progress,
    pub performance_capture: bool,
}
#[derive(Serialize, Clone)]
pub struct StatusView {
    pub market_id: u32,
    pub item_count: u64,
    pub downloading: bool,
    pub has_completed_cache: bool,
    pub synthetic: bool,
}
impl From<Status> for StatusView {
    fn from(value: Status) -> Self {
        Self {
            market_id: value.market_id,
            item_count: value.item_count,
            downloading: value.downloading,
            has_completed_cache: value.has_completed_cache,
            synthetic: value.synthetic,
        }
    }
}
struct Local {
    settings: Settings,
    profile: Profile,
    credential_available: bool,
    error: Option<String>,
    settings_valid: bool,
    approving: bool,
    refreshing: bool,
    approval: Option<ApprovalInfo>,
    approval_cancel: Arc<AtomicBool>,
    notified_error: Option<String>,
}
struct Data {
    app: AppHandle,
    path: PathBuf,
    local: Mutex<Local>,
    gate: Mutex<()>,
    quitting: AtomicBool,
    workshop_review: Mutex<Option<(String,twichui_market_core::delivery::Configuration,chrono::DateTime<Utc>)>>,
    workshop_setup: AtomicBool,
    performance_capture: AtomicBool,
    sync_progress: Mutex<twichui_market_core::performance::Progress>,
    performance_reports: Mutex<std::collections::VecDeque<twichui_market_core::performance::Report>>,
    workshop_failure: Mutex<Option<twichui_market_core::workshop_setup::Failure>>,
}
pub struct Runtime {
    data: Arc<Data>,
    pub worker: Arc<Worker<SystemClock>>,
    auth_thread: Mutex<Option<JoinHandle<()>>>,
}
struct NativeTask(Arc<Data>);
impl Executor for NativeTask {
    fn execute(
        &self,
        server: &str,
        run: &Run,
        progress: &(dyn Fn(u32) + Send + Sync),
    ) -> twichui_market_core::Result<Execution> {
        let _gate = self
            .0
            .gate
            .lock()
            .map_err(|_| Error::Invalid("connection operation interrupted"))?;
        if run.cancelled() || self.0.quitting.load(Ordering::Acquire) {
            return Err(Error::Cancelled);
        }
        let (profile, local_override) = {
            let local = self
                .0
                .local
                .lock()
                .map_err(|_| Error::Invalid("connection settings"))?;
            (local.profile.clone(), local.settings.selected_market)
        };
        if profile.server != server_url(server)?.as_str() {
            return Err(Error::Cancelled);
        }
        let _capture=self.0.begin_capture();
        let synchronize = |client: &MarketClient| {
            let result=synchronizer::synchronize(
                client,
                server,
                &self.0.path.join("market-v1.sqlite"),
                run,
                local_override,
                &SystemClock,
                progress,
                |bootstrap| {
                    if run.cancelled() {
                        return;
                    }
                    if let Err(error) = self.0.save_bootstrap(server, bootstrap) {
                        self.0.set_error(error);
                    }
                },
            )?;
            if matches!(&result,Execution::Completed(_)) {
                match twichui_market_core::delivery::Configuration::load(&self.0.path) {
                    Ok(Some(mut config)) if config.enabled && config.scope.server==server && (config.scope.market_id==run.market||config.version==2)
                        && profile.bootstrap.as_ref().is_some_and(|b|b.account.id==config.scope.account_id)=>{
                        if config.version==2&&config.scope.market_id!=run.market {
                            let region=self.0.local.lock().ok().and_then(|l|l.profile.bootstrap.as_ref().and_then(|b|b.markets.iter().find(|m|m.id==run.market&&m.available_for_sync&&m.player_identity_verified)).map(|m|m.region.clone())).ok_or(Error::Invalid("selected Workshop market unavailable"))?;
                            config=config.follow_selected_market(&self.0.path,run.market,&region)?;
                        }
                        // Delivery has its own durable result. Scalar sync success
                        // is never represented as successful game-file delivery.
                        match twichui_market_core::delivery::synchronize(&self.0.path,client,&config,||run.cancelled()||self.0.quitting.load(Ordering::Acquire)) {
                            Err(e)=>{
                                if matches!(&e,Error::SummaryPreparing(_)) {
                                    if let Ok(mut local)=self.0.local.lock(){if local.error.as_deref().is_some_and(|e|e.starts_with("Workshop delivery:")){local.error=None;}}
                                    return Err(e);
                                }
                                if matches!(&e,Error::Invalid("Waiting for World of Warcraft to close.")) {
                                    if let Ok(mut local)=self.0.local.lock(){if local.error.as_deref().is_some_and(|e|e.starts_with("Workshop delivery:")){local.error=None;}}
                                } else {
                                    self.0.set_error(format!("Workshop delivery: {e}"));
                                    // Use the existing worker's Retry-After/backoff, not a
                                    // second timer. Completed scalar cache remains intact.
                                    if config.version==2 {return Err(e);}
                                }
                            },
                            Ok(_)=>if let Ok(mut local)=self.0.local.lock(){if local.error.as_deref().is_some_and(|e|e.starts_with("Workshop delivery:")){local.error=None;}},
                        }
                    },
                    Err(e)=>self.0.set_error(format!("Workshop delivery configuration: {e}")),
                    _=>{},
                }
            }
            Ok(result)
        };
        let execution=match profile.mode {
            Mode::Companion => AuthorizationClient::new(server)?.authenticated(
                &NativeCredentialStore,
                Utc::now(),
                |session| {
                    if run.cancelled() || self.0.quitting.load(Ordering::Acquire) {
                        return Err(Error::Cancelled);
                    }
                    if !profile.matches_session(session) {
                        return Err(Error::Authentication);
                    }
                    synchronize(&session.client()?)
                },
            ),
            Mode::Legacy => synchronize(&MarketClient::new(server, vault::load(server)?)?),
            Mode::Disconnected => Err(Error::Authentication),
        };
        if matches!(&execution,Ok(Execution::Completed(_))){twichui_market_core::performance::operation(twichui_market_core::performance::Operation::Complete);}
        execution
    }
}
impl Data {
    fn begin_capture(self:&Arc<Self>)->twichui_market_core::performance::Capture {
        let data=self.clone();
        let context=self.local.lock().ok().map(|l|(l.profile.server.clone(),l.profile.bootstrap.as_ref().map(|b|b.account.id)));
        twichui_market_core::performance::Capture::observe(self.performance_capture.load(Ordering::Acquire),move|progress,report|{
            let current=data.local.lock().ok().map(|l|(l.profile.server.clone(),l.profile.bootstrap.as_ref().map(|b|b.account.id)));
            if context!=current{return;}
            if let Ok(mut value)=data.sync_progress.lock(){*value=progress;}
            if data.performance_capture.load(Ordering::Acquire) {if let Some(report)=report {if let Ok(mut reports)=data.performance_reports.lock(){while reports.len()>=4{reports.pop_front();}reports.push_back(report);}}}
            data.emit();
        })
    }
    fn set_error(&self, error: String) {
        if let Ok(mut local) = self.local.lock() {
            local.error = Some(error);
        }
        self.emit();
    }
    fn emit(&self) {
        if let Some(runtime) = self.app.try_state::<Arc<Runtime>>() {
            if let Ok(view) = runtime.view() {
                let _ = self.app.emit("companion-state", view);
            }
        }
    }
    fn save_bootstrap(&self, server: &str, bootstrap: &Bootstrap) -> Result<()> {
        bootstrap.validate().map_err(friendly)?;
        let mut local = self
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?;
        if local.settings.server != server_url(server).map_err(friendly)?.as_str()
            || local.profile.server != local.settings.server
        {
            return Err("Connection changed; the previous server response was discarded".into());
        }
        let mut profile = local.profile.clone();
        if let Some(market) = bootstrap.resolve_market(local.settings.selected_market) {
            profile.last_market = Some(RememberedMarket {
                id: market.id,
                label: market.label.clone(),
            });
        }
        if profile.bootstrap.as_ref().is_some_and(|b|b.account.id!=bootstrap.account.id) {if let Ok(mut reports)=self.performance_reports.lock(){reports.clear();}if let Ok(mut progress)=self.sync_progress.lock(){*progress=Default::default();}}
        profile.bootstrap = Some(bootstrap.clone());
        profile.validate(&local.settings.server).map_err(friendly)?;
        profile.save(&self.path).map_err(friendly)?;
        local.profile = profile;
        drop(local);
        self.emit();
        Ok(())
    }
    fn on_worker(&self, state: State) {
        let mut notify = None;
        if let Ok(mut local) = self.local.lock() {
            if state.sync.last_sync_ms.is_some()
                && !local.settings.onboarding_completed
                && local.settings_valid
            {
                local.settings.onboarding_completed = true;
                if let Err(error) = local.settings.save(&self.path) {
                    local.error = Some(error.to_string());
                }
            }
            if state.error.is_none() {
                local.notified_error = None;
            }
            if let Some(error) = &state.error {
                if local.settings.error_notifications
                    && local.notified_error.as_ref() != Some(error)
                {
                    local.notified_error = Some(error.clone());
                    notify = Some(error.clone());
                }
            }
        }
        crate::shell::update_tray(&self.app, &state);
        if let Some(message) = notify {
            if self
                .app
                .get_webview_window("main")
                .and_then(|window| window.is_visible().ok())
                == Some(false)
            {
                use tauri_plugin_notification::NotificationExt;
                let _ = self
                    .app
                    .notification()
                    .builder()
                    .title("TwichUI Market Companion")
                    .body(message)
                    .show();
            }
        }
        self.emit();
    }
}
impl Runtime {
    pub fn create(app: AppHandle, path: PathBuf) -> Result<Arc<Self>> {
        std::fs::create_dir_all(&path).map_err(friendly)?;
        let (settings,settings_valid,mut error)=match Settings::load(&path){Ok(value)=>(value,true,None),Err(error)=>(Settings::default(),false,Some(format!("Your saved settings need attention: {error}. Restore defaults in Settings to continue; the original file is kept.")))};
        let mut profile = match Profile::load(&path, &settings.server) {
            Ok(Some(profile)) => profile,
            Ok(None) => Profile::disconnected(&settings.server).map_err(friendly)?,
            Err(value) => {
                error=Some(format!("Saved connection details could not be read: {value}. Sign in again to rebuild them."));
                Profile::disconnected(&settings.server).map_err(friendly)?
            }
        };
        let explicit_disconnect = Profile::load(&path, &settings.server)
            .ok()
            .flatten()
            .is_some_and(|value| value.mode == Mode::Disconnected);
        let mut credential_available = false;
        if settings_valid && !explicit_disconnect {
            match NativeCredentialStore.load(&settings.server){
                Ok(session)=>{
                    if !profile.matches_session(&session){profile=Profile::authorized(&settings.server,&session).map_err(friendly)?;}
                    credential_available=true;
                },
                Err(Error::CredentialMissing) if profile.mode!=Mode::Companion=>{
                    if path.join("connection.json").exists() && vault::load(&settings.server).is_ok(){profile.mode=Mode::Legacy;profile.device_id=None;credential_available=true;}
                },
                Err(Error::CredentialMissing)=>error=Some("This desktop connection needs approval. Sign in again; cached data is preserved.".into()),
                Err(value)=>error=Some(value.to_string()), // Never fall back after a failed/corrupt v2 vault read.
            }
        }
        let performance_capture=twichui_market_core::performance::enabled(&path).unwrap_or(false);
        let data = Arc::new(Data {
            app: app.clone(),
            path,
            local: Mutex::new(Local {
                settings: settings.clone(),
                profile,
                credential_available,
                error,
                settings_valid,
                approving: false,
                refreshing: false,
                approval: None,
                approval_cancel: Arc::new(AtomicBool::new(false)),
                notified_error: None,
            }),
            gate: Mutex::new(()),
            quitting: AtomicBool::new(false),
            workshop_review: Mutex::new(None),
            workshop_setup: AtomicBool::new(false),
            performance_capture: AtomicBool::new(performance_capture),
            sync_progress: Mutex::new(Default::default()),
            performance_reports: Mutex::new(Default::default()),
            workshop_failure: Mutex::new(None),
        });
        let observer = data.clone();
        let worker = Arc::new(
            Worker::start(
                SystemClock,
                Settings {
                    selected_market: None,
                    ..settings
                },
                false,
                None,
                Arc::new(NativeTask(data.clone())),
                move |state| observer.on_worker(state),
            )
            .map_err(friendly)?,
        );
        Ok(Arc::new(Self {
            data,
            worker,
            auth_thread: Mutex::new(None),
        }))
    }
    pub fn initialize(self: &Arc<Self>) {
        let (available, has_bootstrap) = {
            let local = self.data.local.lock().unwrap();
            (
                local.credential_available,
                local.profile.bootstrap.is_some(),
            )
        };
        if available && has_bootstrap {
            if let Err(error) = self.configure_worker(true) {
                self.data.set_error(error);
            }
        } else if available {
            let _ = self.refresh_connection();
        }
    }
    pub fn view(&self) -> Result<View> {
        let (settings, profile, connected, approval, approving, refreshing, error, settings_valid) = {
            let local = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings are unavailable")?;
            (
                local.settings.clone(),
                local.profile.clone(),
                local.credential_available,
                local.approval.clone(),
                local.approving,
                local.refreshing,
                local.error.clone(),
                local.settings_valid,
            )
        };
        let sync = self.worker.snapshot().map_err(friendly)?;
        let selected = settings
            .selected_market
            .or(sync.sync.selected_market)
            .or(profile.last_market.as_ref().map(|market| market.id));
        let cache = selected
            .and_then(|id| {
                Cache::open(&self.data.path.join("market-v1.sqlite"))
                    .ok()?
                    .status(&profile.server, id)
                    .ok()
            })
            .map(Into::into);
        Ok(View {
            sync_progress:self.data.sync_progress.lock().map(|p|p.clone()).unwrap_or_default(),
            performance_capture:self.data.performance_capture.load(Ordering::Acquire),
            delivery: match twichui_market_core::delivery::Configuration::load(&self.data.path) {
                Ok(Some(c)) if c.scope.server==profile.server && Some(c.scope.market_id)==selected
                    && profile.bootstrap.as_ref().is_some_and(|b|b.account.id==c.scope.account_id)=>{
                    serde_json::json!({"configuration":c,"status":twichui_market_core::delivery::status_for(&self.data.path,&c).map_err(friendly)?})
                },
                Ok(_)=>serde_json::json!({"notice":"Automatic delivery is off for this account and market. Review setup to enable it."}),
                Err(_)=>serde_json::json!({"notice":"Delivery configuration is invalid; automatic installation is disabled. Review setup."}),
            },
            version: if cfg!(feature = "private-dev") { format!("{} DEV {}", env!("CARGO_PKG_VERSION"), option_env!("COMPANION_DEV_SHA").unwrap_or("local")) } else { env!("CARGO_PKG_VERSION").into() },
            settings,
            mode: profile.mode,
            connected,
            account: profile
                .bootstrap
                .as_ref()
                .map(|value| value.account.clone()),
            bootstrap: profile.bootstrap,
            offline_market: profile.last_market,
            sync,
            cache,
            approval,
            approving,
            refreshing,
            error,
            settings_valid,
            autostart_enabled: crate::startup::is_enabled().unwrap_or(false),
            quitting: self.data.quitting.load(Ordering::Acquire),
            window_visible: self
                .data
                .app
                .get_webview_window("main")
                .and_then(|window| window.is_visible().ok())
                .unwrap_or(false),
        })
    }
    fn effective(&self) -> Result<(Settings, bool)> {
        let local = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?;
        Ok((
            Settings {
                selected_market: local
                    .profile
                    .resolved_market(local.settings.selected_market),
                ..local.settings.clone()
            },
            local.credential_available,
        ))
    }
    fn configure_worker(&self, restore: bool) -> Result<()> {
        let (settings, connected) = self.effective()?;
        let receipt = if restore {
            settings.selected_market.and_then(|id| {
                Cache::open(&self.data.path.join("market-v1.sqlite"))
                    .ok()?
                    .completion(&settings.server, id)
                    .ok()
                    .flatten()
            })
        } else {
            None
        };
        self.worker
            .configure_receipt(settings, connected, receipt.as_ref())
            .map_err(friendly)
    }
    pub fn sign_in(self: &Arc<Self>, device_name: String) -> Result<()> {
        self.cancel_workshop()?;
        if self.quitting() {
            return Err("The companion is closing. Please wait.".into());
        }
        let (server, cancel) = {
            let mut local = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings are unavailable")?;
            if !local.settings_valid {
                return Err("Restore your settings before signing in".into());
            }
            if local.approving || local.refreshing {
                return Err("Finish or cancel the current connection request first".into());
            }
            local.approving = true;
            local.approval = None;
            local.error = None;
            local.approval_cancel = Arc::new(AtomicBool::new(false));
            (local.settings.server.clone(), local.approval_cancel.clone())
        };
        let (settings, _) = self.effective()?;
        self.worker.configure(settings, false).map_err(friendly)?;
        let owned = self.clone();
        let task = thread::Builder::new()
            .name("market-approval".into())
            .spawn(move || {
                let result = (|| -> Result<()> {
                    let _gate = owned
                        .data
                        .gate
                        .lock()
                        .map_err(|_| "Connection operation interrupted")?;
                    if cancel.load(Ordering::Acquire) {
                        return Err("Connection approval was cancelled".into());
                    }
                    let auth = AuthorizationClient::new(&server).map_err(friendly)?;
                    let pending = auth
                        .begin(&device_name, env!("CARGO_PKG_VERSION"))
                        .map_err(friendly)?;
                    let info = pending.info();
                    {
                        let mut local = owned
                            .data
                            .local
                            .lock()
                            .map_err(|_| "Connection settings are unavailable")?;
                        local.approval = Some(info.clone());
                    }
                    owned.data.emit();
                    if owned
                        .data
                        .app
                        .opener()
                        .open_url(&info.authorization_url, None::<&str>)
                        .is_err()
                    {
                        owned.data.set_error(
                            "Your browser could not open. Use Open approval page to try again."
                                .into(),
                        );
                    }
                    let session = auth
                        .complete(pending, &cancel, &NativeCredentialStore)
                        .map_err(friendly)?;
                    let profile = Profile::authorized(&server, &session).map_err(friendly)?;
                    {
                        let mut local = owned
                            .data
                            .local
                            .lock()
                            .map_err(|_| "Connection settings are unavailable")?;
                        local.profile = profile.clone();
                        local.credential_available = true;
                    }
                    profile.save(&owned.data.path).map_err(friendly)?;
                    let bootstrap = session
                        .client()
                        .map_err(friendly)?
                        .bootstrap()
                        .map_err(friendly)?;
                    owned.data.save_bootstrap(&server, &bootstrap)?;
                    crate::shell::restore(&owned.data.app);
                    Ok(())
                })();
                {
                    if let Ok(mut local) = owned.data.local.lock() {
                        local.approving = false;
                        local.approval = None;
                        local.error = result.err();
                    }
                }
                if !owned.data.quitting.load(Ordering::Acquire) {
                    let _ = owned.worker.wait_idle(Duration::from_secs(2));
                    if let Err(error) = owned.configure_worker(true) {
                        owned.data.set_error(error);
                    }
                }
                owned.data.emit();
            })
            .map_err(friendly)?;
        *self
            .auth_thread
            .lock()
            .map_err(|_| "Connection thread unavailable")? = Some(task);
        self.data.emit();
        Ok(())
    }
    pub fn cancel_approval(&self) -> Result<()> {
        self.data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?
            .approval_cancel
            .store(true, Ordering::Release);
        Ok(())
    }
    pub fn reopen_approval(&self) -> Result<()> {
        let info = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?
            .approval
            .clone()
            .ok_or("Start a connection first")?;
        if info.expires_at <= Utc::now() {
            return Err("Approval expired. Start again.".into());
        }
        self.data
            .app
            .opener()
            .open_url(info.authorization_url, None::<&str>)
            .map_err(|_| "Could not open your browser".into())
    }
    pub fn refresh_connection(self: &Arc<Self>) -> Result<()> {
        if self.quitting() {
            return Err("The companion is closing. Please wait.".into());
        }
        let server = {
            let mut local = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings are unavailable")?;
            if local.refreshing || local.approving {
                return Err("A connection request is already running".into());
            }
            local.refreshing = true;
            local.error = None;
            local.settings.server.clone()
        };
        let owned = self.clone();
        thread::Builder::new()
            .name("market-connection".into())
            .spawn(move || {
                let result = (|| -> Result<()> {
                    let _gate = owned
                        .data
                        .gate
                        .lock()
                        .map_err(|_| "Connection operation interrupted")?;
                    let profile = owned
                        .data
                        .local
                        .lock()
                        .map_err(|_| "Connection settings are unavailable")?
                        .profile
                        .clone();
                    if profile.server != server {
                        return Err(
                            "Connection changed; check the current website connection".into()
                        );
                    }
                    if owned.data.quitting.load(Ordering::Acquire) {
                        return Ok(());
                    }
                    let client = match profile.mode {
                        Mode::Companion => {
                            let session = AuthorizationClient::new(&profile.server)
                                .map_err(friendly)?
                                .session(&NativeCredentialStore, Utc::now())
                                .map_err(friendly)?;
                            session.client().map_err(friendly)?
                        }
                        Mode::Legacy => MarketClient::new(
                            &profile.server,
                            vault::load(&profile.server).map_err(friendly)?,
                        )
                        .map_err(friendly)?,
                        Mode::Disconnected => return Err("Sign in to connect this desktop".into()),
                    };
                    let bootstrap = client.bootstrap().map_err(friendly)?;
                    owned.data.save_bootstrap(&profile.server, &bootstrap)?;
                    Ok(())
                })();
                if let Ok(mut local) = owned.data.local.lock() {
                    local.refreshing = false;
                    if local.settings.server == server {
                        if let Err(error) = result {
                            local.error = Some(error);
                        } else {
                            local.credential_available = true;
                        }
                    }
                }
                let _ = owned.worker.wait_idle(Duration::from_secs(2));
                if let Err(error) = owned.configure_worker(true) {
                    owned.data.set_error(error);
                }
                owned.data.emit();
            })
            .map_err(friendly)?;
        self.data.emit();
        Ok(())
    }
    pub fn save_settings(&self, mut settings: Settings, reset_invalid: bool) -> Result<()> {
        if self.quitting() {
            return Err("The companion is closing. Please wait.".into());
        }
        settings.server = server_url(&settings.server).map_err(friendly)?.to_string();
        settings.validate().map_err(friendly)?;
        let (old, valid, approving) = {
            let local = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings are unavailable")?;
            (
                local.settings.clone(),
                local.settings_valid,
                local.approving,
            )
        };
        if !valid && !reset_invalid {
            return Err("Use Restore defaults to preserve and replace invalid settings".into());
        }
        if settings.server != old.server && approving {
            return Err("Cancel browser approval before changing the server".into());
        }
        let changed_profile = if settings.server != old.server {
            Some(
                Profile::load(&self.data.path, &settings.server)
                    .map_err(friendly)?
                    .unwrap_or(Profile::disconnected(&settings.server).map_err(friendly)?),
            )
        } else {
            None
        };
        if !valid {
            let path = self.data.path.join("settings.json");
            if path.exists() {
                if std::fs::metadata(&path).map_err(friendly)?.len() > 8192 {
                    return Err(
                        "The settings file is too large to repair here; the original has been kept"
                            .into(),
                    );
                }
                let bytes = std::fs::read(&path).map_err(friendly)?;
                std::fs::write(
                    self.data.path.join(format!(
                        "settings-before-repair-{}.json",
                        Utc::now().timestamp_millis()
                    )),
                    bytes,
                )
                .map_err(friendly)?;
            }
        }
        let actual = crate::startup::is_enabled()
            .map_err(|_| "Could not read the Windows startup setting")?;
        if settings.launch_at_login != actual {
            if settings.launch_at_login {
                crate::startup::enable()
            } else {
                crate::startup::disable()
            }
            .map_err(|_| "Windows could not update the startup setting")?;
        }
        if settings.server != old.server {
            settings.selected_market = None;
            settings.onboarding_completed = false;
        }
        if let Err(error) = settings.save(&self.data.path) {
            if actual {
                let _ = crate::startup::enable();
            } else {
                let _ = crate::startup::disable();
            }
            return Err(error.to_string());
        }
        {
            let mut local = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings are unavailable")?;
            if let Some(profile) = changed_profile {
                local.profile = profile;
                local.credential_available = false;
            }
            local.settings = settings;
            local.settings_valid = true;
            local.error = None;
        }
        self.configure_worker(false)?;
        self.data.emit();
        Ok(())
    }
    pub fn pause(&self) -> Result<()> {
        let mut settings = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?
            .settings
            .clone();
        settings.automatic_sync = false;
        self.save_settings(settings, false)
    }
    pub fn resume(&self) -> Result<()> {
        let mut settings = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?
            .settings
            .clone();
        settings.automatic_sync = true;
        self.save_settings(settings, false)
    }
    pub fn export(&self) -> Result<String> {
        let view = self.view()?;
        let market = view
            .settings
            .selected_market
            .or(view.sync.sync.selected_market)
            .or(view.offline_market.as_ref().map(|market| market.id))
            .ok_or("Choose a market first")?;
        let dir = self.data.path.join("exports");
        std::fs::create_dir_all(&dir).map_err(friendly)?;
        let output = Cache::open(&self.data.path.join("market-v1.sqlite"))
            .map_err(friendly)?
            .export(&view.settings.server, market, &dir)
            .map_err(friendly)?;
        Ok(output.to_string_lossy().into_owned())
    }
    /// Explicit M1b test export. No automatic schedule, game discovery or installation.
    pub fn export_workshop(&self,algorithm:&str) -> Result<String> {
        let _gate=self.data.gate.lock().map_err(|_| "Connection operation interrupted")?;
        let view=self.view()?;
        if view.approving || view.refreshing || !view.connected {return Err("Finish connecting before exporting Workshop data".into())}
        let profile=self.data.local.lock().map_err(|_| "Connection settings unavailable")?.profile.clone();
        let account=profile.bootstrap.as_ref().ok_or("Refresh the connection before exporting")?.account.id;
        let market=view.settings.selected_market.or(view.sync.sync.selected_market).ok_or("Choose a market first")?;
        let scope=twichui_market_core::bridge::Scope{server:server_url(&view.settings.server).map_err(friendly)?.to_string(),account_id:account,market_id:market,algorithm:algorithm.into()};
        let mut cache=twichui_market_core::bridge::BridgeCache::open(&self.data.path.join("bridge-v1.sqlite")).map_err(friendly)?;
        let download=|client:&MarketClient,cache:&mut twichui_market_core::bridge::BridgeCache| client.download_bridge(cache,&scope,||self.data.quitting.load(Ordering::Acquire));
        match profile.mode {
            Mode::Companion=>AuthorizationClient::new(&scope.server).map_err(friendly)?.authenticated(&NativeCredentialStore,Utc::now(),|session|{
                if !profile.matches_session(session){return Err(Error::Authentication)}
                download(&session.client()?,&mut cache)
            }).map_err(friendly)?,
            Mode::Legacy=>download(&MarketClient::new(&scope.server,vault::load(&scope.server).map_err(friendly)?).map_err(friendly)?,&mut cache).map_err(friendly)?,
            Mode::Disconnected=>return Err("Sign in before exporting".into()),
        }
        if self.data.quitting.load(Ordering::Acquire){return Err("Export cancelled".into())}
        // Settings can change while the native connection gate is held. Never publish
        // an export for a connection/market that is no longer selected.
        let current=self.view()?;
        let current_account=self.data.local.lock().map_err(|_| "Connection settings unavailable")?.profile.bootstrap.as_ref().map(|b|b.account.id);
        if !current.connected || server_url(&current.settings.server).map_err(friendly)?.as_str()!=scope.server
            || current_account!=Some(account) || current.settings.selected_market.or(current.sync.sync.selected_market)!=Some(market) {
            return Err("Connection or market changed. Completed data is preserved; export again for the selected market.".into())
        }
        let root=twichui_market_core::bridge::staging_directory(&self.data.path,&scope).map_err(friendly)?;
        let output=twichui_market_core::bridge::export_staging(&cache,&scope,&root).map_err(friendly)?;
        Ok(output.to_string_lossy().into_owned())
    }
    /// Manual archive/scope setup; the worker uses the same core archive path.
    pub fn archive_workshop(
        &self,
        algorithm: &str,
        disk_budget_mib: u64,
        selected: Option<serde_json::Value>,
        publish: bool,
        compatible: bool,
    ) -> Result<serde_json::Value> {
        let _gate = self
            .data
            .gate
            .lock()
            .map_err(|_| "Connection operation interrupted")?;
        let _capture=self.data.begin_capture();
        let view = self.view()?;
        if view.approving || view.refreshing {
            return Err("Finish connecting before using history archives".into());
        }
        if !(64..=65536).contains(&disk_budget_mib) {
            return Err("Archive disk budget must be 64–65536 MiB".into());
        }
        let profile = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings unavailable")?
            .profile
            .clone();
        if profile.mode == Mode::Disconnected {
            return Err("Sign in before selecting a private archive".into());
        }
        let account = profile
            .bootstrap
            .as_ref()
            .ok_or("Refresh the connection before using an archive")?
            .account
            .id;
        let market = view
            .settings
            .selected_market
            .or(view.sync.sync.selected_market)
            .ok_or("Choose a market first")?;
        let scope = twichui_market_core::bridge::Scope {
            server: server_url(&view.settings.server)
                .map_err(friendly)?
                .to_string(),
            account_id: account,
            market_id: market,
            algorithm: algorithm.into(),
        };
        let mut archive = twichui_market_core::archive::ArchiveStore::open(
            &self.data.path.join("history-archive-v1.sqlite"),
            disk_budget_mib * 1024 * 1024,
        )
        .map_err(friendly)?;
        if selected.is_none() {
            let download =
                |client: &MarketClient, cache: &mut twichui_market_core::archive::ArchiveStore| {
                    client.download_archive(cache, &scope, || {
                        self.data.quitting.load(Ordering::Acquire)
                    })
                };
            match profile.mode {
                Mode::Companion => AuthorizationClient::new(&scope.server)
                    .map_err(friendly)?
                    .authenticated(&NativeCredentialStore, Utc::now(), |session| {
                        if !profile.matches_session(session) {
                            return Err(Error::Authentication);
                        }
                        download(&session.client()?, &mut archive)
                    })
                    .map_err(friendly)?,
                Mode::Legacy => download(
                    &MarketClient::new(
                        &scope.server,
                        vault::load(&scope.server).map_err(friendly)?,
                    )
                    .map_err(friendly)?,
                    &mut archive,
                )
                .map_err(friendly)?,
                Mode::Disconnected => return Err("Sign in before synchronizing history".into()),
            }
        }
        let verify_context = || -> Result<()> {
            let current = self.view()?;
            let account_now = self
                .data
                .local
                .lock()
                .map_err(|_| "Connection settings unavailable")?
                .profile
                .bootstrap
                .as_ref()
                .map(|b| b.account.id);
            if self.data.quitting.load(Ordering::Acquire)
                || server_url(&current.settings.server)
                    .map_err(friendly)?
                    .as_str()
                    != scope.server
                || account_now != Some(account)
                || current
                    .settings
                    .selected_market
                    .or(current.sync.sync.selected_market)
                    != Some(market)
            {
                return Err("Connection or market changed; completed archive preserved".into());
            }
            Ok(())
        };
        verify_context()?;
        let header = archive
            .active(&scope)
            .map_err(friendly)?
            .ok_or("Complete the retained-history download first")?;
        let mut result = serde_json::json!({"header":header,"archive_bytes":archive.allocated_bytes().map_err(friendly)?,"selection":archive.selection(&scope).map_err(friendly)?,
            "schema3_workshop_runtime_available":true,"notice":"Schema 3 requires the compatible installed Workshop reader. Manual exports stay in staging; automatic delivery is separately configured."});
        if let Some(input) = selected {
            let object = input.as_object().ok_or("Invalid exact selection")?;
            if object.len() != 3
                || !["variants", "history_from_day", "history_through_day"]
                    .iter()
                    .all(|k| object.contains_key(*k))
            {
                return Err("Selection requires exact variants and a date window".into());
            }
            let request=twichui_market_core::archive::normalize_selection(serde_json::json!({"format":"twichui-market-selection","contract_version":1,"expected_schema_version":3,
                "issuer_id":header.issuer_id,"market":header.market,"scope_type":"explicit_variants","variants":input["variants"],"history_from_day":input["history_from_day"],"history_through_day":input["history_through_day"],
                "pricing_algorithm":header.pricing_algorithm,"history_basis":header.history_basis,"profile":"daily_research_v1"})).map_err(friendly)?;
            archive.save_selection(&scope, &request).map_err(friendly)?;
            let (generation, receipt, sizes) = twichui_market_core::archive::project(
                &archive,
                &scope,
                &request,
                &twichui_market_core::archive::DeliveryBudget::default(),
            )
            .map_err(friendly)?;
            result["selection"] = request;
            result["sizes"] = serde_json::to_value(sizes).map_err(|_| "Size report unavailable")?;
            result["generation_id"] = generation["generation_id"].clone();
            if publish {
                if !compatible {
                    return Err("Confirm the installed schema-3 Workshop reader before staging".into());
                }
                let current = self.view()?;
                let current_account = self
                    .data
                    .local
                    .lock()
                    .map_err(|_| "Connection settings unavailable")?
                    .profile
                    .bootstrap
                    .as_ref()
                    .map(|b| b.account.id);
                if self.data.quitting.load(Ordering::Acquire)
                    || server_url(&current.settings.server)
                        .map_err(friendly)?
                        .as_str()
                        != scope.server
                    || current_account != Some(account)
                    || current
                        .settings
                        .selected_market
                        .or(current.sync.sync.selected_market)
                        != Some(market)
                {
                    return Err("Connection or market changed; completed archive preserved".into());
                }
                let root = twichui_market_core::bridge::staging_directory(&self.data.path, &scope)
                    .map_err(friendly)?;
                let path = twichui_market_core::bridge::export_generation(
                    &scope,
                    &root,
                    &generation,
                    &receipt,
                    &twichui_market_core::archive::DeliveryBudget::default(),
                )
                .map_err(friendly)?;
                result["path"] = path.to_string_lossy().into_owned().into();
            }
        }
        verify_context()?;
        Ok(result)
    }
    /// The ordinary WebView supplies intent, never an installation path.
    pub fn prepare_workshop(&self) -> Result<serde_json::Value> {
        self.workshop_result(self.prepare_workshop_inner())
    }
    fn workshop_result<T>(&self, result:Result<T>)->Result<T> {
        use twichui_market_core::workshop_setup::Failure;
        match result {
            Ok(value)=>{if let Ok(mut last)=self.data.workshop_failure.lock(){*last=None;} Ok(value)}
            Err(error)=>{
                let failure=serde_json::from_str::<Failure>(&error).unwrap_or_else(|_|{
                    let (code,stage,detail)=match error.as_str() {
                        "Folder selection cancelled." => ("cancelled","folder_picker","native dialog cancelled"),
                        "Connection changed. Connect Workshop again." => ("context_changed","setup_context","account, origin or market changed"),
                        "Workshop confirmation expired. Connect again." | "Connect Workshop again to confirm its installation." => ("context_changed","confirmation","review expired or already consumed"),
                        "Finish signing in before connecting Workshop." | "Sign in before connecting Workshop." | "Choose your market first." | "Your selected market is unavailable. Retry after synchronization." => ("context_changed","setup_context","authenticated market is not ready"),
                        _ => ("internal","setup","unexpected native setup failure"),
                    };
                    Failure::new(code,stage,detail.into())
                });
                if let Ok(mut last)=self.data.workshop_failure.lock(){*last=Some(failure.clone());}
                Err(serde_json::to_string(&failure).unwrap_or_else(|_|"Workshop setup interrupted".into()))
            }
        }
    }
    fn prepare_workshop_inner(&self) -> Result<serde_json::Value> {
        use twichui_market_core::{delivery::{self,Configuration},installation};
        if self.data.workshop_setup.compare_exchange(false,true,Ordering::AcqRel,Ordering::Acquire).is_err() {
            return Err("Workshop setup is already open.".into());
        }
        struct Reset<'a>(&'a AtomicBool);
        impl Drop for Reset<'_>{fn drop(&mut self){self.0.store(false,Ordering::Release);}}
        let _reset=Reset(&self.data.workshop_setup);
        *self.data.workshop_review.lock().map_err(|_|"Workshop setup interrupted")?=None;
        let view=self.view()?;
        if !view.connected||view.approving||view.refreshing {return Err("Finish signing in before connecting Workshop.".into());}
        let account=view.account.as_ref().ok_or("Sign in before connecting Workshop.")?.id;
        let market=view.settings.selected_market.or(view.sync.sync.selected_market).ok_or("Choose your market first.")?;
        let chosen=view.bootstrap.as_ref().and_then(|b|b.markets.iter().find(|m|m.id==market))
            .filter(|m|m.available_for_sync&&m.verified&&m.player_identity_verified).ok_or("Your selected market is unavailable. Retry after synchronization.")?;
        let scope=twichui_market_core::bridge::Scope{server:view.settings.server.clone(),account_id:account,market_id:market,algorithm:"twichui-pricing-v1".into()};
        let previous=delivery::Configuration::load(&self.data.path).map_err(|e|setup_core("saved_configuration",e))?
            .filter(|c|c.scope.server==scope.server&&c.scope.account_id==account);
        if let Some(c)=previous.as_ref().filter(|c|c.version==2&&c.enabled&&c.scope.market_id==market) {
            if delivery::inspect_destination(c).is_ok() {self.worker.sync_now().map_err(friendly)?;return Ok(serde_json::json!({"connected":true}));}
        }
        let found=installation::discover(previous.as_ref().map(|c|c.installation.as_path()));
        let installation=if found.len()==1 {found[0].clone()}else{
            installation::choose_folder().map_err(|e|setup_core("folder_picker",e))?.ok_or("Folder selection cancelled.")?
        };
        let current=self.view()?;
        if !current.connected||current.approving||current.refreshing||current.account.as_ref().map(|a|a.id)!=Some(account)
            ||current.settings.server!=scope.server||current.settings.selected_market.or(current.sync.sync.selected_market)!=Some(market) {
            return Err("Connection changed. Connect Workshop again.".into());
        }
        let mut config=Configuration{version:2,enabled:true,scope,installation,
            selection:serde_json::json!({"kind":"broad_summary","market_id":market,"region":chosen.region}),history_days:0};
        if let Some(old)=previous.as_ref().filter(|old|old.installation!=config.installation) {
            config.selection["previous_installation"]=old.installation.to_string_lossy().into_owned().into();
        }
        if let Some(old)=previous.as_ref().filter(|old|old.version==1&&old.scope!=config.scope) {
            config.selection["previous_scope"]=old.scope.key().map_err(friendly)?.into();
        }
        let inspected=match delivery::inspect_destination(&config) {
            Ok(value)=>value,
            Err(first)=>{
                // A second move can happen before an interrupted first move
                // has updated every bank's marker. Both paths come from the
                // existing account/origin's native configuration, never IPC.
                if let Some(original)=previous.as_ref().and_then(|c|c.selection.get("previous_installation")) {
                    config.selection["previous_installation"]=original.clone();
                    delivery::inspect_destination(&config).map_err(|e|setup_core("destination",e))?
                } else {return Err(setup_core("destination",first));}
            }
        };
        // Discovery/dialog may outlive account changes. Do not authorize or
        // retain a path for a different account/origin/market context.
        let _gate=self.data.gate.lock().map_err(|_|"Connection operation interrupted")?;
        let current=self.view()?;
        if !current.connected||current.approving||current.refreshing||current.account.as_ref().map(|a|a.id)!=Some(account)||current.settings.server!=config.scope.server
            ||current.settings.selected_market.or(current.sync.sync.selected_market)!=Some(market) {
            return Err("Connection changed. Connect Workshop again.".into());
        }
        let review=twichui_market_core::workshop_summary::review_nonce().map_err(friendly)?;
        *self.data.workshop_review.lock().map_err(|_|"Workshop setup interrupted")?=Some((review.clone(),config.clone(),Utc::now()+chrono::Duration::minutes(10)));
        Ok(serde_json::json!({"review_id":review,"installation":config.installation,"market":chosen.label,
            "requires_adoption":inspected["requires_adoption"]}))
    }
    pub fn cancel_workshop(&self)->Result<()> {
        *self.data.workshop_review.lock().map_err(|_|"Workshop setup interrupted")?=None;Ok(())
    }
    pub fn confirm_workshop(&self,review_id:String)->Result<()> {
        self.workshop_result(self.confirm_workshop_inner(review_id))
    }
    fn confirm_workshop_inner(&self,review_id:String)->Result<()> {
        let _gate=self.data.gate.lock().map_err(|_|"Connection operation interrupted")?;
        let review=self.data.workshop_review.lock().map_err(|_|"Workshop setup interrupted")?.take().ok_or("Connect Workshop again to confirm its installation.")?;
        if review.0!=review_id||review.2<Utc::now() {return Err("Workshop confirmation expired. Connect again.".into());}
        let config=review.1;let view=self.view()?;
        if !view.connected||view.approving||view.refreshing||view.account.as_ref().map(|a|a.id)!=Some(config.scope.account_id)
            ||view.settings.server!=config.scope.server||view.settings.selected_market.or(view.sync.sync.selected_market)!=Some(config.scope.market_id) {
            return Err("Connection changed. Connect Workshop again.".into());
        }
        config.save_confirmed(&self.data.path,true).map_err(|e|setup_core("confirmation",e))?;
        self.data.emit();self.worker.sync_now().map_err(friendly)?;Ok(())
    }
    pub fn configure_delivery(&self, installation: String, algorithm: String, history_days: u32, operation: String, confirmed: bool, variants: serde_json::Value) -> Result<serde_json::Value> {
        use twichui_market_core::delivery::{self, Configuration};
        let _gate=self.data.gate.lock().map_err(|_|"Connection operation interrupted")?;
        let view=self.view()?;
        let account=view.account.as_ref().ok_or("Connect before configuring delivery")?.id;
        let market=view.settings.selected_market.or(view.sync.sync.selected_market).ok_or("Choose a market first")?;
        let scope=twichui_market_core::bridge::Scope{server:view.settings.server.clone(),account_id:account,market_id:market,algorithm};
        if operation=="disable" || operation=="rollback" {
            let mut c=Configuration::load(&self.data.path).map_err(friendly)?.ok_or("Delivery has not been configured")?;
            if c.scope!=scope{return Err("Delivery belongs to another account or market; select its original context".into())}
            c.enabled=false;c.save_confirmed(&self.data.path,false).map_err(friendly)?;
            if operation=="rollback" {if !confirmed{return Err("Confirm restoring the previous generation with WoW closed".into())}delivery::restore_previous(&self.data.path,&c).map_err(friendly)?;}
            self.data.emit();return Ok(serde_json::json!({"enabled":false}));
        }
        if !view.connected || view.refreshing || view.approving {return Err("Finish connecting before configuring delivery".into())}
        let store=twichui_market_core::archive::ArchiveStore::open(&self.data.path.join("history-archive-v1.sqlite"),twichui_market_core::archive::DEFAULT_DISK_BUDGET).map_err(friendly)?;
        let selection=store.selection(&scope).map_err(friendly)?.ok_or("Download history and check an explicit selection of up to ten variants first")?;
        let mut checked=selection.clone();checked["variants"]=variants;
        let checked=twichui_market_core::archive::normalize_selection(checked).map_err(friendly)?;
        if checked["variants"]!=selection["variants"] {return Err("Check the current exact selection and sizes before reviewing delivery".into())}
        let c=Configuration{version:1,enabled:true,scope,installation:PathBuf::from(installation),selection,history_days};
        let mut review=delivery::inspect_destination(&c).map_err(friendly)?;
        let header=store.active(&c.scope).map_err(friendly)?.ok_or("Complete the archive first")?;
        let request=delivery::request_for(&c,&header).map_err(friendly)?;
        let (g,_,sizes)=twichui_market_core::archive::project(&store,&c.scope,&request,&delivery::budget()).map_err(friendly)?;
        review["sizes"]=serde_json::to_value(sizes).map_err(|_|"Size report unavailable")?;review["history_days"]=history_days.into();review["generation_id"]=g["generation_id"].clone();
        if operation=="enable" {c.save_confirmed(&self.data.path,confirmed).map_err(friendly)?;self.data.emit();}
        else if operation!="inspect" {return Err("Unknown delivery operation".into())}
        Ok(review)
    }
    pub fn open_exports(&self) -> Result<()> {
        let dir = self.data.path.join("exports");
        std::fs::create_dir_all(&dir).map_err(friendly)?;
        self.data
            .app
            .opener()
            .open_path(dir.to_string_lossy(), None::<&str>)
            .map_err(|_| "Could not open the companion folder".into())
    }
    pub fn open_website(&self, page: &str) -> Result<()> {
        let path = match page {
            "account" => "account",
            "setup" => "companion",
            _ => return Err("Unknown website page".into()),
        };
        let server = self
            .data
            .local
            .lock()
            .map_err(|_| "Connection settings are unavailable")?
            .settings
            .server
            .clone();
        let url = server_url(&server)
            .map_err(friendly)?
            .join(path)
            .map_err(|_| "Website address unavailable")?;
        self.data
            .app
            .opener()
            .open_url(url.as_str(), None::<&str>)
            .map_err(|_| "Could not open your browser".into())
    }
    pub fn disconnect(self: &Arc<Self>) -> Result<()> {
        self.cancel_workshop()?;
        if self.quitting() {
            return Err("The companion is closing. Please wait.".into());
        }
        self.cancel_approval()?;
        let (settings, _) = self.effective()?;
        self.worker.configure(settings, false).map_err(friendly)?;
        let owned = self.clone();
        thread::Builder::new().name("market-disconnect".into()).spawn(move || {
            let result=(||->Result<()> {
                let _gate=owned.data.gate.lock().map_err(|_|"Connection operation interrupted")?;let profile=owned.data.local.lock().map_err(|_|"Connection settings are unavailable")?.profile.clone();let mut warning=None;
                if profile.mode==Mode::Companion {
                    match AuthorizationClient::new(&profile.server).and_then(|auth|{let session=auth.renew(&NativeCredentialStore,Utc::now())?;auth.revoke(&session)}){
                        Ok(())|Err(Error::Authentication)|Err(Error::CredentialMissing)=>{},
                        Err(_)=>warning=Some("Signed out here. When online, revoke this desktop in Account & Devices on the website.".to_string()),
                    }
                    NativeCredentialStore.remove(&profile.server).map_err(friendly)?;
                }else if profile.mode==Mode::Legacy{vault::remove(&profile.server).map_err(friendly)?;warning=Some("Signed out here. Revoke the old device token in Account & Devices on the website.".into());}
                let mut replacement=Profile::disconnected(&profile.server).map_err(friendly)?;
                replacement.last_market=profile.last_market;
                {let mut local=owned.data.local.lock().map_err(|_|"Connection settings are unavailable")?;local.profile=replacement.clone();local.credential_available=false;local.error=warning;}
                replacement.save(&owned.data.path).map_err(friendly)?;Ok(())
            })();if let Err(error)=result{owned.data.set_error(error)}owned.data.emit();
        }).map_err(friendly)?;
        Ok(())
    }
    pub fn should_hide_on_start(&self) -> bool {
        self.effective()
            .ok()
            .is_some_and(|(settings, connected)| settings.should_start_hidden(connected))
    }
    pub fn hide_on_close(&self) -> bool {
        self.data
            .local
            .lock()
            .is_ok_and(|local| local.settings.onboarding_completed && local.settings.close_to_tray)
    }
    pub fn hide_on_minimize(&self) -> bool {
        self.data.local.lock().is_ok_and(|local| {
            local.settings.onboarding_completed && local.settings.minimize_to_tray
        })
    }
    pub fn claim_update_notice(&self, version: &str, background: bool) -> Result<bool> {
        twichui_market_core::update::claim_update_notice(&self.data.path,version,background).map_err(friendly)
    }
    pub fn updates_eligible(&self) -> bool {
        !cfg!(feature = "private-dev") && !self.quitting()
            && self.data.local.lock().is_ok_and(|local| {
                local.settings_valid
                    && local.credential_available
                    && matches!(local.profile.mode, Mode::Companion | Mode::Legacy)
                    && local.profile.server == format!("{}/", twichui_market_core::update::ORIGIN)
                    && local.settings.server == local.profile.server
            })
    }
    /// Tokens remain inside the core client and native gate; no IPC can receive them.
    pub fn with_update_client<T>(
        &self,
        mut operation: impl FnMut(&MarketClient) -> twichui_market_core::Result<T>,
    ) -> twichui_market_core::Result<T> {
        if !self.updates_eligible() {
            return Err(Error::Authentication);
        }
        let _gate = self
            .data
            .gate
            .try_lock()
            .map_err(|_| Error::ServiceUnavailable)?;
        if self.quitting() {
            return Err(Error::Cancelled);
        }
        let profile = self
            .data
            .local
            .lock()
            .map_err(|_| Error::Invalid("connection settings"))?
            .profile
            .clone();
        if profile.server != format!("{}/", twichui_market_core::update::ORIGIN) {
            return Err(Error::Authentication);
        }
        match profile.mode {
            Mode::Companion => AuthorizationClient::new(&profile.server)?.authenticated(
                &NativeCredentialStore,
                Utc::now(),
                |session| operation(&session.client()?),
            ),
            Mode::Legacy => operation(&MarketClient::new(
                &profile.server,
                vault::load(&profile.server)?,
            )?),
            Mode::Disconnected => Err(Error::Authentication),
        }
    }
    pub fn quitting(&self) -> bool {
        self.data.quitting.load(Ordering::Acquire)
    }
    /// Called only after the updater has verified package bytes and signed version.
    pub fn prepare_update(&self) -> Result<()> {
        if self.data.quitting.swap(true, Ordering::AcqRel) {
            return Err("The companion is already closing.".into());
        }
        crate::updates::stop_background(&self.data.app);
        let result = (|| -> Result<()> {
            self.cancel_approval()?;
            self.worker.shutdown().map_err(friendly)?;
            if let Some(task) = self
                .auth_thread
                .lock()
                .map_err(|_| "Connection operation interrupted")?
                .take()
            {
                task.join()
                    .map_err(|_| "Connection operation interrupted")?;
            }
            let _gate = self
                .data
                .gate
                .lock()
                .map_err(|_| "Connection operation interrupted")?;
            Ok(())
        })();
        if result.is_err() {
            self.update_failed();
        }
        result
    }
    pub fn update_failed(&self) {
        self.data.quitting.store(false, Ordering::Release);
        self.data.set_error(
            "Restart the companion to resume synchronization after the interrupted update.".into(),
        );
    }
    pub fn request_quit(self: &Arc<Self>) {
        if self.data.quitting.swap(true, Ordering::AcqRel) {
            return;
        }
        crate::updates::stop_background(&self.data.app);
        let _ = self.cancel_approval();
        let owned = self.clone();
        self.data.emit();
        thread::spawn(move || {
            let _ = owned.worker.shutdown();
            if let Ok(mut handle) = owned.auth_thread.lock() {
                if let Some(task) = handle.take() {
                    let _ = task.join();
                }
            }
            // Any bounded connection/disconnect request releases the same native gate before exit.
            let _gate = owned.data.gate.lock();
            owned.data.app.exit(0);
        });
    }
    pub fn set_performance_capture(&self,enabled:bool)->Result<()> {
        twichui_market_core::performance::set_enabled(&self.data.path,enabled).map_err(friendly)?;
        self.data.performance_capture.store(enabled,Ordering::Release);
        if !enabled {if let Ok(mut reports)=self.data.performance_reports.lock(){reports.clear();}}
        self.data.emit();Ok(())
    }
    pub fn diagnostics(&self) -> Result<String> {
        let view = self.view()?;
        let document = serde_json::json!({"schema_version":1,"version":view.version,"server":view.settings.server,"workshop_setup":self.data.workshop_failure.lock().ok().and_then(|last|last.clone()),
        "workshop_delivery":twichui_market_core::workshop_setup::delivery_diagnostics(&view.delivery),
        "sync_performance":{"enabled":view.performance_capture,"last_runs":self.data.performance_reports.lock().map(|r|r.iter().cloned().collect::<Vec<_>>()).unwrap_or_default(),"timings":"nested inclusive durations; process CPU delta; process-lifetime peak RSS; no payloads, paths or cursors"},
        "phase":view.sync.sync.phase,"last_sync_ms":view.sync.sync.last_sync_ms,"last_server_check_ms":view.sync.sync.last_server_check_ms,
        "upstream_update_ms":view.sync.sync.upstream_update_ms,"cache":view.cache,"error":view.sync.error,"automatic_sync":view.settings.automatic_sync,"interval_minutes":view.settings.interval_minutes});
        let dir = self.data.path.join("exports");
        std::fs::create_dir_all(&dir).map_err(friendly)?;
        let mut file = tempfile::NamedTempFile::new_in(&dir).map_err(friendly)?;
        serde_json::to_writer_pretty(&mut file, &document).map_err(friendly)?;
        file.flush().map_err(friendly)?;
        file.as_file().sync_all().map_err(friendly)?;
        let target = dir.join("diagnostics-v1.json");
        file.persist(&target).map_err(friendly)?;
        Ok(target.to_string_lossy().into_owned())
    }
}
