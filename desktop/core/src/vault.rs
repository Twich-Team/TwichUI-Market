//! Native Windows Credential Manager. Unsupported platforms fail closed; no plaintext fallback.
use crate::{client::server_url, Error, Result};
use sha2::{Digest, Sha256};

pub fn credential_target(server: &str) -> Result<String> {
    let normalized = server_url(server)?.to_string();
    Ok(format!(
        "TwichUI-Market/{:x}",
        Sha256::digest(normalized.as_bytes())
    ))
}

#[cfg(windows)]
mod native {
    use super::*;
    use windows_sys::Win32::Security::Credentials::*;
    fn wide(value: &str) -> Vec<u16> {
        value.encode_utf16().chain(std::iter::once(0)).collect()
    }
    pub fn save(server: &str, token: &str) -> Result<()> {
        if token.is_empty() || token.len() > 256 {
            return Err(Error::Invalid("credential length"));
        }
        let mut target = wide(&credential_target(server)?);
        let mut username = wide("TwichUI Market device");
        let mut bytes = token.as_bytes().to_vec();
        // Win32 copies the input blob before returning; all pointers remain live for the call.
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
        bytes.fill(0);
        if success == 0 {
            return Err(Error::Vault);
        }
        Ok(())
    }
    pub fn load(server: &str) -> Result<String> {
        let target = wide(&credential_target(server)?);
        let mut credential: *mut CREDENTIALW = std::ptr::null_mut();
        if unsafe { CredReadW(target.as_ptr(), CRED_TYPE_GENERIC, 0, &mut credential) } == 0 {
            return Err(Error::Vault);
        }
        // CredReadW owns this allocation; copy the bounded blob before freeing it.
        let result = unsafe {
            let size = (*credential).CredentialBlobSize as usize;
            let result = if size == 0 || size > 256 {
                Err(Error::Vault)
            } else {
                String::from_utf8(
                    std::slice::from_raw_parts((*credential).CredentialBlob, size).to_vec(),
                )
                .map_err(|_| Error::Vault)
            };
            CredFree(credential.cast());
            result
        };
        result
    }
    pub fn remove(server: &str) -> Result<()> {
        let target = wide(&credential_target(server)?);
        if unsafe { CredDeleteW(target.as_ptr(), CRED_TYPE_GENERIC, 0) } == 0 {
            return Err(Error::Vault);
        }
        Ok(())
    }
}

#[cfg(windows)]
pub use native::{load, remove, save};
#[cfg(not(windows))]
pub fn save(_server: &str, _token: &str) -> Result<()> {
    Err(Error::Vault)
}
#[cfg(not(windows))]
pub fn load(_server: &str) -> Result<String> {
    Err(Error::Vault)
}
#[cfg(not(windows))]
pub fn remove(_server: &str) -> Result<()> {
    Err(Error::Vault)
}
