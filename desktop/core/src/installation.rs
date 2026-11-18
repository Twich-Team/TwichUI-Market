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
    crate::workshop_setup::at("workshop_addon", (|| {
        let core=path.join("Interface/AddOns/!!!TwichUI");installed(&core)?;
        need(core.is_dir(),"Workshop needs an update.")?;
        let core_toc=String::from_utf8(read(&core.join("!!!TwichUI.toc"),65536)?).map_err(|_|Error::Invalid("Workshop needs an update."))?;
        need(core_toc.lines().any(|l|l.trim()=="## Interface: 16001"),"Workshop needs an update.")?;
        let folder=path.join("Interface/AddOns/TwichUI_Workshop"); installed(&folder)?;
        need(folder.is_dir(),"Workshop needs an update.")?;
        for name in ["TwichUI_Workshop.toc","Summary.lua","Bridge.lua","MarketDelivery.json"] {
            let file=folder.join(name); installed(&file)?;
            need(file.is_file(),"Workshop needs an update.")?;
            // Existence alone misses valid files that Windows refuses to read.
            // Read a bounded prefix for Lua files; their contents are not run.
            if name.ends_with(".lua") { use std::io::Read; let mut byte=[0u8;1]; std::fs::File::open(file)?.read(&mut byte)?; }
        }
        let cap:Value=crate::bridge::parse(&read(&folder.join("MarketDelivery.json"),4096)?,4096)?;
        need(cap["format"]=="twichui-market-consumer" && cap["summary_delivery_version"]==1
            && cap["game"]=="wow-forever" && cap["interface"]==16001
            && cap["summary_partition_bytes"]==131072 && cap["summary_total_bytes"]==8388608,
            "Workshop needs an update.")?;
        let toc=String::from_utf8(read(&folder.join("TwichUI_Workshop.toc"),32768)?).map_err(|_|Error::Invalid("Workshop needs an update."))?;
        need(toc.lines().any(|l|l.trim()=="## Interface: 16001") && toc.lines().any(|l|l.trim()=="Summary.lua"),"Workshop needs an update.")
    })())
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
