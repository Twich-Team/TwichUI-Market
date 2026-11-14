use crate::{
    protocol::{Operation, Page, Valuation, ALGORITHM},
    Error, Result,
};
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::{io::Write, path::Path};

pub struct Cache {
    db: Connection,
}

#[derive(Debug, Serialize)]
pub struct Status {
    pub market_id: u32,
    pub item_count: u64,
    pub downloading: bool,
    pub observed_at: Option<String>,
    pub has_completed_cache: bool,
    pub synthetic: bool,
}

#[derive(Serialize)]
pub struct Item {
    pub item_id: u32,
    pub variant_key: String,
    pub value: Valuation,
}

/// Nonsecret local completion receipt; optional additive table remains readable by v1.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Completion {
    pub schema_version: u32,
    pub last_sync_ms: i64,
    pub source: crate::connection::Provenance,
}

impl Cache {
    pub fn open(path: &Path) -> Result<Self> {
        Self::initialize(Connection::open(path)?)
    }
    pub fn memory() -> Result<Self> {
        Self::initialize(Connection::open_in_memory()?)
    }
    fn initialize(db: Connection) -> Result<Self> {
        db.busy_timeout(std::time::Duration::from_secs(5))?;
        let version: u32 = db.pragma_query_value(None, "user_version", |row| row.get(0))?;
        if version > 2 {
            return Err(Error::Invalid("newer cache schema"));
        }
        db.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA max_page_count=32768;
            CREATE TABLE IF NOT EXISTS state(server TEXT NOT NULL, market INTEGER NOT NULL, cursor TEXT,
                downloading INTEGER NOT NULL DEFAULT 0, target TEXT, observed_at TEXT, completed INTEGER NOT NULL DEFAULT 0, synthetic INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(server,market));
            CREATE TABLE IF NOT EXISTS active(server TEXT NOT NULL, market INTEGER NOT NULL, item INTEGER NOT NULL,
                variant TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(server,market,item,variant));
            CREATE TABLE IF NOT EXISTS staging(server TEXT NOT NULL, market INTEGER NOT NULL, item INTEGER NOT NULL,
                variant TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(server,market,item,variant));
            CREATE TABLE IF NOT EXISTS completion(server TEXT NOT NULL, market INTEGER NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY(server,market));
            ")?;
        let has_synthetic = {
            let mut statement = db.prepare("PRAGMA table_info(state)")?;
            let names = statement.query_map([], |row| row.get::<_, String>(1))?;
            names
                .collect::<std::result::Result<Vec<_>, _>>()?
                .iter()
                .any(|name| name == "synthetic")
        };
        if !has_synthetic {
            db.execute_batch("ALTER TABLE state ADD COLUMN synthetic INTEGER NOT NULL DEFAULT 0;")?;
        }
        if version != 2 {
            db.pragma_update(None, "user_version", 2)?;
        }
        Ok(Self { db })
    }
    pub fn cursor(&self, server: &str, market: u32) -> Result<Option<String>> {
        Ok(self
            .db
            .query_row(
                "SELECT cursor FROM state WHERE server=?1 AND market=?2",
                params![server, market],
                |row| row.get(0),
            )
            .optional()?
            .flatten())
    }
    pub fn completed_target(&self, server: &str, market: u32) -> Result<Option<String>> {
        Ok(self.db.query_row("SELECT target FROM state WHERE server=?1 AND market=?2 AND completed=1 AND downloading=0",
            params![server,market], |row|row.get(0)).optional()?.flatten())
    }
    pub fn record_completion(
        &mut self,
        server: &str,
        market: u32,
        receipt: &Completion,
    ) -> Result<()> {
        receipt.source.validate(market)?;
        let target = self.completed_target(server, market)?;
        let expected = receipt
            .source
            .watermark_observation_id
            .as_deref()
            .unwrap_or("0");
        if receipt.schema_version != 1 || target.as_deref() != Some(expected) {
            return Err(Error::Invalid(
                "completion receipt does not match the committed cache",
            ));
        }
        self.db.execute("INSERT INTO completion(server,market,value) VALUES(?1,?2,?3) ON CONFLICT(server,market) DO UPDATE SET value=excluded.value",
            params![server,market,serde_json::to_string(receipt)?])?;
        Ok(())
    }
    pub fn completion(&self, server: &str, market: u32) -> Result<Option<Completion>> {
        let value: Option<String> = self
            .db
            .query_row(
                "SELECT value FROM completion WHERE server=?1 AND market=?2",
                params![server, market],
                |row| row.get(0),
            )
            .optional()?;
        value
            .map(|value| {
                if value.len() > 4096 {
                    return Err(Error::Invalid("completion receipt size"));
                }
                let receipt: Completion = serde_json::from_str(&value)?;
                receipt.source.validate(market)?;
                if receipt.schema_version != 1 {
                    return Err(Error::Invalid("completion receipt version"));
                }
                Ok(receipt)
            })
            .transpose()
    }
    pub fn reset(&mut self, server: &str, market: u32) -> Result<()> {
        let tx = self.db.transaction()?;
        tx.execute("UPDATE state SET cursor=NULL, downloading=0, target=NULL WHERE server=?1 AND market=?2",params![server,market])?;
        tx.execute(
            "DELETE FROM staging WHERE server=?1 AND market=?2",
            params![server, market],
        )?;
        tx.commit()?;
        Ok(())
    }
    pub fn apply(
        &mut self,
        server: &str,
        market: u32,
        requested_cursor: Option<&str>,
        page: &Page,
    ) -> Result<()> {
        page.validate(market)?;
        let tx = self.db.transaction()?;
        tx.execute(
            "INSERT OR IGNORE INTO state(server,market) VALUES(?1,?2)",
            params![server, market],
        )?;
        let (saved, downloading, target, completed): (Option<String>, bool, Option<String>, bool) = tx.query_row(
            "SELECT cursor,downloading,target,completed FROM state WHERE server=?1 AND market=?2",
            params![server, market],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        )?;
        if saved.as_deref() != requested_cursor
            || (downloading && target.as_deref() != Some(&page.target_observation_id))
        {
            return Err(Error::Invalid("stale page or changed download target"));
        }
        if completed
            && !downloading
            && requested_cursor.is_some()
            && !page.has_more
            && page.changes.is_empty()
        {
            // A completed incremental no-op changes only provenance/cursor state.
            // Avoid copying and rewriting every cached item on an idle check.
            tx.execute("UPDATE state SET cursor=?3,target=?4,observed_at=?5,synthetic=?6 WHERE server=?1 AND market=?2",
                params![server,market,page.cursor,page.target_observation_id,page.observed_at,page.synthetic])?;
            tx.commit()?;
            return Ok(());
        }
        if !downloading {
            tx.execute(
                "DELETE FROM staging WHERE server=?1 AND market=?2",
                params![server, market],
            )?;
            if requested_cursor.is_some() {
                tx.execute(
                    "INSERT INTO staging SELECT * FROM active WHERE server=?1 AND market=?2",
                    params![server, market],
                )?;
            }
        }
        for change in &page.changes {
            match change.operation {
                Operation::Upsert => {
                    tx.execute("INSERT INTO staging(server,market,item,variant,value) VALUES(?1,?2,?3,?4,?5)
                    ON CONFLICT(server,market,item,variant) DO UPDATE SET value=excluded.value",
                    params![server,market,change.item_id,change.variant_key,serde_json::to_string(change.value.as_ref().unwrap())?])?;
                }
                Operation::Delete => {
                    tx.execute("DELETE FROM staging WHERE server=?1 AND market=?2 AND item=?3 AND variant=?4",
                    params![server,market,change.item_id,change.variant_key])?;
                }
            }
        }
        if !page.has_more {
            tx.execute(
                "DELETE FROM active WHERE server=?1 AND market=?2",
                params![server, market],
            )?;
            tx.execute(
                "INSERT INTO active SELECT * FROM staging WHERE server=?1 AND market=?2",
                params![server, market],
            )?;
            tx.execute(
                "DELETE FROM staging WHERE server=?1 AND market=?2",
                params![server, market],
            )?;
            tx.execute(
                "UPDATE state SET observed_at=?3,completed=1,synthetic=?4 WHERE server=?1 AND market=?2",
                params![server, market, page.observed_at, page.synthetic],
            )?;
        }
        tx.execute(
            "UPDATE state SET cursor=?3,downloading=?4,target=?5 WHERE server=?1 AND market=?2",
            params![
                server,
                market,
                page.cursor,
                page.has_more,
                page.target_observation_id
            ],
        )?;
        tx.commit()?;
        Ok(())
    }
    pub fn status(&self, server: &str, market: u32) -> Result<Status> {
        let state: Option<(bool, Option<String>, bool, bool)> = self
            .db
            .query_row(
                "SELECT downloading,observed_at,completed,synthetic FROM state WHERE server=?1 AND market=?2",
                params![server, market],
                |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
            )
            .optional()?;
        let (downloading, observed_at, completed, synthetic) =
            state.unwrap_or((false, None, false, false));
        let count: i64 = self.db.query_row(
            "SELECT count(*) FROM active WHERE server=?1 AND market=?2",
            params![server, market],
            |row| row.get(0),
        )?;
        Ok(Status {
            market_id: market,
            item_count: count as u64,
            downloading,
            observed_at,
            has_completed_cache: completed,
            synthetic,
        })
    }
    pub fn items(&self, server: &str, market: u32) -> Result<Vec<Item>> {
        let mut statement=self.db.prepare("SELECT item,variant,value FROM active WHERE server=?1 AND market=?2 ORDER BY item,variant")?;
        let rows = statement.query_map(params![server, market], |row| {
            Ok((
                row.get::<_, u32>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
            ))
        })?;
        let mut result = Vec::new();
        for row in rows {
            let (item_id, variant_key, value) = row?;
            let value: Valuation = serde_json::from_str(&value)?;
            value.validate()?;
            result.push(Item {
                item_id,
                variant_key,
                value,
            });
        }
        Ok(result)
    }
    pub fn export(
        &self,
        server: &str,
        market: u32,
        directory: &Path,
    ) -> Result<std::path::PathBuf> {
        let directory = directory.canonicalize()?;
        if directory.components().any(|part| {
            part.as_os_str()
                .to_string_lossy()
                .eq_ignore_ascii_case("SavedVariables")
        }) {
            return Err(Error::Invalid(
                "export directory must be outside SavedVariables",
            ));
        }
        let status = self.status(server, market)?;
        if !status.has_completed_cache {
            return Err(Error::Invalid("complete a synchronization before export"));
        }
        let items = self.items(server, market)?;
        let target = directory.join(format!("twichui-market-v1-{market}.json"));
        let mut temporary = tempfile::NamedTempFile::new_in(&directory)?;
        serde_json::to_writer(
            &mut temporary,
            &serde_json::json!({"format":"twichui-market-addon-data","contract_version":1,
            "algorithm":ALGORITHM,"server":server,"market_id":market,"observed_at":status.observed_at,
            "generated_at":chrono::Utc::now().to_rfc3339(),"synthetic":status.synthetic||items.iter().any(|item|item.value.synthetic),"items":items}),
        )?;
        temporary.flush()?;
        temporary.as_file().sync_all()?;
        temporary
            .persist(&target)
            .map_err(|error| Error::Io(error.error))?;
        Ok(target)
    }
}
