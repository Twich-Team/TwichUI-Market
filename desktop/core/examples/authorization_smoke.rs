//! Actual API approval/renewal/revocation integration. No credentials on stdout/argv/disk.
use chrono::Utc;
use std::{
    io::{self, Write},
    path::PathBuf,
    sync::{atomic::AtomicBool, Arc, Mutex},
    time::Duration,
};
use twichui_market_core::{
    authorization::{AuthorizationClient, CredentialStore, Session},
    cache::Cache,
    scheduler::{Run, SystemClock},
    settings::Settings,
    synchronizer,
    worker::{Execution, Executor, Worker},
    Error, Result,
};

#[cfg(not(windows))]
#[derive(Default)]
struct MemoryStore(Mutex<Option<Vec<u8>>>);
#[cfg(not(windows))]
impl CredentialStore for MemoryStore {
    fn load(&self, _: &str) -> Result<Session> {
        Ok(serde_json::from_slice(
            self.0.lock().unwrap().as_deref().ok_or(Error::Vault)?,
        )?)
    }
    fn save(&self, _: &str, session: &Session) -> Result<()> {
        *self.0.lock().unwrap() = Some(serde_json::to_vec(session)?);
        Ok(())
    }
    fn remove(&self, _: &str) -> Result<()> {
        *self.0.lock().unwrap() = None;
        Ok(())
    }
}
fn report(value: serde_json::Value) {
    println!("{value}");
    io::stdout().flush().unwrap();
}
struct ApiTask<S: CredentialStore + Send + Sync + 'static> {
    store: Arc<S>,
    path: PathBuf,
}
impl<S: CredentialStore + Send + Sync + 'static> Executor for ApiTask<S> {
    fn execute(
        &self,
        server: &str,
        run: &Run,
        progress: &(dyn Fn(u32) + Send + Sync),
    ) -> Result<Execution> {
        let session = AuthorizationClient::new(server)?.session(self.store.as_ref(), Utc::now())?;
        synchronizer::synchronize(
            &session.client()?,
            server,
            &self.path,
            run,
            None,
            &SystemClock,
            progress,
            |_| {},
        )
    }
}
fn main() -> std::result::Result<(), Box<dyn std::error::Error>> {
    let server = std::env::var("MARKET_TEST_SERVER")?;
    assert!(
        server.starts_with("http://127.0.0.1:"),
        "test-only loopback server required"
    );
    let client = AuthorizationClient::new(&server)?;
    #[cfg(windows)]
    let store = twichui_market_core::vault::NativeCredentialStore;
    #[cfg(not(windows))]
    let store = MemoryStore::default();
    let store = Arc::new(store);
    let pending = client.begin("Synthetic native authorization fixture", "2.0.0-beta.1")?;
    report(serde_json::json!({"stage":"approval","info":pending.info()}));
    let session = client.complete(pending, &AtomicBool::new(false), store.as_ref())?;
    session.client()?.authenticate()?;
    let bootstrap = session.client()?.bootstrap()?;
    assert_eq!(bootstrap.account.username, "native_fixture");
    assert_eq!(bootstrap.device.as_ref().unwrap().id, session.device_id());
    let dir = tempfile::tempdir()?;
    let worker = Worker::start(
        SystemClock,
        Settings {
            server: format!("{server}/"),
            selected_market: Some(1),
            automatic_sync: false,
            sync_on_startup: false,
            ..Settings::default()
        },
        true,
        None,
        Arc::new(ApiTask {
            store: store.clone(),
            path: dir.path().join("cache.sqlite"),
        }),
        |_| {},
    )?;
    assert!(worker.sync_now()?);
    assert!(worker.wait_idle(Duration::from_secs(30))?);
    assert!(worker.snapshot()?.error.is_none());
    assert!(worker.snapshot()?.sync.last_sync_ms.is_some());
    worker.shutdown()?;
    let mut cache = Cache::open(&dir.path().join("cache.sqlite"))?;
    assert_eq!(cache.status(&format!("{server}/"), 1)?.item_count, 2);
    let target = cache.completed_target(&format!("{server}/"), 1)?.unwrap();
    let current = client.session(store.as_ref(), Utc::now())?;
    let source = current.client()?.provenance(1, &target)?;
    assert_eq!(source.market_id, 1);
    cache.record_completion(
        &format!("{server}/"),
        1,
        &twichui_market_core::cache::Completion {
            schema_version: 1,
            last_sync_ms: Utc::now().timestamp_millis(),
            source,
        },
    )?;
    assert!(cache.completion(&format!("{server}/"), 1)?.is_some());
    current.client()?.activity(Some(1), "2.0.0-beta.1")?;
    let renewed = client.session(store.as_ref(), Utc::now())?;
    renewed.client()?.authenticate()?;
    assert!(
        matches!(session.client()?.authenticate(), Err(Error::Authentication)),
        "rotation must reject superseded access"
    );
    report(
        serde_json::json!({"stage":"synced_and_renewed","device_id":renewed.device_id(),"item_count":2}),
    );
    let mut line = String::new();
    io::stdin().read_line(&mut line)?;
    assert_eq!(line.trim(), "revoked");
    assert!(matches!(
        renewed.client()?.authenticate(),
        Err(Error::Authentication)
    ));
    assert_eq!(cache.status(&format!("{server}/"), 1)?.item_count, 2);
    store.remove(&server)?;
    report(serde_json::json!({"stage":"revocation_verified_offline_cache_preserved"}));
    Ok(())
}
