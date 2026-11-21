//! Read-only probe for a real unpacked seven-addon package arranged under Interface/AddOns.
fn main() {
    let root = std::env::args_os().nth(1).expect("game-shaped package root required");
    match twichui_market_core::installation::validate_addons(std::path::Path::new(&root)) {
        Ok(()) => println!("{{\"addon_contract\":\"compatible\"}}"),
        Err(error) => {
            println!("{}", serde_json::to_string(&twichui_market_core::workshop_setup::Failure::from_error("workshop_addon", error)).unwrap());
            std::process::exit(1);
        }
    }
}
