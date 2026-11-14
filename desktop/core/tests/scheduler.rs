use std::sync::{
    atomic::{AtomicI64, Ordering},
    Arc,
};
use twichui_market_core::{
    scheduler::{Clock, Outcome, Phase, Receipt, Scheduler},
    settings::Settings,
};

#[derive(Clone)]
struct ManualClock(Arc<AtomicI64>);
impl Clock for ManualClock {
    fn now_ms(&self) -> i64 {
        self.0.load(Ordering::SeqCst)
    }
}
impl ManualClock {
    fn new() -> Self {
        Self(Arc::new(AtomicI64::new(1_000_000)))
    }
    fn advance(&self, millis: i64) {
        self.0.fetch_add(millis, Ordering::SeqCst);
    }
}
fn connected() -> Settings {
    Settings {
        selected_market: Some(2),
        ..Settings::default()
    }
}
fn receipt() -> Outcome {
    Outcome::Success(Receipt {
        server_check_ms: Some(900_000),
        upstream_update_ms: Some(500_000),
        generation: Some("snapshot-16".into()),
    })
}

#[test]
fn startup_and_single_flight_are_owned_by_rust_not_the_window() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    assert!(scheduler.poll().is_none() && scheduler.sync_now().is_none());
    assert!(scheduler.progress(run.id, 3));
    assert!(scheduler.progress(run.id, 1));
    assert_eq!(scheduler.snapshot().pages_completed, 3);
    assert!(scheduler.finish(run.id, receipt()));
    assert_eq!(scheduler.snapshot().phase, Phase::Ready);
    assert_eq!(scheduler.wait_ms(), Some(30 * 60_000));
    clock.advance(30 * 60_000);
    assert!(scheduler.poll().is_some());
}

#[test]
fn startup_disabled_auto_disabled_and_disconnected_have_predictable_behavior() {
    let clock = ManualClock::new();
    let mut settings = connected();
    settings.sync_on_startup = false;
    let mut scheduler = Scheduler::new(clock.clone(), settings.clone(), true).unwrap();
    assert!(scheduler.poll().is_none());
    assert_eq!(scheduler.wait_ms(), Some(30 * 60_000));
    let run = scheduler.sync_now().unwrap();
    scheduler.finish(run.id, receipt());
    settings.automatic_sync = false;
    scheduler.configure(settings.clone(), true).unwrap();
    clock.advance(10 * 60 * 60_000);
    assert!(scheduler.poll().is_none());
    assert_eq!(scheduler.snapshot().phase, Phase::Paused);
    assert!(scheduler.sync_now().is_some()); // Explicit sync remains available while automatic checks are paused.
    let disconnected = Scheduler::new(clock, settings, false).unwrap();
    assert_eq!(disconnected.snapshot().phase, Phase::NotConnected);
}

#[test]
fn pause_resume_and_market_switch_wait_for_cancel_acknowledgement() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock, connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.pause();
    assert!(run.cancelled());
    assert_eq!(scheduler.snapshot().phase, Phase::Cancelling);
    scheduler.resume();
    assert!(scheduler.poll().is_none() && scheduler.sync_now().is_none());
    assert!(!scheduler.progress(run.id, 99));
    scheduler.finish(run.id, Outcome::Cancelled);
    let replacement = scheduler.poll().unwrap();
    assert_ne!(run.id, replacement.id);
    let mut settings = connected();
    settings.selected_market = Some(7);
    scheduler.configure(settings, true).unwrap();
    assert!(replacement.cancelled());
    assert!(scheduler.sync_now().is_none());
    scheduler.finish(replacement.id, receipt());
    let next = scheduler.poll().unwrap();
    assert_eq!(next.market, 7);
    assert!(!scheduler.finish(run.id, receipt()));
    assert!(scheduler.snapshot().running);
}

#[test]
fn offline_recovery_backoff_is_bounded_and_connectivity_can_wake_it() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    for attempt in 0..9 {
        let run = scheduler.poll().unwrap();
        scheduler.finish(run.id, Outcome::Offline);
        let delay = scheduler.wait_ms().unwrap();
        assert!((30_000..=1_800_000).contains(&delay));
        if attempt == 0 {
            assert_eq!(delay, 30_000);
        }
        clock.advance(delay as i64);
    }
    scheduler.connectivity_restored();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    assert_eq!(scheduler.snapshot().retry_attempts, 0);
    assert_eq!(scheduler.snapshot().phase, Phase::Ready);
}

#[test]
fn server_retry_after_cannot_create_a_tight_loop_or_unbounded_delay() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.finish(
        run.id,
        Outcome::ServerUnavailable {
            retry_after_ms: Some(i64::MAX),
        },
    );
    assert_eq!(scheduler.wait_ms(), Some(3_600_000));
    assert_eq!(scheduler.snapshot().phase, Phase::ServerUnavailable);
    scheduler.connectivity_restored();
    assert!(scheduler.poll().is_some());
}

#[test]
fn auth_failures_require_reauthorization_not_silent_retry() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, Outcome::SignInRequired);
    scheduler.resume();
    clock.advance(24 * 60 * 60_000);
    scheduler.connectivity_restored();
    assert!(scheduler.poll().is_none() && scheduler.sync_now().is_none());
    assert_eq!(scheduler.snapshot().phase, Phase::SignInRequired);
    scheduler.authorized();
    assert!(scheduler.poll().is_some());
}

#[test]
fn sleep_wake_and_backwards_clock_changes_never_start_a_catchup_burst() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    clock.advance(-100_000);
    assert_eq!(scheduler.wait_ms(), Some(1_800_000));
    clock.advance(8 * 60 * 60_000);
    let run = scheduler.poll().unwrap();
    assert!(scheduler.poll().is_none());
    scheduler.finish(run.id, receipt());
    assert_eq!(scheduler.wait_ms(), Some(1_800_000));
    assert!(scheduler.poll().is_none());
}

#[test]
fn successful_checks_and_actual_upstream_updates_are_distinct() {
    let clock = ManualClock::new();
    let mut scheduler = Scheduler::new(clock.clone(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    let first = scheduler.snapshot();
    assert_eq!(first.last_sync_ms, Some(1_000_000));
    assert_eq!(first.upstream_update_ms, Some(500_000));
    clock.advance(1_800_000);
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    let checked = scheduler.snapshot();
    assert_eq!(checked.last_sync_ms, Some(2_800_000));
    assert_eq!(checked.upstream_update_ms, first.upstream_update_ms);
    assert!(!checked.received_new_generation);
    let run = scheduler.sync_now().unwrap();
    scheduler.finish(run.id, Outcome::Offline);
    assert_eq!(scheduler.snapshot().last_sync_ms, checked.last_sync_ms);
    assert_eq!(scheduler.snapshot().generation, checked.generation);
}

#[test]
fn shutdown_cancels_background_work_and_forbids_any_new_worker() {
    let mut scheduler = Scheduler::new(ManualClock::new(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.shutdown();
    assert!(run.cancelled());
    assert_eq!(scheduler.snapshot().phase, Phase::Stopped);
    scheduler.finish(run.id, receipt());
    scheduler.resume();
    scheduler.authorized();
    assert!(scheduler.sync_now().is_none() && scheduler.poll().is_none());
    assert!(!scheduler.snapshot().running);
}

#[test]
fn missing_market_never_starts_a_download_or_silently_selects_an_internal_id() {
    let mut scheduler = Scheduler::new(ManualClock::new(), Settings::default(), true).unwrap();
    assert_eq!(scheduler.snapshot().phase, Phase::ChooseMarket);
    assert!(scheduler.sync_now().is_none() && scheduler.poll().is_none());
    scheduler.configure(connected(), true).unwrap();
    assert!(scheduler.poll().is_some());
}

#[test]
fn cancelling_one_download_does_not_immediately_restart_it() {
    let mut scheduler = Scheduler::new(ManualClock::new(), connected(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.cancel();
    assert!(run.cancelled() && scheduler.sync_now().is_none());
    scheduler.finish(run.id, Outcome::Cancelled);
    assert!(scheduler.poll().is_none());
    assert_eq!(scheduler.wait_ms(), Some(1_800_000));
    assert!(scheduler.sync_now().is_some());
}

#[test]
fn unrelated_settings_changes_preserve_deadlines_errors_and_retries() {
    let clock = ManualClock::new();
    let mut settings = connected();
    let mut scheduler = Scheduler::new(clock.clone(), settings.clone(), true).unwrap();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    clock.advance(60_000);
    scheduler.configure(settings.clone(), true).unwrap();
    assert_eq!(scheduler.wait_ms(), Some(1_740_000));
    settings.close_to_tray = false;
    scheduler.configure(settings.clone(), true).unwrap();
    assert_eq!(scheduler.wait_ms(), Some(1_740_000));
    let run = scheduler.sync_now().unwrap();
    scheduler.finish(run.id, Outcome::Offline);
    settings.error_notifications = false;
    scheduler.configure(settings.clone(), true).unwrap();
    assert_eq!(scheduler.snapshot().phase, Phase::Offline);
    assert_eq!(scheduler.wait_ms(), Some(30_000));
    scheduler.connectivity_restored();
    let run = scheduler.poll().unwrap();
    scheduler.finish(run.id, receipt());
    clock.advance(60_000);
    settings.interval_minutes = 15;
    scheduler.configure(settings, true).unwrap();
    assert_eq!(scheduler.wait_ms(), Some(840_000));
}
