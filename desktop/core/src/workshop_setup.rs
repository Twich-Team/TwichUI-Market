//! Public setup failures contain only allowlisted details, never paths or secrets.
use crate::Error;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Failure {
    pub code: String,
    pub stage: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub check: Option<String>,
    pub message: String,
    pub details: String,
}

impl Failure {
    pub fn new(code: &str, stage: &str, details: String) -> Self {
        let message = match code {
            "wrong_folder" => "Choose the Forever game folder containing Wow.exe and Interface/AddOns.",
            "unsupported_client" => "This Wow.exe version is not verified for Forever. Choose a supported Forever installation.",
            "workshop_addon" => "Workshop needs an update or is missing files. Install the compatible TwichUI addon, then retry.",
            "access_denied" => "Windows could not access this installation safely. Choose a folder where your Windows account can read the game and write addon data.",
            "ownership_conflict" => "Existing Market data could not be safely adopted. Reconnect its original Market account and market, or choose another installation. Your files were preserved.",
            "unsafe_path" => "This installation uses an unsafe linked path. Choose a local Forever folder without junctions or symbolic links.",
            "context_changed" => "Your account or market changed during setup. Connect Workshop again.",
            "folder_picker" => "Windows could not open or read the folder picker. Close the dialog and retry Connect Workshop.",
            "cancelled" => "Folder selection cancelled.",
            _ => "Workshop setup could not finish because of an unexpected error. Retry or save developer diagnostics. Your files were preserved.",
        };
        Self {
            code: code.into(),
            stage: stage.into(),
            check: None,
            message: message.into(),
            details,
        }
    }

    pub fn from_error(stage: &str, error: Error) -> Self {
        if let Error::WorkshopSetup(failure) = error {
            return *failure;
        }
        let details = match &error {
            Error::Invalid(reason) => (*reason).to_owned(),
            Error::Io(e) => format!("io_kind={:?}; os_code={:?}", e.kind(), e.raw_os_error()),
            Error::Json(e) => format!(
                "json_category={:?}; line={}; column={}",
                e.classify(),
                e.line(),
                e.column()
            ),
            _ => "unexpected native setup failure".into(),
        };
        let code = match &error {
            Error::Io(e) if e.kind() == std::io::ErrorKind::PermissionDenied => "access_denied",
            Error::Invalid(s) if s.contains("ownership or") || s.contains("ACL") => "access_denied",
            Error::Invalid(s) if s.contains("traversal") || s.contains("unsafe") => "unsafe_path",
            _ => match stage {
                "game_folder" => "wrong_folder",
                "executable_version" => "unsupported_client",
                "workshop_addon" => "workshop_addon",
                "destination" => "ownership_conflict",
                "folder_picker" => "folder_picker",
                _ => "internal",
            },
        };
        Self::new(code, stage, details)
    }
}

pub(crate) fn at<T>(stage: &str, result: crate::Result<T>) -> crate::Result<T> {
    result.map_err(|e| Error::WorkshopSetup(Box::new(Failure::from_error(stage, e))))
}


/// Add only a stable check and an allowlisted explanation; never OS/file payloads.
pub(crate) fn checked<T>(check: &str, message: &str, result: crate::Result<T>) -> crate::Result<T> {
    result.map_err(|error| {
        let mut failure = Failure::from_error("workshop_addon", error);
        failure.check = Some(check.into());
        failure.message = if failure.code == "access_denied" {
            format!("Read permission denied. {message}")
        } else if failure.code == "unsafe_path" {
            format!("Unsafe linked addon path. {message}")
        } else { message.into() };
        Error::WorkshopSetup(Box::new(failure))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diagnostics_keep_stage_and_os_code_without_io_payload() {
        let error = std::io::Error::new(
            std::io::ErrorKind::PermissionDenied,
            "secret-token private-path",
        );
        let failure = Failure::from_error("workshop_addon", Error::Io(error));
        assert_eq!(failure.code, "access_denied");
        assert_eq!(failure.stage, "workshop_addon");
        assert!(!serde_json::to_string(&failure)
            .unwrap()
            .contains("secret-token"));
        assert_eq!(
            Failure::from_error(
                "destination",
                Error::Invalid("destination belongs to another account or market")
            )
            .code,
            "ownership_conflict"
        );
        assert_eq!(
            Failure::from_error(
                "game_folder",
                Error::Invalid("junction/reparse traversal refused")
            )
            .code,
            "unsafe_path"
        );
    }
}
