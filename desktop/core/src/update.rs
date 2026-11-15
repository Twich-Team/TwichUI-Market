//! Controlled HTTPS release metadata and bounded downloads. Tauri independently
//! verifies the pinned updater signature AND its signed version before installation.
use crate::{Error, Result};
use base64::{engine::general_purpose::STANDARD, Engine};
use reqwest::blocking::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use std::{io::Read, time::Duration};
use url::Url;
pub const ORIGIN: &str = "https://market.twich.gg";
pub const MAX_INSTALLER: u64 = 64 * 1024 * 1024;
const MAX_METADATA: u64 = 16384;
/// Owner-controlled Linux publisher verification, using the same maintained
/// Minisign verifier as Tauri. Native installation still verifies with its SDK.
pub fn verify_signature(bytes: &[u8], key: &str, signature: &str, version: &str) -> Result<()> {
    if key.len() > 4096 || signature.len() > 4096 || !release_version(version) {
        return Err(Error::Invalid("release signature metadata"));
    }
    let decode = |value: &str| -> Result<String> {
        String::from_utf8(
            STANDARD
                .decode(value.trim())
                .map_err(|_| Error::Invalid("release signature encoding"))?,
        )
        .map_err(|_| Error::Invalid("release signature encoding"))
    };
    let public = minisign_verify::PublicKey::decode(&decode(key)?)
        .map_err(|_| Error::Invalid("release public key"))?;
    let proof = minisign_verify::Signature::decode(&decode(signature)?)
        .map_err(|_| Error::Invalid("release signature"))?;
    public
        .verify(bytes, &proof, false)
        .map_err(|_| Error::Invalid("release signature verification"))?;
    // The global signature above authenticates this trusted comment. Never use
    // unauthenticated version text to bind a payload to a release.
    let versions: Vec<_> = proof
        .trusted_comment()
        .split('\t')
        .filter_map(|field| field.strip_prefix("version:"))
        .collect();
    if versions != [version] {
        return Err(Error::Invalid("signed release version mismatch"));
    }
    Ok(())
}
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
pub fn release_version(version: &str) -> bool {
    let (base, beta) = match version.split_once("-beta.") {
        Some((base, beta)) => (base, Some(beta)),
        None => (version, None),
    };
    let number = |part: &str| {
        !part.is_empty()
            && part.len() <= 4
            && part.bytes().all(|b| b.is_ascii_digit())
            && (part.len() == 1 || !part.starts_with('0'))
    };
    let parts: Vec<_> = base.split('.').collect();
    parts.len() == 3
        && parts[0] == "2"
        && parts.iter().all(|part| number(part))
        && beta.is_none_or(|part| number(part) && part != "0")
}
pub fn download_path(version: &str) -> Result<String> {
    if !release_version(version) {
        return Err(Error::Invalid("update release version"));
    }
    let channel = if version.contains("-beta.") {
        "private-beta"
    } else {
        "releases"
    };
    Ok(format!("/api/v1/companion/{channel}/{version}/windows-x64"))
}
fn lowercase_hex(value: &str, size: usize) -> bool {
    value.len() == size
        && value
            .bytes()
            .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b))
}
impl Package {
    pub fn validate(&self) -> Result<()> {
        if !release_version(&self.version)
            || !(1024..=MAX_INSTALLER).contains(&self.bytes)
            || !lowercase_hex(&self.sha256, 64)
            || !lowercase_hex(&self.source_commit, 40)
            || self.notes.len() > 4000
            || self.download_url != format!("{ORIGIN}{}", download_path(&self.version)?)
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
    pub(crate) fn download_authenticated(&self, http: &Client, token: &str) -> Result<Vec<u8>> {
        self.validate()?;
        let response = http
            .get(&self.download_url)
            .bearer_auth(token)
            .timeout(Duration::from_secs(120))
            .send()
            .map_err(|_| Error::Network)?;
        if response.status().as_u16() == 401 {
            return Err(Error::Authentication);
        }
        if response.status().as_u16() != 200
            || response
                .content_length()
                .is_some_and(|size| size != self.bytes)
        {
            return Err(Error::Invalid("update download response"));
        }
        self.read_verified(response)
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
    metadata_with(&client()?, installed_version, None)
}
pub(crate) fn private_metadata(
    client: &Client,
    token: &str,
    installed_version: &str,
) -> Result<Option<(Package, serde_json::Value)>> {
    metadata_with(client, installed_version, Some(token))
}
fn metadata_with(
    client: &Client,
    installed_version: &str,
    token: Option<&str>,
) -> Result<Option<(Package, serde_json::Value)>> {
    if installed_version.len() > 64
        || !installed_version
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b".-+".contains(&b))
    {
        return Err(Error::Invalid("installed version"));
    }
    let channel = if token.is_some() {
        "private-beta"
    } else {
        "releases"
    };
    let url = Url::parse(&format!(
        "{ORIGIN}/api/v1/companion/{channel}/update/windows-x86_64/{installed_version}"
    ))
    .map_err(|_| Error::Invalid("update endpoint"))?;
    let request = client.get(url).timeout(Duration::from_secs(15));
    let request = if let Some(token) = token {
        request.bearer_auth(token)
    } else {
        request
    };
    let response = request.send().map_err(|_| Error::Network)?;
    if response.status().as_u16() == 401 {
        return Err(Error::Authentication);
    }
    if response.status().as_u16() == 429 {
        return Err(Error::RateLimited(3600));
    }
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
/// Native update-check policy. Market synchronization preferences do not own it.
#[derive(Default)]
pub struct CheckSchedule {
    next_ms: Option<i64>,
    last_clock_ms: Option<i64>,
}
impl CheckSchedule {
    pub fn claim(&mut self, now_ms: i64, eligible: bool) -> bool {
        if self.last_clock_ms.is_some_and(|previous| now_ms < previous) {
            self.next_ms = Some(now_ms); // Reconcile one backward-clock event.
        }
        self.last_clock_ms = Some(now_ms);
        if eligible && self.next_ms.is_none_or(|next| now_ms >= next) {
            self.next_ms = Some(now_ms.saturating_add(86_400_000));
            true
        } else {
            false
        }
    }
    pub fn completed(&mut self, now_ms: i64, success: bool) {
        self.last_clock_ms = Some(now_ms);
        self.next_ms = Some(now_ms.saturating_add(if success { 86_400_000 } else { 3_600_000 }));
    }
    pub fn connection_ready(&mut self, now_ms: i64) {
        self.next_ms = Some(now_ms);
    }
    pub fn wait_ms(&self, now_ms: i64, eligible: bool) -> u64 {
        if !eligible {
            return 900_000;
        }
        self.next_ms
            .unwrap_or(now_ms)
            .saturating_sub(now_ms)
            .clamp(1000, 900_000) as u64
    }
}
pub fn public_key_fingerprint(key: &str) -> String {
    format!("{:x}", Sha256::digest(key.trim().as_bytes()))
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
        for version in [
            "1.0.0",
            "2.0.0-beta.0",
            "2.0.0-beta.01",
            "2.00.0",
            "2.0.0/../",
        ] {
            let mut changed = original.clone();
            changed.version = version.into();
            assert!(changed.validate().is_err());
        }
    }
    #[test]
    fn private_beta_signature_identity_uses_a_distinct_exact_versioned_route() {
        for version in ["2.0.0-beta.1", "2.4.8-beta.10"] {
            assert!(release_version(version));
            let mut value = package(&vec![b'M'; 1024]);
            value.version = version.into();
            value.download_url = format!("{ORIGIN}{}", download_path(version).unwrap());
            value.validate().unwrap();
            value.download_url = value.download_url.replace("private-beta", "releases");
            assert!(value.validate().is_err());
        }
        for version in [
            "2.0.0-beta.0",
            "2.0.0-beta.01",
            "2.0.0-beta.1+other",
            "2.0.0-beta.1/other",
            "2.0.0-alpha.1",
        ] {
            assert!(!release_version(version));
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

    #[test]
    fn automatic_update_checks_are_daily_single_flight_and_ignore_paused_market_sync() {
        let mut policy = CheckSchedule::default();
        assert!(!policy.claim(1000, false));
        assert!(policy.claim(1000, true));
        assert!(!policy.claim(1001, true));
        policy.completed(2000, true);
        assert!(!policy.claim(86_401_999, true));
        assert!(policy.claim(86_402_000, true));
        assert!(!policy.claim(86_402_000, true));
    }
    #[test]
    fn failed_checks_retry_hourly_and_reconnection_does_not_require_webview_activity() {
        let mut policy = CheckSchedule::default();
        assert!(policy.claim(1000, true));
        policy.completed(2000, false);
        assert!(!policy.claim(3_601_999, true));
        assert!(policy.claim(3_602_000, true));
        policy.completed(3_603_000, true);
        policy.connection_ready(3_604_000);
        assert!(policy.claim(3_604_000, true));
        assert_eq!(policy.wait_ms(3_604_000, false), 900_000);
    }
    #[test]
    fn sleep_and_clock_reconciliation_never_create_catchup_requests() {
        let mut policy = CheckSchedule::default();
        assert!(policy.claim(100_000_000, true));
        policy.completed(100_000_000, true);
        assert!(policy.claim(900_000_000, true));
        assert!(!policy.claim(900_000_000, true));
        policy.completed(900_000_000, true);
        assert!(policy.claim(100_000_000, true));
        assert!(!policy.claim(100_000_000, true));
    }
    #[test]
    fn publisher_verifier_authenticates_the_real_signature_and_version_binding() {
        let bytes = include_bytes!("../../src-tauri/tests/fixtures/synthetic-update.txt");
        let key = include_str!("../../src-tauri/tests/fixtures/synthetic-public.key");
        let signature = include_str!("../../src-tauri/tests/fixtures/synthetic-update.txt.sig");
        verify_signature(bytes, key, signature, "2.0.0").unwrap();
        assert!(verify_signature(bytes, key, signature, "2.0.1").is_err());
        let mut changed = bytes.to_vec();
        changed[0] ^= 1;
        assert!(verify_signature(&changed, key, signature, "2.0.0").is_err());
        let text = String::from_utf8(STANDARD.decode(signature.trim()).unwrap()).unwrap();
        let forged = STANDARD.encode(text.replace("version:2.0.0", "version:2.0.1"));
        assert!(verify_signature(bytes, key, &forged, "2.0.1").is_err());
    }
}
