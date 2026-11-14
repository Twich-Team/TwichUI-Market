//! Actual native threads/condition variables; no WebView, JavaScript timer or network mocks in the worker.
use chrono::{TimeZone, Utc};
use std::{
    sync::{
        atomic::{AtomicI64, AtomicUsize, Ordering},
        mpsc::{self, Receiver, Sender},
        Arc, Mutex,
    },
    time::{Duration, Instant},
};
use twichui_market_core::{
    cache::Completion,
    connection::Provenance,
    scheduler::{Clock, Phase, Run},
    settings::Settings,
    worker::{Execution, Executor, Worker},
    Error, Result,
};
#[derive(Clone)]
struct TestClock(Arc<AtomicI64>);
impl Clock for TestClock {
    fn now_ms(&self) -> i64 {
        self.0.load(Ordering::Acquire)
    }
}
enum Reply {
    Complete,
    Limited,
    Authentication,
    Market(Option<u32>),
    Panic,
}
struct Gate {
    starts: Sender<Run>,
    replies: Mutex<Receiver<Reply>>,
    active: Arc<AtomicUsize>,
    maximum: AtomicUsize,
}
struct Running(Arc<AtomicUsize>);
impl Drop for Running {
    fn drop(&mut self) {
        self.0.fetch_sub(1, Ordering::AcqRel);
    }
}
impl Executor for Gate {
    fn execute(
        &self,
        _: &str,
        run: &Run,
        progress: &(dyn Fn(u32) + Send + Sync),
    ) -> Result<Execution> {
        let count = self.active.fetch_add(1, Ordering::AcqRel) + 1;
        self.maximum.fetch_max(count, Ordering::AcqRel);
        let _guard = Running(self.active.clone());
        if run.cancelled() {
            return Err(Error::Cancelled);
        }
        progress(1);
        self.starts.send(run.clone()).unwrap();
        loop {
            if run.cancelled() {
                progress(99);
                return Err(Error::Cancelled);
            }
            let reply = self
                .replies
                .lock()
                .unwrap()
                .recv_timeout(Duration::from_millis(20));
            match reply {
                Ok(Reply::Complete) => return Ok(Execution::Completed(completion(run.market))),
                Ok(Reply::Limited) => return Err(Error::RateLimited(120)),
                Ok(Reply::Authentication) => return Err(Error::Authentication),
                Ok(Reply::Market(market)) => return Ok(Execution::MarketChanged(market)),
                Ok(Reply::Panic) => panic!("synthetic executor interruption"),
                Err(mpsc::RecvTimeoutError::Timeout) => {}
                Err(_) => return Err(Error::Cancelled),
            }
        }
    }
}
fn completion(market: u32) -> Completion {
    Completion {
        schema_version: 1,
        last_sync_ms: 1000,
        source: Provenance {
            market_id: market,
            server_checked_at: Some(Utc.timestamp_millis_opt(950).unwrap()),
            upstream_updated_at: Some(Utc.timestamp_millis_opt(900).unwrap()),
            observation_id: Some("1".into()),
            watermark_observation_id: Some("1".into()),
            snapshot_id: Some("1".into()),
            generation: Some(format!("1:{}", "a".repeat(64))),
            valuation_generation: Some("b".repeat(64)),
            synthetic: false,
            valuation_synthetic: Some(false),
        },
    }
}
fn start(
    automatic: bool,
) -> (
    Worker<TestClock>,
    TestClock,
    Arc<Gate>,
    Receiver<Run>,
    Sender<Reply>,
) {
    let clock = TestClock(Arc::new(AtomicI64::new(1000)));
    let (tx, starts) = mpsc::channel();
    let (replies_tx, replies) = mpsc::channel();
    let gate = Arc::new(Gate {
        starts: tx,
        replies: Mutex::new(replies),
        active: Arc::new(AtomicUsize::new(0)),
        maximum: AtomicUsize::new(0),
    });
    let settings = Settings {
        automatic_sync: automatic,
        sync_on_startup: false,
        interval_minutes: 15,
        selected_market: Some(1),
        ..Settings::default()
    };
    let worker = Worker::start(clock.clone(), settings, true, None, gate.clone(), |_| {}).unwrap();
    (worker, clock, gate, starts, replies_tx)
}
fn started(starts: &Receiver<Run>) -> Run {
    starts
        .recv_timeout(Duration::from_secs(2))
        .expect("native worker did not start")
}
fn idle(worker: &Worker<TestClock>) {
    assert!(worker.wait_idle(Duration::from_secs(2)).unwrap());
}
#[test]
fn native_manual_work_is_single_flight_and_controls_remain_responsive() {
    let (worker, _, gate, starts, replies) = start(false);
    assert!(worker.sync_now().unwrap());
    let run = started(&starts);
    let begin = Instant::now();
    assert!(!worker.sync_now().unwrap());
    assert_eq!(worker.snapshot().unwrap().sync.phase, Phase::Synchronizing);
    assert!(begin.elapsed() < Duration::from_millis(200));
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    let state = worker.snapshot().unwrap();
    assert_eq!(state.sync.pages_completed, 1);
    assert_eq!(state.sync.phase, Phase::Paused);
    assert!(state.sync.last_sync_ms.is_some());
    assert_eq!(gate.maximum.load(Ordering::Acquire), 1);
    assert!(!run.cancelled());
    worker.shutdown().unwrap();
}
#[test]
fn cancellation_acknowledges_before_resume_and_ignores_stale_progress() {
    let (worker, _, gate, starts, replies) = start(true);
    worker.sync_now().unwrap();
    let old = started(&starts);
    worker.pause().unwrap();
    assert!(old.cancelled());
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.phase, Phase::Paused);
    assert_eq!(worker.snapshot().unwrap().sync.pages_completed, 1);
    worker.resume().unwrap();
    let next = started(&starts);
    assert_ne!(old.id, next.id);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    assert_eq!(gate.maximum.load(Ordering::Acquire), 1);
    worker.shutdown().unwrap();
}
#[test]
fn wall_clock_wake_runs_once_and_schedules_from_completion_without_catchup() {
    let (worker, clock, _, starts, replies) = start(true);
    assert!(starts.recv_timeout(Duration::from_millis(30)).is_err());
    clock.0.store(86_401_000, Ordering::Release);
    worker.wake();
    started(&starts);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    assert_eq!(
        worker.snapshot().unwrap().sync.next_sync_ms,
        Some(87_301_000)
    );
    worker.wake();
    assert!(starts.recv_timeout(Duration::from_millis(50)).is_err());
    worker.shutdown().unwrap();
}
#[test]
fn changing_market_cancels_old_work_and_never_applies_its_completion() {
    let (worker, _, gate, starts, replies) = start(false);
    worker.sync_now().unwrap();
    let old = started(&starts);
    worker
        .configure(
            Settings {
                automatic_sync: false,
                sync_on_startup: false,
                selected_market: Some(2),
                ..Settings::default()
            },
            true,
        )
        .unwrap();
    assert!(old.cancelled());
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.selected_market, Some(2));
    assert!(worker.snapshot().unwrap().sync.last_sync_ms.is_none());
    worker.sync_now().unwrap();
    assert_eq!(started(&starts).market, 2);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    assert_eq!(gate.maximum.load(Ordering::Acquire), 1);
    worker.shutdown().unwrap();
}
#[test]
fn rate_limits_wait_and_authentication_failures_stop_automatic_retries() {
    let (worker, clock, _, starts, replies) = start(true);
    worker.sync_now().unwrap();
    started(&starts);
    replies.send(Reply::Limited).unwrap();
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.next_sync_ms, Some(121000));
    clock.0.store(120999, Ordering::Release);
    worker.wake();
    assert!(starts.recv_timeout(Duration::from_millis(30)).is_err());
    clock.0.store(121000, Ordering::Release);
    worker.wake();
    started(&starts);
    replies.send(Reply::Authentication).unwrap();
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.phase, Phase::SignInRequired);
    clock.0.store(9_000_000, Ordering::Release);
    worker.wake();
    assert!(starts.recv_timeout(Duration::from_millis(30)).is_err());
    worker.authorized().unwrap();
    assert!(worker.sync_now().unwrap());
    started(&starts);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    worker.shutdown().unwrap();
}
#[test]
fn shutdown_cancels_and_joins_the_only_thread_without_a_webview() {
    let (worker, _, gate, starts, _replies) = start(true);
    worker.sync_now().unwrap();
    let run = started(&starts);
    let begin = Instant::now();
    worker.shutdown().unwrap();
    assert!(run.cancelled());
    assert_eq!(gate.active.load(Ordering::Acquire), 0);
    assert!(begin.elapsed() < Duration::from_secs(1));
    assert_eq!(worker.snapshot().unwrap().sync.phase, Phase::Stopped);
    assert!(!worker.sync_now().unwrap());
}
#[test]
fn executor_interruption_is_recoverable_and_does_not_leave_sync_stuck() {
    let (worker, _, _, starts, replies) = start(false);
    worker.sync_now().unwrap();
    started(&starts);
    replies.send(Reply::Panic).unwrap();
    idle(&worker);
    assert_eq!(
        worker.snapshot().unwrap().sync.phase,
        Phase::RecoverableError
    );
    assert!(worker.snapshot().unwrap().error.is_some());
    worker.sync_now().unwrap();
    started(&starts);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    assert!(worker.snapshot().unwrap().error.is_none());
    worker.shutdown().unwrap();
}
#[test]
fn website_market_changes_continue_one_request_and_unavailable_choices_stop() {
    let (worker, _, gate, starts, replies) = start(false);
    worker.sync_now().unwrap();
    assert_eq!(started(&starts).market, 1);
    replies.send(Reply::Market(Some(2))).unwrap();
    assert_eq!(started(&starts).market, 2);
    replies.send(Reply::Complete).unwrap();
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.selected_market, Some(2));
    worker.sync_now().unwrap();
    started(&starts);
    replies.send(Reply::Market(None)).unwrap();
    idle(&worker);
    assert_eq!(worker.snapshot().unwrap().sync.phase, Phase::ChooseMarket);
    assert!(!worker.sync_now().unwrap());
    assert_eq!(gate.maximum.load(Ordering::Acquire), 1);
    worker.shutdown().unwrap();
}
