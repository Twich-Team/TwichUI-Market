//! One native synchronization thread, independent of WebView lifetime and timers.
//! Network/cache work executes outside the control mutex; cancellation/status stay responsive.
use crate::{
    cache::Completion,
    scheduler::{Clock, Outcome, Receipt, Run, Scheduler, Snapshot},
    settings::Settings,
    Error, Result,
};
use serde::Serialize;
use std::{
    sync::{Arc, Condvar, Mutex},
    thread::{self, JoinHandle},
    time::{Duration, Instant},
};

pub enum Execution {
    Completed(Completion),
    MarketChanged(Option<u32>),
}
pub trait Executor: Send + Sync + 'static {
    fn execute(
        &self,
        server: &str,
        run: &Run,
        progress: &(dyn Fn(u32) + Send + Sync),
    ) -> Result<Execution>;
}
#[derive(Clone, Debug, Serialize)]
pub struct State {
    pub revision: u64,
    pub sync: Snapshot,
    pub error: Option<String>,
}
struct Control<C: Clock> {
    scheduler: Scheduler<C>,
    settings: Settings,
    pending: Option<Run>,
    stopped: bool,
    revision: u64,
    error: Option<String>,
}
struct Shared<C: Clock> {
    control: Mutex<Control<C>>,
    changed: Condvar,
    observer: Arc<dyn Fn(State) + Send + Sync>,
}
pub struct Worker<C: Clock + 'static> {
    shared: Arc<Shared<C>>,
    thread: Mutex<Option<JoinHandle<()>>>,
}
impl<C: Clock> Control<C> {
    fn state(&self) -> State {
        State {
            revision: self.revision,
            sync: self.scheduler.snapshot(),
            error: self.error.clone(),
        }
    }
    fn revised(&mut self) -> State {
        self.revision = self.revision.saturating_add(1);
        self.state()
    }
}
impl<C: Clock + 'static> Worker<C> {
    pub fn start(
        clock: C,
        settings: Settings,
        connected: bool,
        completion: Option<&Completion>,
        executor: Arc<dyn Executor>,
        observer: impl Fn(State) + Send + Sync + 'static,
    ) -> Result<Self> {
        let mut scheduler = Scheduler::new(clock, settings.clone(), connected)?;
        if let Some(completion) = completion {
            scheduler.restore_completion(completion)?;
        }
        let shared = Arc::new(Shared {
            control: Mutex::new(Control {
                scheduler,
                settings,
                pending: None,
                stopped: false,
                revision: 0,
                error: None,
            }),
            changed: Condvar::new(),
            observer: Arc::new(observer),
        });
        let owned = shared.clone();
        let task = thread::Builder::new()
            .name("market-sync".into())
            .spawn(move || worker_loop(owned, executor))?;
        Ok(Self {
            shared,
            thread: Mutex::new(Some(task)),
        })
    }
    pub fn snapshot(&self) -> Result<State> {
        Ok(self
            .shared
            .control
            .lock()
            .map_err(|_| Error::Invalid("native worker state"))?
            .state())
    }
    fn change<T>(&self, action: impl FnOnce(&mut Control<C>) -> Result<T>) -> Result<T> {
        let mut control = self
            .shared
            .control
            .lock()
            .map_err(|_| Error::Invalid("native worker state"))?;
        let result = action(&mut control)?;
        let state = control.revised();
        drop(control);
        self.shared.changed.notify_all();
        (self.shared.observer)(state);
        Ok(result)
    }
    pub fn configure(&self, settings: Settings, connected: bool) -> Result<()> {
        self.change(|control| {
            control.scheduler.configure(settings.clone(), connected)?;
            control.settings = settings;
            Ok(())
        })
    }
    pub fn configure_receipt(
        &self,
        settings: Settings,
        connected: bool,
        receipt: Option<&Completion>,
    ) -> Result<()> {
        self.change(|control| {
            if let Some(receipt) = receipt {
                if control.scheduler.snapshot().running
                    || settings.selected_market != Some(receipt.source.market_id)
                    || receipt.schema_version != 1
                {
                    return Err(Error::Invalid("completion receipt identity"));
                }
                receipt.source.validate(receipt.source.market_id)?;
            }
            control.scheduler.configure(settings.clone(), connected)?;
            if let Some(receipt) = receipt {
                control.scheduler.restore_completion(receipt)?;
            }
            control.settings = settings;
            Ok(())
        })
    }
    pub fn authorized(&self) -> Result<()> {
        self.change(|control| {
            control.scheduler.authorized();
            control.error = None;
            Ok(())
        })
    }
    pub fn sync_now(&self) -> Result<bool> {
        self.change(|control| {
            let run = control.scheduler.sync_now();
            let started = run.is_some();
            if started {
                control.pending = run;
                control.error = None;
            }
            Ok(started)
        })
    }
    pub fn cancel(&self) -> Result<()> {
        self.change(|control| {
            control.scheduler.cancel();
            Ok(())
        })
    }
    pub fn pause(&self) -> Result<()> {
        self.change(|control| {
            control.settings.automatic_sync = false;
            control.scheduler.pause();
            Ok(())
        })
    }
    pub fn resume(&self) -> Result<()> {
        self.change(|control| {
            control.settings.automatic_sync = true;
            control.scheduler.resume();
            Ok(())
        })
    }
    /// OS resume/connectivity events and a controllable-clock test can wake the native loop.
    pub fn wake(&self) {
        self.shared.changed.notify_all();
    }
    pub fn connectivity_restored(&self) -> Result<()> {
        self.change(|control| {
            control.scheduler.connectivity_restored();
            Ok(())
        })
    }
    pub fn restore_completion(&self, receipt: &Completion) -> Result<()> {
        self.change(|control| control.scheduler.restore_completion(receipt))
    }
    pub fn wait_idle(&self, timeout: Duration) -> Result<bool> {
        let deadline = Instant::now() + timeout;
        let mut control = self
            .shared
            .control
            .lock()
            .map_err(|_| Error::Invalid("native worker state"))?;
        while control.scheduler.snapshot().running {
            let Some(remaining) = deadline.checked_duration_since(Instant::now()) else {
                return Ok(false);
            };
            let (next, wait) = self
                .shared
                .changed
                .wait_timeout(control, remaining)
                .map_err(|_| Error::Invalid("native worker state"))?;
            control = next;
            if wait.timed_out() && control.scheduler.snapshot().running {
                return Ok(false);
            }
        }
        Ok(true)
    }
    pub fn shutdown(&self) -> Result<()> {
        self.change(|control| {
            control.stopped = true;
            control.scheduler.shutdown();
            Ok(())
        })?;
        if let Some(task) = self
            .thread
            .lock()
            .map_err(|_| Error::Invalid("native worker thread"))?
            .take()
        {
            if task.thread().id() != thread::current().id() {
                task.join()
                    .map_err(|_| Error::Invalid("native worker stopped unexpectedly"))?;
            }
        }
        Ok(())
    }
}
impl<C: Clock> Drop for Worker<C> {
    fn drop(&mut self) {
        if let Ok(mut control) = self.shared.control.lock() {
            control.stopped = true;
            control.scheduler.shutdown();
        }
        self.shared.changed.notify_all();
    }
}
fn worker_loop<C: Clock + 'static>(shared: Arc<Shared<C>>, executor: Arc<dyn Executor>) {
    loop {
        let Ok(mut control) = shared.control.lock() else {
            return;
        };
        if control.stopped {
            if let Some(run) = control.pending.take() {
                control.scheduler.finish(run.id, Outcome::Cancelled);
            }
            shared.changed.notify_all();
            return;
        }
        let run = control.pending.take().or_else(|| control.scheduler.poll());
        let Some(run) = run else {
            // Reconcile wall-clock/sleep changes within 30 seconds even without OS events.
            let wait = control
                .scheduler
                .wait_ms()
                .unwrap_or(30_000)
                .clamp(10, 30_000);
            let _guard = shared
                .changed
                .wait_timeout(control, Duration::from_millis(wait));
            continue;
        };
        let server = control.settings.server.clone();
        let state = control.revised();
        drop(control);
        (shared.observer)(state);
        let report_shared = shared.clone();
        let id = run.id;
        let progress = move |pages| {
            let Ok(mut control) = report_shared.control.lock() else {
                return;
            };
            if control.scheduler.progress(id, pages) {
                let state = control.revised();
                drop(control);
                (report_shared.observer)(state);
            }
        };
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            executor.execute(&server, &run, &progress)
        }))
        .unwrap_or(Err(Error::Invalid("native synchronization interrupted")));
        let Ok(mut control) = shared.control.lock() else {
            return;
        };
        if !run.cancelled() && !control.stopped {
            if let Ok(Execution::MarketChanged(market)) = &result {
                control.scheduler.cancel();
                control.scheduler.finish(run.id, Outcome::Cancelled);
                let mut settings = control.settings.clone();
                settings.selected_market = *market;
                if control.scheduler.configure(settings.clone(), true).is_ok() {
                    control.settings = settings;
                    control.error = None;
                    // Continue the same requested check using the newly resolved website preference.
                    control.pending = control.scheduler.sync_now();
                }
                let state = control.revised();
                drop(control);
                shared.changed.notify_all();
                (shared.observer)(state);
                continue;
            }
        }
        let outcome = match result {
            Ok(Execution::Completed(receipt)) => {
                control.error = None;
                Outcome::Success(Receipt {
                    server_check_ms: receipt
                        .source
                        .server_checked_at
                        .map(|v| v.timestamp_millis()),
                    upstream_update_ms: receipt
                        .source
                        .upstream_updated_at
                        .map(|v| v.timestamp_millis()),
                    generation: receipt.source.generation,
                })
            }
            Ok(Execution::MarketChanged(_)) => Outcome::Cancelled,
            Err(error) => {
                if !matches!(error, Error::Cancelled) && !run.cancelled() {
                    control.error = Some(error.to_string());
                }
                match error {
                    Error::Authentication | Error::CredentialMissing => Outcome::SignInRequired,
                    Error::Network => Outcome::Offline,
                    Error::ServiceUnavailable => Outcome::ServerUnavailable {
                        retry_after_ms: None,
                    },
                    Error::RateLimited(seconds) | Error::SummaryPreparing(seconds) => Outcome::ServerUnavailable {
                        retry_after_ms: Some((seconds.min(3600) * 1000) as i64),
                    },
                    Error::Cancelled => Outcome::Cancelled,
                    _ => Outcome::RecoverableError,
                }
            }
        };
        control.scheduler.finish(run.id, outcome);
        let state = control.revised();
        drop(control);
        shared.changed.notify_all();
        (shared.observer)(state);
    }
}
