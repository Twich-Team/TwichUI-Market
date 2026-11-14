//! Browser-based native authorization. Secrets never implement Debug and must never cross IPC.
//! The callback owns its port before opening the system browser. Refresh intent is saved
//! to the secure store BEFORE sending a rotating request so an interrupted response is retryable.
use crate::{
    client::{server_url, MarketClient},
    Error, Result,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine};
use chrono::{DateTime, Duration as TimeDelta, Utc};
use reqwest::blocking::{Client, Response};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use socket2::{Domain, Protocol, Socket, Type};
use std::{
    io::{Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream},
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, Instant},
};
use subtle::ConstantTimeEq;
use url::Url;
use zeroize::Zeroize;

const CLIENT_ID: &str = "twichui-market-companion";
const CALLBACK_PATH: &str = "/companion/callback";
const SCOPE: &str = "market:read sync:read device:self";
const MAX_JSON: u64 = 64 * 1024;

fn opaque(value: &str) -> bool {
    value.len() == 43
        && value
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
}
pub fn random_nonce() -> Result<String> {
    let mut bytes = [0u8; 32];
    getrandom::getrandom(&mut bytes)
        .map_err(|_| Error::Invalid("secure random source unavailable"))?;
    let value = URL_SAFE_NO_PAD.encode(bytes);
    bytes.zeroize();
    Ok(value)
}

struct Proof {
    state: String,
    verifier: String,
}
impl Proof {
    fn new() -> Result<Self> {
        Ok(Self {
            state: random_nonce()?,
            verifier: random_nonce()?,
        })
    }
    fn challenge(&self) -> String {
        URL_SAFE_NO_PAD.encode(Sha256::digest(self.verifier.as_bytes()))
    }
}
impl Drop for Proof {
    fn drop(&mut self) {
        self.verifier.zeroize();
        self.state.zeroize();
    }
}

/// This socket is never reused, shared, or bound on a public interface.
struct Callback {
    listener: TcpListener,
    authority: String,
}
impl Callback {
    fn bind() -> Result<Self> {
        let socket = Socket::new(Domain::IPV4, Type::STREAM, Some(Protocol::TCP))?;
        socket.set_reuse_address(false)?;
        #[cfg(windows)]
        {
            use std::os::windows::io::AsRawSocket;
            use windows_sys::Win32::Networking::WinSock::{
                setsockopt, SOL_SOCKET, SO_EXCLUSIVEADDRUSE,
            };
            let enabled: i32 = 1;
            // Set before bind: Windows otherwise permits a second SO_REUSEADDR listener.
            if unsafe {
                setsockopt(
                    socket.as_raw_socket() as usize,
                    SOL_SOCKET,
                    SO_EXCLUSIVEADDRUSE,
                    (&enabled as *const i32).cast(),
                    std::mem::size_of::<i32>() as i32,
                )
            } != 0
            {
                return Err(Error::Io(std::io::Error::last_os_error()));
            }
        }
        socket.bind(&SocketAddr::from((Ipv4Addr::LOCALHOST, 0)).into())?;
        socket.listen(8)?;
        let listener: TcpListener = socket.into();
        listener.set_nonblocking(true)?;
        let authority = format!("127.0.0.1:{}", listener.local_addr()?.port());
        Ok(Self {
            listener,
            authority,
        })
    }
    fn uri(&self) -> String {
        format!("http://{}{CALLBACK_PATH}", self.authority)
    }
    fn wait(&self, state: &str, until: Instant, cancel: &AtomicBool) -> Result<String> {
        while Instant::now() < until {
            if cancel.load(Ordering::Acquire) {
                return Err(Error::Cancelled);
            }
            match self.listener.accept() {
                Ok((mut stream, peer)) if peer.ip() == Ipv4Addr::LOCALHOST => {
                    let result = read_callback(&mut stream, &self.authority, state, until, cancel);
                    let (status, message) = match &result {
                        Ok(_) => ("200 OK", "Connection approved. Return to TwichUI Market Companion."),
                        Err(Error::AuthorizationDenied) => ("200 OK", "Connection declined. You can close this page."),
                        _ => ("400 Bad Request", "This request could not be accepted. Return to the companion to continue."),
                    };
                    // Static text only: never echo query values, account details, codes or tokens.
                    let _ = stream.write_all(format!("HTTP/1.1 {status}\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: {}\r\nCache-Control: no-store\r\nReferrer-Policy: no-referrer\r\nContent-Security-Policy: default-src 'none'; frame-ancestors 'none'\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n{message}", message.len()).as_bytes());
                    match result {
                        Ok(code) => return Ok(code),
                        Err(Error::AuthorizationDenied) => return Err(Error::AuthorizationDenied),
                        Err(Error::Cancelled) => return Err(Error::Cancelled),
                        _ => {} // A stray/bogus request cannot consume the real browser callback.
                    }
                }
                Ok(_) => {}
                Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                    std::thread::sleep(Duration::from_millis(50))
                }
                Err(_) => return Err(Error::Network),
            }
        }
        Err(Error::AuthorizationExpired)
    }
}

fn read_callback(
    stream: &mut TcpStream,
    authority: &str,
    state: &str,
    until: Instant,
    cancel: &AtomicBool,
) -> Result<String> {
    stream.set_read_timeout(Some(Duration::from_millis(100)))?;
    stream.set_write_timeout(Some(Duration::from_millis(250)))?;
    let deadline = until.min(Instant::now() + Duration::from_secs(2));
    let mut bytes = Vec::new();
    while bytes.len() <= 8192 && Instant::now() < deadline {
        if cancel.load(Ordering::Acquire) {
            return Err(Error::Cancelled);
        }
        let mut block = [0u8; 1024];
        match stream.read(&mut block) {
            Ok(0) => break,
            Ok(count) => {
                bytes.extend_from_slice(&block[..count]);
                if bytes.windows(4).any(|s| s == b"\r\n\r\n") {
                    break;
                }
            }
            Err(error)
                if matches!(
                    error.kind(),
                    std::io::ErrorKind::WouldBlock | std::io::ErrorKind::TimedOut
                ) => {}
            Err(_) => return Err(Error::Invalid("callback request")),
        }
    }
    parse_callback(&bytes, authority, state)
}

fn parse_callback(bytes: &[u8], authority: &str, state: &str) -> Result<String> {
    let bad = || Error::Invalid("callback request");
    if bytes.len() > 8192 || !bytes.ends_with(b"\r\n\r\n") || !bytes.is_ascii() {
        return Err(bad());
    }
    let request = std::str::from_utf8(bytes).map_err(|_| bad())?;
    let mut lines = request.split("\r\n");
    let first = lines.next().ok_or_else(bad)?.split(' ').collect::<Vec<_>>();
    if first.len() != 3 || first[0] != "GET" || first[2] != "HTTP/1.1" {
        return Err(bad());
    }
    let target = first[1];
    if !target.starts_with(&format!("{CALLBACK_PATH}?")) || target.contains('#') {
        return Err(bad());
    }
    let headers = lines
        .take_while(|line| !line.is_empty())
        .collect::<Vec<_>>();
    let mut host = None;
    for header in headers {
        let (name, value) = header.split_once(':').ok_or_else(bad)?;
        if name.eq_ignore_ascii_case("host") {
            if host.replace(value.trim()).is_some() {
                return Err(bad());
            }
        }
        if name.eq_ignore_ascii_case("content-length")
            || name.eq_ignore_ascii_case("transfer-encoding")
            || name.eq_ignore_ascii_case("origin")
        {
            return Err(bad());
        }
    }
    if host != Some(authority) {
        return Err(bad());
    }
    let parsed = Url::parse(&format!("http://{authority}{target}")).map_err(|_| bad())?;
    let fields = parsed.query_pairs().collect::<Vec<_>>();
    if fields.len() != 2 {
        return Err(bad());
    }
    let states = fields
        .iter()
        .filter(|(key, _)| key == "state")
        .collect::<Vec<_>>();
    if states.len() != 1 || !bool::from(states[0].1.as_bytes().ct_eq(state.as_bytes())) {
        return Err(bad());
    }
    let value = fields
        .iter()
        .find(|(key, _)| key != "state")
        .ok_or_else(bad)?;
    match value.0.as_ref() {
        "code" if opaque(&value.1) => Ok(value.1.to_string()),
        "error" if value.1 == "access_denied" => Err(Error::AuthorizationDenied),
        _ => Err(bad()),
    }
}

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct BeginReply {
    request_id: String,
    authorization_url: String,
    expires_at: DateTime<Utc>,
}
#[derive(Clone, Serialize)]
pub struct ApprovalInfo {
    pub request_id: String,
    pub authorization_url: String,
    pub expires_at: DateTime<Utc>,
}
/// Keep in Rust memory only. Its proof and callback are intentionally not serializable.
pub struct PendingApproval {
    issuer: Url,
    callback: Callback,
    proof: Proof,
    until: Instant,
    info: ApprovalInfo,
}
impl PendingApproval {
    pub fn info(&self) -> ApprovalInfo {
        self.info.clone()
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct TokenDevice {
    id: u32,
    name: String,
    platform: String,
    app_version: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct TokenReply {
    issuer: String,
    access_token: String,
    token_type: String,
    expires_in: u32,
    refresh_token: String,
    refresh_expires_at: DateTime<Utc>,
    authorization_expires_at: DateTime<Utc>,
    scope: String,
    device: TokenDevice,
}
impl Drop for TokenReply {
    fn drop(&mut self) {
        self.access_token.zeroize();
        self.refresh_token.zeroize();
    }
}

/// Versioned secret envelope: Credential Manager ONLY, never an IPC response or settings file.
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Session {
    schema_version: u8,
    issuer: String,
    access_token: String,
    refresh_token: String,
    access_expires_at: DateTime<Utc>,
    refresh_expires_at: DateTime<Utc>,
    authorization_expires_at: DateTime<Utc>,
    pending_rotation_nonce: Option<String>,
    device: TokenDevice,
}
impl Drop for Session {
    fn drop(&mut self) {
        self.access_token.zeroize();
        self.refresh_token.zeroize();
        if let Some(nonce) = self.pending_rotation_nonce.as_mut() {
            nonce.zeroize();
        }
    }
}
impl Session {
    pub fn device_id(&self) -> u32 {
        self.device.id
    }
    pub fn device_name(&self) -> &str {
        &self.device.name
    }
    pub fn access_expires_at(&self) -> DateTime<Utc> {
        self.access_expires_at
    }
    pub fn client(&self) -> Result<MarketClient> {
        MarketClient::new(&self.issuer, self.access_token.clone())
    }
    pub(crate) fn decode(server: &str, bytes: &[u8]) -> Result<Self> {
        if bytes.len() > 4096 {
            return Err(Error::Vault);
        }
        let value: Self = serde_json::from_slice(bytes).map_err(|_| Error::Vault)?;
        value.validate(server)?;
        Ok(value)
    }
    fn validate(&self, server: &str) -> Result<()> {
        if self.schema_version != 1
            || self.issuer != server_url(server)?.as_str()
            || !opaque(&self.access_token)
            || !opaque(&self.refresh_token)
            || self
                .pending_rotation_nonce
                .as_ref()
                .is_some_and(|v| !opaque(v))
            || self.device.id == 0
            || self.device.platform != "Windows"
            || self.device.name.len() > 320
            || self.access_expires_at > self.authorization_expires_at
            || self.refresh_expires_at > self.authorization_expires_at
        {
            return Err(Error::Vault);
        }
        Ok(())
    }
}

pub trait CredentialStore {
    fn load(&self, server: &str) -> Result<Session>;
    /// Must replace a complete envelope atomically. No plaintext fallbacks.
    fn save(&self, server: &str, session: &Session) -> Result<()>;
    fn remove(&self, server: &str) -> Result<()>;
}

pub struct AuthorizationClient {
    server: Url,
    http: Client,
}
impl AuthorizationClient {
    pub fn new(server: &str) -> Result<Self> {
        Ok(Self {
            server: server_url(server)?,
            http: Client::builder()
                .redirect(reqwest::redirect::Policy::none())
                .no_proxy()
                .connect_timeout(Duration::from_secs(10))
                .timeout(Duration::from_secs(20))
                .build()
                .map_err(|_| Error::Network)?,
        })
    }
    pub fn begin(&self, device_name: &str, version: &str) -> Result<PendingApproval> {
        let callback = Callback::bind()?;
        let proof = Proof::new()?;
        let started = Instant::now();
        let reply: BeginReply = response_json(self.http.post(self.server.join("api/v1/companion/authorizations").map_err(|_| Error::Invalid("endpoint"))?)
            .json(&serde_json::json!({"client_id":CLIENT_ID,"redirect_uri":callback.uri(),"state":proof.state,
                "code_challenge":proof.challenge(),"code_challenge_method":"S256","device_name":device_name,"platform":"Windows","app_version":version}))
            .send().map_err(|_| Error::Network)?)?;
        let auth_url =
            Url::parse(&reply.authorization_url).map_err(|_| Error::Invalid("approval URL"))?;
        let expected = self
            .server
            .join("companion/authorize")
            .map_err(|_| Error::Invalid("endpoint"))?;
        let pairs = auth_url.query_pairs().collect::<Vec<_>>();
        if !opaque(&reply.request_id)
            || auth_url.origin() != expected.origin()
            || auth_url.path() != expected.path()
            || auth_url.username() != ""
            || auth_url.password().is_some()
            || auth_url.fragment().is_some()
            || pairs.len() != 1
            || pairs[0].0 != "request"
            || pairs[0].1 != reply.request_id
            || reply.expires_at <= Utc::now()
            || reply.expires_at > Utc::now() + TimeDelta::minutes(6)
        {
            return Err(Error::Invalid("approval response"));
        }
        let seconds = (reply.expires_at - Utc::now()).num_seconds().clamp(0, 300) as u64;
        Ok(PendingApproval {
            issuer: self.server.clone(),
            callback,
            proof,
            until: started + Duration::from_secs(seconds),
            info: ApprovalInfo {
                request_id: reply.request_id,
                authorization_url: reply.authorization_url,
                expires_at: reply.expires_at,
            },
        })
    }
    pub fn complete(
        &self,
        pending: PendingApproval,
        cancel: &AtomicBool,
        store: &impl CredentialStore,
    ) -> Result<Session> {
        if pending.issuer != self.server {
            return Err(Error::Invalid("approval belongs to another server"));
        }
        if cancel.load(Ordering::Acquire) {
            return Err(Error::Cancelled);
        }
        let mut code = pending
            .callback
            .wait(&pending.proof.state, pending.until, cancel)?;
        if cancel.load(Ordering::Acquire) {
            code.zeroize();
            return Err(Error::Cancelled);
        }
        let result = self.exchange(&[
            ("grant_type", "authorization_code"),
            ("client_id", CLIENT_ID),
            ("code", &code),
            ("redirect_uri", &pending.callback.uri()),
            ("state", &pending.proof.state),
            ("code_verifier", &pending.proof.verifier),
        ]);
        code.zeroize();
        let session = result?;
        if cancel.load(Ordering::Acquire) {
            let _ = self.revoke(&session);
            return Err(Error::Cancelled);
        }
        store.save(self.server.as_str(), &session)?;
        Ok(session)
    }
    /// Revoke only this native authorization; caller retains offline cache and decides
    /// whether to remove its local vault entry after showing any network failure.
    pub fn revoke(&self, session: &Session) -> Result<()> {
        session.validate(self.server.as_str())?;
        let response = self
            .http
            .post(
                self.server
                    .join("api/v1/companion/devices/self/revoke")
                    .map_err(|_| Error::Invalid("endpoint"))?,
            )
            .bearer_auth(&session.access_token)
            .send()
            .map_err(|_| Error::Network)?;
        match response.status().as_u16() {
            204 | 401 => Ok(()),
            404 | 502 | 503 => Err(Error::ServiceUnavailable),
            _ => Err(Error::Network),
        }
    }
    fn exchange(&self, fields: &[(&str, &str)]) -> Result<Session> {
        let started = Utc::now();
        let reply: TokenReply = response_json(
            self.http
                .post(
                    self.server
                        .join("api/v1/companion/token")
                        .map_err(|_| Error::Invalid("endpoint"))?,
                )
                .form(fields)
                .send()
                .map_err(|_| Error::Network)?,
        )?;
        if server_url(&reply.issuer)? != self.server
            || reply.token_type != "Bearer"
            || reply.scope != SCOPE
            || reply.expires_in == 0
            || reply.expires_in > 3600
            || reply.refresh_expires_at <= started
            || reply.authorization_expires_at > started + TimeDelta::days(91)
            || reply.authorization_expires_at <= started
        {
            return Err(Error::Invalid("authorization response"));
        }
        let session = Session {
            schema_version: 1,
            issuer: self.server.to_string(),
            access_token: reply.access_token.clone(),
            refresh_token: reply.refresh_token.clone(),
            access_expires_at: started + TimeDelta::seconds(reply.expires_in.into()),
            refresh_expires_at: reply.refresh_expires_at,
            authorization_expires_at: reply.authorization_expires_at,
            pending_rotation_nonce: None,
            device: TokenDevice {
                id: reply.device.id,
                name: reply.device.name.clone(),
                platform: reply.device.platform.clone(),
                app_version: reply.device.app_version.clone(),
            },
        };
        session.validate(self.server.as_str())?;
        Ok(session)
    }
    /// A single native worker owns renewal. An error NEVER removes the stored session/cache.
    pub fn session(&self, store: &impl CredentialStore, now: DateTime<Utc>) -> Result<Session> {
        let mut session = store.load(self.server.as_str())?;
        session.validate(self.server.as_str())?;
        if session.authorization_expires_at <= now || session.refresh_expires_at <= now {
            return Err(Error::Authentication);
        }
        if session.pending_rotation_nonce.is_none()
            && session.access_expires_at > now + TimeDelta::seconds(120)
        {
            return Ok(session);
        }
        if session.pending_rotation_nonce.is_none() {
            session.pending_rotation_nonce = Some(random_nonce()?);
            store.save(self.server.as_str(), &session)?;
        }
        let renewed = self.exchange(&[
            ("grant_type", "refresh_token"),
            ("client_id", CLIENT_ID),
            ("refresh_token", &session.refresh_token),
            (
                "rotation_nonce",
                session
                    .pending_rotation_nonce
                    .as_deref()
                    .ok_or(Error::Vault)?,
            ),
        ])?;
        if renewed.device.id != session.device.id {
            return Err(Error::Invalid("renewed device identity"));
        }
        store.save(self.server.as_str(), &renewed)?;
        Ok(renewed)
    }
}
fn response_json<T: serde::de::DeserializeOwned>(response: Response) -> Result<T> {
    match response.status().as_u16() {
        200 | 201 => {}
        400 | 401 | 403 => return Err(Error::Authentication),
        404 | 502 | 503 => return Err(Error::ServiceUnavailable),
        429 => {
            return Err(Error::RateLimited(
                response
                    .headers()
                    .get("retry-after")
                    .and_then(|v| v.to_str().ok())
                    .and_then(|v| v.parse().ok())
                    .unwrap_or(60)
                    .clamp(1, 3600),
            ))
        }
        _ => return Err(Error::Network),
    }
    let mut bytes = Vec::new();
    response
        .take(MAX_JSON + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| Error::Network)?;
    let parsed = if bytes.len() as u64 > MAX_JSON {
        Err(Error::Invalid("authorization response exceeds limit"))
    } else {
        serde_json::from_slice(&bytes).map_err(|_| Error::Invalid("authorization response"))
    };
    bytes.zeroize();
    parsed
}

#[cfg(test)]
#[path = "authorization_tests.rs"]
mod tests;
