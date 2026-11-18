//! Fixed-field, bounded timings and progress. Never records URLs, cursors or payloads.
use serde::Serialize;
use std::{
    cell::RefCell,
    collections::BTreeMap,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Stage {
    Bootstrap,
    Activity,
    MarketSync,
    NetworkHeaders,
    NetworkTransfer,
    JsonParse,
    Validation,
    SqliteOpen,
    SqliteTransaction,
    SqliteStaging,
    SqliteActivation,
    SqliteCommit,
    Provenance,
    ArchiveSync,
    ArchiveValidation,
    ArchiveActivation,
    WorkshopSync,
    WorkshopDownload,
    WorkshopValidation,
    WorkshopPublication,
    HashVerification,
    FilePublication,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Counter {
    HttpRequests,
    ResponseBodyBytes,
    Pages,
    ReceivedRecords,
    Upserts,
    Deletes,
    ScannedRecords,
    UnchangedRecords,
    ReusedRecords,
}
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Operation {
    #[default]
    CheckingUpdates,
    DownloadingMarket,
    UpdatingCache,
    DownloadingHistory,
    PreparingWorkshop,
    InstallingWorkshop,
    Verifying,
    Complete,
}
#[derive(Clone, Default, Serialize)]
pub struct Timing {
    pub calls: u64,
    pub elapsed_us: u64,
}
#[derive(Clone, Default, Serialize)]
pub struct Report {
    pub elapsed_us: u64,
    pub process_cpu_us: Option<u64>,
    pub process_peak_rss_bytes: Option<u64>,
    pub stages: BTreeMap<Stage, Timing>,
    pub counters: BTreeMap<Counter, u64>,
    pub peak_sqlite_bytes: u64,
    pub peak_wal_bytes: u64,
    pub server_stages: BTreeMap<ServerStage, Timing>,
    pub server_scanned: u64,
    pub server_changed: u64,
    pub server_sql_queries: u64,
}
#[derive(Clone, Default, Serialize)]
pub struct Progress {
    pub active: bool,
    pub operation: Operation,
    pub elapsed_ms: u64,
    pub pages: u64,
    pub records: u64,
    pub bytes: u64,
}
type Observer = Arc<dyn Fn(Progress, Option<Report>) + Send + Sync>;
struct Session {
    report: Report,
    operation: Operation,
    started: Instant,
    cpu_start: Option<u64>,
    detailed: bool,
    observer: Option<Observer>,
    last_emitted: Instant,
    last_operation: Option<Operation>,
}
impl Session {
    fn report(&self) -> Report {
        let mut result = self.report.clone();
        result.elapsed_us = micros(self.started.elapsed());
        let (cpu, rss) = process_usage();
        result.process_cpu_us = cpu
            .zip(self.cpu_start)
            .map(|(end, start)| end.saturating_sub(start));
        result.process_peak_rss_bytes = rss;
        result
    }
    fn progress(&self, active: bool) -> Progress {
        Progress {
            active,
            operation: self.operation,
            elapsed_ms: self.started.elapsed().as_millis().min(u64::MAX as u128) as u64,
            pages: *self.report.counters.get(&Counter::Pages).unwrap_or(&0),
            records: *self
                .report
                .counters
                .get(&Counter::ReceivedRecords)
                .unwrap_or(&0),
            bytes: *self
                .report
                .counters
                .get(&Counter::ResponseBodyBytes)
                .unwrap_or(&0),
        }
    }
}
fn micros(value: Duration) -> u64 {
    value.as_micros().min(u64::MAX as u128) as u64
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ServerStage {
    Authentication,
    Watermark,
    History,
    Pricing,
    Keys,
    Changes,
    Json,
    Sql,
    Lock,
    Total,
    Cpu,
    Calculation,
}
pub fn request_timings() -> bool {
    CURRENT.with(|slot| {
        slot.borrow()
            .as_ref()
            .is_some_and(|s| s.lock().is_ok_and(|s| s.detailed))
    })
}
pub fn server_timings(headers: &reqwest::header::HeaderMap) {
    if !request_timings() {
        return;
    }
    CURRENT.with(|slot| {
        if let Some(session) = slot.borrow().as_ref() {
            if let Ok(mut session) = session.lock() {
                if let Some(value) = headers
                    .get("server-timing")
                    .and_then(|v| v.to_str().ok())
                    .filter(|v| v.len() <= 2048)
                {
                    for metric in value.split(',').take(16) {
                        let Some((name, value)) = metric.split_once(";dur=") else {
                            continue;
                        };
                        let stage = match name.trim() {
                            "authentication" => ServerStage::Authentication,
                            "watermark" => ServerStage::Watermark,
                            "history" => ServerStage::History,
                            "pricing" => ServerStage::Pricing,
                            "keys" => ServerStage::Keys,
                            "changes" => ServerStage::Changes,
                            "json" => ServerStage::Json,
                            "sql" => ServerStage::Sql,
                            "lock" => ServerStage::Lock,
                            "total" => ServerStage::Total,
                            "cpu" => ServerStage::Cpu,
                            "calculation" => ServerStage::Calculation,
                            _ => continue,
                        };
                        if let Ok(ms) = value.parse::<f64>() {
                            if ms.is_finite() && (0.0..=3_600_000.0).contains(&ms) {
                                let timing = session.report.server_stages.entry(stage).or_default();
                                timing.calls = timing.calls.saturating_add(1);
                                timing.elapsed_us =
                                    timing.elapsed_us.saturating_add((ms * 1000.0) as u64);
                            }
                        }
                    }
                }
                if let Some(value) = headers
                    .get("x-companion-sync-counts")
                    .and_then(|v| v.to_str().ok())
                    .filter(|v| v.len() <= 256)
                {
                    for metric in value.split(';').take(4) {
                        let Some((name, value)) = metric.split_once('=') else {
                            continue;
                        };
                        if let Ok(count) = value.parse::<u32>() {
                            match name {
                                "queries" => {
                                    session.report.server_sql_queries = session
                                        .report
                                        .server_sql_queries
                                        .saturating_add(count as u64)
                                }
                                "scanned" => {
                                    session.report.server_scanned =
                                        session.report.server_scanned.saturating_add(count as u64)
                                }
                                "changed" => {
                                    session.report.server_changed =
                                        session.report.server_changed.saturating_add(count as u64)
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }
    });
}
thread_local! { static CURRENT:RefCell<Option<Arc<Mutex<Session>>>>=const { RefCell::new(None) }; }
pub struct Capture {
    session: Arc<Mutex<Session>>,
    previous: Option<Arc<Mutex<Session>>>,
    _thread: std::marker::PhantomData<std::rc::Rc<()>>,
}
impl Capture {
    pub fn begin() -> Self {
        Self::start(true, None)
    }
    pub fn observe(
        detailed: bool,
        observer: impl Fn(Progress, Option<Report>) + Send + Sync + 'static,
    ) -> Self {
        Self::start(detailed, Some(Arc::new(observer)))
    }
    fn start(detailed: bool, observer: Option<Observer>) -> Self {
        let started = Instant::now();
        let session = Arc::new(Mutex::new(Session {
            report: Report::default(),
            operation: Operation::CheckingUpdates,
            started,
            cpu_start: process_usage().0,
            detailed,
            observer,
            last_emitted: started,
            last_operation: None,
        }));
        let previous = CURRENT.with(|slot| slot.replace(Some(session.clone())));
        let result = Self {
            session,
            previous,
            _thread: Default::default(),
        };
        checkpoint();
        result
    }
    pub fn report(&self) -> Report {
        self.session
            .lock()
            .unwrap_or_else(|p| p.into_inner())
            .report()
    }
}
impl Drop for Capture {
    fn drop(&mut self) {
        CURRENT.with(|slot| slot.replace(self.previous.take()));
        let notification = {
            let session = self.session.lock().unwrap_or_else(|p| p.into_inner());
            session.observer.clone().map(|observer| {
                (
                    observer,
                    session.progress(false),
                    session.detailed.then(|| session.report()),
                )
            })
        };
        if let Some((observer, progress, report)) = notification {
            observer(progress, report);
        }
    }
}
pub struct Span {
    session: Option<Arc<Mutex<Session>>>,
    stage: Stage,
    started: Option<Instant>,
}
pub fn measure(stage: Stage) -> Span {
    let session = CURRENT
        .with(|slot| slot.borrow().clone())
        .filter(|s| s.lock().is_ok_and(|s| s.detailed));
    let started = session.as_ref().map(|_| Instant::now());
    Span {
        session,
        stage,
        started,
    }
}
impl Drop for Span {
    fn drop(&mut self) {
        if let (Some(session), Some(start)) = (&self.session, self.started) {
            if let Ok(mut session) = session.lock() {
                let value = session.report.stages.entry(self.stage).or_default();
                value.calls = value.calls.saturating_add(1);
                value.elapsed_us = value.elapsed_us.saturating_add(micros(start.elapsed()));
            }
        }
    }
}
pub fn add(key: Counter, count: u64) {
    CURRENT.with(|slot| {
        if let Some(session) = slot.borrow().as_ref() {
            if let Ok(mut session) = session.lock() {
                let value = session.report.counters.entry(key).or_default();
                *value = value.saturating_add(count);
            }
        }
    });
}
pub fn checkpoint() {
    let notification = CURRENT.with(|slot| {
        let session = slot.borrow().clone()?;
        let mut session = session.lock().ok()?;
        let important = session.last_operation != Some(session.operation)
            && matches!(
                session.operation,
                Operation::PreparingWorkshop
                    | Operation::InstallingWorkshop
                    | Operation::DownloadingHistory
                    | Operation::Complete
            );
        if session.last_operation.is_some()
            && session.last_emitted.elapsed() < Duration::from_millis(250)
            && !important
        {
            return None;
        }
        session.last_emitted = Instant::now();
        session.last_operation = Some(session.operation);
        session.observer.clone().map(|observer| {
            (
                observer,
                session.progress(true),
                session.detailed.then(|| session.report()),
            )
        })
    });
    if let Some((observer, progress, report)) = notification {
        observer(progress, report);
    }
}
pub fn enabled(base: &std::path::Path) -> crate::Result<bool> {
    let path = base.join("sync-performance-v1.json");
    if !path.try_exists()? {
        return Ok(false);
    }
    let value = crate::bridge::parse(&crate::delivery::read(&path, 256)?, 256)?;
    if value.as_object().is_none_or(|m| m.len() != 1) {
        return Err(crate::Error::Invalid("performance preference"));
    }
    value["enabled"]
        .as_bool()
        .ok_or(crate::Error::Invalid("performance preference"))
}
pub fn set_enabled(base: &std::path::Path, value: bool) -> crate::Result<()> {
    crate::delivery::atomic(
        &base.join("sync-performance-v1.json"),
        &serde_json::to_vec(&serde_json::json!({"enabled":value}))?,
    )
}
pub fn operation(value: Operation) {
    CURRENT.with(|slot| {
        if let Some(session) = slot.borrow().as_ref() {
            if let Ok(mut session) = session.lock() {
                session.operation = value;
            }
        }
    });
    checkpoint();
}
pub fn sqlite_size(path: &std::path::Path) {
    CURRENT.with(|slot| {
        if let Some(session) = slot.borrow().as_ref() {
            if let Ok(mut session) = session.lock() {
                if !session.detailed {
                    return;
                }
                let size = |p: &std::path::Path| std::fs::metadata(p).map(|m| m.len()).unwrap_or(0);
                let bytes = size(path);
                let mut wal = path.as_os_str().to_os_string();
                wal.push("-wal");
                session.report.peak_sqlite_bytes = session.report.peak_sqlite_bytes.max(bytes);
                session.report.peak_wal_bytes = session
                    .report
                    .peak_wal_bytes
                    .max(size(std::path::Path::new(&wal)));
            }
        }
    });
}
#[cfg(unix)]
fn process_usage() -> (Option<u64>, Option<u64>) {
    unsafe {
        let mut r: libc::rusage = std::mem::zeroed();
        if libc::getrusage(libc::RUSAGE_SELF, &mut r) != 0 {
            return (None, None);
        }
        let time = |v: libc::timeval| {
            (v.tv_sec.max(0) as u64)
                .saturating_mul(1_000_000)
                .saturating_add(v.tv_usec.max(0) as u64)
        };
        let rss = if cfg!(target_os = "macos") {
            r.ru_maxrss.max(0) as u64
        } else {
            (r.ru_maxrss.max(0) as u64).saturating_mul(1024)
        };
        (
            Some(time(r.ru_utime).saturating_add(time(r.ru_stime))),
            Some(rss),
        )
    }
}
#[cfg(windows)]
fn process_usage() -> (Option<u64>, Option<u64>) {
    unsafe {
        use windows_sys::Win32::{
            Foundation::FILETIME,
            System::{
                ProcessStatus::{GetProcessMemoryInfo, PROCESS_MEMORY_COUNTERS},
                Threading::{GetCurrentProcess, GetProcessTimes},
            },
        };
        let mut created: FILETIME = std::mem::zeroed();
        let mut exited = created;
        let mut kernel = created;
        let mut user = created;
        let cpu = if GetProcessTimes(
            GetCurrentProcess(),
            &mut created,
            &mut exited,
            &mut kernel,
            &mut user,
        ) != 0
        {
            let ticks = |v: FILETIME| ((v.dwHighDateTime as u64) << 32) | v.dwLowDateTime as u64;
            Some(ticks(kernel).saturating_add(ticks(user)) / 10)
        } else {
            None
        };
        let mut memory: PROCESS_MEMORY_COUNTERS = std::mem::zeroed();
        let size = std::mem::size_of_val(&memory) as u32;
        memory.cb = size;
        let rss = if GetProcessMemoryInfo(GetCurrentProcess(), &mut memory, size) != 0 {
            Some(memory.PeakWorkingSetSize as u64)
        } else {
            None
        };
        (cpu, rss)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn opt_in_reports_restore_nested_context_and_progress_is_throttled() {
        let events = Arc::new(Mutex::new(Vec::new()));
        let sink = events.clone();
        let capture = Capture::observe(true, move |progress, report| {
            sink.lock().unwrap().push((progress, report))
        });
        add(Counter::ReceivedRecords, 42);
        {
            let inner = Capture::begin();
            add(Counter::ReceivedRecords, 9);
            assert_eq!(inner.report().counters[&Counter::ReceivedRecords], 9);
        }
        for _ in 0..1000 {
            operation(Operation::DownloadingMarket);
            operation(Operation::UpdatingCache);
        }
        operation(Operation::PreparingWorkshop);
        operation(Operation::InstallingWorkshop);
        assert_eq!(capture.report().counters[&Counter::ReceivedRecords], 42);
        drop(capture);
        let events = events.lock().unwrap();
        assert!(events.len() < 20);
        let (progress, report) = events.last().unwrap();
        assert!(!progress.active);
        assert_ne!(progress.operation, Operation::Complete);
        assert!(report.as_ref().unwrap().process_cpu_us.is_some());
        assert!(events
            .iter()
            .any(|(progress, report)| progress.active
                && report
                    .as_ref()
                    .is_some_and(|r| r.counters.get(&Counter::ReceivedRecords) == Some(&42))));
        assert!(CURRENT.with(|s| s.borrow().is_none()));
    }
    #[test]
    fn disabled_detailed_capture_keeps_progress_without_exporting_report_or_changing_legacy_settings(
    ) {
        let events = Arc::new(Mutex::new(Vec::new()));
        let sink = events.clone();
        {
            let _capture = Capture::observe(false, move |p, r| sink.lock().unwrap().push((p, r)));
            let _span = measure(Stage::MarketSync);
            add(Counter::Pages, 1);
            operation(Operation::Complete);
        }
        let events = events.lock().unwrap();
        assert!(events.last().unwrap().1.is_none());
        assert_eq!(events.last().unwrap().0.pages, 1);
        let d = tempfile::tempdir().unwrap();
        let legacy = d.path().join("settings-v1.json");
        std::fs::write(&legacy, b"preserve legacy bytes").unwrap();
        assert!(!enabled(d.path()).unwrap());
        set_enabled(d.path(), true).unwrap();
        assert!(enabled(d.path()).unwrap());
        assert_eq!(std::fs::read(legacy).unwrap(), b"preserve legacy bytes");
    }
}
