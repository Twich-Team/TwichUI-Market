"""Authenticated internal HTTP boundary and restart-safe scheduler; no Docker socket."""
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import signal
import threading
import time
import uuid
from urllib.parse import urlsplit, parse_qs

from management import Manager, Refused, date, stamp
from providers import StorageError, mapped


class Server(ThreadingHTTPServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(8)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # no token, file paths, transport errors or database diagnostics in logs

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def reply(self, code, value):
        payload = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer '+self.server.token):
            self.reply(401, {'detail': 'Management authorization required'})
            return
        actor = self.headers.get('X-Market-Actor', '')
        if not re.fullmatch(r'(admin:[1-9][0-9]{0,18}|scheduler)', actor):
            self.reply(403, {'detail': 'Auditable actor required'})
            return
        try:
            url = urlsplit(self.path)
            manager = self.server.manager
            body = {}
            if self.command == 'POST':
                length = self.headers.get('Content-Length', '')
                if not length.isdigit() or not 0 < int(length) <= 16384 or self.headers.get('Transfer-Encoding'):
                    self.reply(413, {'detail': 'Invalid management request size'})
                    return
                body = json.loads(self.rfile.read(int(length)))
                if not isinstance(body, dict):
                    raise Refused('Object required')
            if url.path == '/overview' and self.command == 'GET':
                query = parse_qs(url.query)
                offset, limit = int(query.get('offset', ['0'])[0]), int(query.get('limit', ['20'])[0])
                if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
                    raise Refused('Invalid pagination')
                self.reply(200, manager.overview(offset, limit))
            elif url.path == '/storage' and self.command == 'GET':
                self.reply(200,manager.storage_status())
            elif url.path == '/storage/save' and self.command == 'POST':
                self.reply(200,manager.storage_save(actor,body))
            elif url.path == '/storage/test' and self.command == 'POST':
                self.reply(200,manager.storage_test(actor,body['id']))
            elif url.path == '/storage/browse' and self.command == 'POST':
                self.reply(200,manager.storage_browse(actor,body['id'],body.get('directory',''),body.get('offset',0)))
            elif url.path == '/storage/mkdir' and self.command == 'POST':
                self.reply(200,manager.storage_mkdir(actor,body['id'],body['directory']))
            elif url.path == '/storage/migration-preview' and self.command == 'POST':
                self.reply(200,manager.migration_plan(body['id']))
            elif url.path == '/storage/migrate' and self.command == 'POST':
                job=manager.migration_queue(actor,body['id'],body['preview'])
                threading.Thread(target=run_background,args=(manager,actor,job['id'],'migration'),daemon=True).start()
                self.reply(202,job)
            elif url.path == '/storage/remove-originals' and self.command == 'POST':
                self.reply(200,manager.migration_remove_originals(actor,body['id'],body['confirmation']))
            elif url.path == '/delete-selected' and self.command == 'POST':
                job=manager.deletion_queue(actor,body['items'])
                threading.Thread(target=run_background,args=(manager,actor,job['id'],'deletion'),daemon=True).start()
                self.reply(202,job)
            elif url.path == '/restore-test' and self.command == 'POST':
                job=manager.restore_queue(actor,body['id'])
                threading.Thread(target=run_background,args=(manager,actor,job['id'],'restore'),daemon=True).start()
                self.reply(202,job)
            elif url.path == '/policy' and self.command == 'POST':
                self.reply(200, manager.policy(actor, body['revision'], body['values']))
            elif url.path == '/create' and self.command == 'POST':
                job = manager.queue(actor)
                threading.Thread(target=run_job, args=(manager, actor, job['id']), daemon=True).start()
                self.reply(202, job)
            elif match := re.fullmatch(r'/backups/([a-f0-9]{32})/(delete|protect|download|manifest)', url.path):
                key, action = match.groups()
                if action == 'delete' and self.command == 'POST':
                    # Large archives need checksum work outside the bounded API request.
                    with manager.lock(),manager.db() as db:
                        row=manager.find(db,key)
                        large=(row['bytes'] or 0)>64*1024**2 or manager.store.kind=='smb'
                    if large:
                        job=manager.deletion_queue(actor,[dict(body,id=key)])
                        threading.Thread(target=run_background,args=(manager,actor,job['id'],'deletion'),daemon=True).start()
                        self.reply(202,job)
                    else:self.reply(200,manager.delete(actor,key,body['confirmation'],confirm_protected=body.get('confirm_protected') is True,confirm_recovery_loss=body.get('confirm_recovery_loss') is True))
                elif action == 'protect' and self.command == 'POST' and type(body.get('protected')) is bool:
                    self.reply(200, manager.protect(actor, key, body['protected']))
                elif action in ('download', 'manifest') and self.command == 'GET':
                    with manager.download(actor, key) as (row, stream):
                        if action == 'manifest':
                            manifest = manager.read_json(row['filename'][:-5]+'.json')
                            self.reply(200, manifest)
                        else:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/octet-stream')
                            self.send_header('Content-Length', str(row['bytes']))
                            self.send_header('Content-Disposition', 'attachment; filename="'+row['filename']+'"')
                            self.send_header('Cache-Control', 'no-store')
                            self.end_headers()
                            while chunk := stream.read(1024**2):
                                self.wfile.write(chunk)
                else:
                    self.reply(405, {'detail': 'Unsupported operation'})
            else:
                self.reply(404, {'detail': 'Unknown management operation'})
        except (Refused, StorageError) as exc:
            self.reply(409, {'detail': str(exc)})
        except (KeyError, ValueError, TypeError):
            self.reply(422, {'detail': 'Invalid management input'})
        except (BrokenPipeError, ConnectionError, TimeoutError):
            return
        except Exception:
            self.reply(503, {'detail': 'Backup management unavailable; inspect the operations service'})


def run_job(manager, actor, key):
    # A brief competing download may hold the shared flock. Keep the queued job
    # durable, retry lock acquisition; restart marks it interrupted instead of rerunning.
    for _ in range(30):
        try:
            manager.create(actor, job_id=key)
            return
        except Refused:
            time.sleep(1)
    try:
        with manager.db() as db:
            job = manager.get(db, 'job', {})
            if job.get('id') == key and job.get('status') == 'queued':
                job.update(status='failed', error='Backup coordination stayed busy', finished_at=stamp())
                manager.set(db, 'job', job)
                manager.receipt(db, actor, 'backup.failed', job)
    except Refused:
        pass


def run_background(manager,actor,key,kind):
    callback={'migration':manager.migrate,'restore':manager.restore_test,'deletion':manager.deletion_run}[kind]
    setting={'migration':'migration','restore':'restore','deletion':'job'}[kind]
    for _ in range(30):
        try:
            callback(actor,key)
            return
        except Refused:
            time.sleep(1)
        except Exception:
            break
    with manager.db() as db:
        job=manager.get(db,setting,{})
        if job.get('id')==key and job.get('status') in ('queued','running'):
            job.update(status='failed',finished_at=stamp(),error='Operation interrupted or coordination stayed busy; inspect the retained audit receipts before retrying')
            manager.set(db,setting,job);manager.receipt(db,actor,kind+'.interrupted',dict(id=key))


def tick(manager):
    with manager.lock(), manager.db() as db:
        policy = manager.get(db, 'policy')
        if not policy['enabled']:
            return False
        due = manager.get(db, 'next_at')
        if not due or date(due) > datetime.now(timezone.utc):
            return False
        if any(manager.get(db,k,{}).get('status') in ('queued','running') for k in ('job','migration','restore')):
            return False
        manager.set(db, 'next_at', (datetime.now(timezone.utc)+timedelta(seconds=policy['interval_seconds'])).isoformat())
        job = dict(id=uuid.uuid4().hex, status='queued', actor='scheduler', requested_at=stamp())
        manager.set(db, 'job', job)
        manager.receipt(db, 'scheduler', 'backup.queued', job)
    manager.create('scheduler', origin='scheduled', job_id=job['id'])
    return True


def main():
    os.umask(0o077)
    token = Path(os.environ.get('BACKUP_MANAGER_TOKEN_FILE', '/run/secrets/backup-manager-token')).read_text().strip()
    if len(token) < 32 or len(token) > 256:
        raise SystemExit('A private management token is required')
    manager = Manager()
    server = Server(('0.0.0.0', 8091), Handler)
    server.token, server.manager = token, manager
    stopped = threading.Event()
    def stop(*_):
        stopped.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def schedule():
        while not stopped.wait(15):
            try:
                tick(manager)
            except Refused:
                pass
            except Exception:
                print('Backup scheduler paused; inspect management status', flush=True)
    threading.Thread(target=schedule, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
