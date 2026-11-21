//! Bounded, read-only Windows discovery. No disk scans or game execution.
use crate::{delivery::{no_links,read}, Error, Result};
use serde_json::Value;
use std::{collections::HashSet, path::{Path,PathBuf}};

fn need(ok:bool,why:&'static str)->Result<()> {if ok {Ok(())} else {Err(Error::Invalid(why))}}

// Installed code is read, never modified or executed. Do not apply the private
// staging/output owner policy to game or addon files installed by another user.
fn installed(path:&Path)->Result<()> {
    no_links(path)?;
    #[cfg(windows)]
    crate::bridge::windows_owner::local(path)?;
    Ok(())
}

pub fn validate_game(path:&Path)->Result<()> {
    use crate::workshop_setup::at;
    at("game_folder", (|| {
        installed(path)?;
        need(path.is_dir(), "game root is missing")?;
        for dir in ["Interface", "Interface/AddOns"] {
            let child=path.join(dir); installed(&child)?;
            need(child.is_dir(), "game Interface/AddOns is missing")?;
        }
        let exe=path.join("Wow.exe"); installed(&exe)?;
        need(exe.is_file(), "game root does not contain Wow.exe")
    })())?;
    at("executable_version", (|| {
        let identity=executable_identity(&path.join("Wow.exe"))?;
        validate_executable(&identity)
    })())
}

pub fn validate(path:&Path)->Result<()> {
    validate_game(path)?;
    validate_addons(path)
}

// Metadata checks preserve NotFound versus PermissionDenied; Path::is_file()
// would collapse both into a misleading missing/update message.
fn addon_path(path: &Path, directory: bool) -> Result<()> {
    installed(path)?;
    let metadata = std::fs::metadata(path)?;
    need(if directory { metadata.is_dir() } else { metadata.is_file() }, "unexpected addon file type")
}
fn addon_text(path: &Path, max: usize) -> Result<String> {
    addon_path(path, false)?;
    let bytes = read(path, max)?;
    String::from_utf8(bytes).map(|s| s.trim_start_matches('\u{feff}').to_owned())
        .map_err(|_| Error::Invalid("addon text is not UTF-8"))
}
/// Read-only addon contract probe, also used against real seven-addon packages.
/// Does not inspect or change player data, authorize accounts, or publish files.
pub fn validate_addons(path: &Path) -> Result<()> {
    use crate::workshop_setup::checked;
    let core = path.join("Interface/AddOns/!!!TwichUI");
    checked("core_folder", "The core addon folder !!!TwichUI is missing or unreadable in Interface/AddOns.", addon_path(&core, true))?;
    checked("core_toc", "The core addon TOC (!!!TwichUI.toc) is missing or unreadable.", addon_text(&core.join("!!!TwichUI.toc"), 65536))?;
    let folder = path.join("Interface/AddOns/TwichUI_Workshop");
    checked("workshop_folder", "The TwichUI_Workshop folder is missing or unreadable in Interface/AddOns.", addon_path(&folder, true))?;
    let toc = checked("workshop_toc", "TwichUI_Workshop.toc is missing or unreadable.", addon_text(&folder.join("TwichUI_Workshop.toc"), 32768))?;
    for (name, check, message) in [
        ("Summary.lua", "summary_lua", "Workshop Summary.lua is missing or unreadable. This addon package needs the summary consumer."),
        ("Bridge.lua", "bridge_lua", "Workshop Bridge.lua is missing or unreadable."),
    ] {
        checked(check, message, (|| {
            let file = folder.join(name); addon_path(&file, false)?;
            use std::io::Read;
            let mut byte = [0u8; 1]; std::fs::File::open(file)?.read(&mut byte)?;
            Ok(())
        })())?;
    }
    let cap_path = folder.join("MarketDelivery.json");
    checked("capability_file", "Workshop MarketDelivery.json is missing or unreadable.", addon_path(&cap_path, false))?;
    let cap: Value = checked("capability_json", "Workshop MarketDelivery.json could not be read as valid capability JSON.", (|| {
        let bytes = read(&cap_path, 4096)?;
        crate::bridge::parse(bytes.strip_prefix(&[0xef, 0xbb, 0xbf]).unwrap_or(&bytes), 4096)
    })())?;
    // Field names and expected values are static; never echo file contents.
    for (field, expected, message, detail) in [
        ("format", Value::from("twichui-market-consumer"), "Workshop capability format is unsupported.", "format mismatch"),
        ("game", Value::from("wow-forever"), "Workshop capabilities must target wow-forever.", "game mismatch"),
        ("interface", Value::from(16001), "Workshop capabilities must target Interface 16001.", "interface mismatch"),
        ("summary_delivery_version", Value::from(1), "Workshop does not declare summary delivery version 1.", "summary_delivery_version mismatch"),
        ("summary_partition_bytes", Value::from(131072), "Workshop summary partition limit must be 131072 bytes.", "summary_partition_bytes mismatch"),
        ("summary_total_bytes", Value::from(8388608), "Workshop summary total limit must be 8388608 bytes.", "summary_total_bytes mismatch"),
    ] {
        checked("summary_contract", message, need(cap[field] == expected, detail))?;
    }
    checked("summary_toc_entry", "The Workshop TOC does not load Summary.lua. This addon package needs the summary consumer.", need(toc.lines().any(|line| line.trim() == "Summary.lua"), "Summary.lua TOC entry missing"))
}

/// Previous authorized installation wins; otherwise inspect at most 256
/// launcher/registry and common candidates, never recursively enumerate disks.
pub fn candidates(previous:Option<&Path>, supplied:impl IntoIterator<Item=PathBuf>)->Vec<PathBuf> {
    if let Some(p)=previous {if validate_game(p).is_ok(){return vec![p.to_path_buf()]}}
    let mut seen=HashSet::new();let mut out=Vec::new();
    for path in supplied.into_iter().take(256) {
        // Windows spelling is case-insensitive, but never canonicalize away a
        // symlink/junction before the security checks have inspected it.
        if seen.insert(path.to_string_lossy().to_lowercase()) && validate_game(&path).is_ok() {out.push(path);}
    }
    out
}

pub fn discover(previous:Option<&Path>)->Vec<PathBuf> {
    let mut paths=registry_candidates();
    for variable in ["ProgramFiles","ProgramFiles(x86)","LOCALAPPDATA","USERPROFILE"] {
        if let Some(root)=std::env::var_os(variable) {
            for suffix in ["World of Warcraft Forever","World of Warcraft/Forever","World of Warcraft","WoW Forever","Games/World of Warcraft Forever","Games/World of Warcraft/Forever","Games/World of Warcraft","Games/WoW Forever"] {paths.push(PathBuf::from(&root).join(suffix));}
        }
    }
    // Bounded conventional roots; no drive enumeration or traversal.
    for root in [r"C:\Games",r"D:\Games",r"C:\",r"D:\"] {for suffix in ["World of Warcraft Forever","World of Warcraft","WoW Forever"] {paths.push(PathBuf::from(root).join(suffix));}}
    candidates(previous,paths)
}

#[cfg(not(windows))]
fn registry_candidates()->Vec<PathBuf> {Vec::new()}

#[cfg(windows)]
fn registry_candidates()->Vec<PathBuf> {
    use windows_sys::Win32::System::Registry::*;
    fn wide(s:&str)->Vec<u16>{s.encode_utf16().chain(Some(0)).collect()}
    unsafe fn value(root:HKEY,key:&str,name:&str,view:u32)->Option<String> {
        let mut bytes=vec![0u16;2048];let mut length=(bytes.len()*2) as u32;
        if RegGetValueW(root,wide(key).as_ptr(),wide(name).as_ptr(),RRF_RT_REG_SZ|view,
            std::ptr::null_mut(),bytes.as_mut_ptr().cast(),&mut length)!=0 || length>4096 {return None}
        let end=bytes.iter().position(|n|*n==0)?;Some(String::from_utf16_lossy(&bytes[..end]))
    }
    let mut out=Vec::new();
    unsafe {for root in [HKEY_CURRENT_USER,HKEY_LOCAL_MACHINE] {for view in [RRF_SUBKEY_WOW6432KEY,RRF_SUBKEY_WOW6464KEY] {
        for key in [r"Software\Blizzard Entertainment\World of Warcraft",r"Software\Microsoft\Windows\CurrentVersion\App Paths\Wow.exe"] {
            for field in ["InstallPath","Path"] {if let Some(p)=value(root,key,field,view) {out.push(PathBuf::from(p));}}
        }
        let key=r"Software\Microsoft\Windows\CurrentVersion\Uninstall";
        let mut handle=std::ptr::null_mut();
        let access=KEY_READ|if view==RRF_SUBKEY_WOW6432KEY {KEY_WOW64_32KEY}else{KEY_WOW64_64KEY};
        if RegOpenKeyExW(root,wide(key).as_ptr(),0,access,&mut handle)==0 {
            for index in 0..256 {
                let mut name=[0u16;256];let mut length=255;
                if RegEnumKeyExW(handle,index,name.as_mut_ptr(),&mut length,std::ptr::null(),std::ptr::null_mut(),std::ptr::null_mut(),std::ptr::null_mut())!=0 {break}
                let sub=format!("{key}\\{}",String::from_utf16_lossy(&name[..length as usize]));
                if value(root,&sub,"DisplayName",view).is_some_and(|n|n.to_lowercase().contains("forever")) {
                    if let Some(p)=value(root,&sub,"InstallLocation",view) {out.push(PathBuf::from(p));}
                }
            }
            RegCloseKey(handle);
        }
    }}}
    out
}

#[derive(Debug)]
struct ExecutableIdentity {
    file_version:[u16;4],
    product_name:String,
    product_version:String,
    original_filename:String,
}
fn product_version(value:&str)->Option<Vec<u32>> {
    let value=value.trim().strip_prefix("Version ").unwrap_or(value.trim());
    if value.len()>64 {return None}
    let numbers=value.split('.').map(|part| {
        if part.is_empty()||!part.bytes().all(|b|b.is_ascii_digit()){return None}
        part.parse::<u32>().ok()
    }).collect::<Option<Vec<_>>>()?;
    (numbers.len()==3||numbers.len()==4).then_some(numbers)
}
fn validate_executable(identity:&ExecutableIdentity)->Result<()> {
    let product=product_version(&identity.product_version);
    // Owner's Windows Properties screenshot: file 160.1.7095.9, product
    // "Version 1.60.1.70959", World of Warcraft, Wow.exe. File-version fields
    // encode that release differently. Identify the supported product family,
    // not an exact build or the synthetic PE's old 1.60.1 file prefix.
    // Patch/build updates are accepted; unrelated client families fail closed.
    if identity.product_name.trim()=="World of Warcraft"
        && identity.original_filename.trim().eq_ignore_ascii_case("Wow.exe")
        && product.as_ref().is_some_and(|v|v[..2]==[1,60]) {return Ok(())}
    Err(Error::WorkshopSetup(Box::new(crate::workshop_setup::Failure::new(
        "unsupported_client", "executable_version",
        format!("observed_file_version={}.{}.{}.{}; numeric_product_version={product:?}; product_name_matches={}; original_filename_matches={}; accepted_product_family=1.60",
            identity.file_version[0],identity.file_version[1],identity.file_version[2],identity.file_version[3],
            identity.product_name.trim()=="World of Warcraft",identity.original_filename.trim().eq_ignore_ascii_case("Wow.exe")),
    ))))
}

#[cfg(not(windows))]
fn executable_identity(path:&Path)->Result<ExecutableIdentity> {
    #[cfg(test)]
    if read(path,128).ok().as_deref()==Some(b"TWICHUI SYNTHETIC FOREVER 1.60.1".as_slice()) {
        return Ok(ExecutableIdentity{file_version:[160,1,7095,9],product_name:"World of Warcraft".into(),product_version:"Version 1.60.1.70959".into(),original_filename:"Wow.exe".into()})
    }
    let _=path;
    Err(Error::Invalid("Forever installation verification requires Windows"))
}

#[cfg(windows)]
fn executable_identity(path:&Path)->Result<ExecutableIdentity> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::*;
    let name=path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
    unsafe {
        let size=GetFileVersionInfoSizeW(name.as_ptr(),std::ptr::null_mut());
        if size==0 {return Err(std::io::Error::last_os_error().into())}
        need(size<=1024*1024,"The Forever executable version could not be verified.")?;
        let mut buffer=vec![0u64;(size as usize+7)/8];
        if GetFileVersionInfoW(name.as_ptr(),0,size,buffer.as_mut_ptr().cast())==0 {return Err(std::io::Error::last_os_error().into())}
        let query=|key:&str|->Result<(*mut std::ffi::c_void,u32)> {
            let wide=key.encode_utf16().chain(Some(0)).collect::<Vec<_>>();
            let mut result=std::ptr::null_mut();let mut length=0;
            need(VerQueryValueW(buffer.as_ptr().cast(),wide.as_ptr(),&mut result,&mut length)!=0&&!result.is_null(),"executable version metadata field missing")?;
            Ok((result,length))
        };
        let inside=|pointer:*mut std::ffi::c_void,bytes:usize|->Result<()> {
            let start=buffer.as_ptr() as usize;let address=pointer as usize;
            need(address>=start&&address.checked_add(bytes).is_some_and(|end|end<=start+size as usize),"executable version metadata bounds")
        };
        let (root,length)=query("\\")?;inside(root,std::mem::size_of::<VS_FIXEDFILEINFO>())?;
        need(length as usize>=std::mem::size_of::<VS_FIXEDFILEINFO>(),"executable fixed version metadata")?;
        let info=std::ptr::read_unaligned(root.cast::<VS_FIXEDFILEINFO>());
        need(info.dwSignature==0xfeef04bd,"executable fixed version signature")?;
        let file_version=[(info.dwFileVersionMS>>16) as u16,info.dwFileVersionMS as u16,(info.dwFileVersionLS>>16) as u16,info.dwFileVersionLS as u16];
        let (translations,length)=query(r"\VarFileInfo\Translation")?;
        need(length>=4&&length<=128&&length%4==0,"executable language table bound")?;inside(translations,length as usize)?;
        let translations=std::slice::from_raw_parts(translations.cast::<u8>(),length as usize);
        let mut observed=None;
        for pair in translations.chunks_exact(4) {
            let language=u16::from_le_bytes([pair[0],pair[1]]);let codepage=u16::from_le_bytes([pair[2],pair[3]]);
            let string=|field:&str|->Result<String> {
                let (pointer,length)=query(&format!(r"\StringFileInfo\{language:04x}{codepage:04x}\{field}"))?;
                need(length>0&&length<=256&&(pointer as usize)%2==0,"executable string metadata bound")?;inside(pointer,length as usize*2)?;
                let units=std::slice::from_raw_parts(pointer.cast::<u16>(),length as usize);
                need(units.last()==Some(&0),"executable string metadata terminator")?;
                String::from_utf16(&units[..units.len()-1]).map_err(|_|Error::Invalid("executable string metadata encoding"))
            };
            if let (Ok(product_name),Ok(product_version),Ok(original_filename))=(string("ProductName"),string("ProductVersion"),string("OriginalFilename")) {
                let identity=ExecutableIdentity{file_version,product_name,product_version,original_filename};
                if validate_executable(&identity).is_ok(){return Ok(identity)}
                if observed.is_none(){observed=Some(identity);}
            }
        }
        Ok(observed.unwrap_or(ExecutableIdentity{file_version,product_name:String::new(),product_version:String::new(),original_filename:String::new()}))
    }
}

#[cfg(test)]
mod version_tests {
    use super::*;
    fn owner()->ExecutableIdentity {ExecutableIdentity{file_version:[160,1,7095,9],product_name:"World of Warcraft".into(),product_version:"Version 1.60.1.70959".into(),original_filename:"Wow.exe".into()}}
    #[test]
    fn owner_reported_metadata_and_future_patch_builds_use_product_family() {
        assert!(validate_executable(&owner()).is_ok());
        let mut next=owner();next.file_version=[160,2,8123,4];next.product_version="Version 1.60.2.81234".into();
        assert!(validate_executable(&next).is_ok());
        // Native file-version packing is not the compatibility identifier.
        next.file_version=[1,60,3,1234];next.product_version="1.60.3.123456".into();assert!(validate_executable(&next).is_ok());
    }
    #[test]
    fn unsupported_or_incomplete_product_identity_still_fails_closed() {
        for version in ["Version 1.12.1.5875","Version 1.61.1.1234","Version 2.0.0.0","160.1.7095.9","Version 1.60.secret-token","1.60","1.60..1"] {
            let mut wrong=owner();wrong.product_version=version.into();let Error::WorkshopSetup(error)=validate_executable(&wrong).unwrap_err() else {panic!("structured executable diagnostic")};
            assert!(!serde_json::to_string(&error).unwrap().contains("secret-token"));
        }
        let mut wrong=owner();wrong.product_name="Other game".into();assert!(validate_executable(&wrong).is_err());
        wrong=owner();wrong.original_filename="Launcher.exe".into();assert!(validate_executable(&wrong).is_err());
    }
}

/// Real native shell folder picker on its own STA; cancellation never changes
/// the remembered destination. No manual path is accepted by ordinary IPC.
#[cfg(windows)]
pub fn choose_folder()->Result<Option<PathBuf>> {
    use windows_sys::Win32::{System::Com::*,UI::Shell::*};
    std::thread::spawn(||unsafe {
        if CoInitializeEx(std::ptr::null(),COINIT_APARTMENTTHREADED as u32)<0 {return Err(Error::Invalid("Windows folder picker unavailable"))}
        struct Com;impl Drop for Com {fn drop(&mut self){unsafe {CoUninitialize();}}}
        let _com=Com;
        let title="Choose your World of Warcraft Forever folder".encode_utf16().chain(Some(0)).collect::<Vec<_>>();
        let mut display=[0u16;260];
        let info=BROWSEINFOW{hwndOwner:std::ptr::null_mut(),pidlRoot:std::ptr::null_mut(),pszDisplayName:display.as_mut_ptr(),
            lpszTitle:title.as_ptr(),ulFlags:BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE|BIF_EDITBOX,lpfn:None,lParam:0,iImage:0};
        let selected=SHBrowseForFolderW(&info);
        if selected.is_null(){return Ok(None)}
        let mut path=[0u16;260];let success=SHGetPathFromIDListW(selected,path.as_mut_ptr());
        CoTaskMemFree(selected.cast());
        need(success!=0,"Windows could not read the selected folder")?;
        let end=path.iter().position(|n|*n==0).ok_or(Error::Invalid("Windows folder path"))?;
        Ok(Some(PathBuf::from(String::from_utf16_lossy(&path[..end]))))
    }).join().map_err(|_|Error::Invalid("Windows folder picker interrupted"))?
}
#[cfg(not(windows))]
pub fn choose_folder()->Result<Option<PathBuf>> {Err(Error::Invalid("Use the installed Windows companion to choose a folder"))}

#[cfg(test)]
mod addon_tests {
    use super::*;
    use std::fs;
    const CAP: &str = r#"{"format":"twichui-market-consumer","game":"wow-forever","interface":16001,"summary_delivery_version":1,"summary_partition_bytes":131072,"summary_total_bytes":8388608}"#;
    fn fixture() -> tempfile::TempDir {
        let root = tempfile::tempdir().unwrap();
        let addons = root.path().join("Interface/AddOns");
        let core = addons.join("!!!TwichUI"); let workshop = addons.join("TwichUI_Workshop");
        fs::create_dir_all(&core).unwrap(); fs::create_dir_all(&workshop).unwrap();
        fs::write(core.join("!!!TwichUI.toc"), "## Interface: 16001\n").unwrap();
        fs::write(workshop.join("TwichUI_Workshop.toc"), "## Interface: 16001\nSummary.lua\nBridge.lua\n").unwrap();
        for name in ["Summary.lua", "Bridge.lua"] { fs::write(workshop.join(name), "-- fixture\n").unwrap(); }
        fs::write(workshop.join("MarketDelivery.json"), CAP).unwrap(); root
    }
    fn failure(root: &Path) -> crate::workshop_setup::Failure {
        crate::workshop_setup::Failure::from_error("workshop_addon", validate_addons(root).unwrap_err())
    }
    #[test]
    fn addon_failures_identify_each_missing_file_or_folder() {
        for (relative, check) in [
            ("!!!TwichUI", "core_folder"), ("!!!TwichUI/!!!TwichUI.toc", "core_toc"),
            ("TwichUI_Workshop", "workshop_folder"), ("TwichUI_Workshop/TwichUI_Workshop.toc", "workshop_toc"),
            ("TwichUI_Workshop/Summary.lua", "summary_lua"), ("TwichUI_Workshop/Bridge.lua", "bridge_lua"),
            ("TwichUI_Workshop/MarketDelivery.json", "capability_file"),
        ] {
            let root = fixture(); let file = root.path().join("Interface/AddOns").join(relative);
            if file.is_dir() { fs::remove_dir_all(file).unwrap(); } else { fs::remove_file(file).unwrap(); }
            let e = failure(root.path()); assert_eq!(e.code, "workshop_addon"); assert_eq!(e.check.as_deref(), Some(check));
            assert_eq!(e.stage, "workshop_addon"); assert!(!e.message.contains("needs an update"));
        }
    }
    #[test]
    fn addon_toc_and_json_failures_remain_specific_and_redacted() {
        for (relative, content, check, detail) in [
            ("TwichUI_Workshop/TwichUI_Workshop.toc", "## Interface: 16001\n# Summary.lua\n", "summary_toc_entry", "Summary.lua TOC entry missing"),
            ("TwichUI_Workshop/MarketDelivery.json", "{\"secret-token private-path\":", "capability_json", "json_category="),
            ("TwichUI_Workshop/MarketDelivery.json", "{\"format\":1,\"format\":2}", "capability_json", "json_category="),
        ] {
            let root = fixture(); fs::write(root.path().join("Interface/AddOns").join(relative), content).unwrap();
            let e = failure(root.path()); assert_eq!(e.check.as_deref(), Some(check)); assert!(e.details.contains(detail), "{}", e.details);
            let diagnostic = serde_json::json!({"workshop_setup":e}).to_string();
            assert!(!diagnostic.contains("secret-token")); assert!(!diagnostic.contains("private-path"));
            assert!(!diagnostic.contains(root.path().to_str().unwrap()));
        }
    }
    #[test]
    fn addon_contract_identifies_every_field_without_echoing_values() {
        for field in ["format", "game", "interface", "summary_delivery_version", "summary_partition_bytes", "summary_total_bytes"] {
            let root = fixture(); let mut cap: Value = serde_json::from_str(CAP).unwrap();
            cap[field] = "secret-token".into();
            fs::write(root.path().join("Interface/AddOns/TwichUI_Workshop/MarketDelivery.json"), cap.to_string()).unwrap();
            let e = failure(root.path()); assert_eq!(e.check.as_deref(), Some("summary_contract"));
            assert_eq!(e.details, format!("{field} mismatch")); assert!(!serde_json::to_string(&e).unwrap().contains("secret-token"));
        }
    }
    #[test]
    fn addon_toc_interface_metadata_is_not_a_delivery_gate() {
        // Delivery compatibility comes from MarketDelivery.json, not the
        // game loader's TOC Interface metadata (which can vary by client).
        for header in ["## Interface: 16001\n", "## Interface: 11200\n", "## Interface: 16001, 16002\n", "## Title: TwichUI\n"] {
            let root = fixture(); let addons = root.path().join("Interface/AddOns");
            fs::write(addons.join("!!!TwichUI/!!!TwichUI.toc"), header).unwrap();
            fs::write(addons.join("TwichUI_Workshop/TwichUI_Workshop.toc"), format!("{header}Summary.lua\nBridge.lua\n")).unwrap();
            assert!(validate_addons(root.path()).is_ok(), "TOC metadata blocked compatible delivery: {header}");
            // Removing an irrelevant header gate must not allow a consumer
            // with a different summary-delivery contract through setup.
            let mut cap: Value = serde_json::from_str(CAP).unwrap(); cap["summary_delivery_version"] = 2.into();
            fs::write(addons.join("TwichUI_Workshop/MarketDelivery.json"), cap.to_string()).unwrap();
            let e = failure(root.path()); assert_eq!(e.check.as_deref(), Some("summary_contract"));
            assert_eq!(e.details, "summary_delivery_version mismatch");
        }
    }
    #[test]
    fn addon_accepts_windows_text_formatting_without_relaxing_contract() {
        let root = fixture(); let addons = root.path().join("Interface/AddOns");
        fs::write(addons.join("!!!TwichUI/!!!TwichUI.toc"), "\u{feff}## Interface:16001\r\n").unwrap();
        fs::write(addons.join("TwichUI_Workshop/TwichUI_Workshop.toc"), "\u{feff}## Interface:\t16001\r\nSummary.lua\r\nBridge.lua\r\n").unwrap();
        fs::write(addons.join("TwichUI_Workshop/MarketDelivery.json"), format!("\u{feff}{CAP}\r\n")).unwrap();
        assert!(validate_addons(root.path()).is_ok());
    }
    #[test]
    fn addon_permission_failure_retains_file_check_and_safe_os_details() {
        let error: Result<()> = Err(std::io::Error::new(std::io::ErrorKind::PermissionDenied, "secret-token private-path").into());
        let e = crate::workshop_setup::checked("core_toc", "The core TOC is unreadable.", error).unwrap_err();
        let e = crate::workshop_setup::Failure::from_error("workshop_addon", e);
        assert_eq!(e.code, "access_denied"); assert_eq!(e.check.as_deref(), Some("core_toc"));
        assert!(e.details.contains("PermissionDenied")); assert!(e.message.contains("Read permission denied"));
        assert!(!serde_json::to_string(&e).unwrap().contains("secret-token"));
    }
    #[cfg(windows)]
    #[test]
    fn addon_windows_busy_file_identifies_the_exact_file() {
        use std::os::windows::fs::OpenOptionsExt;
        let root = fixture();
        let path = root.path().join("Interface/AddOns/TwichUI_Workshop/Summary.lua");
        // Exclusive handle reproduces an actual native access failure without
        // changing ACLs on any installed addon or relying on synthetic I/O.
        let locked = fs::OpenOptions::new().read(true).share_mode(0).open(path).unwrap();
        let e = failure(root.path());
        assert_eq!(e.code, "file_busy", "{}", e.details); assert_eq!(e.check.as_deref(), Some("summary_lua"));
        assert!(e.details.contains("os_code=Some(32)"));
        drop(locked); assert!(validate_addons(root.path()).is_ok());
    }
    #[cfg(unix)]
    #[test]
    fn addon_linked_files_are_still_refused() {
        let root = fixture(); let path = root.path().join("Interface/AddOns/TwichUI_Workshop/Summary.lua");
        fs::remove_file(&path).unwrap(); std::os::unix::fs::symlink("Bridge.lua", path).unwrap();
        let e = failure(root.path()); assert_eq!(e.code, "unsafe_path"); assert_eq!(e.check.as_deref(), Some("summary_lua"));
    }
    #[test]
    fn addon_oversized_and_invalid_utf8_files_fail_closed() {
        let root = fixture(); let addons = root.path().join("Interface/AddOns");
        fs::write(addons.join("!!!TwichUI/!!!TwichUI.toc"), [0xff]).unwrap();
        assert_eq!(failure(root.path()).check.as_deref(), Some("core_toc"));
        fs::write(addons.join("!!!TwichUI/!!!TwichUI.toc"), "## Interface: 16001\n").unwrap();
        fs::write(addons.join("TwichUI_Workshop/MarketDelivery.json"), vec![b' ';4097]).unwrap();
        assert_eq!(failure(root.path()).check.as_deref(), Some("capability_json"));
    }
}

/// History is negotiated only when the installed addon declares the exact
/// supported contract and bounds. Existing summary-only addons remain valid.
pub fn summary_contract(path:&Path)->Result<u64> {
    let capability=path.join("Interface/AddOns/TwichUI_Workshop/MarketDelivery.json");
    if !capability.try_exists()? {return Ok(1)}
    let raw=read(&capability,4096)?;
    let cap=crate::bridge::parse(raw.strip_prefix(&[0xef,0xbb,0xbf]).unwrap_or(&raw),4096)?;
    if cap["summary_history_contract"]==2 {
        need(cap["summary_history_partition_bytes"]==1048576&&cap["summary_history_total_bytes"]==67108864,"Workshop history capability bounds")?;
        Ok(2)
    }else{Ok(1)}
}
