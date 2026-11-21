//! Fail closed on ambiguous Windows staging ownership or broad write permissions.
use crate::{Error, Result};
use std::{ffi::c_void, os::windows::ffi::OsStrExt, path::{Path, Prefix}};
use windows_sys::Win32::{Foundation::{CloseHandle, LocalFree, HANDLE}, Security::{*, Authorization::{GetNamedSecurityInfoW, SE_FILE_OBJECT}}, Storage::FileSystem::GetDriveTypeW, System::Threading::{GetCurrentProcess, OpenProcessToken}};
fn reject<T>() -> Result<T> { Err(Error::Invalid("Windows bridge staging ownership or ACL is ambiguous")) }
struct Token(HANDLE);
impl Drop for Token { fn drop(&mut self) { unsafe { CloseHandle(self.0); } } }
struct Descriptor(*mut c_void);
impl Drop for Descriptor { fn drop(&mut self) { if !self.0.is_null() { unsafe { LocalFree(self.0); } } } }
// Both installed inputs and output must stay on a local fixed disk.
pub(crate) fn local(path: &Path) -> Result<()> {
    let Some(std::path::Component::Prefix(prefix)) = path.components().next() else { return reject() };
    let drive = match prefix.kind() { Prefix::Disk(c) | Prefix::VerbatimDisk(c) => c, _ => return reject() };
    let root = [drive as u16, b':' as u16, b'\\' as u16, 0];
    if unsafe { GetDriveTypeW(root.as_ptr()) } != 3 { return reject() }
    Ok(())
}
fn os_check<T>(check: &str, message: &str, result: Result<T>) -> Result<T> {
    result.map_err(|error| {
        let mut failure = crate::workshop_setup::Failure::from_error("destination", error);
        failure.check = Some(check.into());
        failure.message = message.into();
        Error::WorkshopSetup(Box::new(failure))
    })
}
fn policy_error(parent: bool, condition: &str, message: &str, details: String) -> Error {
    let role = if parent { "output_parent" } else { "output_owned" };
    let mut failure = crate::workshop_setup::Failure::new("unsafe_permissions", "destination", details);
    failure.check = Some(format!("{role}_{condition}"));
    failure.message = message.into();
    Error::WorkshopSetup(Box::new(failure))
}
/// Record categorical principals only; never disclose SIDs, account names or paths.
unsafe fn principal(sid: *mut c_void, user: *mut c_void, default: *mut c_void) -> &'static str {
    if EqualSid(sid, user) != 0 { return "current_user" }
    if EqualSid(sid, default) != 0 { return "token_default_owner" }
    for (kind, name) in [(WinLocalSystemSid, "system"), (WinBuiltinAdministratorsSid, "administrators"),
        (WinCreatorOwnerSid, "creator_owner"), (WinWorldSid, "everyone"),
        (WinAuthenticatedUserSid, "authenticated_users"), (WinBuiltinUsersSid, "builtin_users"),
        (WinInteractiveSid, "interactive_users"), (WinNetworkSid, "network_users")] {
        if IsWellKnownSid(sid, kind) != 0 { return name }
    }
    "other_principal"
}
// Private exports/staging keep their existing user-only write policy.
pub(crate) fn check(path: &Path) -> Result<()> { check_policy(path, false) }
// A game directory is shared installation data, not private staging storage.
// Do not reject its Windows owner or group grants. Windows enforces access;
// the publisher enforces known files, account markers and content integrity.
pub(crate) fn game_output(path: &Path) -> Result<()> {
    crate::delivery::no_links(path)?;
    local(path)
}
// Access and trust are different checks. An OPEN_EXISTING directory handle
// verifies effective create rights without creating/changing player files.
pub(crate) fn output_parent(path: &Path) -> Result<()> {
    crate::delivery::no_links(path)?;
    local(path)?;
    use windows_sys::Win32::Storage::FileSystem::*;
    let wide = path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
    let handle = unsafe { CreateFileW(wide.as_ptr(), FILE_ADD_SUBDIRECTORY | FILE_ADD_FILE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, std::ptr::null(), OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, std::ptr::null_mut()) };
    os_check("output_parent_create_access", "Windows refused create-file or create-folder access to Interface/AddOns.",
        if handle == windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE {
            Err(std::io::Error::last_os_error().into())
        } else { Ok(Token(handle)) })?;
    Ok(())
}
// This ACL/ownership allowlist applies only to private staging/cache/export paths.
fn check_policy(path: &Path, parent: bool) -> Result<()> {
    local(path)?;
    let role = if parent { "output_parent" } else { "output_owned" };
    let wide = path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
    let reject_policy = |condition, details| policy_error(parent, condition,
        "Companion could not verify this folder's security rules. Save redacted diagnostics for the specific check.", details);
    unsafe {
        let mut handle = std::ptr::null_mut();
        os_check(&format!("{role}_token_open"), "Windows could not inspect the current Windows security token.",
            if OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &mut handle) == 0 {
                Err(std::io::Error::last_os_error().into())
            } else { Ok(()) })?;
        let token = Token(handle);
        let token_info = |class, name| -> Result<Vec<usize>> {
            let mut size = 0;
            GetTokenInformation(token.0, class, std::ptr::null_mut(), 0, &mut size);
            if size == 0 || size > 65536 { return Err(reject_policy("token_shape", format!("token_field={name}; bytes={size}"))) }
            let mut buffer = vec![0usize; (size as usize).div_ceil(std::mem::size_of::<usize>())];
            os_check(&format!("{role}_token_read"), "Windows could not read the current Windows security token.",
                if GetTokenInformation(token.0, class, buffer.as_mut_ptr().cast(), size, &mut size) == 0 {
                    Err(std::io::Error::last_os_error().into())
                } else { Ok(()) })?;
            Ok(buffer)
        };
        let user = token_info(TokenUser, "user")?;
        let default_owner = token_info(TokenOwner, "default_owner")?;
        let user_sid = (*(user.as_ptr().cast::<TOKEN_USER>())).User.Sid;
        let default_sid = (*(default_owner.as_ptr().cast::<TOKEN_OWNER>())).Owner;
        let (mut owner, mut dacl, mut descriptor) = (std::ptr::null_mut(), std::ptr::null_mut(), std::ptr::null_mut());
        let status = GetNamedSecurityInfoW(wide.as_ptr(), SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
            &mut owner, std::ptr::null_mut(), &mut dacl, std::ptr::null_mut(), &mut descriptor);
        let _descriptor = Descriptor(descriptor);
        os_check(&format!("{role}_security_read"), "Windows could not read this folder's owner and access rules.",
            if status != 0 { Err(std::io::Error::from_raw_os_error(status as i32).into()) } else { Ok(()) })?;
        if owner.is_null() || dacl.is_null() { return Err(reject_policy("security_descriptor", format!("owner_present={}; dacl_present={}", !owner.is_null(), !dacl.is_null()))) }
        let mut size = ACL_SIZE_INFORMATION::default();
        if GetAclInformation(dacl, (&mut size as *mut ACL_SIZE_INFORMATION).cast(), std::mem::size_of::<ACL_SIZE_INFORMATION>() as u32, AclSizeInformation) == 0 {
            return os_check(&format!("{role}_acl_read"), "Windows could not read this folder's access-rule table.", Err(std::io::Error::last_os_error().into()));
        }
        if size.AceCount > 1024 { return Err(reject_policy("acl_size", format!("ace_count={}", size.AceCount))) }
        let mut trusted = Vec::new();
        for kind in [WinLocalSystemSid, WinBuiltinAdministratorsSid, WinCreatorOwnerSid] {
            let mut sid = [0usize; 16]; let mut bytes = std::mem::size_of_val(&sid) as u32;
            if CreateWellKnownSid(kind, std::ptr::null_mut(), sid.as_mut_ptr().cast(), &mut bytes) == 0 {
                return os_check(&format!("{role}_trusted_sid"), "Windows could not resolve a required security principal.", Err(std::io::Error::last_os_error().into()));
            }
            trusted.push(sid);
        }
        if EqualSid(owner, user_sid) == 0 && EqualSid(owner, default_sid) == 0
            && !(parent && trusted[..2].iter().any(|s| EqualSid(owner, s.as_ptr().cast_mut().cast()) != 0)) {
            return Err(policy_error(parent, "owner", "Companion rejected this folder's owner. This is an ownership safety check, not a Windows write-permission denial.",
                format!("owner_kind={}; parent_policy={parent}", principal(owner, user_sid, default_sid))));
        }
        for i in 0..size.AceCount {
            let mut ace = std::ptr::null_mut();
            if GetAce(dacl, i, &mut ace) == 0 || ace.is_null() { return Err(reject_policy("ace_read", format!("ace_index={i}"))) }
            let header = &*(ace.cast::<ACE_HEADER>());
            if header.AceType == 1 { continue }
            if header.AceType != 0 || header.AceSize < std::mem::size_of::<ACCESS_ALLOWED_ACE>() as u16 {
                return Err(reject_policy("ace_type", format!("ace_type={}; ace_flags=0x{:02x}; ace_bytes={}", header.AceType, header.AceFlags, header.AceSize)));
            }
            let allowed = &*(ace.cast::<ACCESS_ALLOWED_ACE>());
            let sid = (&allowed.SidStart as *const u32).cast_mut().cast::<c_void>();
            if IsValidSid(sid) == 0 { return Err(reject_policy("ace_sid", format!("ace_index={i}"))) }
            let writes = 0x40000000 | 0x10000000 | 0x000D0000 | 0x00000156;
            if allowed.Mask & writes != 0 && EqualSid(sid, user_sid) == 0 && EqualSid(sid, default_sid) == 0
                && !trusted.iter().any(|s| EqualSid(sid, s.as_ptr().cast_mut().cast()) != 0) {
                return Err(policy_error(parent, "broad_write", "Companion private storage has shared write permissions. Save redacted diagnostics for the specific private-storage check.",
                    format!("principal_kind={}; write_mask=0x{:08x}; ace_flags=0x{:02x}; inheritable={}; inherit_only={}", principal(sid, user_sid, default_sid),
                        allowed.Mask & writes, header.AceFlags, header.AceFlags & 3 != 0, header.AceFlags & 8 != 0)));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{fs, process::Command};
    fn icacls(path: &Path, args: &[&str]) {
        let output = Command::new("icacls").arg(path).args(args).output().unwrap();
        assert!(output.status.success(), "disposable ACL fixture setup failed");
    }
    fn current_sid() -> String {
        let output = Command::new("whoami").args(["/user", "/fo", "csv", "/nh"]).output().unwrap();
        assert!(output.status.success());
        String::from_utf8(output.stdout).unwrap().trim().split(',').last().unwrap().trim_matches('"').to_owned()
    }
    fn fixture() -> tempfile::TempDir {
        let dir = tempfile::tempdir().unwrap();
        let grant = format!("*{}:(OI)(CI)F", current_sid());
        icacls(dir.path(), &["/inheritance:r", "/grant:r", &grant, "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F"]);
        dir
    }
    fn failure(error: Error) -> crate::workshop_setup::Failure {
        crate::workshop_setup::Failure::from_error("destination", error)
    }
    #[test]
    fn parent_readonly_principals_are_allowed_without_changing_files() {
        let dir = fixture(); fs::write(dir.path().join("sentinel"), b"preserve").unwrap();
        icacls(dir.path(), &["/grant", "*S-1-1-0:(OI)(CI)RX"]);
        output_parent(dir.path()).unwrap();
        assert_eq!(fs::read(dir.path().join("sentinel")).unwrap(), b"preserve");
        assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 1);
    }
    #[test]
    fn shared_game_groups_do_not_block_preflight_or_change_files() {
        for grant in ["*S-1-1-0:(OI)(CI)F", "*S-1-1-0:(OI)(CI)(IO)F", "*S-1-5-11:(OI)(CI)F", "*S-1-5-4:(OI)(CI)F"] {
            let root = fixture(); icacls(root.path(), &["/grant", grant]);
            let dir = root.path().join("AddOns"); fs::create_dir(&dir).unwrap();
            output_parent(&dir).unwrap();
            assert!(fs::read_dir(&dir).unwrap().next().is_none());
            // The same permissions are still unsuitable for private storage.
            let e = failure(check(&dir).unwrap_err());
            assert_eq!(e.check.as_deref(), Some("output_owned_broad_write"));
            let redacted = serde_json::to_string(&e).unwrap();
            assert!(!redacted.contains(&current_sid())); assert!(!redacted.contains(dir.to_str().unwrap()));
        }
    }
    #[test]
    fn parent_actual_create_denial_keeps_windows_error_and_distinct_check() {
        let dir = fixture(); let deny = format!("*{}:(WD,AD)", current_sid());
        icacls(dir.path(), &["/deny", &deny]);
        let e = failure(output_parent(dir.path()).unwrap_err());
        assert_eq!(e.code, "access_denied"); assert_eq!(e.check.as_deref(), Some("output_parent_create_access"));
        assert!(e.details.contains("os_code=Some(5)"));
        assert!(!e.details.contains("effective_create_access=true"));
        assert!(fs::read_dir(dir.path()).unwrap().next().is_none());
    }
    #[test]
    fn inherited_shared_rules_allow_game_outputs_but_not_private_storage() {
        // Include the complete family of shared-folder group grants, rather
        // than adding exceptions one principal at a time on the owner's PC.
        for sid in ["S-1-5-32-545", "S-1-5-4", "S-1-5-11", "S-1-1-0"] {
            let root = fixture(); let grant = format!("*{sid}:(OI)(CI)F");
            icacls(root.path(), &["/grant", &grant]);
            let addons = root.path().join("AddOns"); fs::create_dir(&addons).unwrap();
            fs::write(addons.join("existing-addon.lua"), b"unchanged unrelated addon").unwrap();
            output_parent(&addons).unwrap();
            assert_eq!(fs::read_dir(&addons).unwrap().count(), 1, "preflight created files");
            let dir = addons.join("TwichUI_MarketData"); fs::create_dir(&dir).unwrap();
            let path = dir.join("Data.lua");
            crate::delivery::game_atomic(&path, b"synthetic generated data").unwrap();
            game_output(&dir).unwrap(); game_output(&path).unwrap();
            crate::delivery::game_atomic(&path, b"synthetic replacement").unwrap();
            assert_eq!(fs::read(&path).unwrap(), b"synthetic replacement");
            assert_eq!(fs::read(addons.join("existing-addon.lua")).unwrap(), b"unchanged unrelated addon");
            for target in [&addons, &dir, &path] {
                let e = failure(check(target).unwrap_err());
                assert_eq!(e.check.as_deref(), Some("output_owned_broad_write"));
                if target == &addons {
                    assert!(e.details.contains("write_mask=0x000d0156"));
                    assert!(e.details.contains("ace_flags=0x13"));
                    if sid == "S-1-5-4" { assert!(e.details.contains("principal_kind=interactive_users")); }
                }
            }
            assert!(crate::delivery::atomic(&path, b"private operation must fail").is_err());
            assert_eq!(fs::read(&path).unwrap(), b"synthetic replacement");
        }
    }
    #[test]
    fn game_outputs_still_require_actual_windows_write_access() {
        let root = fixture(); icacls(root.path(), &["/grant", "*S-1-1-0:(OI)(CI)F"]);
        let dir = root.path().join("TwichUI_MarketData"); fs::create_dir(&dir).unwrap();
        let deny = format!("*{}:(WD,AD)", current_sid()); icacls(&dir, &["/deny", &deny]);
        let path = dir.join("Data.lua");
        let native = fs::File::create(&path).unwrap_err();
        assert_eq!(native.raw_os_error(), Some(5));
        let Error::Io(error) = crate::delivery::game_atomic(&path, b"must not publish").unwrap_err() else {
            panic!("native file creation must fail when Windows denies it")
        };
        assert_eq!(error.kind(), std::io::ErrorKind::PermissionDenied);
        // tempfile adds path context to its I/O error; the permission-denied
        // kind survives even when raw_os_error() is no longer exposed.
        assert!(!path.exists());
    }
    #[test]
    fn game_output_policy_still_refuses_junctions_before_writing() {
        let root = fixture(); let target = root.path().join("target"); fs::create_dir(&target).unwrap();
        let junction = root.path().join("junction");
        let command = Command::new("cmd").args(["/C", "mklink", "/J"]).arg(&junction).arg(&target).output().unwrap();
        assert!(command.status.success());
        assert!(crate::delivery::game_atomic(&junction.join("Data.lua"), b"must not publish").is_err());
        assert!(fs::read_dir(&target).unwrap().next().is_none());
        fs::remove_dir(&junction).unwrap();
    }
    #[test]
    fn owned_output_remains_protected_from_other_writers() {
        let dir = fixture(); icacls(dir.path(), &["/grant", "*S-1-1-0:(OI)(CI)M"]);
        let e = failure(check(dir.path()).unwrap_err());
        assert_eq!(e.code, "unsafe_permissions"); assert_eq!(e.check.as_deref(), Some("output_owned_broad_write"));
    }
}
