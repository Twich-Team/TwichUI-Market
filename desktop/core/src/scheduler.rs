//! Deterministic native scheduling policy; no WebView timer, networking or SQLite ownership.
//! The runtime keeps exactly one worker and acknowledges cancellation before another run starts.
use crate::settings::Settings;
use serde::Serialize;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::time::{SystemTime, UNIX_EPOCH};

pub trait Clock: Send + Sync {
    fn now_ms(&self) -> i64;
}
#[derive(Clone, Default)]
pub struct SystemClock;
impl Clock for SystemClock {
    fn now_ms(&self) -> i64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis()
            .min(i64::MAX as u128) as i64
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    NotConnected,
    ChooseMarket,
    Ready,
    Synchronizing,
    Cancelling,
    Paused,
    Offline,
    ServerUnavailable,
    SignInRequired,
    RecoverableError,
    Stopped,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct Snapshot {
    pub phase: Phase,
    pub automatic_sync: bool,
    pub next_sync_ms: Option<i64>,
    pub last_sync_ms: Option<i64>,
    pub last_server_check_ms: Option<i64>,
    pub upstream_update_ms: Option<i64>,
    pub generation: Option<String>,
    pub received_new_generation: bool,
    pub pages_completed: u32,
    pub retry_attempts: u32,
    pub selected_market: Option<u32>,
    pub running: bool,
}

#[derive(Clone, Debug)]
pub struct Run {
    pub id: u64,
    pub market: u32,
    cancelled: Arc<AtomicBool>,
}
impl Run {
    pub fn cancelled(&self) -> bool {
        self.cancelled.load(Ordering::Acquire)
    }
    pub fn cancellation(&self) -> Arc<AtomicBool> {
        self.cancelled.clone()
    }
}

#[derive(Clone, Debug)]
pub struct Receipt {
    pub server_check_ms: Option<i64>,
    pub upstream_update_ms: Option<i64>,
    pub generation: Option<String>,
}

#[derive(Clone, Debug)]
pub enum Outcome {
    Success(Receipt),
    Offline,
    ServerUnavailable { retry_after_ms: Option<i64> },
    SignInRequired,
    RecoverableError,
    Cancelled,
}

pub struct Scheduler<C: Clock = SystemClock> {
    clock: C,
    settings: Settings,
    connected: bool,
    stopped: bool,
    authentication_required: bool,
    active: Option<Run>,
    after_cancel_immediate: bool,
    sequence: u64,
    last_clock_ms: i64,
    snapshot: Snapshot,
}

impl<C: Clock> Scheduler<C> {
    pub fn new(clock: C, settings: Settings, connected: bool) -> crate::Result<Self> {
        settings.validate()?;
        let now = clock.now_ms();
        let snapshot = Snapshot {
            phase: Phase::NotConnected,
            automatic_sync: settings.automatic_sync,
            next_sync_ms: None,
            last_sync_ms: None,
            last_server_check_ms: None,
            upstream_update_ms: None,
            generation: None,
            received_new_generation: false,
            pages_completed: 0,
            retry_attempts: 0,
            selected_market: settings.selected_market,
            running: false,
        };
        let mut result = Self {
            clock,
            settings,
            connected,
            stopped: false,
            authentication_required: false,
            active: None,
            after_cancel_immediate: false,
            sequence: 0,
            last_clock_ms: now,
            snapshot,
        };
        result.schedule_idle(now, result.settings.sync_on_startup);
        Ok(result)
    }

    fn now(&mut self) -> i64 {
        let now = self.clock.now_ms();
        // Preserve remaining delay across a backwards wall-clock adjustment. A forward
        // jump/wake is reconciled by poll once; completed runs schedule from current time.
        if now < self.last_clock_ms {
            self.snapshot.next_sync_ms = self
                .snapshot
                .next_sync_ms
                .map(|due| now.saturating_add(due.saturating_sub(self.last_clock_ms).max(0)));
        }
        self.last_clock_ms = now;
        now
    }

    fn available(&self) -> bool {
        self.connected
            && self.settings.selected_market.is_some()
            && !self.authentication_required
            && !self.stopped
    }

    fn idle_phase(&self) -> Phase {
        if self.stopped {
            Phase::Stopped
        } else if !self.connected {
            Phase::NotConnected
        } else if self.authentication_required {
            Phase::SignInRequired
        } else if self.settings.selected_market.is_none() {
            Phase::ChooseMarket
        } else if !self.settings.automatic_sync {
            Phase::Paused
        } else {
            Phase::Ready
        }
    }

    fn schedule_idle(&mut self, now: i64, immediate: bool) {
        self.snapshot.phase = self.idle_phase();
        self.snapshot.next_sync_ms = if self.available() && self.settings.automatic_sync {
            Some(if immediate {
                now
            } else {
                now.saturating_add(self.settings.interval_ms())
            })
        } else {
            None
        };
    }

    pub fn snapshot(&self) -> Snapshot {
        self.snapshot.clone()
    }

    pub fn configure(&mut self, settings: Settings, connected: bool) -> crate::Result<()> {
        settings.validate()?;
        if settings == self.settings && connected == self.connected {
            return Ok(());
        }
        let now = self.now();
        let connection_changed = connected != self.connected
            || settings.server != self.settings.server
            || settings.selected_market != self.settings.selected_market;
        let resumed = settings.automatic_sync && !self.settings.automatic_sync;
        let interval_changed = settings.interval_minutes != self.settings.interval_minutes;
        if connection_changed || !settings.automatic_sync {
            self.cancel_active();
        }
        // Only an explicit connection change clears an authorization failure.
        if connection_changed {
            self.authentication_required = false;
        }
        self.connected = connected;
        self.settings = settings;
        self.snapshot.automatic_sync = self.settings.automatic_sync;
        self.snapshot.selected_market = self.settings.selected_market;
        if connection_changed {
            self.snapshot.last_sync_ms = None;
            self.snapshot.last_server_check_ms = None;
            self.snapshot.upstream_update_ms = None;
            self.snapshot.generation = None;
            self.snapshot.received_new_generation = false;
            self.snapshot.retry_attempts = 0;
            self.after_cancel_immediate = self.settings.sync_on_startup;
        } else if resumed {
            self.after_cancel_immediate = true;
        }
        if self.active.is_none() {
            if connection_changed || resumed || !self.settings.automatic_sync {
                self.schedule_idle(
                    now,
                    resumed || connection_changed && self.settings.sync_on_startup,
                );
            } else if interval_changed && self.snapshot.phase == Phase::Ready {
                self.snapshot.next_sync_ms = Some(
                    self.snapshot
                        .last_sync_ms
                        .unwrap_or(now)
                        .saturating_add(self.settings.interval_ms())
                        .max(now),
                );
            }
        }
        Ok(())
    }

    pub fn authorized(&mut self) {
        let now = self.now();
        self.connected = true;
        self.authentication_required = false;
        self.snapshot.retry_attempts = 0;
        self.after_cancel_immediate = self.settings.sync_on_startup;
        if self.active.is_none() {
            self.schedule_idle(now, self.settings.sync_on_startup);
        }
    }

    fn cancel_active(&mut self) {
        if let Some(run) = &self.active {
            run.cancelled.store(true, Ordering::Release);
            self.snapshot.phase = Phase::Cancelling;
            self.snapshot.next_sync_ms = None;
        }
    }

    pub fn cancel(&mut self) {
        self.after_cancel_immediate = false;
        self.cancel_active();
    }

    pub fn pause(&mut self) {
        self.settings.automatic_sync = false;
        self.snapshot.automatic_sync = false;
        self.after_cancel_immediate = false;
        self.cancel_active();
        if self.active.is_none() {
            self.snapshot.phase = self.idle_phase();
            self.snapshot.next_sync_ms = None;
        }
    }

    pub fn resume(&mut self) {
        let now = self.now();
        self.settings.automatic_sync = true;
        self.snapshot.automatic_sync = true;
        self.after_cancel_immediate = true;
        if self.active.is_none() {
            self.schedule_idle(now, true);
        }
    }

    pub fn connectivity_restored(&mut self) {
        let now = self.now();
        if self.active.is_none()
            && self.available()
            && self.settings.automatic_sync
            && matches!(
                self.snapshot.phase,
                Phase::Offline | Phase::ServerUnavailable
            )
        {
            self.snapshot.next_sync_ms = Some(now);
        }
    }

    pub fn shutdown(&mut self) {
        self.stopped = true;
        self.cancel_active();
        self.snapshot.phase = Phase::Stopped;
        self.snapshot.next_sync_ms = None;
    }

    fn begin(&mut self) -> Option<Run> {
        if !self.available() || self.active.is_some() {
            return None;
        }
        self.sequence = self.sequence.checked_add(1)?;
        let run = Run {
            id: self.sequence,
            market: self.settings.selected_market?,
            cancelled: Arc::new(AtomicBool::new(false)),
        };
        self.active = Some(run.clone());
        self.after_cancel_immediate = false;
        self.snapshot.running = true;
        self.snapshot.phase = Phase::Synchronizing;
        self.snapshot.next_sync_ms = None;
        self.snapshot.pages_completed = 0;
        self.snapshot.received_new_generation = false;
        Some(run)
    }

    pub fn sync_now(&mut self) -> Option<Run> {
        self.now();
        self.begin()
    }

    pub fn poll(&mut self) -> Option<Run> {
        let now = self.now();
        if self.settings.automatic_sync && self.snapshot.next_sync_ms.is_some_and(|due| due <= now)
        {
            self.begin()
        } else {
            None
        }
    }

    pub fn progress(&mut self, id: u64, pages: u32) -> bool {
        if self
            .active
            .as_ref()
            .is_some_and(|run| run.id == id && !run.cancelled())
        {
            self.snapshot.pages_completed = self.snapshot.pages_completed.max(pages);
            true
        } else {
            false
        }
    }

    pub fn finish(&mut self, id: u64, outcome: Outcome) -> bool {
        if !self.active.as_ref().is_some_and(|run| run.id == id) {
            return false;
        }
        let run = self.active.take().unwrap();
        let now = self.now();
        self.snapshot.running = false;
        if run.cancelled() || matches!(outcome, Outcome::Cancelled) || self.stopped {
            // The old worker has acknowledged cancellation. Only now may another start.
            self.schedule_idle(now, self.after_cancel_immediate);
            return true;
        }
        match outcome {
            Outcome::Success(receipt) => {
                self.snapshot.last_sync_ms = Some(now);
                self.snapshot.last_server_check_ms = receipt.server_check_ms;
                self.snapshot.upstream_update_ms = receipt.upstream_update_ms;
                self.snapshot.received_new_generation =
                    receipt.generation.is_some() && self.snapshot.generation != receipt.generation;
                self.snapshot.generation = receipt.generation;
                self.snapshot.retry_attempts = 0;
                self.schedule_idle(now, false);
            }
            Outcome::SignInRequired => {
                self.authentication_required = true;
                self.snapshot.phase = Phase::SignInRequired;
                self.snapshot.next_sync_ms = None;
            }
            Outcome::Offline | Outcome::ServerUnavailable { .. } | Outcome::RecoverableError => {
                self.snapshot.retry_attempts = self.snapshot.retry_attempts.saturating_add(1);
                let exponent = self.snapshot.retry_attempts.saturating_sub(1).min(5);
                let backoff = (30_000i64 * (1 << exponent)).min(900_000);
                let requested = match outcome {
                    Outcome::ServerUnavailable { retry_after_ms } => retry_after_ms.unwrap_or(0),
                    _ => 0,
                };
                let delay = if self.snapshot.retry_attempts > 6 {
                    self.settings.interval_ms()
                } else {
                    backoff
                };
                self.snapshot.next_sync_ms = self
                    .settings
                    .automatic_sync
                    .then_some(now.saturating_add(delay.max(requested).clamp(30_000, 3_600_000)));
                self.snapshot.phase = match outcome {
                    Outcome::Offline => Phase::Offline,
                    Outcome::ServerUnavailable { .. } => Phase::ServerUnavailable,
                    _ => Phase::RecoverableError,
                };
            }
            Outcome::Cancelled => unreachable!(),
        }
        true
    }

    /// Runtime can sleep on a condition variable until this deadline or an app/OS event.
    pub fn wait_ms(&mut self) -> Option<u64> {
        let now = self.now();
        self.snapshot
            .next_sync_ms
            .map(|due| due.saturating_sub(now).max(0) as u64)
    }
}
