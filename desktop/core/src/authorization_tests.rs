use super::*;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    thread,
};

#[derive(Default, Clone)]
struct MemoryVault(Arc<Mutex<Option<Vec<u8>>>>, Arc<AtomicBool>);
impl CredentialStore for MemoryVault {
    fn load(&self, server: &str) -> Result<Session> {
        Session::decode(
            server,
            self.0.lock().unwrap().as_deref().ok_or(Error::Vault)?,
        )
    }
    fn save(&self, _: &str, value: &Session) -> Result<()> {
        if self.1.load(Ordering::Acquire) {
            return Err(Error::Vault);
        }
        *self.0.lock().unwrap() = Some(serde_json::to_vec(value).unwrap());
        Ok(())
    }
    fn remove(&self, _: &str) -> Result<()> {
        *self.0.lock().unwrap() = None;
        Ok(())
    }
}
struct HttpRequest {
    path: String,
    body: Vec<u8>,
}
fn http_request(stream: &mut TcpStream) -> HttpRequest {
    stream
        .set_read_timeout(Some(Duration::from_secs(3)))
        .unwrap();
    let mut bytes = Vec::new();
    let header_end;
    loop {
        let mut b = [0u8; 1024];
        let n = stream.read(&mut b).unwrap();
        assert!(n > 0);
        bytes.extend_from_slice(&b[..n]);
        if let Some(i) = bytes.windows(4).position(|v| v == b"\r\n\r\n") {
            header_end = i + 4;
            break;
        }
        assert!(bytes.len() < 16384);
    }
    let headers = std::str::from_utf8(&bytes[..header_end]).unwrap();
    let path = headers
        .lines()
        .next()
        .unwrap()
        .split(' ')
        .nth(1)
        .unwrap()
        .to_string();
    let size = headers
        .lines()
        .find_map(|s| {
            s.to_ascii_lowercase()
                .strip_prefix("content-length:")
                .map(|v| v.trim().parse::<usize>().unwrap())
        })
        .unwrap_or(0);
    while bytes.len() < header_end + size {
        let mut b = [0u8; 1024];
        let n = stream.read(&mut b).unwrap();
        assert!(n > 0);
        bytes.extend_from_slice(&b[..n]);
    }
    HttpRequest {
        path,
        body: bytes[header_end..header_end + size].to_vec(),
    }
}
fn server(
    count: usize,
    mut handler: impl FnMut(HttpRequest, &str) -> (u16, String) + Send + 'static,
) -> (String, thread::JoinHandle<()>) {
    let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
    listener.set_nonblocking(true).unwrap();
    let origin = format!("http://{}", listener.local_addr().unwrap());
    let base = origin.clone();
    let task = thread::spawn(move || {
        for _ in 0..count {
            let deadline = Instant::now() + Duration::from_secs(5);
            let mut stream = loop {
                match listener.accept() {
                    Ok((stream, _)) => break stream,
                    Err(e)
                        if e.kind() == std::io::ErrorKind::WouldBlock
                            && Instant::now() < deadline =>
                    {
                        thread::sleep(Duration::from_millis(10))
                    }
                    _ => panic!("test server did not receive expected native request"),
                }
            };
            let request = http_request(&mut stream);
            let (status, body) = handler(request, &base);
            let header = format!("HTTP/1.1 {status} test\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",body.len());
            stream.write_all(header.as_bytes()).unwrap();
            stream.write_all(body.as_bytes()).unwrap();
        }
    });
    (origin, task)
}
fn tokens(origin: &str) -> String {
    json!({"issuer":origin,"access_token":"A".repeat(43),"token_type":"Bearer","expires_in":3600,
        "refresh_token":"R".repeat(43),"refresh_expires_at":Utc::now()+TimeDelta::days(30),
        "authorization_expires_at":Utc::now()+TimeDelta::days(90),"scope":SCOPE,
        "device":{"id":7,"name":"Synthetic PC","platform":"Windows","app_version":"2.0.0"}})
    .to_string()
}
fn saved(origin: &str, expires_in: i64) -> Session {
    Session {
        schema_version: 1,
        issuer: server_url(origin).unwrap().to_string(),
        access_token: "O".repeat(43),
        refresh_token: "P".repeat(43),
        access_expires_at: Utc::now() + TimeDelta::seconds(expires_in),
        refresh_expires_at: Utc::now() + TimeDelta::days(30),
        authorization_expires_at: Utc::now() + TimeDelta::days(90),
        pending_rotation_nonce: None,
        device: TokenDevice {
            id: 7,
            name: "Synthetic PC".into(),
            platform: "Windows".into(),
            app_version: "2.0.0".into(),
        },
    }
}
fn request(authority: &str, query: &str) -> Vec<u8> {
    format!("GET {CALLBACK_PATH}?{query} HTTP/1.1\r\nHost: {authority}\r\n\r\n").into_bytes()
}
#[test]
fn pkce_matches_rfc7636_and_nonces_are_independent() {
    let proof = Proof {
        state: "state".into(),
        verifier: "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk".into(),
    };
    assert_eq!(
        proof.challenge(),
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    );
    let proof = Proof::new().unwrap();
    assert!(opaque(&proof.state) && opaque(&proof.verifier));
    assert_ne!(proof.state, proof.verifier);
}
#[test]
fn callbacks_reject_wrong_state_host_duplicates_paths_and_injected_parameters() {
    let authority = "127.0.0.1:43123";
    let state = "S".repeat(43);
    let code = "C".repeat(43);
    let good = request(authority, &format!("code={code}&state={state}"));
    assert_eq!(parse_callback(&good, authority, &state).unwrap(), code);
    let text = String::from_utf8(good.clone()).unwrap();
    for bad in [
        text.replace(&state, &"X".repeat(43)),
        text.replace(authority, "localhost:43123"),
        text.replace("GET ", "POST "),
        text.replace(CALLBACK_PATH, "/companion/%63allback"),
        text.replace(" HTTP/1.1", "&extra=x HTTP/1.1"),
        text.replace(" HTTP/1.1", &format!("&state={state} HTTP/1.1")),
        text.replace("\r\n\r\n", &format!("\r\nHost: {authority}\r\n\r\n")),
        text.replace("\r\n\r\n", "\r\nOrigin: https://attacker.example\r\n\r\n"),
        text.replace("\r\n\r\n", "\r\nContent-Length: 0\r\n\r\n"),
        text.replace("GET /", "GET http://evil.example/"),
        text.replace(" HTTP/1.1", "#ignored HTTP/1.1"),
    ] {
        assert!(parse_callback(bad.as_bytes(), authority, &state).is_err());
    }
    assert!(parse_callback(&vec![b'x'; 8193], authority, &state).is_err());
    assert!(matches!(
        parse_callback(
            &request(authority, &format!("error=access_denied&state={state}")),
            authority,
            &state
        ),
        Err(Error::AuthorizationDenied)
    ));
}
#[test]
fn callback_owns_an_ephemeral_loopback_port_and_ignores_stray_requests() {
    let callback = Callback::bind().unwrap();
    let port = callback.listener.local_addr().unwrap();
    assert_eq!(port.ip(), Ipv4Addr::LOCALHOST);
    assert!(port.port() >= 1024);
    let competing = Socket::new(Domain::IPV4, Type::STREAM, Some(Protocol::TCP)).unwrap();
    competing.set_reuse_address(true).unwrap();
    assert!(competing.bind(&port.into()).is_err());
    let authority = callback.authority.clone();
    let state = "S".repeat(43);
    let expected = state.clone();
    let browser = thread::spawn(move || {
        for state in ["wrong".into(), state] {
            let mut stream = TcpStream::connect(port).unwrap();
            stream
                .write_all(&request(
                    &authority,
                    &format!("code={}&state={state}", "C".repeat(43)),
                ))
                .unwrap();
            let mut reply = String::new();
            stream.read_to_string(&mut reply).unwrap();
            assert!(reply.contains("no-store"));
            assert!(!reply.contains(&"C".repeat(43)));
        }
    });
    assert_eq!(
        callback
            .wait(
                &expected,
                Instant::now() + Duration::from_secs(3),
                &AtomicBool::new(false)
            )
            .unwrap(),
        "C".repeat(43)
    );
    browser.join().unwrap();
}
#[test]
fn callback_cancellation_and_expiry_do_not_wait_for_the_browser() {
    let callback = Callback::bind().unwrap();
    assert!(matches!(
        callback.wait(
            "state",
            Instant::now() + Duration::from_secs(300),
            &AtomicBool::new(true)
        ),
        Err(Error::Cancelled)
    ));
    assert!(matches!(
        callback.wait("state", Instant::now(), &AtomicBool::new(false)),
        Err(Error::AuthorizationExpired)
    ));
    let flag = Arc::new(AtomicBool::new(false));
    let owned = flag.clone();
    let port = callback.listener.local_addr().unwrap();
    let task = thread::spawn(move || {
        let mut slow = TcpStream::connect(port).unwrap();
        slow.write_all(b"GET /companion/callback?").unwrap();
        thread::sleep(Duration::from_millis(120));
        owned.store(true, Ordering::Release);
        thread::sleep(Duration::from_millis(200));
    });
    let start = Instant::now();
    assert!(matches!(
        callback.wait("state", Instant::now() + Duration::from_secs(300), &flag),
        Err(Error::Cancelled)
    ));
    assert!(start.elapsed() < Duration::from_secs(1));
    task.join().unwrap();
}
#[test]
fn browser_code_flow_keeps_tokens_out_of_callback_and_commits_only_to_vault() {
    let (send, receive) = std::sync::mpsc::channel();
    let mut phase = 0;
    let (origin, api) = server(2, move |request, origin| {
        phase += 1;
        if phase == 1 {
            assert_eq!(request.path, "/api/v1/companion/authorizations");
            let body: Value = serde_json::from_slice(&request.body).unwrap();
            assert_eq!(body["code_challenge_method"], "S256");
            assert_eq!(body["platform"], "Windows");
            send.send(body).unwrap();
            (201,json!({"request_id":"I".repeat(43),"authorization_url":format!("{origin}/companion/authorize?request={}","I".repeat(43)),"expires_at":Utc::now()+TimeDelta::minutes(5)}).to_string())
        } else {
            assert_eq!(request.path, "/api/v1/companion/token");
            let fields: HashMap<_, _> = url::form_urlencoded::parse(&request.body)
                .into_owned()
                .collect();
            assert_eq!(fields["code"], "C".repeat(43));
            assert_eq!(fields["client_id"], CLIENT_ID);
            assert_eq!(fields["grant_type"], "authorization_code");
            (200, tokens(origin))
        }
    });
    let client = AuthorizationClient::new(&origin).unwrap();
    let vault = MemoryVault::default();
    let pending = client.begin("Synthetic PC", "2.0.0").unwrap();
    let info = pending.info();
    assert!(info.authorization_url.contains("/companion/authorize?"));
    let body = receive.recv().unwrap();
    let callback = Url::parse(body["redirect_uri"].as_str().unwrap()).unwrap();
    assert_eq!(
        URL_SAFE_NO_PAD.encode(Sha256::digest(pending.proof.verifier.as_bytes())),
        body["code_challenge"]
    );
    let browser = thread::spawn(move || {
        let mut stream = TcpStream::connect(("127.0.0.1", callback.port().unwrap())).unwrap();
        stream
            .write_all(&request(
                &format!("127.0.0.1:{}", callback.port().unwrap()),
                &format!(
                    "code={}&state={}",
                    "C".repeat(43),
                    body["state"].as_str().unwrap()
                ),
            ))
            .unwrap();
        let mut reply = String::new();
        stream.read_to_string(&mut reply).unwrap();
        assert!(reply.starts_with("HTTP/1.1 200"));
        assert!(!reply.contains("access_token"));
    });
    let session = client
        .complete(pending, &AtomicBool::new(false), &vault)
        .unwrap();
    assert_eq!(session.device_id(), 7);
    assert_eq!(vault.load(&origin).unwrap().access_token, "A".repeat(43));
    api.join().unwrap();
    browser.join().unwrap();
}
#[test]
fn renewal_saves_intent_before_network_and_recovers_lost_response_with_the_same_nonce() {
    let vault = MemoryVault::default();
    let inspect = vault.clone();
    let mut nonce = None;
    let mut phase = 0;
    let (origin, api) = server(2, move |request, origin| {
        phase += 1;
        let fields: HashMap<_, _> = url::form_urlencoded::parse(&request.body)
            .into_owned()
            .collect();
        assert_eq!(fields["refresh_token"], "P".repeat(43));
        let stored = inspect.load(origin).unwrap();
        assert_eq!(
            stored.pending_rotation_nonce.as_deref(),
            Some(fields["rotation_nonce"].as_str())
        );
        if phase == 1 {
            nonce = Some(fields["rotation_nonce"].clone());
            (503, "{}".into())
        } else {
            assert_eq!(nonce.as_deref(), Some(fields["rotation_nonce"].as_str()));
            (200, tokens(origin))
        }
    });
    vault.save(&origin, &saved(&origin, -1)).unwrap();
    let client = AuthorizationClient::new(&origin).unwrap();
    assert!(matches!(
        client.session(&vault, Utc::now()),
        Err(Error::ServiceUnavailable)
    ));
    assert!(vault
        .load(&origin)
        .unwrap()
        .pending_rotation_nonce
        .is_some());
    let renewed = client.session(&vault, Utc::now()).unwrap();
    assert_eq!(renewed.refresh_token, "R".repeat(43));
    assert!(vault
        .load(&origin)
        .unwrap()
        .pending_rotation_nonce
        .is_none());
    api.join().unwrap(); // A subsequent healthy access must not make any network request.
    assert_eq!(client.session(&vault, Utc::now()).unwrap().device_id(), 7);
}
#[test]
fn failed_vault_write_never_sends_a_rotation_and_invalid_grants_preserve_cache_and_credentials() {
    let vault = MemoryVault::default();
    let origin = "http://127.0.0.1:1";
    vault.save(origin, &saved(origin, -1)).unwrap();
    vault.1.store(true, Ordering::Release);
    assert!(matches!(
        AuthorizationClient::new(origin)
            .unwrap()
            .session(&vault, Utc::now()),
        Err(Error::Vault)
    ));
    assert!(vault.load(origin).unwrap().pending_rotation_nonce.is_none());
    vault.1.store(false, Ordering::Release);
    let (origin, api) = server(1, |_, _| {
        (400, json!({"error":"invalid_grant"}).to_string())
    });
    vault.save(&origin, &saved(&origin, -1)).unwrap();
    assert!(matches!(
        AuthorizationClient::new(&origin)
            .unwrap()
            .session(&vault, Utc::now()),
        Err(Error::Authentication)
    ));
    assert!(vault
        .load(&origin)
        .unwrap()
        .pending_rotation_nonce
        .is_some());
    api.join().unwrap();
}
#[test]
fn hostile_approval_urls_and_oversize_responses_never_reach_the_browser() {
    for hostile in [
        "https://attacker.example/companion/authorize?request=",
        "http://127.0.0.1:1/companion/authorize?request=",
    ] {
        let hostile = hostile.to_string();
        let (origin, api) = server(1, move |_, _| {
            (201,json!({"request_id":"I".repeat(43),"authorization_url":format!("{hostile}{}","I".repeat(43)),"expires_at":Utc::now()+TimeDelta::minutes(5)}).to_string())
        });
        assert!(matches!(
            AuthorizationClient::new(&origin)
                .unwrap()
                .begin("PC", "2.0.0"),
            Err(Error::Invalid(_))
        ));
        api.join().unwrap();
    }
    let (origin, api) = server(1, |_, _| (201, "x".repeat(MAX_JSON as usize + 1)));
    assert!(matches!(
        AuthorizationClient::new(&origin)
            .unwrap()
            .begin("PC", "2.0.0"),
        Err(Error::Invalid(_))
    ));
    api.join().unwrap();
}
#[test]
fn corrupt_future_and_cross_origin_secret_envelopes_fail_without_rewriting() {
    let origin = "https://market.example";
    let value = saved(origin, 3600);
    let encoded = serde_json::to_vec(&value).unwrap();
    assert!(Session::decode(origin, &encoded).is_ok());
    assert!(Session::decode("https://other.example", &encoded).is_err());
    for (key, value) in [
        ("schema_version", json!(2)),
        ("access_token", json!("bad")),
        ("pending_rotation_nonce", json!("bad")),
        ("password", json!("must not exist")),
    ] {
        let mut body: Value = serde_json::from_slice(&encoded).unwrap();
        body[key] = value;
        assert!(Session::decode(origin, &serde_json::to_vec(&body).unwrap()).is_err());
    }
    assert!(Session::decode(origin, &vec![0; 4097]).is_err());
    assert_ne!(
        crate::vault::credential_target(origin).unwrap(),
        crate::vault::session_target(origin).unwrap()
    );
    assert_eq!(
        crate::vault::session_target(origin).unwrap(),
        crate::vault::session_target("https://market.example/").unwrap()
    );
}
#[cfg(windows)]
#[test]
fn real_windows_vault_round_trip_keeps_legacy_and_new_credentials_separate() {
    use crate::vault::{self, NativeCredentialStore};
    let server = format!("https://vault-{}.invalid", random_nonce().unwrap());
    let value = saved(&server, 3600);
    vault::save(&server, &"L".repeat(43)).unwrap();
    NativeCredentialStore.save(&server, &value).unwrap();
    assert_eq!(NativeCredentialStore.load(&server).unwrap().device_id(), 7);
    assert_eq!(vault::load(&server).unwrap(), "L".repeat(43));
    NativeCredentialStore.remove(&server).unwrap();
    assert!(NativeCredentialStore.load(&server).is_err());
    assert_eq!(vault::load(&server).unwrap(), "L".repeat(43));
    vault::remove(&server).unwrap();
}

#[test]
fn cancellation_during_code_exchange_revokes_the_new_grant_without_saving_it() {
    let cancel = Arc::new(AtomicBool::new(false));
    let mark = cancel.clone();
    let mut step = 0;
    let (origin, api) = server(2, move |req, origin| {
        step += 1;
        if step == 1 {
            assert_eq!(req.path, "/api/v1/companion/token");
            mark.store(true, Ordering::Release);
            (200, tokens(origin))
        } else {
            assert_eq!(req.path, "/api/v1/companion/devices/self/revoke");
            (204, String::new())
        }
    });
    let callback = Callback::bind().unwrap();
    let proof = Proof::new().unwrap();
    let port = callback.listener.local_addr().unwrap();
    let authority = callback.authority.clone();
    let state = proof.state.clone();
    let browser = thread::spawn(move || {
        let mut socket = TcpStream::connect(port).unwrap();
        socket
            .write_all(&request(
                &authority,
                &format!("code={}&state={state}", "C".repeat(43)),
            ))
            .unwrap();
        let mut out = String::new();
        socket.read_to_string(&mut out).unwrap();
    });
    let client = AuthorizationClient::new(&origin).unwrap();
    let pending = PendingApproval {
        issuer: server_url(&origin).unwrap(),
        callback,
        proof,
        until: Instant::now() + Duration::from_secs(3),
        info: ApprovalInfo {
            request_id: "I".repeat(43),
            authorization_url: format!("{origin}/companion/authorize?request={}", "I".repeat(43)),
            expires_at: Utc::now() + TimeDelta::minutes(5),
        },
    };
    let vault = MemoryVault::default();
    assert!(matches!(
        client.complete(pending, &cancel, &vault),
        Err(Error::Cancelled)
    ));
    assert!(vault.load(&origin).is_err());
    api.join().unwrap();
    browser.join().unwrap();
}
#[test]
fn renewal_rejects_wrong_issuer_scope_lifetime_or_device_without_replacing_credentials() {
    for (key, value) in [
        ("issuer", json!("https://attacker.example")),
        ("scope", json!("admin")),
        ("expires_in", json!(86400)),
        (
            "device",
            json!({"id":999,"name":"Other PC","platform":"Windows","app_version":"2.0.0"}),
        ),
    ] {
        let (origin, api) = server(1, move |_, origin| {
            let mut body: Value = serde_json::from_str(&tokens(origin)).unwrap();
            body[key] = value.clone();
            (200, body.to_string())
        });
        let vault = MemoryVault::default();
        vault.save(&origin, &saved(&origin, -1)).unwrap();
        assert!(matches!(
            AuthorizationClient::new(&origin)
                .unwrap()
                .session(&vault, Utc::now()),
            Err(Error::Invalid(_))
        ));
        let old = vault.load(&origin).unwrap();
        assert_eq!(old.refresh_token, "P".repeat(43));
        assert!(old.pending_rotation_nonce.is_some());
        api.join().unwrap();
    }
}
#[test]
fn approval_proofs_cannot_be_exchanged_through_a_different_issuer() {
    let callback = Callback::bind().unwrap();
    let pending = PendingApproval {
        issuer: server_url("https://market.example").unwrap(),
        callback,
        proof: Proof::new().unwrap(),
        until: Instant::now() + Duration::from_secs(300),
        info: ApprovalInfo {
            request_id: "I".repeat(43),
            authorization_url: "https://market.example/companion/authorize".into(),
            expires_at: Utc::now() + TimeDelta::minutes(5),
        },
    };
    let before = Instant::now();
    assert!(matches!(
        AuthorizationClient::new("http://127.0.0.1:1")
            .unwrap()
            .complete(pending, &AtomicBool::new(false), &MemoryVault::default()),
        Err(Error::Invalid(_))
    ));
    assert!(before.elapsed() < Duration::from_secs(1));
}
