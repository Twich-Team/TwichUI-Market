//! Bounded, read-only Windows discovery. No disk scans or game execution.
use crate::{delivery::{owned,read}, Error, Result};
use serde_json::Value;
use std::{collections::HashSet, path::{Path,PathBuf}};

fn need(ok:bool,why:&'static str)->Result<()> {if ok {Ok(())} else {Err(Error::Invalid(why))}}

pub fn validate_game(path:&Path)->Result<()> {
    owned(path)?; owned(&path.join("Interface"))?; owned(&path.join("Interface/AddOns"))?;
    let exe=path.join("Wow.exe"); owned(&exe)?;
    need(exe.is_file(),"Couldn't find your WoW installation. Choose folder.")?;
    let version=executable_version(&exe)?;
    // Existing verified Forever source/Simulator profile: 1.60.1, interface
    // 16001. Unknown editions fail closed; native acceptance remains separate.
    need(version[..3]==[1,60,1],"This client version is not verified for Forever. Choose the supported Forever installation.")
}

pub fn validate(path:&Path)->Result<()> {
    validate_game(path)?;
    let core=path.join("Interface/AddOns/!!!TwichUI");need(core.is_dir(),"Workshop needs an update.")?;owned(&core)?;
    let core_toc=String::from_utf8(read(&core.join("!!!TwichUI.toc"),65536)?).map_err(|_|Error::Invalid("Workshop needs an update."))?;
    need(core_toc.lines().any(|l|l.trim()=="## Interface: 16001"),"Workshop needs an update.")?;
    let folder=path.join("Interface/AddOns/TwichUI_Workshop");
    need(folder.is_dir(),"Workshop needs an update.")?;owned(&folder)?;
    for name in ["TwichUI_Workshop.toc","Summary.lua","Bridge.lua","MarketDelivery.json"] {need(folder.join(name).is_file(),"Workshop needs an update.")?;owned(&folder.join(name))?;}
    let cap:Value=crate::bridge::parse(&read(&folder.join("MarketDelivery.json"),4096)?,4096)?;
    need(cap["format"]=="twichui-market-consumer" && cap["summary_delivery_version"]==1
        && cap["game"]=="wow-forever" && cap["interface"]==16001
        && cap["summary_partition_bytes"]==131072 && cap["summary_total_bytes"]==8388608,
        "Workshop needs an update.")?;
    let toc=String::from_utf8(read(&folder.join("TwichUI_Workshop.toc"),32768)?).map_err(|_|Error::Invalid("Workshop needs an update."))?;
    need(toc.lines().any(|l|l.trim()=="## Interface: 16001") && toc.lines().any(|l|l.trim()=="Summary.lua"),"Workshop needs an update.")
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

#[cfg(not(windows))]
fn executable_version(path:&Path)->Result<[u16;4]> {
    #[cfg(test)]
    if read(path,128).ok().as_deref()==Some(b"TWICHUI SYNTHETIC FOREVER 1.60.1".as_slice()) {return Ok([1,60,1,7053])}
    let _=path;
    Err(Error::Invalid("Forever installation verification requires Windows"))
}

#[cfg(windows)]
fn executable_version(path:&Path)->Result<[u16;4]> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::*;
    let name=path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
    unsafe {
        let size=GetFileVersionInfoSizeW(name.as_ptr(),std::ptr::null_mut());
        need(size>0 && size<=1024*1024,"The Forever executable version could not be verified.")?;
        // u64 storage provides alignment for VS_FIXEDFILEINFO.
        let mut buffer=vec![0u64;(size as usize+7)/8];
        need(GetFileVersionInfoW(name.as_ptr(),0,size,buffer.as_mut_ptr().cast())!=0,"The Forever executable version could not be verified.")?;
        let mut result=std::ptr::null_mut();let mut length=0;
        need(VerQueryValueW(buffer.as_ptr().cast(),[b'\\' as u16,0].as_ptr(),&mut result,&mut length)!=0
            && length as usize>=std::mem::size_of::<VS_FIXEDFILEINFO>() && !result.is_null(),"The Forever executable version could not be verified.")?;
        let info=&*(result as *const VS_FIXEDFILEINFO);
        need(info.dwSignature==0xfeef04bd,"The Forever executable version could not be verified.")?;
        Ok([(info.dwFileVersionMS>>16) as u16,info.dwFileVersionMS as u16,
            (info.dwFileVersionLS>>16) as u16,info.dwFileVersionLS as u16])
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
