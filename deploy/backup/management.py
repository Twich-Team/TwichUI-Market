"""Private backup boundary. Only this service sees archives or PostgreSQL credentials.

The shared flock also coordinates the operator's backup/restore helpers. All archive
access is relative to a pinned directory descriptor, never to a client supplied path.
"""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import fcntl
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import sqlite3
import stat
import subprocess
import time
import uuid

GIB = 1024**3
RESERVE = 2 * GIB
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\.dump\Z')
ID = re.compile(r'[a-f0-9]{32}\Z')
DEFAULT = dict(enabled=False, interval_seconds=86400, daily=2, weekly=0, monthly=0,
               max_bytes=None, minimum_recovery_points=1, warning_free_bytes=3*GIB)


class Refused(Exception):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def date(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def identifier(name):
    return hashlib.sha256(name.encode()).hexdigest()[:32]


def validate_policy(value):
    if not isinstance(value, dict) or set(value) != set(DEFAULT):
        raise Refused('Specify the complete backup policy')
    if type(value['enabled']) is not bool:
        raise Refused('Invalid schedule')
    bounds = dict(interval_seconds=(3600, 31*86400), daily=(1, 365), weekly=(0, 104),
                  monthly=(0, 120), minimum_recovery_points=(1, 30), warning_free_bytes=(RESERVE, 1024**5))
    for key, (low, high) in bounds.items():
        if type(value[key]) is not int or not low <= value[key] <= high:
            raise Refused('Invalid backup policy: ' + key)
    if value['max_bytes'] is not None and (type(value['max_bytes']) is not int or not 1024**2 <= value['max_bytes'] <= 1024**5):
        raise Refused('Invalid managed archive budget')
    return dict(value)


from providers import Local, StorageError, digest, mapped, CHUNK
from storage_config import StorageConfiguration


class Manager(StorageConfiguration):
    def __init__(self, root='/backups', state='/state', *, require_mount=True):
        self.root = Path(root).absolute()
        self.state = Path(state).absolute()
        if self.root.resolve() != self.root or self.root.is_symlink() or not self.root.is_dir():
            raise Refused('Managed backup directory is missing or unsafe')
        if require_mount:
            mounts = [line.split()[4] for line in Path('/proc/self/mountinfo').read_text().splitlines()]
            if str(self.root) not in mounts:
                raise Refused('Backup directory must be a dedicated verified mount')
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(self.fd)
        if info.st_uid != os.geteuid() or info.st_mode & 0o077:
            os.close(self.fd)
            raise Refused('Backup root must be owned by this service with mode 0700')
        if self.state.resolve() != self.state or self.state.is_symlink():
            raise Refused('Unsafe management state directory')
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        if (self.state/'management.sqlite').is_symlink():
            raise Refused('Unsafe management database')
        self.db_path = self.state/'management.sqlite'
        self._stores = {}
        self._location = None
        with self.lock():
            with self.db() as db:
                db.executescript('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);'
                                 'CREATE TABLE IF NOT EXISTS receipts (id TEXT PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);'
                                 "CREATE INDEX IF NOT EXISTS receipts_action_reference ON receipts(action,json_extract(detail,'$.receipt_id'));"
                                 'CREATE INDEX IF NOT EXISTS receipts_action_time ON receipts(action,at DESC);')
                if not db.execute("SELECT 1 FROM settings WHERE key='policy'").fetchone():
                    self.set(db, 'policy', dict(revision=1, **DEFAULT))
                    self.receipt(db, 'migration', 'policy.initialized', {'policy': DEFAULT, 'notice': 'Schedule disabled; no legacy archives adopted or deleted'})
                # A crash is never treated as a completed backup or a deletion authorization.
                job = self.get(db, 'job', {})
                restore = self.get(db,'restore',{})
                if restore.get('status') in ('queued','running'):
                    self.set(db,'restore',{**restore,'status':'interrupted','finished_at':stamp()})
                migration = self.get(db, 'migration', {})
                if migration.get('status') in ('queued', 'running'):
                    self.remember_temporary(db,migration)
                    self.set(db, 'migration', {**migration, 'status':'interrupted', 'finished_at':stamp(), 'originals_preserved':True})
                if job.get('status') in ('queued', 'running'):
                    self.remember_temporary(db,job)
                    self.set(db, 'job', {**job, 'status': 'interrupted', 'finished_at': stamp()})
            self.reconcile()

    def close(self):
        os.close(self.fd)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.db_path, timeout=5)
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def get(db, key, default=None):
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def set(db, key, value):
        db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))

    @staticmethod
    def receipt(db, actor, action, detail):
        key = uuid.uuid4().hex
        db.execute('INSERT INTO receipts VALUES (?,?,?,?,?)', (key, stamp(), str(actor)[:80], action, json.dumps(detail)))
        return key

    @contextmanager
    def lock(self):
        fd = self.open('.backup.lock', os.O_CREAT | os.O_WRONLY)
        acquired = False
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused('Backup, download, deletion or restore operation is busy') from None
            acquired = True
            self._stores = {}
            self._location = None
            self._operation_deadline = None
            yield
        finally:
            if acquired:
                for store in self._stores.values(): store.close()
                self._stores = {}
                self._location = None
            os.close(fd)

    def open(self, name, flags=os.O_RDONLY):
        fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=self.fd)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid():
            os.close(fd)
            raise Refused('Unsafe managed file')
        return fd

    def read_json(self, name):
        with self.store.open(name) as stream:
            if self.store.info(name)['bytes'] > 65536:
                raise ValueError('Oversized metadata')
            return json.load(stream)

    def write_json(self, name, value):
        temporary = '.metadata-' + uuid.uuid4().hex
        try:
            with self.store.open(temporary, 'xb') as stream:
                stream.write(json.dumps(value).encode())
                stream.flush()
                if self.store.kind == 'local': os.fsync(stream.fileno())
            self.store.rename(temporary, name, replace=True)
        finally:
            try:
                self.store.remove(temporary)
            except FileNotFoundError:
                pass

    def filesystem(self):
        return dict(self.store.capacity(), reserve_bytes=RESERVE)

    def rows(self):
        configs, active = self.configs()
        with self.db() as db:
            previous = self.get(db, 'storage_previous')
        rows, other = [], []
        self._inventory_by_storage = {}
        seen = set()
        for key in dict.fromkeys([active, previous]):
            if not key: continue
            with self.location(key):
                entries, artifacts = self.rows_current()
            # Physical copies, before recovery-point deduplication across migration locations.
            self._inventory_by_storage[key] = dict(count=len(entries),
                bytes=sum(row['bytes'] for row in entries) if all(row['bytes'] is not None for row in entries) else None)
            for row in entries:
                # Migration creates verified duplicate copies; inventory identifies the active copy first.
                if row['filename'] in seen: continue
                seen.add(row['filename'])
                row.update(id=identifier(row['filename']) if key=='local' else identifier(key+':'+row['filename']),storage_id=key, storage_name=configs[key]['name'])
                rows.append(row)
            other.extend(dict(item, storage_id=key) for item in artifacts)
        return sorted(rows, key=lambda r:(r['created_at'] or '',r['filename']), reverse=True), other

    def rows_current(self):
        rows, other = [], []
        names = set(self.store.names())
        for name in sorted(names):
            if name == '.backup.lock':
                continue
            if not NAME.fullmatch(name):
                if name.endswith(('.json', '.partial')) or name.startswith('.metadata-'):
                    kind = 'orphan_manifest' if name.endswith('.json') and name[:-5]+'.dump' not in names else 'incomplete'
                    if name.endswith('.json') and any(r['filename'] == name[:-5]+'.dump' for r in rows):
                        continue
                    other.append(dict(name=name[:190], type=kind))
                continue
            row = dict(id=identifier(name), filename=name, type='legacy', origin='unknown', created_at=None,
                       bytes=None, sha256=None, verification='unknown', restoration_verified_at=None,
                       protected=True, required_by=[], eligible=False, reason='Legacy archive requires separate operator classification')
            try:
                info = self.store.info(name)
                row['bytes'] = info['bytes']
                manifest = self.read_json(name[:-5]+'.json')
                row['created_at'] = date(manifest['created_at']).isoformat()
                if manifest.get('filename') != name or manifest.get('bytes') != info['bytes'] or not re.fullmatch('[a-f0-9]{64}', manifest.get('sha256', '')):
                    raise ValueError('Inconsistent metadata')
                row['sha256'] = manifest['sha256']
                if manifest.get('version') != 2 or manifest.get('manager') != 'market-backups-v2':
                    row['verification'] = 'legacy_metadata_only'
                else:
                    if manifest['origin'] not in ('scheduled', 'manual', 'release', 'restore-verification'):
                        raise ValueError('Unknown origin')
                    if (not isinstance(manifest['protected'], bool) or not isinstance(manifest.get('required_by'), list)
                            or any(not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9_:-]{1,80}', value) for value in manifest['required_by'])):
                        raise ValueError('Invalid protection metadata')
                    if manifest.get('restoration_verified_at'):
                        date(manifest['restoration_verified_at'])
                        if not isinstance(manifest.get('restored'), dict) or not manifest['restored']:
                            raise ValueError('Restore evidence missing')
                    row.update(type=manifest['origin'], origin=manifest['origin'], protected=manifest['protected'] or manifest.get('recovery_pin') is True,
                               keep_flag=manifest['protected'], recovery_pin=manifest.get('recovery_pin') is True,
                               required_by=manifest['required_by'], verification=manifest.get('verification', 'unknown'),
                               restoration_verified_at=manifest.get('restoration_verified_at'))
                    # Only files generated by this manager and fully decoded by pg_restore are owned.
                    if (row['verification'] == 'archive_integrity_verified' and type(manifest.get('postgres_major')) is int
                            and manifest.get('file_identity') == info['identity']):
                        row['eligible'] = not row['protected'] and not row['required_by']
                        row['reason'] = 'Protected or required by a recovery operation' if not row['eligible'] else 'Eligible for explicit deletion'
                    else:
                        row.update(reason='Archive changed or integrity verification is incomplete', verification='unavailable', restoration_verified_at=None)
            except (OSError, ValueError, TypeError, KeyError, Refused) as exc:
                if isinstance(exc, StorageError) or (self.store.kind == 'smb' and isinstance(exc,OSError) and not isinstance(exc,FileNotFoundError)): raise
                row.update(eligible=False, reason='Missing, unsafe or inconsistent archive/manifest', verification='unavailable')
            rows.append(row)
        archive_manifests = {r['filename'][:-5]+'.json' for r in rows}
        return sorted(rows, key=lambda r: (r['created_at'] or '', r['filename']), reverse=True), [o for o in other if o['name'] not in archive_manifests]

    def active_backup_references(self,db):
        active=set()
        for kind in ('restore','migration'):
            job=self.get(db,kind,{})
            if job.get('status') not in ('queued','running'):continue
            if job.get('backup_id'):active.add(job['backup_id'])
            for row in job.get('plan',{}).get('items',[]):active.add(row['id'])
        current=self.get(db,'automatic_recovery',{}).get('backup_id')
        lease=self.get(db,'recovery_lease_until')
        if current and lease and date(lease)>datetime.now(timezone.utc):active.add(current)
        # Unknown installations remain conservative. A configured current receipt
        # distinguishes completed release reservations from actual use.
        known=bool(current)
        directory=os.environ.get('BACKUP_RECOVERY_DIRECTORY')
        if directory:
            try:
                evidence=json.loads((Path(directory)/'evidence.json').read_text())
                known=bool(evidence.get('backup_id'))
            except (OSError,ValueError):pass
        return active,known,current

    def guarded_rows(self, db):
        rows, other = self.rows()
        minimum = self.get(db, 'policy')['minimum_recovery_points']
        active,known,current=self.active_backup_references(db)
        for row in rows:
            row['active_use']=row['id'] in active or (bool(row['required_by']) and not known)
            row['reserved']=bool(row['required_by']) and not row['active_use']
            row['current_recovery']=row['id']==current
            if row['active_use']:row.update(eligible=False,reason='In use by recovery or restoration; pause cleanup and wait for its short recovery lease to expire')
        # Preserve the newest N archive-integrity points AND restored recovery points.
        for points in ([r for r in rows if r['verification'] == 'archive_integrity_verified'],
                       [r for r in rows if r['restoration_verified_at']]):
            for row in points[:minimum]:
                row['eligible']=False
                if not row['active_use']:row['reason']='Minimum recovery-point safeguard'
        return rows, other

    def preview(self, db, rows):
        policy = self.get(db, 'policy')
        scheduled = [r for r in rows if r['origin'] == 'scheduled' and r['verification'] == 'archive_integrity_verified']
        keep = set()
        for tier, pattern in [('daily', '%Y-%m-%d'), ('weekly', '%G-%V'), ('monthly', '%Y-%m')]:
            buckets = set()
            for row in scheduled:
                bucket = date(row['created_at']).strftime(pattern)
                if bucket not in buckets and len(buckets) < policy[tier]:
                    buckets.add(bucket)
                    keep.add(row['id'])
        candidates = [r for r in reversed(scheduled) if r['eligible'] and r['id'] not in keep]
        used = sum(r['bytes'] or 0 for r in rows)
        return dict(candidates=[dict(id=r['id'], filename=r['filename'], bytes=r['bytes']) for r in candidates],
                    reclaimable_bytes=sum(r['bytes'] for r in candidates),
                    budget_exceeded=bool(policy['max_bytes'] and used > policy['max_bytes']),
                    scope='Only scheduled v2 archives outside retained UTC day/week/month buckets. Manual, release, legacy and protected archives are excluded. Saving never deletes files; rotation follows a successful new scheduled backup.')

    def overview(self, offset=0, limit=20, filters=None):
        filters = self.inventory_filters(filters or {})
        try:
            result = self.measured_overview(offset, limit, filters)
            result['inventory_stale'] = False
            return result
        except (Refused, StorageError, OSError) as exc:
            if isinstance(exc,OSError) and exc.errno==errno.ELOOP: raise
            with self.db() as db:
                cached = self.get(db, self.inventory_cache_key(offset, limit, filters))
                if cached is None:
                    raise Refused('Backup operation is busy; inventory measurements unavailable') from None
                cached['service_status'] = 'operation_busy' if isinstance(exc,Refused) else 'storage_unavailable'
                cached['inventory_stale'] = True
                cached['job'] = self.get(db, 'job', {})
                cached['storage_error'] = 'Storage is unavailable or an operation is in progress; showing the last successful inventory'
                cached['items'] = [dict(row,eligible=False,reason='Operation busy; refresh after completion' if isinstance(exc,Refused) else 'Storage unavailable; reconnect and refresh') for row in cached['items']]
                return cached

    @staticmethod
    def inventory_filters(filters):
        choices = {'protection': ('all','protected','unprotected'),
                   'verification': ('all','restored','integrity','unknown'),
                   'backup_type': ('all','scheduled','manual','release','restore-verification','legacy','unknown'),
                   'sort': ('created_desc','created_asc','bytes_desc','bytes_asc')}
        if not isinstance(filters,dict) or set(filters)-set(choices)-{'search','storage_id'}:
            raise Refused('Invalid inventory filters')
        for key,value in filters.items():
            if not isinstance(value,str) or len(value)>190 or (key in choices and value not in choices[key]):
                raise Refused('Invalid inventory filter: '+key)
            if key=='storage_id' and value and not re.fullmatch(r'(local|[a-f0-9]{32})',value):
                raise Refused('Invalid inventory storage')
        return {key:value for key,value in filters.items()
                if value and value!='all' and not (key=='sort' and value=='created_desc')}

    @staticmethod
    def inventory_cache_key(offset, limit, filters):
        suffix = ':'+hashlib.sha256(json.dumps(filters,sort_keys=True).encode()).hexdigest()[:24] if filters else ''
        return 'overview:'+str(offset)+':'+str(limit)+suffix

    @staticmethod
    def filter_inventory(rows, filters):
        rows = [row for row in rows if
            (not filters.get('search') or filters['search'].casefold() in (' '.join(str(row.get(key) or '') for key in ('filename','storage_name','created_at','origin'))).casefold()) and
            (not filters.get('storage_id') or row.get('storage_id')==filters['storage_id']) and
            (not filters.get('protection') or bool(row['protected'])==(filters['protection']=='protected')) and
            (not filters.get('backup_type') or row.get('type')==filters['backup_type']) and
            (not filters.get('verification') or
             (bool(row.get('restoration_verified_at')) if filters['verification']=='restored' else
              row.get('verification')=='archive_integrity_verified' if filters['verification']=='integrity' else
              not row.get('restoration_verified_at') and row.get('verification')!='archive_integrity_verified'))]
        order = filters.get('sort','created_desc')
        return sorted(rows,key=lambda row: ((row.get('bytes') or 0) if order.startswith('bytes') else (row.get('created_at') or ''),row['filename']),reverse=order.endswith('desc'))

    def reliability(self, db):
        since = (datetime.now(timezone.utc)-timedelta(days=41)).replace(hour=0,minute=0,second=0,microsecond=0)
        events = db.execute("SELECT at,actor,action,detail FROM receipts WHERE action IN ('backup.published','backup.failed') AND at>=? ORDER BY at DESC LIMIT 1001",(since.isoformat(),)).fetchall()
        days = {}; attempts = []
        for at,actor,action,payload in events[:1000]:
            detail=json.loads(payload);manifest=detail.get('manifest',{})
            outcome='succeeded' if action=='backup.published' else 'failed'
            origin=manifest.get('origin',detail.get('origin','scheduled' if actor=='scheduler' else 'unknown'))
            day=days.setdefault(at[:10],dict(succeeded=0,failed=0))
            day[outcome]+=1
            if len(attempts)<200:
                attempts.append(dict(at=at,status=outcome,origin=origin,backup_id=detail.get('id') if outcome=='succeeded' else None,bytes=manifest.get('bytes')))
        return dict(since=since.isoformat(),days=[dict(day=day,**counts) for day,counts in sorted(days.items())],
            attempts=attempts,truncated=len(events)>1000,schedule_history_available=False,
            notice='Recorded execution receipts only. Missing days and missed schedules are unknown; current policy is not historical schedule evidence.')

    def measured_overview(self, offset=0, limit=20, filters=None):
        filters = filters or {}
        with self.lock(), self.db() as db:
            self._operation_deadline=time.monotonic()+20
            self.reconcile(remote=True)
            rows, other = self.guarded_rows(db)
            matching = self.filter_inventory(rows,filters)
            policy = self.get(db, 'policy')
            fs = self.filesystem()
            successes = [r for r in rows if r['verification'] == 'archive_integrity_verified']
            restores = [r['restoration_verified_at'] for r in rows if r['restoration_verified_at']]
            job = self.get(db, 'job', {})
            next_at = self.get(db, 'next_at') if policy['enabled'] else None
            result = dict(measured_at=stamp(), policy=policy, service_status='enabled' if policy['enabled'] else 'scheduled_backups_disabled',
                        last_success=successes[0]['created_at'] if successes else None,
                        last_restoration_verified_at=max(restores) if restores else None,
                        total=len(rows), matched_total=len(matching), total_bytes=sum(r['bytes'] or 0 for r in rows), filesystem=fs,
                        inventory_by_storage=self._inventory_by_storage,reliability=self.reliability(db),
                        protected_count=sum(r['protected'] for r in rows),protected_bytes=sum(r['bytes'] or 0 for r in rows if r['protected']),storage=self.storage_status(),
                        storage_pressure=fs['available_bytes'] is not None and fs['available_bytes'] < policy['warning_free_bytes'], next_scheduled_at=next_at,
                        estimate_bytes=self.estimate(rows), job=job, items=matching[offset:offset+limit], offset=offset, limit=limit,
                        artifacts=other[:100], artifact_count=len(other), preview=self.preview(db, rows),
                        receipts=[dict(id=r[0], at=r[1], actor=r[2], action=r[3], detail=json.loads(r[4]))
                                  for r in db.execute('SELECT * FROM receipts ORDER BY at DESC LIMIT 20')])
            self.set(db, self.inventory_cache_key(offset,limit,filters), result)
            # Bound cached pages; the immutable audit ledger is stored separately.
            db.execute("DELETE FROM settings WHERE key LIKE 'overview:%' AND rowid NOT IN (SELECT rowid FROM settings WHERE key LIKE 'overview:%' ORDER BY rowid DESC LIMIT 20)")
            return result

    def policy(self, actor, revision, values):
        values = validate_policy(values)
        with self.lock(), self.db() as db:
            previous = self.get(db, 'policy')
            if revision != previous['revision']:
                raise Refused('Policy changed; refresh and review it again')
            updated = dict(revision=revision+1, **values)
            self.receipt(db, actor, 'policy.updated', dict(before=previous, after=updated))
            self.set(db, 'policy', updated)
            # Saving an enabled schedule starts only after a full cadence, never on service startup.
            self.set(db, 'next_at', (datetime.now(timezone.utc)+timedelta(seconds=values['interval_seconds'])).isoformat() if values['enabled'] else None)
            return updated

    def find(self, db, key):
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise Refused('Invalid backup identifier')
        rows, _ = self.guarded_rows(db)
        row = next((r for r in rows if r['id'] == key), None)
        if row is None:
            raise Refused('Backup is no longer available')
        self._location = row.get('storage_id')
        return row

    def protect(self, actor, key, protected):
        with self.lock(), self.db() as db:
            self.idle(db)
            row = self.find(db, key)
            if row['type'] == 'legacy' or row['verification'] != 'archive_integrity_verified':
                raise Refused('Unknown ownership or verification; protection cannot be changed')
            if not protected and row['required_by']:
                raise Refused('Recovery operation still requires this archive')
            manifest = self.read_json(row['filename'][:-5]+'.json')
            self.receipt(db, actor, 'protection.intent', dict(id=key, protected=protected))
            db.commit()
            manifest['protected'] = protected
            self.write_json(row['filename'][:-5]+'.json', manifest)
            self.receipt(db, actor, 'protection.updated', dict(id=key, protected=protected))
            return dict(protected=protected)

    def checksum(self, name):
        return digest(self.store, name)

    def delete(self, actor, key, confirmation, *, automatic=False, confirm_protected=False, confirm_recovery_loss=False, confirm_reserved=False, job_id=None):
        with self.lock(), self.db() as db:
            self._operation_deadline=time.monotonic()+7200
            if job_id:
                job=self.get(db,'job',{})
                if job.get('id')!=job_id or job.get('kind')!='deletion' or job.get('status')!='running':raise Refused('Deletion job changed')
            else:self.idle(db)
            row = self.find(db, key)
            if confirmation != row['filename']:
                raise Refused('Type the exact backup filename to confirm')
            if automatic and not row['eligible']: raise Refused(row['reason'])
            if not automatic and row['reason']=='Minimum recovery-point safeguard' and not confirm_recovery_loss:
                raise Refused('Explicit acknowledgement is required to delete the newest or last recovery point')
            if row.get('active_use'):raise Refused('An active recovery operation still requires this backup; pause cleanup and wait for the recovery lease to expire')
            if row['required_by'] and not confirm_reserved:raise Refused('Explicit acknowledgement of inactive recovery reservations is required')
            if row['type'] == 'legacy' or row['verification'] != 'archive_integrity_verified':
                raise Refused('Verified ownership is required for backup deletion')
            if row['protected'] and (automatic or not confirm_protected):
                raise Refused('Explicit protected backup deletion acknowledgement is required')
            if automatic and key not in {r['id'] for r in self.preview(db, self.guarded_rows(db)[0])['candidates']}:
                raise Refused('Retention candidates changed')
            if self.checksum(row['filename']) != row['sha256']:
                raise Refused('Archive checksum changed; deletion refused')
            survivors, _ = self.guarded_rows(db)
            intact = []
            for survivor in survivors:
                if survivor['id'] != key and survivor['verification'] == 'archive_integrity_verified':
                    try:
                        with self.location(survivor.get('storage_id')):
                            if self.checksum(survivor['filename']) == survivor['sha256']:
                                intact.append(survivor)
                    except (OSError, Refused):
                        pass
            if len(intact) < self.get(db, 'policy')['minimum_recovery_points'] and (automatic or not confirm_recovery_loss):
                raise Refused('Too few intact recovery points would remain')
            if row['restoration_verified_at'] and not any(point['restoration_verified_at'] for point in intact) and (automatic or not confirm_recovery_loss):
                raise Refused('The final intact restored recovery point must be retained')
            manifest_name = row['filename'][:-5]+'.json'
            manifest = self.read_json(manifest_name)
            receipt = self.receipt(db, actor, 'deletion.intent', dict(backup=row, manifest=manifest, automatic=automatic, confirm_protected=confirm_protected, confirm_recovery_loss=confirm_recovery_loss, confirm_reserved=confirm_reserved, policy_revision=self.get(db, 'policy')['revision']))
            db.commit()  # durable authorization and metadata survive any filesystem failure
            removed, manifest_removed = False, False
            try:
                self.store.remove(row['filename'])
                removed = True
                self.store.remove(manifest_name)
                manifest_removed = True
            except OSError:
                pass
            result = dict(receipt_id=receipt, archive_removed=removed, manifest_removed=manifest_removed,
                          unlinked_bytes=row['bytes'] if removed else 0, status='deleted' if removed and manifest_removed else 'partial_failure')
            self.receipt(db, actor, 'deletion.result', result)
            return result

    def reconcile(self, *, remote=False):
        # Called on restart under the same lock. Only remove a leftover manifest when
        # a durable deletion intent names it, the archive is gone, and metadata matches.
        with self.db() as db:
            for key, payload in db.execute("SELECT i.id,i.detail FROM receipts i LEFT JOIN receipts r ON r.action='deletion.result' AND json_extract(r.detail,'$.receipt_id')=i.id LEFT JOIN receipts done ON done.action='deletion.reconciled' AND json_extract(done.detail,'$.receipt_id')=i.id WHERE i.action='deletion.intent' AND done.id IS NULL AND (r.id IS NULL OR (json_extract(r.detail,'$.archive_removed')=1 AND json_extract(r.detail,'$.manifest_removed')=0)) ORDER BY i.at DESC LIMIT 100").fetchall():
                data = json.loads(payload)
                name = data['backup']['filename']
                self._location = data['backup'].get('storage_id','local')
                if not remote and self._location!='local':continue
                try:
                    if name in self.store.names(): continue
                    if self.read_json(name[:-5]+'.json') != data['manifest']:
                        continue
                    self.store.remove(name[:-5]+'.json')
                    self.receipt(db, 'restart', 'deletion.reconciled', {'receipt_id': key, 'manifest_removed': True})
                except StorageError:
                    break
                except (OSError, ValueError, Refused):
                    pass
            self._location = None

    @contextmanager
    def download(self, actor, key):
        with self.lock(), self.db() as db:
            self.idle(db)
            row = self.find(db, key)
            if row['verification'] != 'archive_integrity_verified' or (self.store.kind=='local' and self.checksum(row['filename']) != row['sha256']):
                raise Refused('Verified ownership and matching SHA-256 are required to download')
            self.receipt(db, actor, 'download.authorized', dict(id=key, sha256=row['sha256']))
            db.commit()
            with self.store.open(row['filename']) as stream:
                yield row, stream

    @staticmethod
    def estimate(rows):
        measured = [r['bytes'] for r in rows if r['verification'] == 'archive_integrity_verified'][:5]
        return math.ceil(max(measured)*1.5)+64*1024**2 if measured else GIB

    def queue(self, actor):
        with self.lock(), self.db() as db:
            self.idle(db)
            self.cleanup_temporaries(db)
            previous = self.get(db, 'job', {})
            if previous.get('status') in ('queued', 'running'):
                raise Refused('A backup is already queued or running')
            rows, _ = self.rows()
            self.capacity(db, rows, self.estimate(rows))
            job = dict(id=uuid.uuid4().hex, status='queued', actor=str(actor), requested_at=stamp())
            self.set(db, 'job', job)
            self.receipt(db, actor, 'backup.queued', job)
            return job

    def capacity(self, db, rows, allowance):
        policy = self.get(db, 'policy')
        if self.filesystem()['available_bytes'] is not None and self.filesystem()['available_bytes'] < allowance+RESERVE:
            raise Refused('Insufficient space for a new full backup and safe reserve; review emergency cleanup preview')
        if policy['max_bytes'] and sum(r['bytes'] or 0 for r in rows)+allowance > policy['max_bytes']:
            raise Refused('Managed backup budget cannot accommodate a replacement; no recovery point was deleted')

    def create(self, actor, origin='manual', job_id=None):
        if origin not in ('scheduled', 'manual', 'release', 'restore-verification'):
            raise Refused('Invalid backup origin')
        with self.lock(), self.db() as db:
            job = self.get(db, 'job', {})
            if (job_id and (job.get('id') != job_id or job.get('status') != 'queued')) or (not job_id and job.get('status') in ('queued', 'running')):
                raise Refused('Backup job changed')
            job = dict(id=job_id or uuid.uuid4().hex, status='running', actor=str(actor), started_at=stamp())
            self.set(db, 'job', job)
            self.receipt(db, actor, 'backup.started', job)
            db.commit()
            name = 'market-'+origin+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:12]+'.dump'
            temporary = name[:-5]+'.partial'
            _,active=self.configs()
            job.update(temporary=temporary,storage_id=active)
            self.set(db,'job',job);db.commit()
            published = False
            try:
                rows, _ = self.rows()
                self.cleanup_temporaries(db)
                estimate = self.estimate(rows)
                self.capacity(db, rows, estimate)
                server = subprocess.check_output(['psql', '-Atc', 'SHOW server_version_num'], timeout=20, stderr=subprocess.DEVNULL).decode().strip()
                major = int(server)//10000
                client = subprocess.check_output(['pg_dump', '--version'], timeout=10).decode()
                if int(re.search(r'(\d+)\.', client)[1]) != major:
                    raise Refused('PostgreSQL client/server major versions must match')
                with self.store.open(temporary, 'xb') as stream:
                    process = subprocess.Popen(['pg_dump', '--format=custom', '--no-owner', '--no-acl'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    started = time.monotonic()
                    written = 0
                    next_capacity = 0
                    selector = selectors.DefaultSelector()
                    selector.register(process.stdout, selectors.EVENT_READ)
                    try:
                        while True:
                            if time.monotonic()-started > 7200:
                                raise Refused('Backup exceeded operational deadline')
                            if time.monotonic() >= next_capacity:
                                available=self.filesystem()['available_bytes']
                                if available is not None and available < CHUNK+RESERVE:
                                    raise Refused('Backup exceeded storage reserve')
                                next_capacity=time.monotonic()+1
                            if not selector.select(timeout=2):
                                continue
                            chunk = os.read(process.stdout.fileno(), 1024**2)
                            if not chunk:
                                break
                            written += len(chunk)
                            budget = self.get(db, 'policy')['max_bytes']
                            if budget and sum(r['bytes'] or 0 for r in rows)+written > budget:
                                raise Refused('Backup exceeded managed archive budget')
                            stream.write(chunk)
                            stream.flush()
                        if process.wait(timeout=30) != 0:
                            raise Refused('pg_dump failed')
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                        process.stdout.close()
                        selector.close()
                    stream.flush()
                    if self.store.kind == 'local': os.fsync(stream.fileno())
                # Decode the ENTIRE custom archive; listing its TOC alone misses corrupt data.
                with self.store.open(temporary) as source:
                    self.decode(source)
                info = self.store.info(temporary)
                manifest = dict(version=2, manager='market-backups-v2', filename=name, source='development', origin=origin,
                                created_at=stamp(), bytes=info['bytes'], sha256=self.checksum(temporary), postgres_major=major,
                                verification='archive_integrity_verified', restoration_verified_at=None,
                                protected=origin != 'scheduled', required_by=[], file_identity=info['identity'])
                # Manifest first; inventory publishes the pair only when the completed archive appears.
                self.write_json(name[:-5]+'.json', manifest)
                self.store.rename(temporary, name)
                if self.store.kind=='smb':
                    manifest['file_identity']=self.store.info(name)['identity']
                    self.write_json(name[:-5]+'.json',manifest)
                published = True
                job.update(status='succeeded', finished_at=stamp(), backup_id=self.archive_id(name))
                self.set(db, 'job', job)
                self.receipt(db, actor, 'backup.published', dict(id=self.archive_id(name), manifest=manifest))
            except Exception:
                job.update(status='failed', finished_at=stamp(), error='Backup creation or integrity verification failed; valid recovery points retained')
                self.set(db, 'job', job)
                self.receipt(db, actor, 'backup.failed', job)
            finally:
                try:
                    self.store.remove(temporary)
                except FileNotFoundError:
                    pass
                except (OSError,StorageError):
                    job['cleanup_pending'] = True
                    self.remember_temporary(db,job)
                    self.set(db, 'job', job)
                    self.receipt(db, actor, 'backup.cleanup_pending', {'id': job['id']})
            db.commit()
        # Each deletion takes the global lock and re-evaluates the latest policy/protection.
        if published and job['status'] == 'succeeded' and origin == 'scheduled':
            overview = self.overview()
            results = []
            for candidate in overview['preview']['candidates']:
                try:
                    results.append(self.delete('rotation', candidate['id'], candidate['filename'], automatic=True))
                except Refused:
                    break
            with self.lock(), self.db() as db:
                self.receipt(db, 'rotation', 'retention.receipt', dict(replacement=self.archive_id(name), results=results, policy_revision=overview['policy']['revision']))
        return job

    @staticmethod
    def decode(source, database=None, *, env=None, check=None):
        command=['pg_restore','--no-owner','--no-acl','--exit-on-error','-d',database] if database else ['pg_restore','--file=/dev/null']
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env)
        started=time.monotonic()
        os.set_blocking(process.stdin.fileno(),False)
        selector=selectors.DefaultSelector();selector.register(process.stdin,selectors.EVENT_WRITE)
        try:
            for chunk in iter(lambda:source.read(CHUNK),b''):
                offset=0
                while offset<len(chunk):
                    if check:check()
                    if time.monotonic()-started>7200:raise Refused('Archive verification deadline reached')
                    if selector.select(timeout=1):
                        try:offset+=os.write(process.stdin.fileno(),chunk[offset:])
                        except BlockingIOError:pass
            process.stdin.close()
            while process.poll() is None:
                if time.monotonic()-started>7200:raise Refused('Archive verification deadline reached')
                if check:check()
                try:process.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
            if process.returncode!=0:raise Refused('Archive decode or restore failed')
        finally:
            selector.close()
            if process.poll() is None:process.kill();process.wait()
            if not process.stdin.closed:process.stdin.close()

    def bulk_delete(self,actor,items,*,job_id=None):
        if not isinstance(items,list) or not 1<=len(items)<=50:raise Refused('Select between 1 and 50 backups')
        results=[]
        started=time.monotonic()
        for item in items:
            try:
                if time.monotonic()-started>7200:raise Refused('Bulk deletion deadline reached; remaining copies retained')
                result=self.delete(actor,item['id'],item['confirmation'],confirm_protected=item.get('confirm_protected') is True,
                    confirm_recovery_loss=item.get('confirm_recovery_loss') is True,confirm_reserved=item.get('confirm_reserved') is True,job_id=job_id)
                results.append(dict(id=item['id'],**result))
            except Exception as exc:
                results.append(dict(id=item.get('id'),status='retained',error=str(exc) if isinstance(exc,Refused) else 'Backup unavailable; no deletion was confirmed'))
        return dict(results=results,status='complete' if all(r['status']=='deleted' for r in results) else 'partial_failure')

    def restore_queue(self,actor,key):
        with self.lock(),self.db() as db:
            self.idle(db)
            row=self.find(db,key)
            if row['verification']!='archive_integrity_verified':raise Refused('Select an integrity-checked backup')
            job=dict(id=uuid.uuid4().hex,status='queued',backup_id=key,actor=str(actor),requested_at=stamp())
            self.set(db,'restore',job);self.receipt(db,actor,'restore.queued',job)
            return job

    def restore_test(self,actor,job_id):
        from recovery import restore
        return restore(self,actor,job_id)

    def archive_id(self,name):
        _,active=self.configs()
        return identifier(name) if active=='local' else identifier(active+':'+name)

    def deletion_queue(self,actor,items):
        if not isinstance(items,list) or not 1<=len(items)<=50:raise Refused('Select between 1 and 50 backups')
        with self.lock(),self.db() as db:
            self.idle(db)
            for item in items:
                if not ID.fullmatch(item.get('id','')) or not NAME.fullmatch(item.get('confirmation','')):
                    raise Refused('Select a valid backup identifier and exact filename')
            job=dict(id=uuid.uuid4().hex,kind='deletion',status='queued',actor=str(actor),requested_at=stamp(),items=items)
            self.set(db,'job',job);self.receipt(db,actor,'deletion.queued',dict(id=job['id'],count=len(items)))
            return {k:v for k,v in job.items() if k!='items'}

    def deletion_run(self,actor,job_id):
        with self.lock(),self.db() as db:
            job=self.get(db,'job',{})
            if job.get('id')!=job_id or job.get('status')!='queued' or job.get('kind')!='deletion':raise Refused('Deletion job changed')
            job.update(status='running',started_at=stamp());self.set(db,'job',job)
        results=self.bulk_delete(actor,job['items'],job_id=job_id)
        with self.lock(),self.db() as db:
            job.update(status='succeeded' if results['status']=='complete' else 'partial_failure',finished_at=stamp(),result=results)
            self.set(db,'job',job);self.receipt(db,actor,'deletion.job.finished',dict(id=job_id,status=job['status']))
        return job

    def remember_temporary(self,db,job):
        name=job.get('temporary');location=job.get('storage_id')
        if not name or not location:return
        if not re.fullmatch(r'(market-[A-Za-z0-9_.-]+\.partial|\.migration-[a-f0-9]{32}-market-[A-Za-z0-9_.-]+\.dump)',name):
            raise Refused('Unsafe incomplete-file receipt')
        pending=self.get(db,'pending_cleanup',[])
        item=dict(name=name,storage_id=location)
        if item not in pending:pending.append(item)
        if len(pending)>50:raise Refused('Incomplete backup cleanup limit reached')
        self.set(db,'pending_cleanup',pending)

    def cleanup_temporaries(self,db):
        pending=self.get(db,'pending_cleanup',[])
        remaining=[]
        for item in pending:
            try:
                with self.location(item['storage_id']) as store:store.remove(item['name'])
            except FileNotFoundError:pass
            except Exception:remaining.append(item)
        self.set(db,'pending_cleanup',remaining)
        db.commit()
        if remaining:raise Refused('Incomplete backup cleanup is pending; restore storage access and retry cleanup before starting another transfer')
        return len(pending)

    def cleanup_incomplete(self,actor):
        with self.lock(),self.db() as db:
            self.idle(db)
            removed=self.cleanup_temporaries(db)
            self.receipt(db,actor,'incomplete.cleanup',dict(receipts_reconciled=removed))
            return dict(status='complete',receipts_reconciled=removed)
