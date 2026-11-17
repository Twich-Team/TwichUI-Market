use super::wire::{id, need, Entry, Envelope, Header, Order, Page};
use crate::{
    bridge::{canonical, parse, validation::hash, Scope},
    Error, Result,
};
use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    path::{Path, PathBuf},
};
pub const DEFAULT_DISK_BUDGET: u64 = 4 * 1024 * 1024 * 1024;

#[derive(Clone, Default, serde::Serialize)]
pub struct ArchiveMetrics {
    pub pages_applied: u64,
    pub received_bytes: u64,
    pub final_validation_us: u64,
    pub promotion_us: u64,
}
pub struct ArchiveStore {
    pub(super) db: Connection,
    path: Option<PathBuf>,
    budget: u64,
    metrics: ArchiveMetrics,
}
impl ArchiveStore {
    pub fn open(path: &Path, budget: u64) -> Result<Self> {
        let db = Connection::open(path)?;
        let result = Self::initialize(db, Some(path.to_path_buf()), budget)?;
        let check: String = result
            .db
            .query_row("PRAGMA quick_check(1)", [], |r| r.get(0))?;
        need(check == "ok", "archive SQLite integrity")?;
        Ok(result)
    }
    pub fn memory(budget: u64) -> Result<Self> {
        Self::initialize(Connection::open_in_memory()?, None, budget)
    }
    fn initialize(db: Connection, path: Option<PathBuf>, budget: u64) -> Result<Self> {
        need(
            (65536..=64 * 1024 * 1024 * 1024).contains(&budget),
            "archive disk budget",
        )?;
        let version: u32 = db.pragma_query_value(None, "user_version", |r| r.get(0))?;
        need(version <= 1, "newer archive schema")?;
        db.busy_timeout(std::time::Duration::from_secs(5))?;
        db.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA wal_autocheckpoint=1000;
          CREATE TABLE IF NOT EXISTS history_headers(scope TEXT NOT NULL,slot TEXT NOT NULL,header TEXT NOT NULL,cursor TEXT,position INTEGER NOT NULL,chain TEXT NOT NULL,last_key TEXT,completed_at TEXT,PRIMARY KEY(scope,slot));
          CREATE TABLE IF NOT EXISTS history_entries(scope TEXT NOT NULL,phase INTEGER NOT NULL,source_id INTEGER NOT NULL,item_id INTEGER NOT NULL,variant TEXT NOT NULL,snapshot_ref INTEGER NOT NULL,at_us INTEGER NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(scope,phase,source_id,item_id,variant));
          CREATE TABLE IF NOT EXISTS history_stage(scope TEXT NOT NULL,phase INTEGER NOT NULL,source_id INTEGER NOT NULL,item_id INTEGER NOT NULL,variant TEXT NOT NULL,snapshot_ref INTEGER NOT NULL,at_us INTEGER NOT NULL,day TEXT NOT NULL,value TEXT NOT NULL,sha256 TEXT NOT NULL,PRIMARY KEY(scope,phase,source_id,item_id,variant));
          CREATE TABLE IF NOT EXISTS history_members(scope TEXT NOT NULL,checkpoint TEXT NOT NULL,phase INTEGER NOT NULL,source_id INTEGER NOT NULL,PRIMARY KEY(scope,checkpoint,phase,source_id));
          CREATE TABLE IF NOT EXISTS history_selections(scope TEXT PRIMARY KEY,request TEXT NOT NULL);
          CREATE INDEX IF NOT EXISTS history_variant_identity ON history_entries(scope,phase,item_id,variant,source_id);
          CREATE INDEX IF NOT EXISTS history_observation_time ON history_entries(scope,phase,at_us,source_id);
          CREATE INDEX IF NOT EXISTS history_observation_day ON history_entries(scope,phase,day,source_id);
          PRAGMA user_version=1;")?;
        let page_size: u64 = db.pragma_query_value(None, "page_size", |r| unsigned(r, 0))?;
        db.pragma_update(None, "max_page_count", (budget / page_size) as i64)?;
        Ok(Self {
            db,
            path,
            budget,
            metrics: ArchiveMetrics::default(),
        })
    }
    fn storage(db: &Connection, path: Option<&Path>, budget: u64, extra: u64) -> Result<()> {
        let count: u64 = db.pragma_query_value(None, "page_count", |r| unsigned(r, 0))?;
        let size: u64 = db.pragma_query_value(None, "page_size", |r| unsigned(r, 0))?;
        let wal = path
            .and_then(|p| std::fs::metadata(format!("{}-wal", p.display())).ok())
            .map(|m| m.len())
            .unwrap_or(0);
        let used = count
            .saturating_mul(size)
            .saturating_add(wal)
            .saturating_add(extra);
        if used > budget {
            return Err(Error::Capacity {
                limit: "archive_disk",
                actual: used,
                maximum: budget,
            });
        }
        if let Some(parent) = path.and_then(Path::parent) {
            let free = available(parent)?;
            let required = extra.saturating_add(16 * 1024 * 1024);
            if free < required {
                return Err(Error::Capacity {
                    limit: "free_disk_space",
                    actual: required,
                    maximum: free,
                });
            }
        }
        Ok(())
    }
    pub fn metrics(&self) -> ArchiveMetrics {
        self.metrics.clone()
    }
    pub fn allocated_bytes(&self) -> Result<u64> {
        let count: u64 = self
            .db
            .pragma_query_value(None, "page_count", |r| unsigned(r, 0))?;
        let size: u64 = self
            .db
            .pragma_query_value(None, "page_size", |r| unsigned(r, 0))?;
        Ok(count * size)
    }
    pub fn active(&self, scope: &Scope) -> Result<Option<Header>> {
        self.header(scope, "active")
    }
    pub fn previous(&self, scope: &Scope) -> Result<Option<Header>> {
        self.header(scope, "previous")
    }
    fn header(&self, scope: &Scope, slot: &str) -> Result<Option<Header>> {
        let raw: Option<String> = self
            .db
            .query_row(
                "SELECT header FROM history_headers WHERE scope=?1 AND slot=?2",
                params![super::coverage_key(scope)?, slot],
                |r| r.get(0),
            )
            .optional()?;
        raw.map(|s| {
            let h: Header = serde_json::from_value(parse(s.as_bytes(), 65536)?)?;
            h.validate(scope)?;
            Ok(h)
        })
        .transpose()
    }
    pub fn pending(&self, scope: &Scope) -> Result<Option<(Header, String)>> {
        let raw: Option<String> = self
            .db
            .query_row(
                "SELECT cursor FROM history_headers WHERE scope=?1 AND slot='staging'",
                [super::coverage_key(scope)?],
                |r| r.get(0),
            )
            .optional()?;
        raw.map(|cursor| {
            Ok((
                self.header(scope, "staging")?
                    .ok_or(Error::Invalid("archive staging"))?,
                cursor,
            ))
        })
        .transpose()
    }
    pub fn abandon_pending(&mut self, scope: &Scope) -> Result<()> {
        let key = super::coverage_key(scope)?;
        let tx = self.db.transaction()?;
        tx.execute("DELETE FROM history_stage WHERE scope=?1", [&key])?;
        tx.execute(
            "DELETE FROM history_headers WHERE scope=?1 AND slot='staging'",
            [key],
        )?;
        tx.commit()?;
        Ok(())
    }
    pub fn begin(&mut self, scope: &Scope, raw: &[u8]) -> Result<()> {
        let envelope: Envelope = serde_json::from_value(parse(raw, 131072)?)?;
        let h = envelope.header;
        h.validate(scope)?;
        need(
            !envelope.cursor.is_empty() && envelope.cursor.len() <= 2048,
            "archive initial cursor",
        )?;
        if let Some(base) = &h.base_checkpoint_id {
            need(
                self.active(scope)?.is_some_and(|old| {
                    old.checkpoint_id == *base
                        && old.watermark_observation_id == h.base_watermark_observation_id
                        && old.issuer_id == h.issuer_id
                        && old.market == h.market
                }),
                "archive incremental base",
            )?;
        }
        let estimate = h
            .transfer_bytes
            .saturating_mul(2)
            .saturating_add(h.transferred().saturating_mul(256));
        Self::storage(&self.db, self.path.as_deref(), self.budget, estimate)?;
        let key = super::coverage_key(scope)?;
        let tx = self.db.transaction()?;
        tx.execute("DELETE FROM history_stage WHERE scope=?1", [&key])?;
        tx.execute(
            "DELETE FROM history_headers WHERE scope=?1 AND slot='staging'",
            [&key],
        )?;
        tx.execute(
            "INSERT INTO history_headers VALUES(?1,'staging',?2,?3,0,?4,NULL,NULL)",
            params![
                key,
                String::from_utf8(canonical(&serde_json::to_value(h)?)?).unwrap(),
                envelope.cursor,
                "0".repeat(64)
            ],
        )?;
        tx.commit()?;
        Ok(())
    }
    pub fn apply(&mut self, scope: &Scope, requested: &str, raw: &[u8]) -> Result<bool> {
        let page: Page = serde_json::from_value(parse(raw, 1024 * 1024)?)?;
        let key = super::coverage_key(scope)?;
        let (header, cursor) = self
            .pending(scope)?
            .ok_or(Error::Invalid("archive pending download"))?;
        need(
            cursor == requested
                && page.format == "twichui-history-archive-page"
                && page.protocol_version == header.protocol_version
                && page.checkpoint_id == header.checkpoint_id
                && page.account_id == scope.account_id
                && page.market_id == scope.market_id
                && page.entries.len() <= 100,
            "archive page identity/order",
        )?;
        let (position, chain, last): (u64, String, Option<String>) = self.db.query_row(
            "SELECT position,chain,last_key FROM history_headers WHERE scope=?1 AND slot='staging'",
            [&key],
            |r| Ok((unsigned(r, 0)?, r.get(1)?, r.get(2)?)),
        )?;
        let end = position
            .checked_add(page.entries.len() as u64)
            .ok_or(Error::Invalid("archive count overflow"))?;
        need(
            page.offset == position
                && page.previous_sha256 == chain
                && end <= header.transferred()
                && page.has_more == (end < header.transferred())
                && (!page.has_more || !page.entries.is_empty())
                && page.has_more == page.next_cursor.is_some()
                && page
                    .next_cursor
                    .as_ref()
                    .is_none_or(|s| !s.is_empty() && s.len() <= 2048),
            "archive page continuity",
        )?;
        need(
            hash(&Value::Array(page.entries.clone()))? == page.page_sha256,
            "archive page digest",
        )?;
        let previous = decode_hex(&chain)?;
        let mut hasher = Sha256::new();
        hasher.update(previous);
        hasher.update(canonical(&Value::Array(page.entries.clone()))?);
        need(
            format!("{:x}", hasher.finalize()) == page.chain_sha256,
            "archive chain digest",
        )?;
        let mut last: Option<Order> = last.map(|s| serde_json::from_str(&s)).transpose()?;
        let mut rows = Vec::new();
        for value in &page.entries {
            let entry: Entry = serde_json::from_value(value.clone())?;
            entry.validate(&header)?;
            let order = entry.order()?;
            need(
                last.as_ref().is_none_or(|old| order > *old),
                "archive duplicate/unordered entry",
            )?;
            let (snapshot_ref, at_us, day) = match &entry {
                Entry::Observation { observation: o } => (
                    id(o["snapshot_id"].as_str().unwrap())?,
                    super::wire::time_value(&o["observed_at"])?.timestamp_micros(),
                    o["utc_day"].as_str().unwrap().to_owned(),
                ),
                Entry::Snapshot { snapshot_id, .. } | Entry::Variant { snapshot_id, .. } => {
                    (id(snapshot_id)?, 0, String::new())
                }
            };
            if header.base_checkpoint_id.is_some() && order.0 == 0 {
                need(
                    order.1 > header.base_watermark_observation_id.parse::<u64>().unwrap(),
                    "archive incremental observation",
                )?;
            }
            let encoded = canonical(value)?;
            need(encoded.len() <= 65536, "archive entry bytes")?;
            let sum = format!("{:x}", Sha256::digest(&encoded));
            rows.push((
                order.clone(),
                snapshot_ref,
                at_us,
                day,
                String::from_utf8(encoded).unwrap(),
                sum,
            ));
            last = Some(order);
        }
        Self::storage(
            &self.db,
            self.path.as_deref(),
            self.budget,
            raw.len() as u64 * 3,
        )?;
        let tx = self.db.transaction()?;
        for (o, sid, at, day, value, sum) in rows {
            tx.execute(
                "INSERT INTO history_stage VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10)",
                params![key, o.0, o.1 as i64, o.2, o.3, sid as i64, at, day, value, sum],
            )?;
        }
        tx.execute("UPDATE history_headers SET cursor=?2,position=?3,chain=?4,last_key=?5 WHERE scope=?1 AND slot='staging'",params![key,page.next_cursor,end as i64,page.chain_sha256,last.map(|x|serde_json::to_string(&x)).transpose()?])?;
        let mut validation_us = 0;
        let mut promoted = None;
        if !page.has_more {
            let started = std::time::Instant::now();
            complete(&tx, &key, &header)?;
            validation_us = started.elapsed().as_micros() as u64;
            promoted = Some(std::time::Instant::now());
            // Set-based promotion shares immutable evidence with prior checkpoints;
            // no archive-sized serde_json::Value or whole-history clone exists.
            Self::storage(
                &tx,
                self.path.as_deref(),
                self.budget,
                header
                    .transfer_bytes
                    .saturating_add(header.transferred() * 128),
            )?;
            if let Some(base) = &header.base_checkpoint_id {
                tx.execute("INSERT INTO history_members SELECT scope,?2,phase,source_id FROM history_members WHERE scope=?1 AND checkpoint=?3",params![key,header.checkpoint_id,base])?;
            }
            tx.execute("INSERT OR IGNORE INTO history_members SELECT scope,?2,phase,source_id FROM history_stage WHERE scope=?1 AND phase<2",params![key,header.checkpoint_id])?;
            tx.execute(
                "INSERT OR IGNORE INTO history_entries SELECT * FROM history_stage WHERE scope=?1",
                [&key],
            )?;
            tx.execute("DELETE FROM history_stage WHERE scope=?1", [&key])?;
            let active: Option<String> = tx
                .query_row(
                    "SELECT header FROM history_headers WHERE scope=?1 AND slot='active'",
                    [&key],
                    |r| r.get(0),
                )
                .optional()?;
            let same = active
                .map(|s| serde_json::from_str::<Header>(&s))
                .transpose()?
                .is_some_and(|h| h.checkpoint_id == header.checkpoint_id);
            if !same {
                tx.execute(
                    "DELETE FROM history_headers WHERE scope=?1 AND slot='previous'",
                    [&key],
                )?;
                tx.execute("INSERT INTO history_headers SELECT scope,'previous',header,cursor,position,chain,last_key,completed_at FROM history_headers WHERE scope=?1 AND slot='active'",[&key])?;
            }
            tx.execute(
                "DELETE FROM history_headers WHERE scope=?1 AND slot='active'",
                [&key],
            )?;
            tx.execute("UPDATE history_headers SET slot='active',completed_at=?2 WHERE scope=?1 AND slot='staging'",params![key,Utc::now().to_rfc3339()])?;
            tx.execute("DELETE FROM history_members WHERE scope=?1 AND checkpoint NOT IN (SELECT json_extract(header,'$.checkpoint_id') FROM history_headers WHERE scope=?1 AND slot IN ('active','previous'))",[&key])?;
        }
        tx.commit()?;
        self.metrics.pages_applied += 1;
        self.metrics.received_bytes += raw.len() as u64;
        self.metrics.final_validation_us += validation_us;
        if let Some(at) = promoted {
            self.metrics.promotion_us += at.elapsed().as_micros() as u64;
        }
        Ok(page.has_more)
    }
    pub fn save_selection(&mut self, scope: &Scope, request: &Value) -> Result<()> {
        super::scoped::selection(request)?;
        let h = self
            .active(scope)?
            .ok_or(Error::Invalid("complete an archive first"))?;
        need(
            request["market"] == h.market
                && request["issuer_id"] == h.issuer_id
                && request["pricing_algorithm"] == h.pricing_algorithm,
            "archive selection context",
        )?;
        self.db.execute("INSERT INTO history_selections VALUES(?1,?2) ON CONFLICT(scope) DO UPDATE SET request=excluded.request",params![super::coverage_key(scope)?,String::from_utf8(canonical(request)?).unwrap()])?;
        Ok(())
    }
    pub fn selection(&self, scope: &Scope) -> Result<Option<Value>> {
        let s: Option<String> = self
            .db
            .query_row(
                "SELECT request FROM history_selections WHERE scope=?1",
                [super::coverage_key(scope)?],
                |r| r.get(0),
            )
            .optional()?;
        s.map(|s| parse(s.as_bytes(), 128 * 1024)).transpose()
    }
    pub(super) fn checked(raw: String, sum: String) -> Result<Value> {
        need(
            format!("{:x}", Sha256::digest(raw.as_bytes())) == sum,
            "archive stored evidence checksum",
        )?;
        parse(raw.as_bytes(), 65536)
    }
}
fn complete(db: &Connection, key: &str, h: &Header) -> Result<()> {
    let mismatch:bool=db.query_row("SELECT EXISTS(SELECT 1 FROM history_stage s JOIN history_entries e ON s.scope=e.scope AND s.phase=e.phase AND s.source_id=e.source_id AND s.item_id=e.item_id AND s.variant=e.variant WHERE s.scope=?1 AND s.value<>e.value)",[key],|r|r.get(0))?;
    need(!mismatch, "immutable archive evidence changed")?;
    let counts = (0..3)
        .map(|phase| {
            db.query_row(
                "SELECT count(*) FROM history_stage WHERE scope=?1 AND phase=?2",
                params![key, phase],
                |r| unsigned(r, 0),
            )
        })
        .collect::<std::result::Result<Vec<_>, _>>()?;
    need(
        counts
            == [
                h.transfer_observations,
                h.transfer_snapshots,
                h.transfer_records,
            ],
        "archive incomplete transfer",
    )?;
    let transferred = db.query_row(
        "SELECT coalesce(sum(length(CAST(value AS BLOB))+1),0) FROM history_stage WHERE scope=?1",
        [key],
        |r| unsigned(r, 0),
    )?;
    need(
        transferred == h.transfer_bytes,
        "archive transfer byte count",
    )?;
    // Full metadata digest is independently reconstructed from trusted old and new
    // rows; source pruning or missing bootstrap members cannot silently promote.
    let union="SELECT e.phase,e.source_id,e.value,e.sha256,e.snapshot_ref FROM history_entries e JOIN history_members m ON e.scope=m.scope AND e.phase=m.phase AND e.source_id=m.source_id WHERE e.scope=?1 AND m.checkpoint=?2 AND e.phase<2 UNION ALL SELECT s.phase,s.source_id,s.value,s.sha256,s.snapshot_ref FROM history_stage s WHERE s.scope=?1 AND s.phase<2 AND NOT EXISTS(SELECT 1 FROM history_members m WHERE m.scope=s.scope AND m.checkpoint=?2 AND m.phase=s.phase AND m.source_id=s.source_id) ORDER BY phase,source_id";
    let mut statement = db.prepare(union)?;
    let mut rows = statement.query(params![key, h.base_checkpoint_id.as_deref().unwrap_or("")])?;
    let mut sha = Sha256::new();
    let mut meta_counts = [0u64; 2];
    let mut snapshots = BTreeMap::new();
    let mut observed_snapshots = std::collections::BTreeSet::new();
    let mut maximum_observation = 0;
    let mut days = std::collections::BTreeSet::new();
    while let Some(r) = rows.next()? {
        let phase = r.get::<_, u8>(0)? as usize;
        let source: u64 = unsigned(r, 1)?;
        let value = ArchiveStore::checked(r.get(2)?, r.get(3)?)?;
        sha.update(canonical(&value)?);
        sha.update(b"\n");
        meta_counts[phase] += 1;
        if phase == 1 {
            snapshots.insert(source, value);
        } else {
            maximum_observation = maximum_observation.max(source);
            days.insert(value["observation"]["utc_day"].as_str().unwrap().to_owned());
            observed_snapshots.insert((
                unsigned(r, 4)?,
                value["observation"]["snapshot_content_sha256"]
                    .as_str()
                    .unwrap()
                    .to_owned(),
            ));
        }
    }
    need(
        meta_counts == [h.total_observations, h.total_snapshots]
            && format!("{:x}", sha.finalize()) == h.metadata_sha256,
        "archive metadata completeness/digest",
    )?;
    need(
        observed_snapshots.iter().all(|(sid, sum)| {
            snapshots
                .get(sid)
                .is_some_and(|s| s["content_sha256"] == *sum)
        }) && observed_snapshots.len() == snapshots.len()
            && maximum_observation == id(&h.watermark_observation_id)?,
        "archive missing snapshot reference",
    )?;
    need(
        days.first() == Some(&h.retained_from_day) && days.last() == Some(&h.retained_through_day),
        "archive retained date coverage",
    )?;
    // Verify each transferred snapshot in a single ordered row stream.
    let mut digests: BTreeMap<u64, (u64, u64, Sha256)> = BTreeMap::new();
    let mut q=db.prepare("SELECT source_id,value,sha256 FROM history_stage WHERE scope=?1 AND phase=2 ORDER BY source_id,item_id,variant")?;
    let mut r = q.query([key])?;
    while let Some(row) = r.next()? {
        let sid: u64 = unsigned(row, 0)?;
        need(
            snapshots.contains_key(&sid),
            "archive variant snapshot reference",
        )?;
        let value = ArchiveStore::checked(row.get(1)?, row.get(2)?)?;
        let raw = canonical(&value)?;
        let d = digests.entry(sid).or_insert_with(|| (0, 0, Sha256::new()));
        d.0 += 1;
        d.1 += raw.len() as u64 + 1;
        d.2.update(raw);
        d.2.update(b"\n");
    }
    let mut q = db.prepare("SELECT source_id FROM history_stage WHERE scope=?1 AND phase=1")?;
    for sid in q.query_map([key], |r| unsigned(r, 0))? {
        let sid = sid?;
        let d = digests
            .remove(&sid)
            .unwrap_or_else(|| (0, 0, Sha256::new()));
        let s = &snapshots[&sid];
        need(
            s["record_count"] == d.0
                && s["records_bytes"] == d.1
                && s["records_sha256"] == format!("{:x}", d.2.finalize()),
            "archive snapshot record integrity",
        )?;
    }
    need(
        digests.is_empty(),
        "archive variants without transferred snapshot",
    )?;
    let total: u64 = snapshots
        .values()
        .map(|s| s["record_count"].as_u64().unwrap_or(u64::MAX))
        .try_fold(0u64, |a, b| a.checked_add(b))
        .ok_or(Error::Invalid("archive record total"))?;
    need(total == h.total_records, "archive total records")?;
    Ok(())
}
fn decode_hex(s: &str) -> Result<Vec<u8>> {
    need(super::wire::hex(s), "archive chain hex")?;
    (0..32)
        .map(|i| {
            u8::from_str_radix(&s[2 * i..2 * i + 2], 16)
                .map_err(|_| Error::Invalid("archive chain hex"))
        })
        .collect()
}
#[cfg(unix)]
fn available(path: &Path) -> Result<u64> {
    use std::{ffi::CString, os::unix::ffi::OsStrExt};
    let path =
        CString::new(path.as_os_str().as_bytes()).map_err(|_| Error::Invalid("archive path"))?;
    let mut info = std::mem::MaybeUninit::<libc::statvfs>::uninit();
    if unsafe { libc::statvfs(path.as_ptr(), info.as_mut_ptr()) } != 0 {
        return Err(std::io::Error::last_os_error().into());
    }
    let info = unsafe { info.assume_init() };
    Ok((info.f_bavail as u64).saturating_mul(info.f_frsize as u64))
}
#[cfg(windows)]
fn available(path: &Path) -> Result<u64> {
    use std::os::windows::ffi::OsStrExt;
    let wide = path
        .as_os_str()
        .encode_wide()
        .chain(Some(0))
        .collect::<Vec<_>>();
    let mut free = 0u64;
    if unsafe {
        windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW(
            wide.as_ptr(),
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

pub(super) fn unsigned(row: &rusqlite::Row<'_>, column: usize) -> rusqlite::Result<u64> {
    let n: i64 = row.get(column)?;
    u64::try_from(n).map_err(|_| rusqlite::Error::IntegralValueOutOfRange(column, n))
}

#[cfg(test)]
mod disk_tests {
    use super::*;
    #[test]
    fn sqlite_full_rolls_back_progress_and_preserves_completed_pointer() {
        let mut store = ArchiveStore::memory(64 * 1024 * 1024).unwrap();
        store.db.execute("INSERT INTO history_headers VALUES('scope','active','completed',NULL,0,'chain',NULL,'receipt')",[]).unwrap();
        store.db.execute("INSERT INTO history_headers VALUES('scope','staging','candidate','before',0,'chain',NULL,NULL)",[]).unwrap();
        let pages: i64 = store
            .db
            .pragma_query_value(None, "page_count", |r| r.get(0))
            .unwrap();
        store
            .db
            .pragma_update(None, "max_page_count", pages)
            .unwrap();
        {
            let tx = store.db.transaction().unwrap();
            tx.execute(
                "UPDATE history_headers SET cursor='after' WHERE slot='staging'",
                [],
            )
            .unwrap();
            let error=tx.execute("INSERT INTO history_stage VALUES('scope',2,1,1,'key',1,0,'',zeroblob(65536),'sha')",[]).unwrap_err();
            assert!(
                matches!(error,rusqlite::Error::SqliteFailure(ref e,_) if e.code==rusqlite::ErrorCode::DiskFull)
            );
            // SQLite may already have rolled back after SQLITE_FULL. Drop is safe.
        }
        let (cursor,active):(String,String)=store.db.query_row("SELECT (SELECT cursor FROM history_headers WHERE slot='staging'),(SELECT header FROM history_headers WHERE slot='active')",[],|r|Ok((r.get(0)?,r.get(1)?))).unwrap();
        assert_eq!(cursor, "before");
        assert_eq!(active, "completed");
    }
}
