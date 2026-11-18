//! Actual native OS discovery/picker acceptance; no path supplied to the picker.
use twichui_market_core::installation;
fn main()->Result<(),Box<dyn std::error::Error>> {
 let action=std::env::args().nth(1).ok_or("choose|discover required")?;
 if action=="discover" {println!("{}",serde_json::json!({"candidates":installation::discover(None)}));}
 else if action=="choose" {
  let selected=installation::choose_folder()?;
  let valid=selected.as_ref().map(|p|installation::validate(p).is_ok());
  println!("{}",serde_json::json!({"selected":selected,"valid":valid}));
 }else{return Err("unknown picker fixture action".into())}
 Ok(())
}
