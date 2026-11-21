//! One cancellable native download. Authentication is supplied by the native vault owner;
//! neither this engine nor the worker needs an open or visible WebView.
use crate::{
    cache::{Cache, Completion},
    client::{server_url, MarketClient},
    connection::Bootstrap,
    scheduler::{Clock, Run},
    worker::Execution,
    Error, Result,
};
use std::path::Path;

pub fn synchronize(
    client: &MarketClient,
    server: &str,
    path: &Path,
    run: &Run,
    local_override: Option<u32>,
    clock: &impl Clock,
    progress: &(dyn Fn(u32) + Send + Sync),
    bootstrap_changed: impl FnOnce(&Bootstrap),
) -> Result<Execution> {
    let cancelled = || {
        if run.cancelled() {
            Err(Error::Cancelled)
        } else {
            Ok(())
        }
    };
    let _sync=crate::performance::measure(crate::performance::Stage::MarketSync);
    crate::performance::operation(crate::performance::Operation::CheckingUpdates);
    cancelled()?;
    let bootstrap = client.bootstrap()?;
    cancelled()?;
    let selected = bootstrap
        .resolve_market(local_override)
        .map(|market| market.id);
    bootstrap_changed(&bootstrap);
    if selected != Some(run.market) {
        return Ok(Execution::MarketChanged(selected));
    }
    let market = bootstrap
        .markets
        .iter()
        .find(|market| market.id == run.market)
        .ok_or(Error::Invalid("selected market"))?;
    if bootstrap.device.is_some() {
        client.activity(Some(run.market), env!("CARGO_PKG_VERSION"))?;
    }
    cancelled()?;
    let server = server_url(server)?.to_string();
    let mut cache = Cache::open(path)?;
    let mut finished = false;
    crate::performance::operation(crate::performance::Operation::DownloadingMarket);
    for pages in 1..=10_000 {
        cancelled()?;
        let mut cursor = cache.cursor(&server, run.market)?;
        let page = match client.page(run.market, cursor.as_deref()) {
            Err(Error::ResetRequired) if cursor.is_some() => {
                cancelled()?;
                cache.reset(&server, run.market)?;
                cursor = None;
                client.page(run.market, None)?
            }
            value => value?,
        };
        cancelled()?;
        cache.apply(&server, run.market, cursor.as_deref(), &page)?;
        crate::performance::sqlite_size(path);
        crate::performance::checkpoint();
        progress(pages);
        if !page.has_more {
            finished = true;
            break;
        }
    }
    if !finished {
        return Err(Error::Invalid("synchronization exceeded safe page limit"));
    }
    cancelled()?;
    let target = cache
        .completed_target(&server, run.market)?
        .ok_or(Error::Invalid("completed cache generation"))?;
    crate::performance::operation(crate::performance::Operation::Verifying);
    let source = if target == "0" {
        market.source.clone()
    } else {
        client.provenance(run.market, &target)?
    };
    cancelled()?;
    crate::performance::operation(crate::performance::Operation::Verifying);
    let receipt = Completion {
        schema_version: 1,
        last_sync_ms: clock.now_ms(),
        source,
    };
    cache.record_completion(&server, run.market, &receipt)?;
    Ok(Execution::Completed(receipt))
}

/// Retry preparation within the current single-flight run. Completed price
/// downloads must not restart while Workshop is preparing its generation.
pub fn finish_preparing<T>(mut attempt:impl FnMut()->Result<T>,mut wait:impl FnMut(u64)->Result<()>)->Result<T> {
    loop {match attempt() {
        Err(Error::SummaryPreparing(seconds))=>wait(seconds.clamp(1,3600))?,
        result=>return result,
    }}
}

pub fn wait_preparing(seconds:u64,cancelled:impl Fn()->bool)->Result<()> {
    let until=std::time::Instant::now()+std::time::Duration::from_secs(seconds.clamp(1,3600));
    loop {
        if cancelled(){return Err(Error::Cancelled)}
        let remaining=until.saturating_duration_since(std::time::Instant::now());
        if remaining.is_zero(){return Ok(())}
        std::thread::sleep(remaining.min(std::time::Duration::from_millis(50)));
    }
}

#[cfg(test)]
mod preparation_tests {
    use super::*;
    #[test]
    fn preparing_retries_delivery_and_respects_server_delay() {
        let mut attempts=0;let mut waits=Vec::new();
        let value=finish_preparing(||{attempts+=1;if attempts<=3{Err(Error::SummaryPreparing(5))}else{Ok("published")}},|s|{waits.push(s);Ok(())}).unwrap();
        assert_eq!(value,"published");assert_eq!(attempts,4);assert_eq!(waits,vec![5,5,5]);
    }
    #[test]
    fn cancellation_stops_before_another_delivery_request() {
        let mut attempts=0;
        let result:Result<()>=finish_preparing(||{attempts+=1;Err(Error::SummaryPreparing(3600))},|_|Err(Error::Cancelled));
        assert!(matches!(result,Err(Error::Cancelled)));assert_eq!(attempts,1);
        let before=std::time::Instant::now();assert!(matches!(wait_preparing(3600,||true),Err(Error::Cancelled)));assert!(before.elapsed()<std::time::Duration::from_millis(100));
    }
    #[test]
    fn other_failures_return_to_worker_backoff_without_busy_loop() {
        let mut attempts=0;let result:Result<()>=finish_preparing(||{attempts+=1;Err(Error::Network)},|_|panic!("not preparation"));
        assert!(matches!(result,Err(Error::Network)));assert_eq!(attempts,1);
    }
}
