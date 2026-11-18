//! Bounded opt-in timings. Never records URLs, cursors, credentials or item data.
use serde::Serialize;
use std::{cell::RefCell, collections::BTreeMap, sync::{Arc,Mutex}, time::Instant};
#[derive(Clone,Copy,Debug,PartialEq,Eq,PartialOrd,Ord,Serialize)]
#[serde(rename_all="snake_case")]
pub enum Stage { Bootstrap,Activity,MarketSync,NetworkHeaders,NetworkTransfer,JsonParse,Validation,SqliteOpen,SqliteTransaction,SqliteStaging,SqliteActivation,SqliteCommit,Provenance,ArchiveSync,ArchiveValidation,ArchiveActivation,WorkshopSync,WorkshopDownload,WorkshopValidation,WorkshopPublication,HashVerification,FilePublication }
#[derive(Clone,Copy,Debug,PartialEq,Eq,PartialOrd,Ord,Serialize)]
#[serde(rename_all="snake_case")]
pub enum Counter { HttpRequests,ResponseBodyBytes,Pages,ReceivedRecords,Upserts,Deletes,ScannedRecords,UnchangedRecords }
#[derive(Clone,Default,Serialize)]
pub struct Timing { pub calls:u64,pub elapsed_us:u64 }
#[derive(Clone,Default,Serialize)]
pub struct Report {pub elapsed_us:u64,pub stages:BTreeMap<Stage,Timing>,pub counters:BTreeMap<Counter,u64>,pub peak_sqlite_bytes:u64,pub peak_wal_bytes:u64}
thread_local! { static CURRENT:RefCell<Option<Arc<Mutex<Report>>>>=const { RefCell::new(None) }; }
pub struct Capture {report:Arc<Mutex<Report>>,previous:Option<Arc<Mutex<Report>>>,started:Instant}
impl Capture {
    pub fn begin()->Self {let report=Arc::new(Mutex::new(Report::default()));let previous=CURRENT.with(|slot|slot.replace(Some(report.clone())));Self{report,previous,started:Instant::now()}}
    pub fn report(&self)->Report {let mut result=self.report.lock().unwrap_or_else(|p|p.into_inner()).clone();result.elapsed_us=self.started.elapsed().as_micros().min(u64::MAX as u128) as u64;result}
}
impl Drop for Capture {fn drop(&mut self){CURRENT.with(|slot|slot.replace(self.previous.take()));}}
pub struct Span {report:Option<Arc<Mutex<Report>>>,stage:Stage,started:Option<Instant>}
pub fn measure(stage:Stage)->Span {let report=CURRENT.with(|slot|slot.borrow().clone());let started=report.as_ref().map(|_|Instant::now());Span{report,stage,started}}
impl Drop for Span {fn drop(&mut self){if let (Some(report),Some(start))=(&self.report,self.started){if let Ok(mut report)=report.lock(){let value=report.stages.entry(self.stage).or_default();value.calls=value.calls.saturating_add(1);value.elapsed_us=value.elapsed_us.saturating_add(start.elapsed().as_micros().min(u64::MAX as u128) as u64);}}}}
pub fn add(key:Counter,count:u64){CURRENT.with(|slot|{if let Some(report)=slot.borrow().as_ref(){if let Ok(mut report)=report.lock(){let value=report.counters.entry(key).or_default();*value=value.saturating_add(count);}}});}
pub fn sqlite_size(path:&std::path::Path){CURRENT.with(|slot|{if let Some(report)=slot.borrow().as_ref(){let size=|p:&std::path::Path|std::fs::metadata(p).map(|m|m.len()).unwrap_or(0);let bytes=size(path);let mut wal=path.as_os_str().to_os_string();wal.push("-wal");let wal=size(std::path::Path::new(&wal));if let Ok(mut report)=report.lock(){report.peak_sqlite_bytes=report.peak_sqlite_bytes.max(bytes);report.peak_wal_bytes=report.peak_wal_bytes.max(wal);}}});}
