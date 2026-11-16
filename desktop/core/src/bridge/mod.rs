//! Opt-in bridge path. Independent of legacy cache/synchronizer and native schedule.
pub(crate) mod validation;
mod cache;
mod export;
pub use validation::{canonical, parse, validate, validate_header, validate_record, MAX_BYTES, MAX_RECORD_BYTES};
pub use cache::{BridgeCache, Scope};
pub use export::{export_generation, export_staging, inspect_artifact, staging_directory};

#[cfg(windows)]
mod windows_owner;
