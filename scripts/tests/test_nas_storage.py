"""Fault injection uses isolated directories; actual SMB is verified separately."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'deploy/backup'))
from management import Manager, Refused, identifier, stamp
from providers import Local, StorageError, digest, relative


class NASStorage(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        self.local=root/'local';self.local.mkdir(mode=0o700)
        self.remote=root/'nas';self.remote.mkdir(mode=0o700)
        self.manager=Manager(self.local,root/'state',require_mount=False)
        self.remote_manager=Manager(self.remote,root/'remote-state',require_mount=False)
        self.key='b'*32
        self.destination=dict(id=self.key,revision=1,type='smb',name='Synthetic NAS',host='192.168.1.2',port=445,
            username='fixture',share='backups',directory='',secret='fixture',key_id='fixture')
        with self.manager.db() as db:
            self.manager.set(db,'storage_configs',{'local':dict(id='local',revision=1,type='local',name='Local',directory=''),self.key:self.destination})
            self.manager.set(db,'storage_health',{self.key:dict(healthy=True,revision=1,tested_at=stamp())})
        class FakeRemote(Local):
            kind='smb'
        self.remote_store=FakeRemote(self.remote_manager.fd,self.remote_manager.open)
        self.factory=patch('storage_config.SMB',return_value=self.remote_store);self.factory.start()
        self.password=patch.object(self.manager,'password',return_value='synthetic-secret');self.password.start()

    def tearDown(self):
        self.password.stop();self.factory.stop()
        self.manager.close();self.remote_manager.close();self.temp.cleanup()

    def archive(self,name='market-fixture.dump',protected=True):
        path=self.local/name;path.write_bytes(b'PGDMP isolated test fixture')
        info=path.stat()
        manifest=dict(version=2,manager='market-backups-v2',filename=name,origin='manual',created_at='2026-11-24T01:00:00+00:00',
            bytes=info.st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),postgres_major=17,
            verification='archive_integrity_verified',restoration_verified_at=None,protected=protected,required_by=[],
            file_identity=[info.st_ino,info.st_size,info.st_mtime_ns])
        self.manager.write_json(name[:-5]+'.json',manifest)
        return identifier(name),name

    def migrate(self):
        plan=self.manager.migration_plan(self.key)
        job=self.manager.migration_queue('admin:1',self.key,plan)
        return self.manager.migrate('admin:1',job['id'])

    def test_protected_deletion_requires_both_acknowledgements_without_unprotect(self):
        key,name=self.archive()
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name,confirm_protected=True)
        result=self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True)
        self.assertEqual(result['status'],'deleted')
        with self.manager.db() as db:
            self.assertFalse(db.execute("SELECT 1 FROM receipts WHERE action='protection.updated'").fetchone())
        self.assertFalse((self.local/name).exists())

    def test_required_recovery_backup_cannot_be_overridden(self):
        key,name=self.archive()
        manifest=self.manager.read_json(name[:-5]+'.json');manifest['required_by']=['active-recovery']
        self.manager.write_json(name[:-5]+'.json',manifest)
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True)
        self.assertTrue((self.local/name).exists())

    def test_bulk_reports_each_partial_failure_and_missing_file(self):
        key,name=self.archive()
        result=self.manager.bulk_delete('admin:1',[dict(id=key,confirmation=name,confirm_protected=True,confirm_recovery_loss=True),dict(id='c'*32,confirmation='market-missing.dump')])
        self.assertEqual([r['status'] for r in result['results']],['deleted','retained'])
        self.assertEqual(result['status'],'partial_failure')
        self.assertEqual(self.manager.bulk_delete('admin:1',[dict(id=key,confirmation=name)])['results'][0]['status'],'retained')

    def test_migration_preserves_original_metadata_and_scopes_identifiers(self):
        key,name=self.archive();before=self.manager.read_json(name[:-5]+'.json')
        result=self.migrate();self.assertEqual(result['status'],'succeeded',result)
        after=self.manager.read_json(name[:-5]+'.json')
        self.assertEqual({k:v for k,v in before.items() if k!='file_identity'},{k:v for k,v in after.items() if k!='file_identity'})
        row=self.manager.overview()['items'][0]
        self.assertNotEqual(row['id'],key);self.assertEqual(row['storage_id'],self.key);self.assertTrue(row['protected'])
        self.assertTrue((self.local/name).exists())
        result=self.manager.delete('admin:1',row['id'],name,confirm_protected=True,confirm_recovery_loss=True)
        self.assertEqual(result['status'],'deleted')
        # A retried remote deletion must never delete the separately identified local original.
        with self.assertRaises(Refused):self.manager.delete('admin:1',row['id'],name,confirm_protected=True,confirm_recovery_loss=True)
        self.assertTrue((self.local/name).exists())

    def test_insufficient_capacity_never_activates_destination(self):
        self.archive()
        with patch.object(self.remote_store,'capacity',return_value=dict(available_bytes=1,capacity_bytes=2)):
            plan=self.manager.migration_plan(self.key)
            self.assertFalse(plan['enough_space'])
            with self.assertRaises(Refused):self.manager.migration_queue('admin:1',self.key,plan)
        self.assertEqual(self.manager.storage_status()['active_id'],'local')

    def test_conflicting_destination_never_overwritten(self):
        _,name=self.archive();(self.remote/name).write_bytes(b'different')
        result=self.migrate()
        self.assertEqual(result['status'],'failed');self.assertEqual((self.remote/name).read_bytes(),b'different')
        self.assertEqual(self.manager.storage_status()['active_id'],'local')
        self.assertTrue((self.local/name).exists())

    def test_checksum_failure_keeps_original_and_old_destination(self):
        _,name=self.archive()
        real=digest
        with patch('storage_config.digest',side_effect=lambda provider,name:'0'*64 if name.startswith('.migration-') else real(provider,name)):
            result=self.migrate()
        self.assertEqual(result['status'],'failed');self.assertTrue((self.local/name).exists())
        self.assertFalse((self.remote/name).exists());self.assertEqual(self.manager.storage_status()['active_id'],'local')
        self.assertEqual(self.migrate()['status'],'succeeded')

    def test_transfer_failure_cleans_partial_and_retry_recovers(self):
        _,name=self.archive()
        real=self.remote_store.open
        def fail(name,mode='rb'):
            if mode=='xb' and name.startswith('.migration-'):raise StorageError('Injected network outage')
            return real(name,mode)
        with patch.object(self.remote_store,'open',side_effect=fail):result=self.migrate()
        self.assertEqual(result['status'],'failed');self.assertTrue((self.local/name).exists())
        self.assertEqual(list(self.remote.glob('.migration-*')),[])
        self.assertEqual(self.migrate()['status'],'succeeded')

    def test_outage_preserves_cached_inventory_and_never_looks_empty(self):
        self.archive();self.assertEqual(self.migrate()['status'],'succeeded')
        before=self.manager.overview()
        with patch('storage_config.SMB',side_effect=StorageError('Injected unavailable NAS')):
            cached=self.manager.overview()
            self.assertTrue(cached['inventory_stale']);self.assertEqual([r['id'] for r in cached['items']],[r['id'] for r in before['items']]);self.assertTrue(all(not r['eligible'] for r in cached['items']));self.assertEqual(cached['service_status'],'storage_unavailable')
            self.assertEqual(cached['total'],1)
        self.assertEqual(self.manager.overview()['total'],1)

    def test_explicit_original_cleanup_verifies_destination_first(self):
        _,name=self.archive();result=self.migrate()
        with self.assertRaises(Refused):self.manager.migration_remove_originals('admin:1',result['id'],'yes')
        (self.remote/name).write_bytes(b'corrupt')
        with self.assertRaises(Refused):self.manager.migration_remove_originals('admin:1',result['id'],'REMOVE VERIFIED ORIGINALS',confirm_protected=True)
        self.assertTrue((self.local/name).exists())

    def test_migration_preview_is_bounded_and_rejects_changed_source(self):
        self.archive();plan=self.manager.migration_plan(self.key)
        self.assertNotIn('items',plan);self.assertLess(len(json.dumps(plan)),1024)
        self.archive('market-second.dump')
        with self.assertRaises(Refused):self.manager.migration_queue('admin:1',self.key,plan)

    def test_settings_and_jobs_survive_restart_without_rerunning(self):
        self.archive()
        plan=self.manager.migration_plan(self.key);job=self.manager.migration_queue('admin:1',self.key,plan)
        self.manager.close()
        self.manager=Manager(self.local,Path(self.temp.name)/'state',require_mount=False)
        status=self.manager.storage_status()
        self.assertEqual(status['migration']['status'],'interrupted');self.assertEqual(status['active_id'],'local')
        self.assertEqual(len(status['destinations']),2)

    def test_large_deletion_job_is_durable_and_preserves_confirmations(self):
        key,name=self.archive()
        queued=self.manager.deletion_queue('admin:1',[dict(id=key,confirmation=name,confirm_protected=True,confirm_recovery_loss=True)])
        self.assertEqual(queued['status'],'queued')
        with self.assertRaises(Refused):self.manager.queue('admin:1')
        result=self.manager.deletion_run('admin:1',queued['id'])
        self.assertEqual(result['status'],'succeeded');self.assertFalse((self.local/name).exists())

    def test_network_attempt_rate_limit_is_persistent_and_bounded(self):
        with self.manager.db() as db:
            for _ in range(10):self.manager.throttle(db,'admin:1','connection',10)
            with self.assertRaises(Refused):self.manager.throttle(db,'admin:1','connection',10)

    def test_restore_target_refuses_production_server(self):
        from recovery import target_environment
        with patch.dict(os.environ,dict(PGHOST='production-db',PGDATABASE='market',RESTORE_PGHOST='production-db'),clear=True):
            with self.assertRaises(Refused):target_environment()
        with patch.dict(os.environ,dict(PGHOST='production-db',PGDATABASE='market'),clear=True):
            with self.assertRaises(Refused):target_environment()
        with patch.dict(os.environ,dict(PGHOST='production-db',PGDATABASE='market',RESTORE_PGHOST='isolated-db'),clear=True):
            self.assertEqual(target_environment()['PGHOST'],'isolated-db')

    def test_destination_alias_is_rejected_before_migration_or_deletion(self):
        self.archive()
        with patch('storage_config.SMB',return_value=Local(self.manager.fd,self.manager.open)):
            with self.assertRaises(Refused):self.manager.migration_plan(self.key)
        self.assertEqual(self.manager.overview()['total'],1)
        self.assertEqual(list(self.local.glob('.market-location-*')),[])

    def test_restart_tracks_only_journaled_incomplete_files_and_cleanup_retries(self):
        name='market-interrupted-fixture.partial'
        (self.local/name).write_bytes(b'incomplete')
        (self.local/'market-unknown.partial').write_bytes(b'unknown provenance')
        with self.manager.db() as db:
            self.manager.set(db,'job',dict(id='c'*32,status='running',temporary=name,storage_id='local'))
        self.manager.close();self.manager=Manager(self.local,Path(self.temp.name)/'state',require_mount=False)
        self.assertEqual(self.manager.storage_status()['pending_cleanup_count'],1)
        result=self.manager.cleanup_incomplete('admin:1')
        self.assertEqual(result['receipts_reconciled'],1)
        self.assertFalse((self.local/name).exists());self.assertTrue((self.local/'market-unknown.partial').exists())

    def test_startup_serves_configuration_without_connecting_to_an_unavailable_nas(self):
        with self.manager.db() as db:
            self.manager.set(db,'storage_active',self.key)
            self.manager.receipt(db,'admin:1','deletion.intent',dict(backup=dict(filename='market-gone.dump',storage_id=self.key),manifest={}))
        self.manager.close()
        with patch('storage_config.SMB',side_effect=StorageError('Unavailable')) as connect:
            self.manager=Manager(self.local,Path(self.temp.name)/'state',require_mount=False)
            self.assertEqual(self.manager.storage_status()['active_id'],self.key)
            connect.assert_not_called()

    def test_recovery_proof_rejects_changed_archive_identity(self):
        from recovery import proof
        key,name=self.archive()
        manifest=self.manager.read_json(name[:-5]+'.json')
        manifest.update(recovery_pin=True,required_by=['automatic-retention'],restoration_verified_at=stamp(),restored={'tables':1})
        self.manager.write_json(name[:-5]+'.json',manifest)
        with self.manager.db() as db:
            self.manager.set(db,'automatic_recovery',dict(backup_id=key,sha256=manifest['sha256'],bytes=manifest['bytes'],file_identity=manifest['file_identity'],verified_at=manifest['restoration_verified_at']))
        self.assertTrue(proof(self.manager,key)['protected'])
        (self.local/name).write_bytes(b'changed')
        with self.assertRaises(Refused):proof(self.manager,key)

    def test_completed_reservations_can_be_explicitly_deleted_without_unprotecting(self):
        key,name=self.archive()
        manifest=self.manager.read_json(name[:-5]+'.json');manifest['required_by']=['release:completed','restore-recovery-gate']
        self.manager.write_json(name[:-5]+'.json',manifest)
        directory=Path(self.temp.name)/'recovery';directory.mkdir();(directory/'evidence.json').write_text(json.dumps({'backup_id':'f'*32}))
        with patch.dict(os.environ,{'BACKUP_RECOVERY_DIRECTORY':str(directory)}):
            row=self.manager.overview()['items'][0]
            self.assertTrue(row['reserved']);self.assertFalse(row['active_use'])
            with self.assertRaises(Refused):self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True)
            result=self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True,confirm_reserved=True)
            self.assertEqual(result['status'],'deleted')

    def test_live_cleanup_lease_prevents_recovery_deletion_until_expiration(self):
        from recovery import proof
        from datetime import datetime,timezone,timedelta
        key,name=self.archive()
        manifest=self.manager.read_json(name[:-5]+'.json')
        manifest.update(recovery_pin=True,required_by=['automatic-retention'],restoration_verified_at=stamp(),restored={'tables':1})
        self.manager.write_json(name[:-5]+'.json',manifest)
        with self.manager.db() as db:self.manager.set(db,'automatic_recovery',dict(backup_id=key,sha256=manifest['sha256'],bytes=manifest['bytes'],file_identity=manifest['file_identity'],verified_at=manifest['restoration_verified_at']))
        proof(self.manager,key)
        with self.assertRaises(Refused):self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True,confirm_reserved=True)
        with self.manager.db() as db:self.manager.set(db,'recovery_lease_until',(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
        self.assertEqual(self.manager.delete('admin:1',key,name,confirm_protected=True,confirm_recovery_loss=True,confirm_reserved=True)['status'],'deleted')

    def test_original_copy_cleanup_is_a_durable_background_operation(self):
        _,name=self.archive();migration=self.migrate();self.assertEqual(migration['status'],'succeeded')
        queued=self.manager.original_cleanup_queue('admin:1',migration['id'],'REMOVE VERIFIED ORIGINALS',True,True)
        self.assertTrue((self.local/name).exists())
        result=self.manager.original_cleanup_run('admin:1',queued['id'])
        self.assertEqual(result['status'],'succeeded',result);self.assertEqual(result['removed'],1)
        self.assertTrue((self.remote/name).exists());self.assertFalse((self.local/name).exists())

    def test_local_adoption_publication_failure_backs_off_and_preserves_protection(self):
        from recovery import automatic_tick
        key,name=self.archive()
        manifest=self.manager.read_json(name[:-5]+'.json')
        manifest.update(created_at=stamp(),restoration_verified_at=stamp(),restored={'tables':1})
        self.manager.write_json(name[:-5]+'.json',manifest)
        with patch.dict(os.environ,{'BACKUP_AUTOMATIC_RESTORE':'true'}),patch('recovery.publish_recovery',side_effect=Refused('Unavailable evidence directory')) as publish:
            self.assertFalse(automatic_tick(self.manager))
            self.assertFalse(automatic_tick(self.manager))
            self.assertEqual(publish.call_count,1)
        self.assertEqual(self.manager.read_json(name[:-5]+'.json'),manifest)
        with self.manager.db() as db:self.assertTrue(self.manager.get(db,'automatic_restore_retry'))

    def test_interrupted_original_cleanup_is_visible_after_restart(self):
        self.archive();migration=self.migrate()
        self.manager.original_cleanup_queue('admin:1',migration['id'],'REMOVE VERIFIED ORIGINALS',True,True)
        self.manager.close();self.manager=Manager(self.local,Path(self.temp.name)/'state',require_mount=False)
        self.assertEqual(self.manager.storage_status()['original_cleanup']['status'],'interrupted')

    def test_verified_original_cleanup_retires_empty_previous_nas(self):
        self.archive();self.assertEqual(self.migrate()['status'],'succeeded')
        self.assertTrue(self.manager.storage_test('admin:1','local')['healthy'])
        plan=self.manager.migration_plan('local');queued=self.manager.migration_queue('admin:1','local',plan)
        result=self.manager.migrate('admin:1',queued['id']);self.assertEqual(result['status'],'succeeded',result)
        removed=self.manager.migration_remove_originals('admin:1',result['id'],'REMOVE VERIFIED ORIGINALS',confirm_protected=True)
        self.assertEqual(removed['results'][0]['status'],'deleted')
        with patch('storage_config.SMB',side_effect=StorageError('Old NAS is offline')) as old:
            self.assertFalse(self.manager.overview()['inventory_stale']);old.assert_not_called()

    def test_previous_storage_identity_cannot_be_relocated_while_originals_are_tracked(self):
        self.archive();self.assertEqual(self.migrate()['status'],'succeeded')
        self.assertTrue(self.manager.storage_test('admin:1','local')['healthy'])
        plan=self.manager.migration_plan('local');job=self.manager.migration_queue('admin:1','local',plan)
        self.assertEqual(self.manager.migrate('admin:1',job['id'])['status'],'succeeded')
        values=dict(id=self.key,revision=1,type='smb',name='Previous NAS',host='192.168.9.9',port=445,username='fixture',share='backups',directory='')
        with self.assertRaises(Refused):self.manager.storage_save('admin:1',values)
        with self.assertRaises(Refused):self.manager.storage_save('admin:1',dict(values,type='mounted'))
        self.assertEqual(self.manager.candidate(self.key)['host'],'192.168.1.2')
