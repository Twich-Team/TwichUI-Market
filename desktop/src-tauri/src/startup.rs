//! Current-user only, opt-in startup. Never inspect/write/delete HKLM entries.
#[cfg(windows)]
mod native {
    use windows_registry::CURRENT_USER;
    const KEY: &str = r"Software\Microsoft\Windows\CurrentVersion\Run";
    const APPROVED: &str =
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run";
    const NAME: &str = if cfg!(feature = "private-dev") { "TwichUI Market Companion DEV" } else { "TwichUI Market Companion" };
    type Result<T> = std::result::Result<T, String>;
    fn command() -> Result<String> {
        Ok(format!(
            "\"{}\" --background",
            std::env::current_exe()
                .map_err(|_| "Application location unavailable")?
                .display()
        ))
    }
    pub fn is_enabled() -> Result<bool> {
        let registered = CURRENT_USER
            .open(KEY)
            .ok()
            .and_then(|key| key.get_string(NAME).ok());
        if registered.as_deref() != Some(command()?.as_str()) {
            return Ok(false);
        }
        let approved = CURRENT_USER
            .open(APPROVED)
            .ok()
            .and_then(|key| key.get_value(NAME).ok());
        Ok(approved
            .as_ref()
            .is_none_or(|value| value.first().is_none_or(|byte| *byte == 2)))
    }
    pub fn enable() -> Result<()> {
        let expected = command()?;
        CURRENT_USER
            .create(KEY)
            .and_then(|key| key.set_string(NAME, &expected))
            .map_err(|_| "Windows could not enable launch at login".to_string())?;
        // Re-enable only our own current-user Task Manager entry when explicitly requested.
        if let Ok(key) = CURRENT_USER.options().write().open(APPROVED) {
            key.set_bytes(
                NAME,
                windows_registry::Type::Bytes,
                &[2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            )
            .map_err(|_| "Windows could not enable this startup entry".to_string())?;
        }
        Ok(())
    }
    pub fn disable() -> Result<()> {
        let expected = command()?;
        if let Ok(key) = CURRENT_USER.open(KEY) {
            if key.get_string(NAME).ok().as_deref() == Some(expected.as_str()) {
                CURRENT_USER
                    .create(KEY)
                    .and_then(|key| key.remove_value(NAME))
                    .map_err(|_| "Windows could not disable launch at login".to_string())?;
                if let Ok(approved) = CURRENT_USER.options().write().open(APPROVED) {
                    let _ = approved.remove_value(NAME);
                }
            }
        }
        Ok(())
    }
}
#[cfg(windows)]
pub use native::*;
#[cfg(not(windows))]
pub fn is_enabled() -> Result<bool, String> {
    Ok(false)
}
#[cfg(not(windows))]
pub fn enable() -> Result<(), String> {
    Err("Windows startup is unavailable on this platform".into())
}
#[cfg(not(windows))]
pub fn disable() -> Result<(), String> {
    Ok(())
}
