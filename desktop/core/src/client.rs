use crate::{
    protocol::{Page, MAX_PAGE_BYTES},
    Error, Result,
};
use reqwest::blocking::Client;
use std::io::Read;
use std::time::Duration;
use url::Url;

pub fn server_url(value: &str) -> Result<Url> {
    let mut url = Url::parse(value).map_err(|_| Error::Invalid("server URL"))?;
    if !url.username().is_empty()
        || url.password().is_some()
        || url.query().is_some()
        || url.fragment().is_some()
        || !matches!(url.path(), "" | "/")
        || url.host_str().is_none()
    {
        return Err(Error::Invalid(
            "use a server origin without credentials, path, query or fragment",
        ));
    }
    let loopback = matches!(
        url.host_str(),
        Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
    );
    if url.scheme() != "https" && !(url.scheme() == "http" && loopback) {
        return Err(Error::Invalid(
            "HTTPS required except for loopback development",
        ));
    }
    url.set_path("/");
    Ok(url)
}

pub struct MarketClient {
    server: Url,
    token: String,
    http: Client,
}

impl MarketClient {
    pub fn new(server: &str, token: String) -> Result<Self> {
        if token.len() < 20
            || token.len() > 256
            || !token
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        {
            return Err(Error::Invalid("device token format"));
        }
        let http = Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .no_proxy()
            .connect_timeout(Duration::from_secs(10))
            .timeout(Duration::from_secs(60))
            .build()
            .map_err(|_| Error::Network)?;
        Ok(Self {
            server: server_url(server)?,
            token,
            http,
        })
    }
    fn get(&self, path: &str, cursor: Option<&str>) -> Result<Vec<u8>> {
        let mut url = self
            .server
            .join(path)
            .map_err(|_| Error::Invalid("endpoint"))?;
        if let Some(cursor) = cursor {
            url.query_pairs_mut().append_pair("cursor", cursor);
        }
        let response = self
            .http
            .get(url)
            .bearer_auth(&self.token)
            .send()
            .map_err(|_| Error::Network)?;
        match response.status().as_u16() {
            401 | 403 => return Err(Error::Authentication),
            409 => return Err(Error::ResetRequired),
            200 => {}
            _ => return Err(Error::Network),
        }
        let mut bytes = Vec::new();
        response
            .take(MAX_PAGE_BYTES + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| Error::Network)?;
        if bytes.len() as u64 > MAX_PAGE_BYTES {
            return Err(Error::Invalid("response exceeds 2 MiB"));
        }
        Ok(bytes)
    }
    pub fn authenticate(&self) -> Result<()> {
        let response: serde_json::Value =
            serde_json::from_slice(&self.get("api/v1/auth/me", None)?)?;
        if response.get("active").and_then(|v| v.as_bool()) != Some(true)
            || response.get("username").and_then(|v| v.as_str()).is_none()
        {
            return Err(Error::Authentication);
        }
        Ok(())
    }
    pub fn page(&self, market: u32, cursor: Option<&str>) -> Result<Page> {
        let page: Page =
            serde_json::from_slice(&self.get(&format!("api/v1/sync/markets/{market}"), cursor)?)?;
        page.validate(market)?;
        Ok(page)
    }
}
