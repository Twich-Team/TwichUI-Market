//! Native Windows Credential Manager. Unsupported platforms fail closed; no plaintext fallback.
use crate::{
    authorization::{CredentialStore, Session},
    client::server_url,
    Error, Result,
};
use sha2::{Digest, Sha256};
use zeroize::Zeroize;

pub fn credential_target(server: &str) -> Result<String> {
    let normalized = server_url(server)?.to_string();
    let namespace = if cfg!(feature = "private-dev") { "TwichUI-Market-DEV" } else { "TwichUI-Market" };
    Ok(format!(
        "{namespace}/{:x}",
        Sha256::digest(normalized.as_bytes())
    ))
}
pub fn session_target(server: &str) -> Result<String> {
    Ok(format!("{}:companion-v2", credential_target(server)?))
}

/// The v2 entry is separate: approving a new connection never destroys the legacy key.
pub struct NativeCredentialStore;
impl CredentialStore for NativeCredentialStore {
    fn load(&self, server: &str) -> Result<Session> {
        let mut bytes = native::load_blob(&session_target(server)?, 4096)?;
        let result = Session::decode(server, &bytes);
        bytes.zeroize();
        result
    }
    fn save(&self, server: &str, session: &Session) -> Result<()> {
        let mut bytes = serde_json::to_vec(session).map_err(|_| Error::Vault)?;
        let result = native::save_blob(&session_target(server)?, &bytes, 4096);
        bytes.zeroize();
        result
    }
    fn remove(&self, server: &str) -> Result<()> {
        native::remove_blob(&session_target(server)?)
    }
}

pub fn save(server: &str, token: &str) -> Result<()> {
    native::save_blob(&credential_target(server)?, token.as_bytes(), 256)
}
pub fn load(server: &str) -> Result<String> {
    let mut bytes = native::load_blob(&credential_target(server)?, 256)?;
    let result = String::from_utf8(bytes.clone()).map_err(|_| Error::Vault);
    bytes.zeroize();
    result
}
pub fn remove(server: &str) -> Result<()> {
    native::remove_blob(&credential_target(server)?)
}

#[cfg(windows)]
mod native {
    use super::*;
    use windows_sys::Win32::Foundation::{GetLastError, ERROR_NOT_FOUND};
    use windows_sys::Win32::Security::Credentials::*;
    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }
    pub fn save_blob(target_name: &str, blob: &[u8], max: usize) -> Result<()> {
        if blob.is_empty() || blob.len() > max {
            return Err(Error::Invalid("credential length"));
        }
        let mut target = wide(target_name);
        let mut username = wide("TwichUI Market device");
        let mut bytes = blob.to_vec();
        // CredWriteW atomically replaces this generic entry and copies the input before returning.
        let credential = CREDENTIALW {
            Flags: 0,
            Type: CRED_TYPE_GENERIC,
            TargetName: target.as_mut_ptr(),
            Comment: std::ptr::null_mut(),
            LastWritten: unsafe { std::mem::zeroed() },
            CredentialBlobSize: bytes.len() as u32,
            CredentialBlob: bytes.as_mut_ptr(),
            Persist: CRED_PERSIST_LOCAL_MACHINE,
            AttributeCount: 0,
            Attributes: std::ptr::null_mut(),
            TargetAlias: std::ptr::null_mut(),
            UserName: username.as_mut_ptr(),
        };
        let success = unsafe { CredWriteW(&credential, 0) };
        bytes.zeroize();
        if success == 0 {
            return Err(Error::Vault);
        }
        Ok(())
    }
    pub fn load_blob(target_name: &str, max: usize) -> Result<Vec<u8>> {
        let target = wide(target_name);
        let mut credential: *mut CREDENTIALW = std::ptr::null_mut();
        if unsafe { CredReadW(target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut credential) } == 0 {
            return Err(if unsafe { GetLastError() } == ERROR_NOT_FOUND {
                Error::CredentialMissing
            } else {
                Error::Vault
            });
        }
        // CredReadW owns this allocation. Wipe both the native blob and any bounded copy on failure.
        unsafe {
            let size = (*credential).CredentialBlobSize as usize;
            let result = if size == 0 || size > max {
                Err(Error::Vault)
            } else {
                Ok(std::slice::from_raw_parts((*credential).CredentialBlob, size).to_vec())
            };
            if size <= 4096 && !(*credential).CredentialBlob.is_null() {
                std::slice::from_raw_parts_mut((*credential).CredentialBlob, size).zeroize();
            }
            CredFree(credential.cast());
            result
        }
    }
    pub fn remove_blob(target_name: &str) -> Result<()> {
        let target = wide(target_name);
        if unsafe { CredDeleteW(target.as_ptr(), CRED_TYPE_GENERIC, 0) } == 0 {
            if unsafe { GetLastError() } != ERROR_NOT_FOUND {
                return Err(Error::Vault);
            }
        }
        Ok(())
    }
}
#[cfg(not(windows))]
mod native {
    use super::*;
    pub fn save_blob(_: &str, _: &[u8], _: usize) -> Result<()> {
        Err(Error::Vault)
    }
    pub fn load_blob(_: &str, _: usize) -> Result<Vec<u8>> {
        Err(Error::Vault)
    }
    pub fn remove_blob(_: &str) -> Result<()> {
        Err(Error::Vault)
    }
}

#[cfg(all(test, feature = "private-dev"))]
mod dev_tests {
    #[cfg(windows)]
    #[test]
    fn private_dev_vault_operations_preserve_production_credentials() {
        use sha2::{Digest, Sha256};
        let server = format!("https://dev-isolation-{}.invalid/", std::process::id());
        let production = format!("TwichUI-Market/{:x}", Sha256::digest(server.as_bytes()));
        let development = super::credential_target(&server).unwrap();
        struct Cleanup(Vec<String>);
        impl Drop for Cleanup { fn drop(&mut self) { for name in &self.0 { let _ = super::native::remove_blob(name); } } }
        let _cleanup = Cleanup(vec![production.clone(), development]);
        super::native::save_blob(&production, b"production-fixture", 256).unwrap();
        super::save(&server, "dev-fixture").unwrap();
        assert_eq!(super::load(&server).unwrap(), "dev-fixture");
        super::remove(&server).unwrap();
        assert_eq!(super::native::load_blob(&production, 256).unwrap(), b"production-fixture");
    }
    #[test]
    fn private_dev_never_uses_production_credential_names() {
        let legacy = super::credential_target("https://market.twich.gg").unwrap();
        let session = super::session_target("https://market.twich.gg").unwrap();
        assert!(legacy.starts_with("TwichUI-Market-DEV/"));
        assert!(session.starts_with("TwichUI-Market-DEV/"));
        assert!(session.ends_with(":companion-v2"));
    }
}
