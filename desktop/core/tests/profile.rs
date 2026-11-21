use std::fs;
use twichui_market_core::profile::{Mode, Profile};
#[test]
fn profile_is_origin_scoped_bounded_and_preserves_legacy_connection() {
    let dir = tempfile::tempdir().unwrap();
    fs::write(
        dir.path().join("connection.json"),
        r#"{"server":"https://market.example"}"#,
    )
    .unwrap();
    let profile = Profile {
        mode: Mode::Legacy,
        ..Profile::disconnected("https://market.example").unwrap()
    };
    profile.save(dir.path()).unwrap();
    assert_eq!(
        Profile::load(dir.path(), "https://market.example/")
            .unwrap()
            .unwrap()
            .mode,
        Mode::Legacy
    );
    assert!(Profile::load(dir.path(), "https://other.example")
        .unwrap()
        .is_none());
    assert!(dir.path().join("connection.json").exists());
    assert!(
        !fs::read_to_string(Profile::path(dir.path(), "https://market.example").unwrap())
            .unwrap()
            .contains("token")
    );
}
#[test]
fn corrupt_or_future_profile_is_never_silently_rewritten() {
    let dir = tempfile::tempdir().unwrap();
    let server = "https://market.example";
    let path = Profile::path(dir.path(), server).unwrap();
    for text in [
        r#"{"schema_version":99,"server":"https://market.example/","mode":"disconnected","device_id":null,"bootstrap":null}"#,
        r#"{"schema_version":1,"server":"https://other.example/","mode":"disconnected","device_id":null,"bootstrap":null}"#,
        r#"{"schema_version":1,"server":"https://market.example/","mode":"companion","device_id":null,"bootstrap":null}"#,
        r#"{"schema_version":1,"server":"https://market.example/","mode":"disconnected","device_id":null,"bootstrap":null,"access_token":"invalid"}"#,
    ] {
        fs::write(&path, text).unwrap();
        assert!(Profile::load(dir.path(), server).is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), text);
    }
    fs::write(&path, vec![b'x'; 262_145]).unwrap();
    assert!(Profile::load(dir.path(), server).is_err());
    assert_eq!(fs::metadata(path).unwrap().len(), 262_145);
}

#[test]
fn sign_out_can_retain_market_context_without_retaining_account_or_device_metadata() {
    let dir = tempfile::tempdir().unwrap();
    let mut profile = Profile::disconnected("https://market.example").unwrap();
    profile.last_market = Some(twichui_market_core::profile::RememberedMarket {
        id: 2,
        label: "US — Normal — Horde".into(),
    });
    profile.save(dir.path()).unwrap();
    let restored = Profile::load(dir.path(), "https://market.example")
        .unwrap()
        .unwrap();
    assert_eq!(restored.mode, Mode::Disconnected);
    assert!(restored.bootstrap.is_none() && restored.device_id.is_none());
    assert_eq!(restored.last_market.unwrap().id, 2);
}
