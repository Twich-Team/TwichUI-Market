//! Opt-in delivery on the existing native worker. No game IPC or reloads.
use crate::{
    archive::{self, ArchiveStore, DeliveryBudget},
    bridge::{self, Scope},
    client::MarketClient,
    Error, Result,
};
use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::{Read, Write},
    path::{Component, Path, PathBuf},
};

pub(crate) const TOC: &[u8] = b"## Interface: 16001\n## Title: TwichUI Market Data\n## Notes: Companion-generated market observations. No local scans or SavedVariables.\n## LoadOnDemand: 1\nData.lua\n";
const CAPABILITY: &str = "twichui-market-consumer";
pub const CONFIG: &str = "workshop-delivery-v1.json";
pub fn budget() -> DeliveryBudget {
    DeliveryBudget {
        records: 10,
        ..DeliveryBudget::default()
    }
}
fn need(ok: bool, why: &'static str) -> Result<()> {
    if ok {
        Ok(())
    } else {
        Err(Error::Invalid(why))
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Configuration {
    pub version: u32,
    pub enabled: bool,
    pub scope: Scope,
    pub installation: PathBuf,
    pub selection: Value,
    pub history_days: u32,
}
impl Configuration {
    pub fn validate(&self) -> Result<()> {
        if self.version == 2 {
            self.scope.key()?;
            let fields=self.selection.as_object();
            let previous=self.selection.get("previous_installation");
            return need(self.history_days == 0 && self.scope.algorithm == "twichui-pricing-v1"
                && self.installation.is_absolute() && fields.is_some_and(|m|(3..=5).contains(&m.len())&&m.keys().all(|k|["kind","market_id","region","previous_installation","previous_scope"].contains(&k.as_str())))
                && previous.is_none_or(|v|v.as_str().is_some_and(|p|Path::new(p).is_absolute()&&!Path::new(p).components().any(|c|matches!(c,Component::ParentDir|Component::CurDir))))
                && self.selection.get("previous_scope").is_none_or(|v|v.as_str().is_some_and(|s|s.len()==64&&s.bytes().all(|b|b.is_ascii_digit()||(b'a'..=b'f').contains(&b))))
                && self.selection["kind"] == "broad_summary" && self.selection["market_id"] == self.scope.market_id
                && self.selection["region"].as_str().is_some_and(|r|["us","eu","kr","tw"].contains(&r)),
                "automatic Workshop summary configuration");
        }
        need(
            self.version == 1 && (1..=60).contains(&self.history_days),
            "delivery configuration version/window",
        )?;
        self.scope.key()?;
        let r = archive::normalize_selection(self.selection.clone())?;
        need(
            r == self.selection
                && r["variants"]
                    .as_array()
                    .is_some_and(|v| !v.is_empty() && v.len() <= 10)
                && r["market"]["server_market_id"] == self.scope.market_id
                && r["pricing_algorithm"] == self.scope.algorithm,
            "delivery exact selection/account market",
        )?;
        need(
            self.installation.is_absolute(),
            "choose an absolute WoW Forever installation",
        )
    }
    pub fn load(base: &Path) -> Result<Option<Self>> {
        let path = base.join(CONFIG);
        if !path.try_exists()? {
            return Ok(None);
        }
        let value: Self = serde_json::from_slice(&read(&path, 16384)?)?;
        value.validate()?;
        Ok(Some(value))
    }
    /// Call only after the player has reviewed the returned exact destination.
    pub fn save_confirmed(&self, base: &Path, confirmed: bool) -> Result<()> {
        self.validate()?;
        need(
            !self.enabled || confirmed,
            "confirm the addon destination before enabling delivery",
        )?;
        if self.enabled {
            inspect_destination(self)?;
        }
        if self.version==2 {
            let old=base.join(CONFIG);let backup=base.join("workshop-delivery-v1.previous.json");
            if old.try_exists()?&&!backup.try_exists()? {
                let raw=read(&old,16384)?;
                if crate::bridge::parse(&raw,16384)?["version"]==1 {atomic(&backup,&raw)?;}
            }
        }
        atomic(&base.join(CONFIG), &serde_json::to_vec_pretty(self)?)
    }
    /// One installation grant follows the already authenticated market choice.
    /// Ownership stays account/origin-bound; payloads/caches stay market-bound.
    pub fn follow_selected_market(&self,base:&Path,market:u32,region:&str)->Result<Self> {
        self.validate()?;need(self.version==2&&self.enabled,"connect automatic Workshop delivery first")?;
        let saved=Self::load(base)?.ok_or(Error::Cancelled)?;
        need(saved.version==2&&saved.enabled&&saved.scope==self.scope&&saved.installation==self.installation&&saved.selection==self.selection,"Workshop connection changed")?;
        let mut next=self.clone();next.scope.market_id=market;next.selection["market_id"]=market.into();next.selection["region"]=region.into();
        next.validate()?;inspect_destination(&next)?;
        atomic(&base.join(CONFIG),&serde_json::to_vec_pretty(&next)?)?;Ok(next)
    }
}

#[derive(Clone, Default, Debug, Serialize, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Status {
    pub download_bytes: Option<u64>,
    pub download_requests: Option<u32>,
    pub summary_records: Option<u64>,
    pub projection_input: Option<String>,
    pub archive_checkpoint: Option<String>,
    pub validated_generation: Option<String>,
    pub published_generation: Option<String>,
    pub last_successful_write: Option<String>,
    pub last_attempt: Option<String>,
    pub installation: Option<PathBuf>,
    pub canonical_bytes: Option<u64>,
    pub lua_bytes: Option<u64>,
    pub result: String,
    pub error: Option<String>,
    // Always unknown: file publication cannot establish client consumption.
    pub loaded_game_generation: Option<String>,
}
fn status_path(base: &Path, scope: &Scope) -> Result<PathBuf> {
    Ok(base.join(format!("delivery-{}.json", scope.key()?)))
}
pub fn status(base: &Path, scope: &Scope) -> Result<Status> {
    let p = status_path(base, scope)?;
    if !p.try_exists()? {
        return Ok(Status::default());
    }
    Ok(serde_json::from_slice(&read(&p, 8192)?)?)
}
pub fn status_for(base: &Path, config: &Configuration) -> Result<Status> {
    let s = status(base, &config.scope)?;
    Ok(if s.installation.as_ref() == Some(&config.installation) {
        s
    } else {
        Status::default()
    })
}
pub(crate) fn save_status(base: &Path, scope: &Scope, s: &Status) -> Result<()> {
    atomic(&status_path(base, scope)?, &serde_json::to_vec_pretty(s)?)
}

pub fn request_for(config: &Configuration, h: &archive::Header) -> Result<Value> {
    config.validate()?;
    let mut request = config.selection.clone();
    need(
        request["market"] == h.market && request["issuer_id"] == h.issuer_id,
        "delivery source identity changed; review setup",
    )?;
    let day = chrono::DateTime::parse_from_rfc3339(&h.generated_at)
        .map_err(|_| Error::Invalid("archive UTC day"))?
        .date_naive();
    request["history_through_day"] = day.to_string().into();
    request["history_from_day"] = (day - Duration::days(i64::from(config.history_days) - 1))
        .to_string()
        .into();
    Ok(request)
}

/// Called after a successful scalar sync with the same authenticated client.
/// A failure is recorded separately; the previous completed archive/files survive.
pub fn synchronize(
    base: &Path,
    client: &MarketClient,
    config: &Configuration,
    cancelled: impl Fn() -> bool,
) -> Result<Status> {
    config.validate()?;
    need(config.enabled, "automatic delivery is disabled")?;
    if config.version == 2 {
        return crate::workshop_summary::synchronize(base, client, config, cancelled);
    }
    let mut s = status_for(base, config)?;
    s.last_attempt = Some(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true));
    s.installation = Some(config.installation.clone());
    s.error = None;
    s.loaded_game_generation = None;
    let result = (|| -> Result<()> {
        if cancelled() {
            return Err(Error::Cancelled);
        }
        let mut store = ArchiveStore::open(
            &base.join("history-archive-v1.sqlite"),
            archive::DEFAULT_DISK_BUDGET,
        )?;
        client.download_archive(&mut store, &config.scope, &cancelled)?;
        let h = store
            .active(&config.scope)?
            .ok_or(Error::Invalid("completed history archive"))?;
        s.archive_checkpoint = Some(h.checkpoint_id.clone());
        save_status(base, &config.scope, &s)?;
        let request = request_for(config, &h)?;
        let input = format!(
            "{:x}",
            Sha256::digest(bridge::canonical(
                &serde_json::json!({"checkpoint":h,"selection":request,"budget":budget()})
            )?)
        );
        if s.projection_input.as_ref() == Some(&input) && s.validated_generation.is_some() {
            let destination = inspect_destination(config)?;
            if destination["existing_generation"].as_str() == s.validated_generation.as_deref() {
                s.published_generation = s.validated_generation.clone();
                s.result = "unchanged; archive, selection and files already match".into();
                return Ok(());
            }
        }
        let (g, receipt, sizes) = archive::project(&store, &config.scope, &request, &budget())?;
        s.validated_generation = g["generation_id"].as_str().map(str::to_owned);
        s.canonical_bytes = Some(sizes.canonical_bytes);
        s.lua_bytes = Some(sizes.lua_bytes);
        save_status(base, &config.scope, &s)?;
        if cancelled() {
            return Err(Error::Cancelled);
        }
        // Check again immediately before publication, including permissions/links.
        let changed = publish(config, &g, &receipt)?;
        s.projection_input = Some(input);
        s.published_generation = s.validated_generation.clone();
        if changed {
            s.last_successful_write =
                Some(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true));
        }
        s.result = if changed {
            "published; login or manually reload WoW"
        } else {
            "unchanged; files already match"
        }
        .into();
        Ok(())
    })();
    if let Err(error) = result {
        s.result = "delivery failed; previous files preserved; retry on next sync".into();
        s.error = Some(error.to_string());
        save_status(base, &config.scope, &s)?;
        return Err(error);
    }
    save_status(base, &config.scope, &s)?;
    Ok(s)
}

fn no_links(path: &Path) -> Result<()> {
    need(path.is_absolute(), "absolute local installation required")?;
    let mut p = PathBuf::new();
    for part in path.components() {
        need(
            !matches!(part, Component::ParentDir | Component::CurDir),
            "unsafe parent path",
        )?;
        let name = part.as_os_str().to_string_lossy();
        need(
            !["wtf", "savedvariables"].contains(&name.to_ascii_lowercase().as_str()),
            "never write SavedVariables",
        )?;
        #[cfg(windows)]
        need(
            !name.ends_with('.') && !name.ends_with(' ') && !name.contains(':')
                || matches!(part, Component::Prefix(_)),
            "unsafe Windows alias",
        )?;
        p.push(part);
        match fs::symlink_metadata(&p) {
            Ok(m) => {
                need(!m.file_type().is_symlink(), "symlink traversal refused")?;
                #[cfg(windows)]
                {
                    use std::os::windows::fs::MetadataExt;
                    need(
                        m.file_attributes() & 0x400 == 0,
                        "junction/reparse traversal refused",
                    )?;
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {}
            Err(e) => return Err(e.into()),
        }
    }
    Ok(())
}
pub(crate) fn owned(path: &Path) -> Result<()> {
    no_links(path)?;
    #[cfg(windows)]
    crate::bridge::windows_owner::check(path)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        let m = fs::metadata(path)?;
        need(
            m.uid() == unsafe { libc::geteuid() } && m.mode() & 0o022 == 0,
            "installation ownership or write permissions",
        )?;
    }
    Ok(())
}
pub(crate) fn read(path: &Path, max: usize) -> Result<Vec<u8>> {
    no_links(path)?;
    let mut b = Vec::new();
    fs::File::open(path)?
        .take(max as u64 + 1)
        .read_to_end(&mut b)?;
    need(b.len() <= max, "delivery file exceeds size limit")?;
    Ok(b)
}
pub(crate) fn atomic(path: &Path, bytes: &[u8]) -> Result<()> {
    let parent = path.parent().ok_or(Error::Invalid("delivery parent"))?;
    owned(parent)?;
    no_links(path)?;
    if path.exists() {
        owned(path)?;
    }
    let mut f = tempfile::NamedTempFile::new_in(parent)?;
    f.write_all(bytes)?;
    f.flush()?;
    f.as_file().sync_all()?;
    f.persist(path).map_err(|e| Error::Io(e.error))?;
    #[cfg(unix)]
    fs::File::open(parent)?.sync_all()?;
    Ok(())
}
/// Read-only preflight. Unknown addon folders and incompatible consumers fail closed.
pub fn inspect_destination(c: &Configuration) -> Result<Value> {
    c.validate()?;
    if c.version == 2 {
        return crate::workshop_summary::inspect_destination(c);
    }
    let root = &c.installation;
    owned(root)?;
    need(
        root.join("Wow.exe").is_file(),
        "select the game directory containing Wow.exe",
    )?;
    let addons = root.join("Interface").join("AddOns");
    owned(&root.join("Interface"))?;
    owned(&addons)?;
    let consumer = addons.join("TwichUI_Workshop");
    owned(&consumer)?;
    let capability: Value =
        serde_json::from_slice(&read(&consumer.join("MarketDelivery.json"), 4096)?)?;
    need(
        capability["format"] == CAPABILITY
            && capability["capability_version"] == 1
            && capability["schema_versions"] == serde_json::json!([3])
            && capability["contract_version"] == 1
            && capability["transport_version"] == 1
            && capability["canonical_bytes"]
                .as_u64()
                .is_some_and(|n| n >= budget().canonical_bytes)
            && capability["lua_bytes"]
                .as_u64()
                .is_some_and(|n| n >= budget().lua_bytes),
        "install the compatible M2 Workshop consumer first",
    )?;
    let destination = addons.join("TwichUI_MarketData");
    if destination.try_exists()? {
        owned(&destination)?;
        for e in fs::read_dir(&destination)? {
            let p = e?.path();
            owned(&p)?;
            need(
                p.is_file()
                    && [
                        "TwichUI_MarketData.toc",
                        "Data.lua",
                        "Previous.lua",
                        ".twichui-delivery.json",
                    ]
                    .contains(&p.file_name().unwrap().to_string_lossy().as_ref()),
                "unknown files in Market data addon; review manually",
            )?;
        }
        let toc = destination.join("TwichUI_MarketData.toc");
        if toc.try_exists()? {
            need(
                read(&toc, 1024)? == TOC,
                "incompatible existing Market data TOC",
            )?;
        }
        let marker = destination.join(".twichui-delivery.json");
        if marker.try_exists()? {
            let identity: Value = serde_json::from_slice(&read(&marker, 4096)?)?;
            need(
                identity == identity_for(c)?,
                "destination belongs to another account, installation or market",
            )?;
        } else {
            // A recognized manual export can be explicitly adopted after review;
            // its account/installation cannot be inferred from the payload.
            need(
                fs::read_dir(&destination)?.next().is_none()
                    || (toc.is_file() && destination.join("Data.lua").is_file()),
                "incomplete unowned Market folder; preserve it outside AddOns before setup",
            )?;
        }
        for name in ["Data.lua", "Previous.lua"] {
            let p = destination.join(name);
            if p.try_exists()? {
                let (g, _) = bridge::inspect_artifact(&read(&p, 3 * 1024 * 1024)?)?;
                need(
                    g["market"] == c.selection["market"]
                        && g["issuer_id"] == c.selection["issuer_id"]
                        && g["pricing_algorithm"] == c.scope.algorithm,
                    "existing generation source mismatch",
                )?;
            }
        }
    }
    Ok(
        serde_json::json!({"destination":destination,"market":c.selection["market"],"requires_adoption":destination.join("Data.lua").is_file()&&!destination.join(".twichui-delivery.json").try_exists()?,"existing_generation":if destination.join("Data.lua").is_file(){bridge::inspect_artifact(&read(&destination.join("Data.lua"),3*1024*1024)?)?.0["generation_id"].clone()}else{Value::Null},"schema":3}),
    )
}
fn identity_for(c: &Configuration) -> Result<Value> {
    Ok(
        serde_json::json!({"version":1,"scope":c.scope.key()?,"installation":fs::canonicalize(&c.installation)?.to_string_lossy(),"market":c.selection["market"],"issuer_id":c.selection["issuer_id"]}),
    )
}
pub(crate) fn free_space(path: &Path) -> Result<u64> {
    #[cfg(unix)]
    {
        use std::{ffi::CString, os::unix::ffi::OsStrExt};
        let p = CString::new(path.as_os_str().as_bytes())
            .map_err(|_| Error::Invalid("installation path"))?;
        let mut s = std::mem::MaybeUninit::<libc::statvfs>::uninit();
        if unsafe { libc::statvfs(p.as_ptr(), s.as_mut_ptr()) } != 0 {
            return Err(std::io::Error::last_os_error().into());
        }
        let s = unsafe { s.assume_init() };
        Ok(s.f_bavail.saturating_mul(s.f_frsize))
    }
    #[cfg(windows)]
    {
        use std::os::windows::ffi::OsStrExt;
        let p = path
            .as_os_str()
            .encode_wide()
            .chain(Some(0))
            .collect::<Vec<_>>();
        let mut free = 0;
        if unsafe {
            windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW(
                p.as_ptr(),
                &mut free,
                std::ptr::null_mut(),
                std::ptr::null_mut(),
            )
        } == 0
        {
            return Err(std::io::Error::last_os_error().into());
        }
        Ok(free)
    }
}
/// Fixed TOC is written last on first installation, and never changed on updates.
/// Only Data.lua is the commit point; Previous.lua is never in the load list.
pub fn publish(c: &Configuration, g: &Value, receipt: &Value) -> Result<bool> {
    publish_with(c, g, receipt, atomic)
}
fn publish_with(
    c: &Configuration,
    g: &Value,
    receipt: &Value,
    replace: impl FnOnce(&Path, &[u8]) -> Result<()>,
) -> Result<bool> {
    need(c.enabled, "automatic delivery disabled")?;
    archive::preflight(g, receipt, &budget())?;
    need(
        g["market"] == c.selection["market"]
            && g["issuer_id"] == c.selection["issuer_id"]
            && g["pricing_algorithm"] == c.scope.algorithm,
        "publication source mismatch",
    )?;
    inspect_destination(c)?;
    need(
        !game_running()?,
        "close WoW before installing Market files; delivery deferred",
    )?;
    let dir = c.installation.join("Interface/AddOns/TwichUI_MarketData");
    let bytes = crate::bridge::export::artifact(g, receipt)?;
    need(
        free_space(&c.installation)? >= 16 * 1024 * 1024 + 4 * bytes.len() as u64,
        "insufficient free disk space for recoverable delivery",
    )?;
    if !dir.try_exists()? {
        fs::create_dir(&dir)?;
    }
    owned(&dir)?;
    let marker = dir.join(".twichui-delivery.json");
    if !marker.try_exists()? {
        atomic(&marker, &serde_json::to_vec(&identity_for(c)?)?)?;
    }
    let target = dir.join("Data.lua");
    let old = if target.try_exists()? {
        Some(read(&target, 3 * 1024 * 1024)?)
    } else {
        None
    };
    if let Some(b) = &old {
        let (existing, _) = bridge::inspect_artifact(b)?;
        if existing == *g {
            // Receipt time/build differences must not rewrite identical data.
            if !dir.join("TwichUI_MarketData.toc").try_exists()? {
                atomic(&dir.join("TwichUI_MarketData.toc"), TOC)?;
            }
            return Ok(false);
        }
        atomic(&dir.join("Previous.lua"), b)?;
    }
    if let Err(e) = replace(&target, &bytes) {
        // Atomic replacement errors preserve the old file; also recover an
        // interrupted/corrupt writer in the independent fault-injection seam.
        if let Some(b) = &old {
            if read(&target, 3 * 1024 * 1024).ok().as_ref() != Some(b) {
                atomic(&target, b)?;
            }
        }
        return Err(e);
    }
    let check = read(&target, 3 * 1024 * 1024).and_then(|b| {
        need(
            Sha256::digest(&b) == Sha256::digest(&bytes),
            "published bytes/hash mismatch",
        )
    });
    if let Err(e) = check {
        if let Some(b) = old {
            atomic(&target, &b)?;
        } else {
            fs::remove_file(&target)?;
        }
        return Err(e);
    }
    let toc = dir.join("TwichUI_MarketData.toc");
    if !toc.try_exists()? {
        atomic(&toc, TOC)?;
    }
    Ok(true)
}
pub fn rollback(c: &Configuration) -> Result<()> {
    if c.version == 2 {
        return crate::workshop_summary::rollback(c);
    }
    inspect_destination(c)?;
    need(!game_running()?, "close WoW before rollback")?;
    let dir = c.installation.join("Interface/AddOns/TwichUI_MarketData");
    let previous = read(&dir.join("Previous.lua"), 3 * 1024 * 1024)?;
    bridge::inspect_artifact(&previous)?;
    atomic(&dir.join("Data.lua"), &previous)?;
    need(
        read(&dir.join("Data.lua"), 3 * 1024 * 1024)? == previous,
        "rollback byte verification",
    )
}
pub fn restore_previous(base: &Path, c: &Configuration) -> Result<Status> {
    if c.version == 2 {
        return crate::workshop_summary::restore_previous(base, c);
    }
    rollback(c)?;
    let data = c
        .installation
        .join("Interface/AddOns/TwichUI_MarketData/Data.lua");
    let (g, _) = bridge::inspect_artifact(&read(&data, 3 * 1024 * 1024)?)?;
    let mut s = status_for(base, c)?;
    s.installation = Some(c.installation.clone());
    s.published_generation = g["generation_id"].as_str().map(str::to_owned);
    s.last_successful_write = Some(Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, true));
    s.projection_input = None;
    s.error = None;
    s.loaded_game_generation = None;
    s.result = "previous generation restored; delivery disabled".into();
    save_status(base, &c.scope, &s)?;
    Ok(s)
}
#[cfg(not(windows))]
pub(crate) fn game_running() -> Result<bool> {
    Ok(false)
}
#[cfg(windows)]
pub(crate) fn game_running() -> Result<bool> {
    use windows_sys::Win32::{
        Foundation::{CloseHandle, GetLastError, ERROR_NO_MORE_FILES, INVALID_HANDLE_VALUE},
        System::Diagnostics::ToolHelp::*,
    };
    unsafe {
        let h = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if h == INVALID_HANDLE_VALUE {
            return Err(std::io::Error::last_os_error().into());
        }
        let mut e: PROCESSENTRY32W = std::mem::zeroed();
        e.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
        if Process32FirstW(h, &mut e) == 0 {
            CloseHandle(h);
            return Err(std::io::Error::last_os_error().into());
        }
        loop {
            let end = e
                .szExeFile
                .iter()
                .position(|x| *x == 0)
                .unwrap_or(e.szExeFile.len());
            let name = String::from_utf16_lossy(&e.szExeFile[..end]).to_lowercase();
            if name.starts_with("wow") && name.ends_with(".exe") {
                CloseHandle(h);
                return Ok(true);
            }
            if Process32NextW(h, &mut e) == 0 {
                let error = GetLastError();
                if error != ERROR_NO_MORE_FILES {
                    CloseHandle(h);
                    return Err(std::io::Error::from_raw_os_error(error as i32).into());
                }
                break;
            }
        }
        CloseHandle(h);
        Ok(false)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    static TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());
    fn fixture(name: &str) -> Value {
        let root =
            Path::new(env!("CARGO_MANIFEST_DIR")).join("../../contracts/bridge/scoped-l1/fixtures");
        serde_json::from_slice(&fs::read(root.join(name)).unwrap()).unwrap()
    }
    fn setup() -> (tempfile::TempDir, Configuration, Value, Value) {
        let temp = tempfile::tempdir().unwrap();
        let install = temp.path().join("Forever");
        let addon = install.join("Interface/AddOns/TwichUI_Workshop");
        fs::create_dir_all(&addon).unwrap();
        fs::write(
            install.join("Wow.exe"),
            b"synthetic installation fixture only",
        )
        .unwrap();
        fs::write(addon.join("MarketDelivery.json"),br#"{"format":"twichui-market-consumer","capability_version":1,"contract_version":1,"transport_version":1,"schema_versions":[3],"canonical_bytes":2097152,"lua_bytes":3145728}"#).unwrap();
        let g = fixture("scoped.json");
        let receipt = fixture("receipt.json");
        let c = Configuration {
            version: 1,
            enabled: true,
            scope: Scope {
                server: "http://127.0.0.1:43321/".into(),
                account_id: 1,
                market_id: 2,
                algorithm: "twichui-pricing-v1".into(),
            },
            installation: install,
            selection: g["scope"]["request"].clone(),
            history_days: 3,
        };
        (temp, c, g, receipt)
    }
    #[test]
    fn confirmed_destination_noop_recovery_and_fixed_toc() {
        let _guard = TEST_LOCK.lock().unwrap();
        let (temp, c, g, r) = setup();
        assert!(Configuration::load(temp.path()).unwrap().is_none());
        assert!(c.save_confirmed(temp.path(), false).is_err());
        let review = inspect_destination(&c).unwrap();
        assert!(review["existing_generation"].is_null());
        assert!(!c
            .installation
            .join("Interface/AddOns/TwichUI_MarketData")
            .exists());
        c.save_confirmed(temp.path(), true).unwrap();
        assert_eq!(
            Configuration::load(temp.path()).unwrap().unwrap().scope,
            c.scope
        );
        assert!(publish(&c, &g, &r).unwrap());
        let data = c
            .installation
            .join("Interface/AddOns/TwichUI_MarketData/Data.lua");
        let before = fs::read(&data).unwrap();
        let mtime = fs::metadata(&data).unwrap().modified().unwrap();
        assert!(!publish(&c, &g, &r).unwrap());
        assert_eq!(fs::metadata(&data).unwrap().modified().unwrap(), mtime);
        let mut changed_receipt = r.clone();
        changed_receipt["desktop_build"] = "another-compatible-build".into();
        assert!(!publish(&c, &g, &changed_receipt).unwrap());
        assert_eq!(fs::read(&data).unwrap(), before);
        let g2 = fixture("large-money-scoped.json");
        let mut r2 = r.clone();
        r2["generation_id"] = g2["generation_id"].clone();
        assert!(publish_with(&c, &g2, &r2, |_, _| Err(std::io::Error::other(
            "disk full or antivirus lock"
        )
        .into()))
        .is_err());
        assert_eq!(fs::read(&data).unwrap(), before);
        assert!(publish_with(&c, &g2, &r2, |p, _| {
            fs::write(p, b"interrupted corrupt write")?;
            Ok(())
        })
        .is_err());
        assert_eq!(fs::read(&data).unwrap(), before);
        assert!(publish(&c, &g2, &r2).unwrap());
        assert_eq!(
            bridge::inspect_artifact(&fs::read(&data).unwrap())
                .unwrap()
                .0,
            g2
        );
        let restored = restore_previous(temp.path(), &c).unwrap();
        assert_eq!(
            restored.published_generation,
            g["generation_id"].as_str().map(str::to_owned)
        );
        assert!(restored.loaded_game_generation.is_none());
        assert_eq!(
            status_for(temp.path(), &c).unwrap().published_generation,
            restored.published_generation
        );
        let mut other = c.clone();
        other.installation = temp.path().join("Other-Forever");
        assert!(status_for(temp.path(), &other)
            .unwrap()
            .published_generation
            .is_none());
        assert_eq!(fs::read(&data).unwrap(), before);
        let toc = data.parent().unwrap().join("TwichUI_MarketData.toc");
        fs::write(&toc, b"unknown TOC").unwrap();
        assert!(publish(&c, &g, &r).is_err());
        assert_eq!(fs::read(&data).unwrap(), before);
    }
    #[test]
    fn refuses_unknown_folders_scopes_consumers_and_large_selection() {
        let _guard = TEST_LOCK.lock().unwrap();
        let (_temp, mut c, g, r) = setup();
        let folder = c.installation.join("Interface/AddOns/TwichUI_MarketData");
        fs::create_dir(&folder).unwrap();
        fs::write(folder.join("unrelated.lua"), b"third party").unwrap();
        assert!(inspect_destination(&c).is_err());
        fs::remove_file(folder.join("unrelated.lua")).unwrap();
        publish(&c, &g, &r).unwrap();
        fs::remove_file(folder.join(".twichui-delivery.json")).unwrap();
        assert_eq!(inspect_destination(&c).unwrap()["requires_adoption"], true);
        assert!(c.save_confirmed(_temp.path(), false).is_err());
        c.save_confirmed(_temp.path(), true).unwrap();
        assert!(!publish(&c, &g, &r).unwrap());
        c.scope.account_id = 2;
        assert!(inspect_destination(&c).is_err());
        c.scope.account_id = 1;
        c.selection["issuer_id"] = "00000000-0000-4000-8000-000000000099".into();
        assert!(publish(&c, &g, &r).is_err());
        c.selection = g["scope"]["request"].clone();
        let cap = c
            .installation
            .join("Interface/AddOns/TwichUI_Workshop/MarketDelivery.json");
        fs::write(&cap, b"{}").unwrap();
        assert!(inspect_destination(&c).is_err());
        let extra = (0..11)
            .map(|i| serde_json::json!({"item_id":100+i,"variant_key":format!("{i:064x}")}))
            .collect::<Vec<_>>();
        c.selection["variants"] = extra.into();
        assert!(c.validate().is_err());
    }
    #[cfg(unix)]
    #[test]
    fn refuses_links_unsafe_parents_and_broad_writes() {
        let _guard = TEST_LOCK.lock().unwrap();
        use std::os::unix::fs::{symlink, PermissionsExt};
        let (temp, mut c, _, _) = setup();
        let real = c.installation.clone();
        symlink(&real, temp.path().join("linked")).unwrap();
        c.installation = temp.path().join("linked");
        assert!(inspect_destination(&c).is_err());
        c.installation = real.join("..").join("Forever");
        assert!(inspect_destination(&c).is_err());
        c.installation = real.clone();
        fs::set_permissions(real, fs::Permissions::from_mode(0o777)).unwrap();
        assert!(inspect_destination(&c).is_err());
    }
    #[cfg(windows)]
    #[test]
    fn running_wow_named_fixture_defers_writes() {
        let _guard = TEST_LOCK.lock().unwrap();
        let (temp, c, g, r) = setup();
        publish(&c, &g, &r).unwrap();
        let path = c
            .installation
            .join("Interface/AddOns/TwichUI_MarketData/Data.lua");
        let old = fs::read(&path).unwrap();
        let exe = temp.path().join("Wow-M2-Fixture.exe");
        fs::copy(
            std::env::var_os("COMSPEC").expect("Windows command processor"),
            &exe,
        )
        .unwrap();
        struct Process(std::process::Child);
        impl Drop for Process {
            fn drop(&mut self) {
                let _ = self.0.kill();
                let _ = self.0.wait();
            }
        }
        let _child = Process(
            std::process::Command::new(exe)
                .args(["/C", "ping -n 30 127.0.0.1 > NUL"])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn()
                .unwrap(),
        );
        let mut detected = false;
        for _ in 0..50 {
            if game_running().unwrap() {
                detected = true;
                break;
            }
            std::thread::sleep(std::time::Duration::from_millis(20));
        }
        assert!(
            detected,
            "actual process enumeration detects the modeled executable name"
        );
        assert!(publish(&c, &g, &r).is_err());
        assert_eq!(fs::read(path).unwrap(), old);
    }
    #[cfg(windows)]
    #[test]
    fn locked_data_file_retains_previous_bytes() {
        let _guard = TEST_LOCK.lock().unwrap();
        use std::os::windows::fs::OpenOptionsExt;
        let (_temp, c, g, r) = setup();
        publish(&c, &g, &r).unwrap();
        let path = c
            .installation
            .join("Interface/AddOns/TwichUI_MarketData/Data.lua");
        let old = fs::read(&path).unwrap();
        let lock = fs::OpenOptions::new()
            .read(true)
            .share_mode(1)
            .open(&path)
            .unwrap();
        let g2 = fixture("large-money-scoped.json");
        let mut r2 = r;
        r2["generation_id"] = g2["generation_id"].clone();
        assert!(publish(&c, &g2, &r2).is_err());
        drop(lock);
        assert_eq!(fs::read(&path).unwrap(), old);
    }
}
