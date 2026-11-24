"""Small persistent destination workflow; secrets use Market's existing AEAD keyring."""
from contextlib import contextmanager
import base64
import json
import os
import re
import time
import uuid

from providers import Local, SMB, StorageError, digest, mapped, relative, CHUNK

LOCAL = dict(id='local', type='local', name='Local backups', directory='', revision=1)


class StorageConfiguration:
    @property
    def store(self):
        key = getattr(self, '_location', None)
        with self.db() as db:
            key = key or self.get(db, 'storage_active', 'local')
            configs = self.get(db, 'storage_configs', {'local': LOCAL})
        if key not in self._stores:
            if key == 'local': self._stores[key] = Local(self.fd, self.open)
            else:
                c = configs[key]
                if c['type'] == 'mounted':
                    # Mounted compatibility is the existing approved /backups root, never arbitrary host paths.
                    self._stores[key] = Local(self.fd, self.open)
                else:
                    self._stores[key] = SMB(c, self.password(c),deadline=getattr(self,'_operation_deadline',None))
        return self._stores[key]

    @contextmanager
    def location(self, key):
        previous = self._location
        self._location = key
        try: yield self.store
        finally: self._location = previous

    def configs(self):
        with self.db() as db:
            return self.get(db, 'storage_configs', {'local': LOCAL}), self.get(db, 'storage_active', 'local')

    @staticmethod
    def public(config):
        return {**{k:v for k,v in config.items() if k not in ('secret','key_id')}, 'password_saved':bool(config.get('secret'))}

    @staticmethod
    def password(config):
        from provider_secrets import decrypt
        return decrypt('backup-smb:'+config['id'], config['key_id'], base64.b64decode(config['secret']))

    def storage_status(self):
        configs, active = self.configs()
        with self.db() as db:
            health = self.get(db, 'storage_health', {})
            job = self.get(db, 'migration', {})
            restore = self.get(db,'restore',{})
            recovery = self.get(db,'automatic_recovery',{})
        return dict(active_id=active, destinations=[self.public(c) for c in configs.values()], health=health, migration={**job,'plan':{k:v for k,v in job.get('plan',{}).items() if k!='items'}},restore=restore,restore_available=os.environ.get('BACKUP_RESTORE_TEST_ENABLED')=='true',
            automatic_recovery=recovery,automatic_restore_enabled=os.environ.get('BACKUP_AUTOMATIC_RESTORE')=='true',share_enumeration_supported=False,
            share_notice='This native SMB client does not enumerate server shares. Enter a known share; folders can then be browsed.',
            mounted_notice='Mounted filesystem uses the installation’s existing persistent backup directory. Native SMB needs no host mount.')

    def storage_save(self, actor, values):
        from management import Refused
        allowed = {'id','revision','type','name','host','port','username','password','domain','share','directory','require_encryption'}
        if set(values)-allowed or values.get('type') not in ('smb','local','mounted'):
            raise Refused('Choose Local, SMB / NAS or the existing mounted filesystem')
        if not isinstance(values.get('name'),str) or not 1 <= len(values['name'].strip()) <= 80:
            raise Refused('Enter a storage name of 1–80 characters')
        with self.lock(), self.db() as db:
            self.idle(db)
            configs = self.get(db, 'storage_configs', {'local':LOCAL})
            active = self.get(db,'storage_active','local')
            key = values.get('id') or uuid.uuid4().hex
            old = configs.get(key,{})
            if old and values.get('revision') != old['revision']:
                raise Refused('Storage configuration changed; refresh before saving')
            identity=('type','directory','host','port','share') if old.get('type')=='smb' else ('type','directory')
            if key == active and any(values.get(k,old.get(k)) != old.get(k) for k in identity):
                raise Refused('Configure a new destination to change the active backup location; existing files are preserved')
            # One active, one previous and one candidate keeps location tracking deliberately small.
            previous = self.get(db, 'storage_previous')
            keep = {active, previous, 'local'}
            if len(configs) >= 4 and key not in configs:
                raise Refused('Finish the existing migration before adding another destination')
            c = {k:v for k,v in values.items() if k not in ('password','revision')}
            c.update(id=key, revision=old.get('revision',0)+1, directory=relative(values.get('directory',''),empty=True))
            if c['type'] == 'smb':
                if not isinstance(c.get('host'),str) or not isinstance(c.get('username'),str) or not 1<=len(c['username'])<=160 or len(c.get('domain',''))>100:
                    raise Refused('Enter a NAS address and dedicated account username')
                if c.get('port',445) != 445: raise Refused('Only SMB TCP port 445 is supported')
                relative(c.get('share',''))
                if '/' in c['share'] or c['share'].endswith('$'): raise Refused('Choose a regular NAS share')
                if type(c.get('require_encryption',True)) is not bool: raise Refused('Choose an encryption setting')
                if values.get('password') is not None:
                    password=values['password']
                    if not isinstance(password,str) or not 1<=len(password)<=1024: raise Refused('Enter a password, or leave it unchanged when editing')
                    from provider_secrets import encrypt
                    kid,secret=encrypt('backup-smb:'+key,password)
                    c.update(key_id=kid,secret=base64.b64encode(secret).decode())
                elif old.get('secret'): c.update(secret=old['secret'],key_id=old['key_id'])
                else: raise Refused('Enter the NAS account password')
            configs[key] = c
            health=self.get(db,'storage_health',{});health.pop(key,None);self.set(db,'storage_health',health)
            self.set(db,'storage_configs',configs)
            self.receipt(db,actor,'storage.saved',dict(id=key,revision=c['revision'],credential_updated=values.get('password') is not None))
            return self.public(c)

    @staticmethod
    def idle(db):
        from management import Manager, Refused
        if any(Manager.get(db,k,{}).get('status') in ('queued','running') for k in ('job','migration','restore')):
            raise Refused('A backup, migration or restore is already queued or running')

    def candidate(self, key):
        from management import Refused
        configs, _ = self.configs()
        if key not in configs: raise Refused('Unknown storage destination')
        return configs[key]

    def throttle(self,db,actor,category,limit):
        from management import Refused
        key='storage_attempts:'+str(actor)+':'+category
        recent=[t for t in self.get(db,key,[]) if t>time.time()-60]
        if len(recent)>=limit:raise Refused('Too many storage operations; wait one minute before retrying')
        self.set(db,key,[*recent,time.time()]);db.commit()

    def storage_test(self, actor, key):
        from management import stamp
        with self.lock(), self.db() as db:
            self.idle(db)
            self.throttle(db,actor,'connection',10)
            config=self.candidate(key)
            self._operation_deadline=time.monotonic()+20
            report=dict(id=key,revision=config['revision'],tested_at=stamp(),reachable=False,authenticated=False,share_accessible=False,
                directory_exists=False,read=False,write=False,create_directory=False,rename=False,delete=False,healthy=False,
                capacity_bytes=None,available_bytes=None)
            temp='.market-test-'+uuid.uuid4().hex
            created=[]
            store=None
            try:
                with self.location(key) as store:
                    report.update(reachable=True,authenticated=True,share_accessible=True,directory_exists=True)
                    store.names();report['read']=True
                    with store.open(temp,'xb') as out:out.write(b'Market backup storage permission test\n')
                    created.append(temp);report['write']=True
                    if digest(store,temp) != __import__('hashlib').sha256(b'Market backup storage permission test\n').hexdigest():
                        raise StorageError('NAS test read did not match its written content')
                    store.rename(temp,temp+'-renamed');created=[temp+'-renamed'];report['rename']=True
                    store.remove(temp+'-renamed');created=[];report['delete']=True
                    if config['type']=='smb':
                        store.mkdir(temp);created=[temp+'/'];report['create_directory']=True
                        store.remove(temp,directory=True);created=[]
                    else:report['create_directory']=None
                    report.update(store.capacity());report['healthy']=True;report['last_success_at']=stamp()
            except Exception as exc:
                stage=getattr(exc,'connection_stage',None)
                if stage is not None:
                    report['reachable']=stage in ('authenticate','share','directory')
                    report['authenticated']=stage in ('share','directory')
                    report['share_accessible']=stage=='directory'
                report['error']=str(mapped(exc))
            finally:
                if store is not None:store.deadline=time.monotonic()+2
                for name in created:
                    try: store.remove(name.rstrip('/'),directory=name.endswith('/')) if name.endswith('/') else store.remove(name)
                    except Exception:report['cleanup_pending']=True
            health=self.get(db,'storage_health',{});previous=health.get(key,{})
            if not report.get('last_success_at') and previous.get('last_success_at'):report['last_success_at']=previous['last_success_at']
            health[key]=report;self.set(db,'storage_health',health)
            self.receipt(db,actor,'storage.tested',dict(id=key,healthy=report['healthy'],cleanup_pending=report.get('cleanup_pending',False)))
            return report

    def storage_browse(self, actor, key, directory='', offset=0):
        from management import Refused
        config=self.candidate(key)
        if config['type']!='smb':raise Refused('The existing local backup root does not expose host directory browsing')
        directory=relative(directory,empty=True)
        if type(offset) is not int or not 0<=offset<=2000:raise Refused('Invalid folder page')
        # Browser starts at the selected share, not a general remote filesystem.
        with self.lock(), self.db() as db:
            self.idle(db)
            self.throttle(db,actor,'browse',60)
            browse_config={**config,'directory':''}
            store=SMB(browse_config,self.password(config),deadline=time.monotonic()+20)
            try:
                store._check_directory(directory)
                entries=store.entries(directory,maximum=2000)
                folders=sorted(e['name'] for e in entries if e['directory'] and not e['name'].startswith('.'))
                return dict(directory=directory,folders=folders[offset:offset+100],offset=offset,next_offset=offset+100 if len(folders)>offset+100 else None)
            finally:store.close()

    def storage_mkdir(self, actor, key, directory):
        from management import Refused
        config=self.candidate(key)
        if config['type']!='smb':raise Refused('Folder creation is restricted to the NAS share')
        relative(directory)
        with self.lock(), self.db() as db:
            self.idle(db)
            self.throttle(db,actor,'browse',60)
            store=SMB({**config,'directory':''},self.password(config),deadline=time.monotonic()+20)
            try:store.mkdir(directory)
            finally:store.close()
            self.receipt(db,actor,'storage.folder.created',dict(id=key))
            return dict(created=True)

    def migration_assessment(self, key):
        from management import Refused
        self.candidate(key)
        with self.lock(),self.db() as db:
            self.idle(db)
            configs,active=self.configs()
            if key==active:raise Refused('Destination is already active')
            if configs[key]['type']!='smb' and configs[active]['type']!='smb':
                raise Refused('Both destinations refer to the existing backup filesystem; no copy is needed')
            tested=self.get(db,'storage_health',{}).get(key,{})
            from management import date
            from datetime import datetime,timezone
            if not tested.get('healthy') or tested.get('revision')!=configs[key]['revision'] or not tested.get('tested_at') or (datetime.now(timezone.utc)-date(tested['tested_at'])).total_seconds()>900:
                raise Refused('Test the saved destination successfully before previewing migration')
            with self.location(active):rows,other=self.rows_current()
            if any(r['verification']!='archive_integrity_verified' for r in rows):raise Refused('Unverified legacy archives need separate classification before migration')
            with self.location(key) as destination:
                capacity=destination.capacity()
            total=sum(r['bytes'] for r in rows)
            return dict(source_id=active,destination_id=key,source_revision=configs[active]['revision'],destination_revision=configs[key]['revision'],
                count=len(rows),bytes=total,protected_count=sum(r['protected'] for r in rows),available_bytes=capacity['available_bytes'],
                enough_space=capacity['available_bytes'] is None or capacity['available_bytes']>=total+2*1024**3,
                originals_preserved=True,items=[dict(id=r['id'],filename=r['filename'],sha256=r['sha256'],bytes=r['bytes']) for r in rows])

    def migration_plan(self,key):
        plan=self.migration_assessment(key)
        token=uuid.uuid4().hex
        with self.db() as db:self.set(db,'migration_preview',dict(token=token,expires=time.time()+900,plan=plan))
        return dict({k:v for k,v in plan.items() if k!='items'},token=token)

    def migration_queue(self,actor,key,expected):
        from management import Refused,stamp
        with self.db() as db:saved=self.get(db,'migration_preview',{})
        if not saved or saved['expires']<time.time() or expected!=dict({k:v for k,v in saved['plan'].items() if k!='items'},token=saved['token']):
            raise Refused('Migration preview expired or changed; review a fresh preview')
        plan=self.migration_assessment(key)
        # Free space fluctuates; recheck the current reserve without invalidating unchanged inventory.
        if any(plan[k]!=saved['plan'][k] for k in ('items','source_id','destination_id','source_revision','destination_revision')):
            raise Refused('Migration inventory or destination changed; review a fresh preview')
        if not plan['enough_space']:raise Refused('Destination cannot fit the verified migration and safety reserve')
        with self.lock(),self.db() as db:
            self.idle(db)
            job=dict(id=uuid.uuid4().hex,status='queued',actor=str(actor),plan=plan,copied=0,bytes_copied=0,requested_at=stamp())
            self.set(db,'migration',job);self.receipt(db,actor,'storage.migration.queued',dict(id=job['id'],destination_id=key))
            return {k:v for k,v in job.items() if k!='plan'}

    def migrate(self,actor,job_id):
        from management import Refused,stamp
        with self.lock(),self.db() as db:
            job=self.get(db,'migration',{})
            if job.get('id')!=job_id or job.get('status')!='queued':raise Refused('Migration job changed')
            job.update(status='running',started_at=stamp());self.set(db,'migration',job);db.commit()
            plan=job['plan'];destination_id=plan['destination_id'];source_id=plan['source_id']
            try:
                configs,active=self.configs()
                if active!=source_id or configs[destination_id]['revision']!=plan['destination_revision'] or configs[source_id]['revision']!=plan['source_revision']:
                    raise Refused('Storage configuration changed; preview migration again')
                started=time.monotonic()
                with self.location(source_id):
                    current,_=self.rows_current()
                if [dict(id=r['id'],filename=r['filename'],sha256=r['sha256'],bytes=r['bytes']) for r in current]!=plan['items']:
                    raise Refused('Source inventory changed; preview migration again')
                source=self.provider_for(source_id);destination=self.provider_for(destination_id)
                for row in current:
                    if time.monotonic()-started>7200:raise Refused('Migration time budget reached; verified copies can be reused on retry')
                    name=row['filename'];temporary='.migration-'+job_id+'-'+name
                    try:
                        existing=destination.info(name)
                    except FileNotFoundError:existing=None
                    if existing:
                        if existing['bytes']!=row['bytes'] or digest(destination,name)!=row['sha256']:
                            raise Refused('Destination filename conflicts with a different archive; originals retained')
                    else:
                        try:destination.remove(temporary)
                        except FileNotFoundError:pass
                        try:
                            with source.open(name) as src,destination.open(temporary,'xb') as dst:
                                for block in iter(lambda:src.read(CHUNK),b''):
                                    if time.monotonic()-started>7200:raise Refused('Migration time budget reached')
                                    dst.write(block)
                            if digest(destination,temporary)!=row['sha256']:raise Refused('Migration checksum mismatch; original retained')
                            destination.rename(temporary,name)
                        finally:
                            try:destination.remove(temporary)
                            except FileNotFoundError:pass
                    with self.location(source_id):manifest=self.read_json(name[:-5]+'.json')
                    manifest['file_identity']=destination.info(name)['identity']
                    with self.location(destination_id):self.write_json(name[:-5]+'.json',manifest)
                    job['copied']+=1;job['bytes_copied']+=row['bytes'];self.set(db,'migration',job);db.commit()
                with self.location(destination_id):verified,_=self.rows_current()
                if not all(any(v['filename']==r['filename'] and v['sha256']==r['sha256'] and v['verification']=='archive_integrity_verified' for v in verified) for r in current):
                    raise Refused('Copied inventory failed reconciliation; original destination remains active')
                self.set(db,'storage_previous',source_id);self.set(db,'storage_active',destination_id)
                job.update(status='succeeded',finished_at=stamp(),originals_preserved=True)
                self.receipt(db,actor,'storage.migration.activated',dict(id=job_id,source_id=source_id,destination_id=destination_id,count=job['copied']))
            except Exception as exc:
                job.update(status='failed',finished_at=stamp(),error=str(mapped(exc)),originals_preserved=True)
                self.receipt(db,actor,'storage.migration.failed',dict(id=job_id))
            self.set(db,'migration',job)
            return job

    def provider_for(self,key):
        with self.location(key) as store:return store

    def migration_remove_originals(self,actor,job_id,confirmation,*,confirm_protected=False):
        from management import Refused
        if confirmation!='REMOVE VERIFIED ORIGINALS':raise Refused('Type REMOVE VERIFIED ORIGINALS to confirm')
        with self.lock(),self.db() as db:
            self.idle(db)
            job=self.get(db,'migration',{})
            if job.get('id')!=job_id or job.get('status')!='succeeded':raise Refused('A completed verified migration is required')
            plan=job['plan'];configs,active=self.configs()
            if active!=plan['destination_id']:raise Refused('Migrated destination is no longer active')
            source=self.provider_for(plan['source_id']);destination=self.provider_for(active)
            if plan.get('protected_count',0) and not confirm_protected:
                raise Refused('Explicit protected original-copy deletion acknowledgement is required')
            results=[]
            # Revalidate every target before deleting ANY original. A disconnect cannot become an empty inventory.
            for row in plan['items']:
                if digest(destination,row['filename'])!=row['sha256']:raise Refused('Destination verification failed; all originals retained')
            for row in plan['items']:
                name=row['filename']
                try:
                    if digest(source,name)!=row['sha256']:raise Refused('Original changed; retained')
                    with self.location(plan['source_id']):manifest=self.read_json(name[:-5]+'.json')
                    if manifest.get('required_by'):raise Refused('Original is still required by an active recovery operation')
                    if manifest.get('protected') and not confirm_protected:raise Refused('Original became protected; explicit acknowledgement is required')
                    self.receipt(db,actor,'migration.original.deletion.intent',dict(job_id=job_id,filename=name));db.commit()
                    source.remove(name);source.remove(name[:-5]+'.json')
                    results.append(dict(filename=name,status='deleted'))
                except FileNotFoundError:results.append(dict(filename=name,status='already_missing'))
                except Exception:results.append(dict(filename=name,status='retained',error='Original could not be safely removed'))
            self.receipt(db,actor,'migration.originals.result',dict(job_id=job_id,results=results))
            return dict(results=results)
