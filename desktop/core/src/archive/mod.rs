//! Manual retained-history archive and bounded schema-3 projection. No scheduler.
mod project;
pub(crate) mod scoped;
mod store;
mod wire;
pub use crate::bridge::Scope;
pub use project::project;
pub use scoped::{
    normalize as normalize_selection, preflight, validate as validate_scoped, DeliveryBudget,
    Selection, Sizes, VariantIdentity,
};
pub use store::{ArchiveMetrics, ArchiveStore, DEFAULT_DISK_BUDGET};
pub use wire::{Entry, Envelope, Header, Page};

fn coverage_key(scope: &Scope, protocol: u32) -> crate::Result<String> {
    if protocol == 1 { scope.key() } else { Ok(format!("{}:source-coverage-v2", scope.key()?)) }
}
