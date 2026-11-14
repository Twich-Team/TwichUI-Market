//! Controlled HTTPS release metadata and bounded downloads. Tauri independently
//! verifies the pinned updater signature AND its signed version before installation.
use crate::{Error, Result};
use reqwest::blocking::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{io::Read, time::Duration};
use url::Url;
pub const ORIGIN: &str = "https://market.twich.gg";
pub const MAX_INSTALLER: u64 = 64 * 1024 * 1024;
const MAX_METADATA: u64 = 16384;
#[derive(Clone, Deserialize)]
pub struct Package {
    pub version: String,
    #[serde(rename = "url")]
    pub download_url: String,
    pub bytes: u64,
    pub sha256: String,
    pub source_commit: String,
    pub notes: String,
}
fn stable_version(version: &str) -> bool {
    let parts: Vec<_> = version.split('.').collect();
    parts.len() == 3
        && parts[0] == "2"
        && parts.iter().all(|part| {
            !part.is_empty()
                && part.len() <= 4
                && part.bytes().all(|b| b.is_ascii_digit())
                && (part.len() == 1 || !part.starts_with('0'))
        })
}
fn lowercase_hex(value: &str, size: usize) -> bool {
    value.len() == size
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
impl Package {
    pub fn validate(&self) -> Result<()> {
        if !stable_version(&self.version)
            || !(1024..=MAX_INSTALLER).contains(&self.bytes)
            || !lowercase_hex(&self.sha256, 64)
            || !lowercase_hex(&self.source_commit, 40)
            || self.notes.len() > 4000
            || self.download_url
                != format!(
                    "{ORIGIN}/api/v1/companion/releases/{}/windows-x64",
                    self.version
                )
        {
            return Err(Error::Invalid("verified Windows release metadata"));
        }
        Ok(())
    }
    pub fn read_verified(&self, reader: impl Read) -> Result<Vec<u8>> {
        self.validate()?;
        let mut bytes = Vec::with_capacity(self.bytes as usize);
        reader.take(self.bytes + 1).read_to_end(&mut bytes)?;
        if bytes.len() as u64 != self.bytes
            || format!("{:x}", Sha256::digest(&bytes)) != self.sha256
        {
            return Err(Error::Invalid("update package integrity"));
        }
        Ok(bytes)
    }
    pub fn download(&self) -> Result<Vec<u8>> {
        self.validate()?;
        let response = client()?
            .get(&self.download_url)
            .send()
            .map_err(|_| Error::Network)?;
        if response.status().as_u16() != 200
            || response
                .content_length()
                .is_some_and(|size| size != self.bytes)
        {
            return Err(Error::Invalid("update download response"));
        }
        self.read_verified(response)
    }
}
fn client() -> Result<Client> {
    Client::builder()
        .https_only(true)
        .redirect(reqwest::redirect::Policy::none())
        .no_proxy()
        .connect_timeout(Duration::from_secs(10))
        .timeout(Duration::from_secs(120))
        .build()
        .map_err(|_| Error::Network)
}
pub fn metadata(installed_version: &str) -> Result<Option<(Package, serde_json::Value)>> {
    if installed_version.len() > 64
        || !installed_version
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b".-+".contains(&b))
    {
        return Err(Error::Invalid("installed version"));
    }
    let url = Url::parse(&format!(
        "{ORIGIN}/api/v1/companion/releases/update/windows-x86_64/{installed_version}"
    ))
    .map_err(|_| Error::Invalid("update endpoint"))?;
    let response = client()?.get(url).send().map_err(|_| Error::Network)?;
    if response.status().as_u16() == 204 {
        return Ok(None);
    }
    if response.status().as_u16() != 200 {
        return Err(Error::Network);
    }
    let mut bytes = Vec::new();
    response.take(MAX_METADATA + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > MAX_METADATA {
        return Err(Error::Invalid("update metadata exceeds limit"));
    }
    let raw: serde_json::Value = serde_json::from_slice(&bytes)?;
    let package: Package = serde_json::from_value(raw.clone())?;
    package.validate()?;
    Ok(Some((package, raw)))
}
#[cfg(test)]
mod tests {
    use super::*;
    fn package(bytes: &[u8]) -> Package {
        Package {
            version: "2.0.0".into(),
            download_url: format!("{ORIGIN}/api/v1/companion/releases/2.0.0/windows-x64"),
            bytes: bytes.len() as u64,
            sha256: format!("{:x}", Sha256::digest(bytes)),
            source_commit: "a".repeat(40),
            notes: "Synthetic integrity fixture".into(),
        }
    }
    #[test]
    fn update_transport_and_identity_are_pinned_independently_of_account_server() {
        let original = package(&vec![b'M'; 1024]);
        original.validate().unwrap();
        for url in [
            original.download_url.replace("https:", "http:"),
            original
                .download_url
                .replace("market.twich.gg", "other.example"),
            format!("{}?redirect=other", original.download_url),
            format!("{}#fragment", original.download_url),
            original.download_url.replace("2.0.0", "2.0.1"),
        ] {
            let mut changed = original.clone();
            changed.download_url = url;
            assert!(changed.validate().is_err());
        }
        for version in ["1.0.0", "2.0.0-beta.1", "2.00.0", "2.0.0/../"] {
            let mut changed = original.clone();
            changed.version = version.into();
            assert!(changed.validate().is_err());
        }
    }
    #[test]
    fn bounded_update_reader_rejects_truncation_extra_bytes_and_digest_changes() {
        let bytes = vec![b'M'; 1024];
        let value = package(&bytes);
        assert_eq!(value.read_verified(bytes.as_slice()).unwrap(), bytes);
        assert!(value.read_verified(&bytes[..1023]).is_err());
        assert!(value.read_verified(vec![b'M'; 1025].as_slice()).is_err());
        assert!(value.read_verified(vec![b'X'; 1024].as_slice()).is_err());
        let mut large = value.clone();
        large.bytes = MAX_INSTALLER + 1;
        assert!(large.read_verified(bytes.as_slice()).is_err());
        let mut bad = value.clone();
        bad.sha256 = "Z".repeat(64);
        assert!(bad.validate().is_err());
    }
}
