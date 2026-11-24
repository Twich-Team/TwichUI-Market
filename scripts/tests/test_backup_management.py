"""Disposable filesystem safety tests. Never opens a production backup directory."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'deploy/backup'))
from management import Manager, Refused, DEFAULT, GIB, RESERVE, identifier, validate_policy
from service import tick, Server, Handler


class Backups(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)/'archives'
        self.root.mkdir(mode=0o700)
        self.state = Path(self.temp.name)/'state'
        self.manager = Manager(self.root, self.state, require_mount=False)

    def tearDown(self):
        self.manager.close()
        self.temp.cleanup()

    def archive(self, label, at, origin='scheduled', protected=False, restored=False):
        name = f'market-{label}.dump'
        path = self.root/name
        path.write_bytes(('PGDMP fixture '+label).encode())
        info = path.stat()
        manifest = dict(version=2, manager='market-backups-v2', filename=name, origin=origin,
            source='development', created_at=at, bytes=info.st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            postgres_major=17, verification='archive_integrity_verified', protected=protected, required_by=[],
            restoration_verified_at=at if restored else None, file_identity=[info.st_ino,info.st_size,info.st_mtime_ns])
        if restored:
            manifest['restored'] = {'migration':'synthetic', 'users':1}
        self.manager.write_json(name[:-5]+'.json',manifest)
        return identifier(name), name

    def policy(self, **values):
        current = self.manager.overview()['policy']
        return self.manager.policy('admin:1', current.pop('revision'), {**current, **values})

    def test_inventory_pagination_capacity_and_distinct_measurements(self):
        for day in range(1,13):
            self.archive(str(day),f'2026-11-{day:02d}T01:00:00+00:00')
        usage=os.fstatvfs(self.manager.fd)
        with patch('management.os.fstatvfs',return_value=usage) as measurement:
            data=self.manager.overview(10,2)
        self.assertEqual(measurement.call_args.args[0],self.manager.fd)
        self.assertEqual((data['total'],len(data['items'])),(12,2))
        self.assertEqual(data['filesystem']['available_bytes'],usage.f_bavail*usage.f_frsize)
        self.assertEqual(data['filesystem']['capacity_bytes'],usage.f_blocks*usage.f_frsize)
        self.assertNotIn('database_bytes',data)
        self.assertEqual(data['total_bytes'],sum(p.stat().st_size for p in self.root.glob('*.dump')))

    def test_dashboard_filters_apply_before_pagination_and_preserve_global_totals(self):
        self.archive('protected-large','2026-11-02T01:00:00+00:00',origin='manual',protected=True,restored=True)
        self.archive('scheduled','2026-11-03T01:00:00+00:00')
        self.archive('other','2026-11-01T01:00:00+00:00',origin='manual')
        data=self.manager.overview(0,1,dict(protection='protected',verification='restored',backup_type='manual',storage_id='local',search='PROTECTED'))
        self.assertEqual((data['total'],data['matched_total'],len(data['items'])),(3,1,1))
        self.assertEqual(data['items'][0]['filename'],'market-protected-large.dump')
        self.assertEqual(self.manager.overview(0,1,dict(sort='created_asc'))['items'][0]['filename'],'market-other.dump')
        self.assertEqual(self.manager.overview(0,1,dict(sort='bytes_desc'))['items'][0]['filename'],'market-protected-large.dump')
        self.assertEqual(data['inventory_by_storage']['local']['count'],3)
        with self.assertRaises(Refused):self.manager.overview(filters={'sort':'DROP TABLE'})
        with self.assertRaises(Refused):self.manager.overview(filters={'storage_id':'../../secret'})

    def test_dashboard_filtered_stale_cache_does_not_return_another_query(self):
        self.archive('A','2026-11-02T01:00:00+00:00')
        self.archive('B','2026-11-03T01:00:00+00:00')
        self.manager.overview(filters=dict(search='market-A'))
        self.manager.overview(filters=dict(search='market-B'))
        with patch.object(self.manager,'measured_overview',side_effect=Refused('busy')):
            data=self.manager.overview(filters=dict(search='market-A'))
            self.assertTrue(data['inventory_stale'])
            self.assertEqual([r['filename'] for r in data['items']],['market-A.dump'])
            with self.assertRaises(Refused):self.manager.overview(filters=dict(search='uncached'))

    def test_dashboard_reliability_uses_bounded_recorded_outcomes(self):
        with self.manager.db() as db:
            self.assertEqual(self.manager.reliability(db)['days'],[])
            self.manager.receipt(db,'scheduler','backup.published',dict(id='a'*32,manifest=dict(origin='scheduled',bytes=100)))
            self.manager.receipt(db,'scheduler','backup.failed',dict(id='b'*32))
            result=self.manager.reliability(db)
            self.assertEqual(result['days'][0]['succeeded'],1)
            self.assertEqual(result['days'][0]['failed'],1)
            self.assertFalse(result['schedule_history_available'])
            self.assertTrue(all(r['origin']=='scheduled' for r in result['attempts']))
            self.assertFalse(result['truncated'])
            db.executemany('INSERT INTO receipts VALUES (?,?,?,?,?)',[(str(i),result['attempts'][0]['at'],'scheduler','backup.failed','{}') for i in range(1000)])
            result=self.manager.reliability(db)
            self.assertTrue(result['truncated'])
            self.assertEqual(len(result['attempts']),200)
            self.assertEqual(sum(day['succeeded']+day['failed'] for day in result['days']),1000)

    def test_dashboard_physical_inventory_counts_retained_migration_copies(self):
        from contextlib import nullcontext
        self.archive('same','2026-11-02T01:00:00+00:00')
        entries,_=self.manager.rows_current()
        nas='a'*32
        with self.manager.db() as db:self.manager.set(db,'storage_previous','local')
        with patch.object(self.manager,'configs',return_value=({'local':{'name':'Local'},nas:{'name':'NAS'}},nas)), \
             patch.object(self.manager,'location',side_effect=lambda _:nullcontext()), \
             patch.object(self.manager,'rows_current',side_effect=[([dict(row) for row in entries],[]),([dict(row) for row in entries],[])]):
            rows,_=self.manager.rows()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['storage_id'],nas)
        self.assertEqual(self.manager._inventory_by_storage[nas]['count'],1)
        self.assertEqual(self.manager._inventory_by_storage['local']['count'],1)
        self.assertEqual(self.manager._inventory_by_storage[nas]['bytes'],self.manager._inventory_by_storage['local']['bytes'])

    def test_keep_two_preview_and_rotation_deletes_only_a(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00')
        b=self.archive('B','2026-11-02T00:00:00+00:00')
        self.archive('C','2026-11-03T00:00:00+00:00')
        self.assertEqual([r['filename'] for r in self.manager.overview()['preview']['candidates']],[a[1]])
        result=self.manager.delete('rotation',*a,automatic=True)
        self.assertEqual(result['status'],'deleted')
        self.assertEqual([r['filename'] for r in self.manager.overview()['items']],['market-C.dump',b[1]])
        self.assertFalse((self.root/'market-A.json').exists())
        with self.manager.db() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts WHERE action LIKE 'deletion.%'").fetchone()[0],2)

    def test_weekly_and_monthly_union_preserves_representatives(self):
        self.policy(daily=1,weekly=2,monthly=2)
        self.archive('old-month','2026-10-31T00:00:00+00:00')
        self.archive('old-week','2026-11-08T00:00:00+00:00')
        expendable=self.archive('extra','2026-11-17T00:00:00+00:00')
        self.archive('new','2026-11-18T00:00:00+00:00')
        self.assertEqual([r['id'] for r in self.manager.overview()['preview']['candidates']],[expendable[0]])

    def test_protection_release_manual_legacy_and_required_recovery(self):
        entries=[self.archive('protected','2026-10-01T00:00:00+00:00',protected=True),
                 self.archive('release','2026-10-02T00:00:00+00:00',origin='release',protected=True),
                 self.archive('manual','2026-10-03T00:00:00+00:00',origin='manual')]
        latest=self.archive('new','2026-11-18T00:00:00+00:00')
        self.assertEqual(self.manager.overview()['preview']['candidates'],[])
        for key,name in entries[:2]+[latest]:
            with self.assertRaises(Refused):self.manager.delete('admin:1',key,name)
        key,name=entries[2]
        self.manager.protect('admin:1',key,True)
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name)
        self.manager.protect('admin:1',key,False)
        manifest=self.manager.read_json(name[:-5]+'.json');manifest['required_by']=['active-release']
        self.manager.write_json(name[:-5]+'.json',manifest)
        with self.assertRaises(Refused):self.manager.protect('admin:1',key,False)
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name)

    def test_last_restored_point_survives_new_integrity_only_points(self):
        key,name=self.archive('restored','2026-10-01T00:00:00+00:00',restored=True)
        self.archive('new','2026-11-18T00:00:00+00:00')
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name)
        self.assertEqual(self.manager.overview()['items'][-1]['reason'],'Minimum recovery-point safeguard')

    def test_strong_confirmation_and_actual_deletion_result(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00')
        self.archive('B','2026-11-02T00:00:00+00:00')
        with self.assertRaises(Refused):self.manager.delete('admin:1',a[0],'wrong.dump')
        size=(self.root/a[1]).stat().st_size
        result=self.manager.delete('admin:1',*a)
        self.assertEqual(result['unlinked_bytes'],size)
        self.assertTrue(result['archive_removed'] and result['manifest_removed'])
        with self.assertRaises(Refused):self.manager.delete('admin:1',*a)

    def test_partial_failure_is_audited_and_restart_reconciles_only_matching_manifest(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00')
        self.archive('B','2026-11-02T00:00:00+00:00')
        unlink=os.unlink
        def fail_manifest(name,*args,**kwargs):
            if name=='market-A.json':raise OSError('simulated filesystem failure')
            return unlink(name,*args,**kwargs)
        with patch('management.os.unlink',side_effect=fail_manifest):
            result=self.manager.delete('admin:1',*a)
        self.assertEqual(result['status'],'partial_failure')
        self.assertTrue(result['archive_removed']);self.assertFalse(result['manifest_removed'])
        self.manager.close();self.manager=Manager(self.root,self.state,require_mount=False)
        self.assertFalse((self.root/'market-A.json').exists())
        self.assertIn('deletion.reconciled',[r['action'] for r in self.manager.overview()['receipts']])

    def test_manual_deletion_corrupt_archive_is_refused(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00')
        self.archive('B','2026-11-02T00:00:00+00:00')
        original=(self.root/a[1]).stat();(self.root/a[1]).write_bytes(b'x'*original.st_size)
        os.utime(self.root/a[1],ns=(original.st_atime_ns,original.st_mtime_ns))
        with self.assertRaises(Refused):self.manager.delete('admin:1',*a)
        self.assertTrue((self.root/a[1]).exists())

    def test_silent_corruption_of_surviving_point_prevents_deleting_valid_archive(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00')
        b=self.archive('B','2026-11-02T00:00:00+00:00')
        before=(self.root/b[1]).stat()
        (self.root/b[1]).write_bytes(b'x'*before.st_size)
        os.utime(self.root/b[1],ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(Refused):self.manager.delete('admin:1',*a)
        self.assertTrue((self.root/a[1]).exists())

    def test_symlinks_hardlinks_and_path_traversal_fail_closed(self):
        outside=Path(self.temp.name)/'valuable';outside.write_text('keep')
        (self.root/'market-link.dump').symlink_to(outside)
        os.link(outside,self.root/'market-hard.dump')
        for row in self.manager.overview()['items']:self.assertFalse(row['eligible'])
        for key in ('../valuable','/etc/passwd','%2e%2e','a'*31,'x'*32):
            with self.assertRaises(Refused):self.manager.delete('admin:1',key,'anything')
        self.assertEqual(outside.read_text(),'keep')
        (self.root/'.backup.lock').unlink();(self.root/'.backup.lock').symlink_to(outside)
        with self.assertRaises(OSError):self.manager.overview()

    def test_incomplete_orphan_legacy_and_corrupt_manifests_are_not_adopted(self):
        for name in ('market-legacy.dump','market-bad.dump','market-incomplete.partial'):(self.root/name).write_text('fixture')
        (self.root/'market-legacy.json').write_text(json.dumps(dict(version=1,filename='market-legacy.dump',created_at='2026-01-01T00:00:00+00:00',bytes=7,sha256='a'*64)))
        (self.root/'market-bad.json').write_text('{')
        (self.root/'market-orphan.json').write_text('{}')
        data=self.manager.overview()
        self.assertEqual(data['artifact_count'],2)
        self.assertTrue(all(not row['eligible'] for row in data['items']))
        self.assertEqual(data['preview']['candidates'],[])
        for row in data['items']:
            with self.assertRaises(Refused):self.manager.protect('admin:1',row['id'],False)

    def test_concurrent_operation_blocks_delete_backup_and_policy(self):
        a=self.archive('A','2026-11-01T00:00:00+00:00');self.archive('B','2026-11-02T00:00:00+00:00')
        self.manager.overview()
        with self.manager.lock():
            cached=self.manager.overview()
            self.assertTrue(cached['inventory_stale'])
            self.assertTrue(all(not row['eligible'] for row in cached['items']))
            for action in (lambda:self.manager.delete('admin:1',*a),lambda:self.manager.create('admin:1'),lambda:self.manager.policy('admin:1',1,{**DEFAULT,'daily':3})):
                with self.assertRaises(Refused):action()
        with self.manager.download('admin:1',a[0]) as (row,stream):
            self.assertEqual(stream.read(),(self.root/a[1]).read_bytes())
            with self.assertRaises(Refused):self.manager.delete('admin:1',*a)

    def test_policy_persistence_optimistic_revision_and_restart_no_backup(self):
        updated=self.policy(enabled=True,weekly=2)
        self.assertEqual(updated['revision'],2)
        with self.assertRaises(Refused):self.manager.policy('admin:2',1,DEFAULT)
        self.manager.close();self.manager=Manager(self.root,self.state,require_mount=False)
        self.assertEqual(self.manager.overview()['policy'],updated)
        self.assertFalse(tick(self.manager))
        self.assertEqual(self.manager.overview()['total'],0)

    def test_disabled_initialization_and_interrupted_job(self):
        self.assertFalse(self.manager.overview()['policy']['enabled'])
        self.assertFalse(tick(self.manager))
        job=self.manager.queue('admin:1')
        with self.assertRaises(Refused):self.manager.queue('admin:2')
        self.manager.close();self.manager=Manager(self.root,self.state,require_mount=False)
        self.assertEqual(self.manager.overview()['job']['status'],'interrupted')

    def test_low_storage_and_budget_never_predelete(self):
        self.archive('safe','2026-11-01T00:00:00+00:00',protected=True)
        self.policy(max_bytes=1024**2)
        with self.assertRaises(Refused):self.manager.queue('admin:1')
        self.policy(max_bytes=None)
        fs={**self.manager.filesystem(),'available_bytes':RESERVE+1}
        with patch.object(self.manager,'filesystem',return_value=fs):
            with self.assertRaises(Refused):self.manager.queue('admin:1')
        self.assertEqual(self.manager.overview()['total'],1)

    def test_estimate_uses_archive_sizes_not_database_allocation(self):
        self.assertEqual(self.manager.estimate([]),GIB)
        self.archive('measured','2026-11-01T00:00:00+00:00')
        row=self.manager.overview()['items'][0]
        self.assertEqual(self.manager.estimate([row]),int(row['bytes']*1.5+0.999)+64*1024**2)

    def test_failed_dump_and_failed_verification_do_not_rotate(self):
        protected=self.archive('protected','2026-01-01T00:00:00+00:00',protected=True)
        def output(command,**kwargs):
            return b'170012' if command[0]=='psql' else b'pg_dump (PostgreSQL) 17.12'
        for fail_verification in (False,True):
            original=subprocess.Popen
            def process(*args,**kwargs):
                return original([sys.executable,'-c',"import sys;sys.stdout.write('PGDMP fixture');sys.exit("+('0' if fail_verification else '1')+")"],**kwargs)
            with patch('management.subprocess.check_output',side_effect=output),patch('management.subprocess.Popen',side_effect=process),patch.object(self.manager,'decode',side_effect=subprocess.CalledProcessError(1,['pg_restore'])):
                result=self.manager.create('scheduler',origin='scheduled')
            self.assertEqual(result['status'],'failed')
            self.assertTrue((self.root/protected[1]).exists())
            self.assertEqual(self.manager.overview()['total'],1)

    def test_failed_partial_cleanup_records_pending_receipt_without_rotation(self):
        self.archive('protected','2026-01-01T00:00:00+00:00',protected=True)
        original=subprocess.Popen
        def process(*args,**kwargs):
            return original([sys.executable,'-c',"import sys;sys.stdout.write('partial');sys.exit(1)"],**kwargs)
        unlink=os.unlink
        def fail_partial(name,*args,**kwargs):
            if str(name).endswith('.partial'):raise OSError('simulated cleanup refusal')
            return unlink(name,*args,**kwargs)
        def output(command,**kwargs):
            return b'170012' if command[0]=='psql' else b'pg_dump (PostgreSQL) 17.12'
        with patch('management.subprocess.check_output',side_effect=output),patch('management.subprocess.Popen',side_effect=process),patch('management.os.unlink',side_effect=fail_partial):
            result=self.manager.create('scheduler',origin='scheduled')
        self.assertEqual(result['status'],'failed')
        self.assertTrue(result['cleanup_pending'])
        self.assertEqual(self.manager.overview()['total'],1)
        self.assertIn('backup.cleanup_pending',[r['action'] for r in self.manager.overview()['receipts']])

    def test_missing_root_permissions_and_required_mount(self):
        with self.assertRaises(Refused):Manager(self.root/'missing',self.state,require_mount=False)
        with self.assertRaises(Refused):Manager(self.root,self.state)
        self.root.chmod(0o755)
        with self.assertRaises(Refused):Manager(self.root,self.state,require_mount=False)
        self.root.chmod(0o700)

    def test_policy_bounds(self):
        for key,value in [('daily',0),('weekly',-1),('monthly',121),('minimum_recovery_points',0),('warning_free_bytes',1),('enabled','yes'),('max_bytes',-1)]:
            with self.assertRaises(Refused):validate_policy({**DEFAULT,key:value})

    def test_http_authentication_routes_and_no_unrestricted_listing(self):
        import urllib.request, urllib.error
        server=Server(('127.0.0.1',0),Handler);server.manager=self.manager;server.token='x'*40
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with self.assertRaises(urllib.error.HTTPError) as result:urllib.request.urlopen(base+'/overview')
            self.assertEqual(result.exception.code,401)
            for path,code in [('/overview',200),('/etc/passwd',404),('/backups/../../etc/passwd/download',404)]:
                request=urllib.request.Request(base+path,headers={'Authorization':'Bearer '+server.token,'X-Market-Actor':'admin:1'})
                if code==200:
                    with urllib.request.urlopen(request) as response:self.assertEqual(response.status,200)
                else:
                    with self.assertRaises(urllib.error.HTTPError) as result:urllib.request.urlopen(request)
                    self.assertEqual(result.exception.code,code)
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__ == '__main__':
    unittest.main()
