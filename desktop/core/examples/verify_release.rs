//! Offline publisher check; no private key, network, installation or database access.
use serde::Deserialize;
use std::{fs::File, io::Read, path::PathBuf};
use twichui_market_core::{
    update::{self, Package},
    Error,
};
#[derive(Deserialize)]
struct Receipt {
    version: String,
    filename: String,
    bytes: u64,
    sha256: String,
    source_commit: String,
    notes: String,
    updater_signature: String,
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let arguments: Vec<_> = std::env::args_os().skip(1).collect();
    if arguments.len() != 2 {
        return Err(Error::Invalid("provide receipt and installer paths").into());
    }
    let path = PathBuf::from(&arguments[0]);
    let mut document = Vec::new();
    File::open(path)?.take(16385).read_to_end(&mut document)?;
    if document.len() > 16384 {
        return Err(Error::Invalid("release receipt exceeds limit").into());
    }
    let receipt: Receipt = serde_json::from_slice(&document)?;
    if receipt.filename
        != format!(
            "TwichUI-Market-Companion-{}-windows-x64.exe",
            receipt.version
        )
    {
        return Err(Error::Invalid("release filename").into());
    }
    let package = Package {
        version: receipt.version,
        download_url: String::new(),
        bytes: receipt.bytes,
        sha256: receipt.sha256,
        source_commit: receipt.source_commit,
        notes: receipt.notes,
    };
    let package = Package {
        download_url: format!(
            "{}/api/v1/companion/releases/{}/windows-x64",
            update::ORIGIN,
            package.version
        ),
        ..package
    };
    let bytes = package.read_verified(File::open(PathBuf::from(&arguments[1]))?)?;
    let key = std::env::var("COMPANION_UPDATER_PUBLIC_KEY")
        .map_err(|_| Error::Invalid("publisher trust key required"))?;
    update::verify_signature(&bytes, &key, &receipt.updater_signature, &package.version)?;
    println!(
        "{}",
        serde_json::json!({"signature_verified":true,"signed_version":package.version,"sha256":package.sha256})
    );
    Ok(())
}
