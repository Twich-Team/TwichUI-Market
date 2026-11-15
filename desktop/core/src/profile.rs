//! Nonsecret, origin-scoped connection metadata. Never use a failed v2 vault read
//! as permission to fall back to a retained legacy credential.
use crate::{authorization::Session, client::server_url, connection::Bootstrap, Error, Result};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    io::{Read, Write},
    path::{Path, PathBuf},
};
const MAX_BYTES: u64 = 262_144;
#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    Disconnected,
    Legacy,
    Companion,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Profile {
    pub schema_version: u32,
    pub server: String,
    pub mode: Mode,
    pub device_id: Option<u32>,
    pub bootstrap: Option<Bootstrap>,
    pub last_market: Option<RememberedMarket>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RememberedMarket {
    pub id: u32,
    pub label: String,
}
impl Profile {
    pub fn disconnected(server: &str) -> Result<Self> {
        Ok(Self {
            schema_version: 1,
            server: server_url(server)?.to_string(),
            mode: Mode::Disconnected,
            device_id: None,
            bootstrap: None,
            last_market: None,
        })
    }
    pub fn authorized(server: &str, session: &Session) -> Result<Self> {
        Ok(Self {
            mode: Mode::Companion,
            device_id: Some(session.device_id()),
            ..Self::disconnected(server)?
        })
    }
    pub fn validate(&self, server: &str) -> Result<()> {
        if self.schema_version != 1
            || self.server != server_url(server)?.as_str()
            || (self.mode == Mode::Companion) != (self.device_id.is_some())
            || self.device_id == Some(0)
        {
            return Err(Error::Invalid("saved connection identity"));
        }
        if self.mode == Mode::Disconnected && self.bootstrap.is_some() {
            return Err(Error::Invalid("disconnected account profile"));
        }
        if self.last_market.as_ref().is_some_and(|market| {
            market.id == 0
                || market.id > i32::MAX as u32
                || market.label.is_empty()
                || market.label.len() > 320
        }) {
            return Err(Error::Invalid("saved market identity"));
        }
        if let Some(bootstrap) = &self.bootstrap {
            bootstrap.validate()?;
            match self.mode {
                Mode::Companion
                    if bootstrap.device.as_ref().map(|device| device.id) == self.device_id => {}
                Mode::Legacy if bootstrap.device.is_none() => {}
                _ => return Err(Error::Invalid("saved device identity")),
            }
        }
        Ok(())
    }
    pub fn matches_session(&self, session: &Session) -> bool {
        self.mode == Mode::Companion && self.device_id == Some(session.device_id())
    }
    pub fn path(directory: &Path, server: &str) -> Result<PathBuf> {
        Ok(directory.join(format!(
            "connection-v2-{:x}.json",
            Sha256::digest(server_url(server)?.as_str().as_bytes())
        )))
    }
    pub fn load(directory: &Path, server: &str) -> Result<Option<Self>> {
        let path = Self::path(directory, server)?;
        let mut file = match std::fs::File::open(path) {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(error.into()),
        };
        let mut bytes = Vec::new();
        (&mut file).take(MAX_BYTES + 1).read_to_end(&mut bytes)?;
        if bytes.len() as u64 > MAX_BYTES {
            return Err(Error::Invalid("connection profile size"));
        }
        let profile: Self = serde_json::from_slice(&bytes)?;
        profile.validate(server)?;
        Ok(Some(profile))
    }
    pub fn save(&self, directory: &Path) -> Result<()> {
        self.validate(&self.server)?;
        let bytes = serde_json::to_vec_pretty(self)?;
        if bytes.len() as u64 > MAX_BYTES {
            return Err(Error::Invalid("connection profile size"));
        }
        std::fs::create_dir_all(directory)?;
        let mut file = tempfile::NamedTempFile::new_in(directory)?;
        file.write_all(&bytes)?;
        file.flush()?;
        file.as_file().sync_all()?;
        file.persist(Self::path(directory, &self.server)?)
            .map_err(|error| Error::Io(error.error))?;
        Ok(())
    }
    pub fn resolved_market(&self, local_override: Option<u32>) -> Option<u32> {
        self.bootstrap
            .as_ref()?
            .resolve_market(local_override)
            .map(|market| market.id)
    }
}
