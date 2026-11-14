//! Actual API approval/renewal/revocation integration. No credentials on stdout/argv/disk.
use chrono::Utc;
use std::{
    io::{self, Write},
    sync::{atomic::AtomicBool, Mutex},
};
use twichui_market_core::{
    authorization::{AuthorizationClient, CredentialStore, Session},
    cache::Cache,
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
    let pending = client.begin("Synthetic native authorization fixture", "2.0.0-beta.1")?;
    report(serde_json::json!({"stage":"approval","info":pending.info()}));
    let session = client.complete(pending, &AtomicBool::new(false), &store)?;
    session.client()?.authenticate()?;
    let dir = tempfile::tempdir()?;
    let mut cache = Cache::open(&dir.path().join("cache.sqlite"))?;
    while session.client()?.synchronize_page(&mut cache, 1)? {}
    assert_eq!(cache.status(&format!("{server}/"), 1)?.item_count, 2);
    let renewed = client.session(&store, Utc::now())?;
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
