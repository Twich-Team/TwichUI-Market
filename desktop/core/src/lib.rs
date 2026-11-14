pub mod authorization;
pub mod cache;
pub mod client;
pub mod connection;
pub mod profile;
pub mod protocol;
pub mod scheduler;
pub mod settings;
pub mod synchronizer;
pub mod vault;
pub mod worker;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Unsupported or invalid market data: {0}")]
    Invalid(&'static str),
    #[error("Local cache could not be read or written")]
    Database(#[from] rusqlite::Error),
    #[error("Local file could not be read or written")]
    Io(#[from] std::io::Error),
    #[error("Market data is not valid JSON")]
    Json(#[from] serde_json::Error),
    #[error("Server request failed; cached data remains available")]
    Network,
    #[error("This connection needs approval; sign in again in your browser")]
    Authentication,
    #[error("Connection approval was cancelled")]
    Cancelled,
    #[error("Connection approval was denied in your browser")]
    AuthorizationDenied,
    #[error("Connection approval expired; start again")]
    AuthorizationExpired,
    #[error("Desktop connection is temporarily unavailable; please try again later")]
    ServiceUnavailable,
    #[error("Please wait before trying again")]
    RateLimited(u64),
    #[error("Server rejected the saved cursor; reset this market to synchronize again")]
    ResetRequired,
    #[error("Windows Credential Manager is unavailable")]
    Vault,
    #[error("No saved desktop connection; sign in in your browser")]
    CredentialMissing,
}

pub type Result<T> = std::result::Result<T, Error>;
