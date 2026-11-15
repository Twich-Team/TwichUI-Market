use std::fs;
use twichui_market_core::settings::{Settings, INTERVAL_MINUTES, PRODUCTION_ORIGIN};

#[test]
fn safe_defaults_and_first_run_cannot_disappear_into_the_tray() {
    let mut value = Settings::default();
    assert_eq!(value.server, PRODUCTION_ORIGIN);
    assert_eq!(value.interval_minutes, 30);
    assert!(value.automatic_sync && value.sync_on_startup && value.close_to_tray);
    assert!(!value.launch_at_login && !value.minimize_to_tray && !value.start_in_tray);
    value.start_in_tray = true;
    value.selected_market = Some(2);
    assert!(!value.should_start_hidden(true));
    value.onboarding_completed = true;
    assert!(!value.should_start_hidden(false));
    assert!(value.should_start_hidden(true));
}

#[test]
fn persistent_settings_round_trip_and_legacy_migration_preserve_connection() {
    let directory = tempfile::tempdir().unwrap();
    fs::write(
        directory.path().join("connection.json"),
        br#"{"server":"https://market.twich.gg"}"#,
    )
    .unwrap();
    let mut value = Settings::load(directory.path()).unwrap();
    assert_eq!(value.server, PRODUCTION_ORIGIN);
    assert!(!value.onboarding_completed);
    value.selected_market = Some(2);
    value.interval_minutes = 120;
    value.start_in_tray = true;
    value.save(directory.path()).unwrap();
    assert_eq!(Settings::load(directory.path()).unwrap(), value);
    assert!(directory.path().join("connection.json").exists());
    value.interval_minutes = 240;
    value.save(directory.path()).unwrap();
    assert_eq!(
        Settings::load(directory.path()).unwrap().interval_minutes,
        240
    );
    let document = fs::read_to_string(directory.path().join("settings.json")).unwrap();
    assert!(!document.contains("token") && !document.contains("password"));
}

#[test]
fn invalid_or_future_settings_are_preserved_without_silent_reset() {
    let directory = tempfile::tempdir().unwrap();
    for document in [
        r#"{"schema_version":99}"#,
        r#"{"interval_minutes":5}"#,
        r#"{"selected_market":0}"#,
        r#"{"launch_at_login":"yes"}"#,
        r#"{"server":"https://user:password@example.test"}"#,
        r#"{"server":"http://example.test"}"#,
        r#"{"token":"must-not-be-stored"}"#,
    ] {
        fs::write(directory.path().join("settings.json"), document).unwrap();
        assert!(Settings::load(directory.path()).is_err(), "{document}");
        assert_eq!(
            fs::read_to_string(directory.path().join("settings.json")).unwrap(),
            document
        );
    }
    fs::write(directory.path().join("settings.json"), vec![b' '; 8193]).unwrap();
    assert!(Settings::load(directory.path()).is_err());
}

#[test]
fn only_the_requested_intervals_and_safe_market_ids_can_be_saved() {
    let directory = tempfile::tempdir().unwrap();
    for minutes in INTERVAL_MINUTES {
        let value = Settings {
            interval_minutes: minutes,
            ..Settings::default()
        };
        value.save(directory.path()).unwrap();
        assert_eq!(value.interval_ms(), i64::from(minutes) * 60_000);
    }
    let invalid = Settings {
        selected_market: Some(u32::MAX),
        ..Settings::default()
    };
    assert!(invalid.save(directory.path()).is_err());
    assert_eq!(
        Settings::load(directory.path()).unwrap().interval_minutes,
        240
    );
}
