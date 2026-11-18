use crate::{
    protocol::{Page, MAX_PAGE_BYTES},
    Error, Result,
};
use reqwest::blocking::Client;
use std::io::Read;
use std::time::Duration;
use url::Url;
use zeroize::Zeroize;

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
    page_limit: Option<u32>,
}
impl Drop for MarketClient {
    fn drop(&mut self) {
        self.token.zeroize();
    }
}

impl MarketClient {
    /// Fixed same-origin summary routes only. No redirects, provider URLs or
    /// credentials in payloads. A 304 is meaningful only with a validated cache.
    pub(crate) fn summary_request(&self, path: &str, etag: Option<&str>, maximum: usize) -> Result<Option<Vec<u8>>> {
        if !path.starts_with("api/v1/workshop/markets/") || path.contains(['?', '#']) {
            return Err(Error::Invalid("Workshop summary endpoint"));
        }
        let url=self.server.join(path).map_err(|_|Error::Invalid("summary endpoint"))?;
        let mut request=self.http.get(url).bearer_auth(&self.token);
        if let Some(id)=etag { request=request.header("If-None-Match",format!("\"{id}\"")); }
        let response=request.send().map_err(|_|Error::Network)?;
        match response.status().as_u16() {
            304 if etag.is_some()=>return Ok(None),
            401|403=>return Err(Error::Authentication),
            202=>return Err(Error::SummaryPreparing(response.headers().get("retry-after").and_then(|s|s.to_str().ok()).and_then(|s|s.parse::<u64>().ok()).unwrap_or(5).clamp(1,3600))),
            429=>return Err(Error::RateLimited(response.headers().get("retry-after").and_then(|s|s.to_str().ok()).and_then(|s|s.parse::<u64>().ok()).unwrap_or(30).clamp(1,3600))),
            409|410=>return Err(Error::ServiceUnavailable),
            404|502|503=>return Err(Error::ServiceUnavailable),
            200=>{},_=>return Err(Error::Network),
        }
        if response.content_length().is_some_and(|n|n>maximum as u64) {return Err(Error::Invalid("summary response size"));}
        let mut bytes=Vec::new();response.take(maximum as u64+1).read_to_end(&mut bytes).map_err(|_|Error::Network)?;
        if bytes.len()>maximum {return Err(Error::Invalid("summary response size"));}
        Ok(Some(bytes))
    }
    pub fn synchronize_page(&self, cache: &mut crate::cache::Cache, market: u32) -> Result<bool> {
        let server = self.server.as_str();
        let mut cursor = cache.cursor(server, market)?;
        let page = match self.page(market, cursor.as_deref()) {
            Err(Error::ResetRequired) if cursor.is_some() => {
                // Reset only pending download state; the completed offline generation remains intact.
                cache.reset(server, market)?;
                cursor = None;
                self.page(market, None)?
            }
            result => result?,
        };
        cache.apply(server, market, cursor.as_deref(), &page)?;
        Ok(page.has_more)
    }
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
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|_| Error::Network)?;
        Ok(Self {
            server: server_url(server)?,
            token,
            http,
            page_limit: None,
        })
    }
    /// Measurement/compatibility seam; the default still uses the existing server page size.
    pub fn with_page_limit(mut self, limit:u32)->Result<Self> {
        if !(1..=100).contains(&limit) {return Err(Error::Invalid("sync page limit"))}
        self.page_limit=Some(limit);Ok(self)
    }
    fn get(&self, path: &str, cursor: Option<&str>) -> Result<Vec<u8>> {
        let mut url = self
            .server
            .join(path)
            .map_err(|_| Error::Invalid("endpoint"))?;
        if let Some(cursor) = cursor {
            url.query_pairs_mut().append_pair("cursor", cursor);
        }
        if path.starts_with("api/v1/sync/markets/") {
            if let Some(limit)=self.page_limit {url.query_pairs_mut().append_pair("limit",&limit.to_string());}
        }
        let headers=crate::performance::measure(crate::performance::Stage::NetworkHeaders);
        crate::performance::add(crate::performance::Counter::HttpRequests,1);
        let response = self
            .http
            .get(url)
            .bearer_auth(&self.token)
            .send()
            .map_err(|_| Error::Network)?;
        drop(headers);
        match response.status().as_u16() {
            401 | 403 => return Err(Error::Authentication),
            409 => return Err(Error::ResetRequired),
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
            404 | 502 | 503 => return Err(Error::ServiceUnavailable),
            200 => {}
            _ => return Err(Error::Network),
        }
        let transfer=crate::performance::measure(crate::performance::Stage::NetworkTransfer);
        let mut bytes = Vec::new();
        response
            .take(MAX_PAGE_BYTES + 1)
            .read_to_end(&mut bytes)
            .map_err(|_| Error::Network)?;
        drop(transfer);crate::performance::add(crate::performance::Counter::ResponseBodyBytes,bytes.len() as u64);
        if bytes.len() as u64 > MAX_PAGE_BYTES {
            return Err(Error::Invalid("response exceeds 2 MiB"));
        }
        Ok(bytes)
    }
    fn update_authority(&self) -> Result<()> {
        if self.server.as_str() != format!("{}/", crate::update::ORIGIN) {
            return Err(Error::Invalid(
                "updates require the trusted Market connection",
            ));
        }
        Ok(())
    }
    pub fn update_metadata(
        &self,
        installed: &str,
    ) -> Result<Option<(crate::update::Package, serde_json::Value)>> {
        self.update_authority()?;
        crate::update::private_metadata(&self.http, &self.token, installed)
    }
    pub fn download_update(&self, package: &crate::update::Package) -> Result<Vec<u8>> {
        self.update_authority()?;
        package.download_authenticated(&self.http, &self.token)
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
        let bytes=self.get(&format!("api/v1/sync/markets/{market}"),cursor)?;
        let parse=crate::performance::measure(crate::performance::Stage::JsonParse);
        let page:Page=serde_json::from_slice(&bytes)?;drop(parse);
        let validation=crate::performance::measure(crate::performance::Stage::Validation);
        page.validate(market)?;drop(validation);
        crate::performance::add(crate::performance::Counter::Pages,1);
        crate::performance::add(crate::performance::Counter::ReceivedRecords,page.changes.len() as u64);
        for c in &page.changes {crate::performance::add(match c.operation {crate::protocol::Operation::Upsert=>crate::performance::Counter::Upserts,crate::protocol::Operation::Delete=>crate::performance::Counter::Deletes},1);}
        Ok(page)
    }
    pub fn bootstrap(&self) -> Result<crate::connection::Bootstrap> {
        let _stage=crate::performance::measure(crate::performance::Stage::Bootstrap);
        let value: crate::connection::Bootstrap =
            serde_json::from_slice(&self.get("api/v1/companion/bootstrap", None)?)?;
        value.validate()?;
        Ok(value)
    }
    pub fn provenance(
        &self,
        market: u32,
        watermark: &str,
    ) -> Result<crate::connection::Provenance> {
        let _stage=crate::performance::measure(crate::performance::Stage::Provenance);
        crate::connection::observation_id(watermark)?;
        let value: crate::connection::Provenance = serde_json::from_slice(&self.get(
            &format!("api/v1/companion/markets/{market}/observations/{watermark}"),
            None,
        )?)?;
        value.validate(market)?;
        if value.watermark_observation_id.as_deref() != Some(watermark) {
            return Err(Error::Invalid("source receipt watermark"));
        }
        Ok(value)
    }
    pub fn activity(&self, market: Option<u32>, version: &str) -> Result<()> {
        let _stage=crate::performance::measure(crate::performance::Stage::Activity);
        let headers=crate::performance::measure(crate::performance::Stage::NetworkHeaders);
        crate::performance::add(crate::performance::Counter::HttpRequests,1);
        let response = self
            .http
            .post(
                self.server
                    .join("api/v1/companion/activity")
                    .map_err(|_| Error::Invalid("endpoint"))?,
            )
            .bearer_auth(&self.token)
            .json(&serde_json::json!({"market_id":market,"app_version":version}))
            .send()
            .map_err(|_| Error::Network)?;
        drop(headers);
        match response.status().as_u16() {
            204 => Ok(()),
            401 | 403 => Err(Error::Authentication),
            404 | 502 | 503 => Err(Error::ServiceUnavailable),
            _ => Err(Error::Network),
        }
    }
}

#[cfg(test)]
mod update_authority_tests {
    use super::*;
    #[test]
    fn private_update_tokens_cannot_follow_a_custom_account_server() {
        for server in [
            "http://127.0.0.1:43123",
            "https://other.example",
            "https://market.twich.gg:8443",
        ] {
            let client =
                MarketClient::new(server, "synthetic-update-token-not-a-secret".into()).unwrap();
            assert!(matches!(
                client.update_metadata("2.0.0-beta.1"),
                Err(Error::Invalid(
                    "updates require the trusted Market connection"
                ))
            ));
        }
        let trusted = MarketClient::new(
            "https://MARKET.TWICH.GG:443",
            "synthetic-update-token-not-a-secret".into(),
        )
        .unwrap();
        trusted.update_authority().unwrap(); // No HTTP request or production credential.
    }
}

impl MarketClient {
    /// Reuses the same origin, no-redirect HTTP client and native credential. No scheduler calls this.
    pub fn download_bridge(&self, cache: &mut crate::bridge::BridgeCache, scope: &crate::bridge::Scope,
        cancelled: impl Fn()->bool) -> Result<()> {
        if self.server.as_str()!=scope.server {return Err(Error::Invalid("bridge origin scope"))}
        let(_,bootstrap_bytes)=self.bridge_request("/api/v1/companion/bootstrap",&[],262144)?;
        let bootstrap_value=crate::bridge::parse(&bootstrap_bytes,262144)?;
        let bootstrap:crate::connection::Bootstrap=serde_json::from_value(bootstrap_value.clone())?;
        bootstrap.validate()?;
        let expected=bootstrap_value["markets"].as_array().and_then(|a|a.iter().find(|m|m["id"]==scope.market_id)).ok_or(Error::Invalid("bridge selected market"))?;
        let identity_matches=|h:&serde_json::Value| h["market"]["region"]==expected["region"] && h["market"]["house_id"]==expected["house_id"] && h["market"]["transport_ruleset_id"]==expected["ruleset_id"] && h["market"]["source_kind"]==expected["source_kind"] && h["market"]["mapping_verified"]==expected["player_identity_verified"];
        if bootstrap.account.id!=scope.account_id || bootstrap.resolve_market(Some(scope.market_id)).map(|m|m.id)!=Some(scope.market_id) {
            return Err(Error::Authentication);
        }
        let mut resets=0;
        for _ in 0..10_000 {
            if cancelled(){return Err(Error::Cancelled)}
            if cache.pending(scope)?.is_none() {
                let mut ready=false;
                for _ in 0..17 {
                    if cancelled(){return Err(Error::Cancelled)}
                    let(status,bytes)=self.bridge_request(&format!("/api/v1/bridge/markets/{}/manifest",scope.market_id),&[("algorithm",&scope.algorithm)],70*1024)?;
                    if status==202 {
                        let value=crate::bridge::parse(&bytes,4096)?;
                        if value!=serde_json::json!({"state":"preparing","retry_after_seconds":1}) {return Err(Error::Invalid("bridge preparation response"))}
                        std::thread::sleep(Duration::from_secs(1));continue;
                    }
                    let manifest=crate::bridge::parse(&bytes,70*1024)?;
                    if !identity_matches(&manifest["manifest"]){return Err(Error::Invalid("bridge identity differs from selected authenticated market"))}
                    cache.start(scope,&bytes)?;ready=true;break;
                }
                if !ready{return Err(Error::ServiceUnavailable)}
            }
            let(header,cursor)=cache.pending(scope)?.ok_or(Error::Invalid("bridge staging"))?;
            if !identity_matches(&header){return Err(Error::Invalid("pending bridge identity no longer matches selected market"))}
            let generation=header["generation_id"].as_str().ok_or(Error::Invalid("bridge generation"))?;
            let response=self.bridge_request(&format!("/api/v1/bridge/markets/{}/records",scope.market_id),&[("cursor",&cursor),("generation",generation)],1024*1024);
            let(_,bytes)=match response {
                Err(Error::ResetRequired) if resets<1=>{cache.abandon_pending(scope)?;resets+=1;continue},
                value=>value?,
            };
            if cancelled(){return Err(Error::Cancelled)}
            if !cache.apply(scope,&cursor,&bytes,chrono::Utc::now())? {return Ok(())}
        }
        Err(Error::Invalid("bridge page limit"))
    }
    fn bridge_request(&self,path:&str,query:&[(&str,&str)],maximum:usize)->Result<(u16,Vec<u8>)> {
        let url=self.server.join(path).map_err(|_|Error::Invalid("bridge endpoint"))?;
        let response=self.http.get(url).query(query).bearer_auth(&self.token).send().map_err(|_|Error::Network)?;
        let status=response.status().as_u16();
        match status {200|202=>{},401|403=>return Err(Error::Authentication),409=>return Err(Error::ResetRequired),
            429=>return Err(Error::RateLimited(60)),404|502|503=>return Err(Error::ServiceUnavailable),_=>return Err(Error::Network)}
        let mut bytes=Vec::new();response.take(maximum as u64+1).read_to_end(&mut bytes).map_err(|_|Error::Network)?;
        if bytes.len()>maximum{return Err(Error::Invalid("bridge response size"))}Ok((status,bytes))
    }
}

impl MarketClient {
    /// Explicit manual archive synchronization. Independent of legacy background scheduling.
    pub fn download_archive(
        &self,
        store: &mut crate::archive::ArchiveStore,
        scope: &crate::bridge::Scope,
        cancelled: impl Fn() -> bool,
    ) -> Result<()> {
        if self.download_archive_pages(store, scope, cancelled, 1_100_000)? {
            Ok(())
        } else {
            Err(Error::Invalid("archive page safety bound"))
        }
    }
    /// Bounded stepping also provides a real interruption/resume seam for native tests.
    pub fn download_archive_pages(
        &self,
        store: &mut crate::archive::ArchiveStore,
        scope: &crate::bridge::Scope,
        cancelled: impl Fn() -> bool,
        max_pages: usize,
    ) -> Result<bool> {
        if self.server.as_str() != scope.server {
            return Err(Error::Invalid("archive origin scope"));
        }
        let (_, bytes) = self.bridge_request("/api/v1/companion/bootstrap", &[], 262144)?;
        let value = crate::bridge::parse(&bytes, 262144)?;
        let bootstrap: crate::connection::Bootstrap = serde_json::from_value(value.clone())?;
        bootstrap.validate()?;
        if bootstrap.account.id != scope.account_id
            || bootstrap
                .resolve_market(Some(scope.market_id))
                .map(|m| m.id)
                != Some(scope.market_id)
        {
            return Err(Error::Authentication);
        }
        let expected = value["markets"]
            .as_array()
            .and_then(|a| a.iter().find(|m| m["id"] == scope.market_id))
            .ok_or(Error::Invalid("archive selected market"))?;
        let matches = |h: &crate::archive::Header| {
            h.market["region"] == expected["region"]
                && h.market["house_id"] == expected["house_id"]
                && h.market["transport_ruleset_id"] == expected["ruleset_id"]
                && h.market["source_kind"] == expected["source_kind"]
                && h.market["mapping_verified"] == expected["player_identity_verified"]
        };
        let mut resets = 0;
        let mut full = false;
        for _ in 0..max_pages {
            if cancelled() {
                return Err(Error::Cancelled);
            }
            if store.pending(scope)?.is_none() {
                let active = store.active(scope)?;
                let mut ready = false;
                for _ in 0..4097 {
                    if cancelled() {
                        return Err(Error::Cancelled);
                    }
                    let mut query = vec![("algorithm", scope.algorithm.as_str()), ("protocol", "2")];
                    if !full {
                        if let Some(h) = &active {
                            query.push(("base", h.checkpoint_id.as_str()));
                        }
                    }
                    let response = self.bridge_request(
                        &format!("/api/v1/archive/markets/{}/checkpoint", scope.market_id),
                        &query,
                        131072,
                    );
                    let (status, bytes) = match response {
                        Err(Error::ResetRequired) if resets < 2 => {
                            full = true;
                            resets += 1;
                            continue;
                        }
                        other => other?,
                    };
                    if status == 202 {
                        if crate::bridge::parse(&bytes, 4096)?
                            != serde_json::json!({"state":"preparing","retry_after_seconds":1})
                        {
                            return Err(Error::Invalid("archive preparation response"));
                        }
                        std::thread::sleep(Duration::from_secs(1));
                        continue;
                    }
                    let e: crate::archive::Envelope =
                        serde_json::from_value(crate::bridge::parse(&bytes, 131072)?)?;
                    e.header.validate(scope)?;
                    if !matches(&e.header) {
                        return Err(Error::Invalid("archive differs from authenticated market"));
                    }
                    if active.as_ref().is_some_and(|h| {
                        h.watermark_observation_id == e.header.watermark_observation_id
                            && h.metadata_sha256 == e.header.metadata_sha256
                            && h.generated_at.get(..10) == e.header.generated_at.get(..10)
                            && h.issuer_id == e.header.issuer_id
                            && h.market == e.header.market
                    }) {
                        return Ok(true);
                    }
                    store.begin(scope, &bytes)?;
                    ready = true;
                    break;
                }
                if !ready {
                    return Err(Error::ServiceUnavailable);
                }
            }
            let (header, cursor) = store
                .pending(scope)?
                .ok_or(Error::Invalid("archive staging"))?;
            if !matches(&header) {
                return Err(Error::Invalid("pending archive market changed"));
            }
            let response = self.bridge_request(
                &format!("/api/v1/archive/markets/{}/pages", scope.market_id),
                &[("checkpoint", &header.checkpoint_id), ("cursor", &cursor)],
                1024 * 1024,
            );
            let (_, bytes) = match response {
                Err(Error::ResetRequired) if resets < 2 => {
                    store.abandon_pending(scope)?;
                    resets += 1;
                    continue;
                }
                other => other?,
            };
            if cancelled() {
                return Err(Error::Cancelled);
            }
            if !store.apply(scope, &cursor, &bytes)? {
                return Ok(true);
            }
        }
        Ok(false)
    }
}
