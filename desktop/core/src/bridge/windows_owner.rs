//! Fail closed on ambiguous Windows staging ownership or broad write permissions.
use crate::{Error,Result};
use std::{ffi::c_void,os::windows::ffi::OsStrExt,path::{Path,Prefix}};
use windows_sys::Win32::{Foundation::{CloseHandle,LocalFree,HANDLE},Security::{*,Authorization::{GetNamedSecurityInfoW,SE_FILE_OBJECT}},Storage::FileSystem::GetDriveTypeW,System::Threading::{GetCurrentProcess,OpenProcessToken}};
fn reject<T>()->Result<T>{Err(Error::Invalid("Windows bridge staging ownership or ACL is ambiguous"))}
struct Token(HANDLE);
impl Drop for Token{fn drop(&mut self){unsafe{CloseHandle(self.0);}}}
struct Descriptor(*mut c_void);
impl Drop for Descriptor{fn drop(&mut self){if !self.0.is_null(){unsafe{LocalFree(self.0);}}}}
// Both installed inputs and output must stay on a local fixed disk.
pub(crate) fn local(path:&Path)->Result<()> {
 let Some(std::path::Component::Prefix(prefix))=path.components().next() else{return reject()};
 let drive=match prefix.kind(){Prefix::Disk(c)|Prefix::VerbatimDisk(c)=>c,_=>return reject()};
 let root=[drive as u16,b':' as u16,b'\\' as u16,0];
 if unsafe {GetDriveTypeW(root.as_ptr())}!=3{return reject()}
 Ok(())
}
pub(crate) fn check(path:&Path)->Result<()>{check_policy(path,false)}
// The AddOns parent may be administrator/SYSTEM owned. The current user must
// have effective create access, and unrelated principals must not have writes.
pub(crate) fn output_parent(path:&Path)->Result<()>{
 check_policy(path,true)?;
 use windows_sys::Win32::Storage::FileSystem::*;
 let wide=path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
 let handle=unsafe {CreateFileW(wide.as_ptr(),FILE_ADD_SUBDIRECTORY|FILE_ADD_FILE,
     FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,std::ptr::null(),OPEN_EXISTING,
     FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_OPEN_REPARSE_POINT,std::ptr::null_mut())};
 if handle==windows_sys::Win32::Foundation::INVALID_HANDLE_VALUE{return Err(std::io::Error::last_os_error().into())}
 drop(Token(handle)); Ok(())
}
fn check_policy(path:&Path,installed_parent:bool)->Result<()>{
 local(path)?;
 let wide=path.as_os_str().encode_wide().chain(Some(0)).collect::<Vec<_>>();
 // Buffers are naturally aligned, bounded, and owned for the lifetime of each SID.
 unsafe {
  let mut handle=std::ptr::null_mut();if OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&mut handle)==0{return reject()}let token=Token(handle);
  let token_info=|class|->Result<Vec<usize>>{let mut size=0;GetTokenInformation(token.0,class,std::ptr::null_mut(),0,&mut size);if size==0||size>65536{return reject()}let mut buf=vec![0usize;(size as usize).div_ceil(std::mem::size_of::<usize>())];if GetTokenInformation(token.0,class,buf.as_mut_ptr().cast(),size,&mut size)==0{return reject()}Ok(buf)};
  let user=token_info(TokenUser)?;let default_owner=token_info(TokenOwner)?;
  let user_sid=(*(user.as_ptr().cast::<TOKEN_USER>())).User.Sid;
  let default_sid=(*(default_owner.as_ptr().cast::<TOKEN_OWNER>())).Owner;
  let(mut owner,mut dacl,mut descriptor)=(std::ptr::null_mut(),std::ptr::null_mut(),std::ptr::null_mut());
  let status=GetNamedSecurityInfoW(wide.as_ptr(),SE_FILE_OBJECT,OWNER_SECURITY_INFORMATION|DACL_SECURITY_INFORMATION,&mut owner,std::ptr::null_mut(),&mut dacl,std::ptr::null_mut(),&mut descriptor);let _descriptor=Descriptor(descriptor);
  if status!=0 {return Err(std::io::Error::from_raw_os_error(status as i32).into())}
  if owner.is_null()||dacl.is_null(){return reject()}
  let mut size=ACL_SIZE_INFORMATION::default();if GetAclInformation(dacl,(&mut size as *mut ACL_SIZE_INFORMATION).cast(),std::mem::size_of::<ACL_SIZE_INFORMATION>() as u32,AclSizeInformation)==0||size.AceCount>1024{return reject()}
  let mut trusted=Vec::new();for kind in [WinLocalSystemSid,WinBuiltinAdministratorsSid,WinCreatorOwnerSid]{let mut sid=[0usize;16];let mut bytes=std::mem::size_of_val(&sid) as u32;if CreateWellKnownSid(kind,std::ptr::null_mut(),sid.as_mut_ptr().cast(),&mut bytes)==0{return reject()}trusted.push(sid)}
  if EqualSid(owner,user_sid)==0&&EqualSid(owner,default_sid)==0
      && !(installed_parent&&trusted[..2].iter().any(|s|EqualSid(owner,s.as_ptr().cast_mut().cast())!=0)){return reject()}
  for i in 0..size.AceCount{let mut ace=std::ptr::null_mut();if GetAce(dacl,i,&mut ace)==0||ace.is_null(){return reject()}let header=&*(ace.cast::<ACE_HEADER>());if header.AceFlags&INHERIT_ONLY_ACE as u8!=0{continue}if header.AceType==1{continue}if header.AceType!=0||header.AceSize<(std::mem::size_of::<ACCESS_ALLOWED_ACE>() as u16){return reject()}let allowed=&*(ace.cast::<ACCESS_ALLOWED_ACE>());let sid=(&allowed.SidStart as *const u32).cast_mut().cast::<c_void>();if IsValidSid(sid)==0{return reject()}let writes=0x40000000|0x10000000|0x000D0000|0x00000156;if allowed.Mask&writes!=0&&EqualSid(sid,user_sid)==0&&EqualSid(sid,default_sid)==0&&!trusted.iter().any(|s|EqualSid(sid,s.as_ptr().cast_mut().cast())!=0){return reject()}}
 }
 Ok(())
}
