//! Non-sensitive desktop settings. Credentials belong exclusively in the native vault.
use crate::{client::server_url, Error, Result};
use serde::{Deserialize, Serialize};
use std::{
    fs::File,
    io::{Read, Write},
    path::Path,
};

pub const SETTINGS_VERSION: u32 = 1;
pub const MAX_SETTINGS_BYTES: u64 = 8192;
pub const INTERVAL_MINUTES: [u32; 5] = [15, 30, 60, 120, 240];
pub const PRODUCTION_ORIGIN: &str = "https://market.twich.gg/";

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Settings {
    pub schema_version: u32,
    pub server: String,
    pub launch_at_login: bool,
    pub start_in_tray: bool,
    pub minimize_to_tray: bool,
    pub close_to_tray: bool,
    pub automatic_sync: bool,
    pub interval_minutes: u32,
    pub sync_on_startup: bool,
    pub error_notifications: bool,
    pub selected_market: Option<u32>,
    pub onboarding_completed: bool,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            schema_version: SETTINGS_VERSION,
            server: PRODUCTION_ORIGIN.into(),
            launch_at_login: false,
            start_in_tray: false,
            minimize_to_tray: false,
            close_to_tray: true,
            automatic_sync: true,
            interval_minutes: 30,
            sync_on_startup: true,
            error_notifications: true,
            selected_market: None,
            onboarding_completed: false,
        }
    }
}

fn bounded_read(path: &Path) -> Result<Vec<u8>> {
    let mut bytes = Vec::new();
    File::open(path)?
        .take(MAX_SETTINGS_BYTES + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_SETTINGS_BYTES {
        return Err(Error::Invalid("settings exceed size limit"));
    }
    Ok(bytes)
}

impl Settings {
    pub fn validate(&self) -> Result<()> {
        if self.schema_version != SETTINGS_VERSION {
            return Err(Error::Invalid("unsupported settings version"));
        }
        server_url(&self.server)?;
        if !INTERVAL_MINUTES.contains(&self.interval_minutes) {
            return Err(Error::Invalid("synchronization interval"));
        }
        if self
            .selected_market
            .is_some_and(|id| id == 0 || id > i32::MAX as u32)
        {
            return Err(Error::Invalid("selected market"));
        }
        Ok(())
    }

    /// Read legacy nonsecret connection.json without deleting it or changing its vault/cache key.
    pub fn load(directory: &Path) -> Result<Self> {
        let current = directory.join("settings.json");
        let settings = if current.exists() {
            serde_json::from_slice(&bounded_read(&current)?)?
        } else if directory.join("connection.json").exists() {
            #[derive(Deserialize)]
            #[serde(deny_unknown_fields)]
            struct Legacy {
                server: String,
            }
            let legacy: Legacy =
                serde_json::from_slice(&bounded_read(&directory.join("connection.json"))?)?;
            Self {
                server: server_url(&legacy.server)?.to_string(),
                ..Self::default()
            }
        } else {
            Self::default()
        };
        settings.validate()?;
        Ok(settings)
    }

    pub fn save(&self, directory: &Path) -> Result<()> {
        self.validate()?;
        std::fs::create_dir_all(directory)?;
        let mut file = tempfile::NamedTempFile::new_in(directory)?;
        serde_json::to_writer_pretty(&mut file, self)?;
        file.flush()?;
        file.as_file().sync_all()?;
        file.persist(directory.join("settings.json"))
            .map_err(|error| Error::Io(error.error))?;
        Ok(())
    }

    pub fn interval_ms(&self) -> i64 {
        i64::from(self.interval_minutes) * 60_000
    }

    pub fn should_start_hidden(&self, credential_available: bool) -> bool {
        self.start_in_tray
            && self.onboarding_completed
            && credential_available
            && self.selected_market.is_some()
    }
}
