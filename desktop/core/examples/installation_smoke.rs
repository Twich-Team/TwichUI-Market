//! Actual native OS discovery/picker acceptance; no path supplied to the picker.
use twichui_market_core::{installation,delivery,bridge::Scope};
fn main()->Result<(),Box<dyn std::error::Error>> {
 let action=std::env::args().nth(1).ok_or("choose|discover required")?;
 if action=="inspect" {
  let path=std::env::args().nth(2).ok_or("fixture path required")?;
  let account=std::env::args().nth(3).map(|s|s.parse::<u32>()).transpose()?.unwrap_or(1);
  let config=delivery::Configuration{version:2,enabled:true,scope:Scope{server:"https://fixture.invalid/".into(),account_id:account,market_id:2,algorithm:"twichui-pricing-v1".into()},installation:path.into(),selection:serde_json::json!({"kind":"broad_summary","market_id":2,"region":"us"}),history_days:0};
  let (elevated,admin_enabled)=token_security()?;
  let result=match delivery::inspect_destination(&config) {
   Ok(_)=>serde_json::json!({"accepted":true,"elevated":elevated,"admin_enabled":admin_enabled}),
   Err(e)=>serde_json::json!({"accepted":false,"elevated":elevated,"admin_enabled":admin_enabled,"failure":twichui_market_core::workshop_setup::Failure::from_error("destination",e)}),
  };
  println!("{result}");
 }
 else if action=="discover" {println!("{}",serde_json::json!({"candidates":installation::discover(None)}));}
 else if action=="choose" {
  let selected=installation::choose_folder()?;
  let valid=selected.as_ref().map(|p|installation::validate(p).is_ok());
  println!("{}",serde_json::json!({"selected":selected,"valid":valid}));
 }else{return Err("unknown picker fixture action".into())}
 Ok(())
}

#[cfg(windows)]
fn token_security()->Result<(bool,bool),Box<dyn std::error::Error>> {
 use windows_sys::Win32::{Foundation::CloseHandle,Security::*,System::Threading::*};
 unsafe {
  let mut token=std::ptr::null_mut();
  if OpenProcessToken(GetCurrentProcess(),TOKEN_QUERY,&mut token)==0{return Err(std::io::Error::last_os_error().into())}
  let mut elevation=TOKEN_ELEVATION::default();let mut size=0;
  let ok=GetTokenInformation(token,TokenElevation,(&mut elevation as *mut TOKEN_ELEVATION).cast(),std::mem::size_of::<TOKEN_ELEVATION>() as u32,&mut size);
  CloseHandle(token);
  if ok==0{return Err(std::io::Error::last_os_error().into())}
  let mut sid=[0usize;16];let mut bytes=std::mem::size_of_val(&sid) as u32;let mut admin=0;
  if CreateWellKnownSid(WinBuiltinAdministratorsSid,std::ptr::null_mut(),sid.as_mut_ptr().cast(),&mut bytes)==0
      || CheckTokenMembership(std::ptr::null_mut(),sid.as_mut_ptr().cast(),&mut admin)==0{return Err(std::io::Error::last_os_error().into())}
  Ok((elevation.TokenIsElevated!=0,admin!=0))
 }
}
#[cfg(not(windows))]
fn token_security()->Result<(bool,bool),Box<dyn std::error::Error>> {Ok((false,false))}
