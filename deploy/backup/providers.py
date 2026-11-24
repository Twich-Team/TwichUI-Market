"""Backup-only streaming storage. SMB uses one pinned peer, never DFS referrals."""
from contextlib import contextmanager
import errno
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import uuid

CHUNK = 1024 * 1024
MAX_ENTRIES = 10000


class StorageError(ValueError):
    pass


def relative(value, *, empty=False):
    if not isinstance(value, str) or len(value) > 1024 or (not value and not empty):
        raise StorageError('Choose a valid folder within the selected share')
    if value and any(not p or p in ('.', '..') or len(p) > 180 or p[-1:] in (' ', '.') or
                     re.search(r'[\x00-\x1f\\:*?"<>|]', p) for p in value.split('/')):
        raise StorageError('Folder names cannot contain paths, traversal or special network characters')
    return value


def endpoint(host, port):
    if type(port) is not int or port != 445:
        raise StorageError('Native SMB uses TCP port 445; other ports are not permitted')
    if not isinstance(host, str) or len(host) > 253 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.:-]*', host):
        raise StorageError('Enter a NAS hostname or IP address, without a URL or path')
    # DNS resolution also has a deadline, independently of the SMB connect deadline.
    code = 'import socket,json,sys;print(json.dumps(sorted({r[4][0] for r in socket.getaddrinfo(sys.argv[1],445,type=socket.SOCK_STREAM)})))'
    try:
        addresses = json.loads(subprocess.check_output([sys.executable, '-c', code, host], timeout=4, stderr=subprocess.DEVNULL))
    except (OSError, ValueError, subprocess.SubprocessError):
        raise StorageError('NAS address could not be resolved within four seconds') from None
    if not addresses or len(addresses) > 8:
        raise StorageError('NAS address does not resolve to a bounded destination')
    for address in addresses:
        ip = ipaddress.ip_address(address)
        # Dedicated LAN functionality: no internet, loopback, link-local/metadata or multicast probes.
        networks = ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','fc00::/7')
        if not any(ip in ipaddress.ip_network(n) for n in networks):
            raise StorageError('Choose a private LAN NAS address; loopback, link-local and public addresses are refused')
    return addresses[0]


def digest(provider, name):
    result = hashlib.sha256()
    with provider.open(name, 'rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            result.update(block)
    return result.hexdigest()


class Local:
    kind = 'local'

    def __init__(self, fd, opener):
        self.fd, self.opener = fd, opener

    def names(self):
        names = os.listdir(self.fd)
        if len(names) > MAX_ENTRIES:
            raise StorageError('Backup directory exceeds the 10,000 entry safety limit')
        return names

    def open(self, name, mode='rb'):
        relative(name)
        flags = os.O_RDONLY if mode == 'rb' else os.O_WRONLY | os.O_CREAT | os.O_EXCL
        return os.fdopen(self.opener(name, flags), mode)

    def info(self, name):
        with self.open(name) as stream:
            s = os.fstat(stream.fileno())
        return dict(bytes=s.st_size, identity=[s.st_ino, s.st_size, s.st_mtime_ns])

    def remove(self, name):
        relative(name)
        with self.open(name):
            pass
        os.unlink(name, dir_fd=self.fd)
        os.fsync(self.fd)

    def rename(self, source, target, *, replace=False):
        relative(source); relative(target)
        if not replace:
            # Hard-link publication fails atomically if target exists, then release the temporary name.
            os.link(source, target, src_dir_fd=self.fd, dst_dir_fd=self.fd, follow_symlinks=False)
            os.unlink(source, dir_fd=self.fd)
        else:
            os.replace(source, target, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        os.fsync(self.fd)

    def capacity(self):
        s = os.fstatvfs(self.fd)
        return dict(capacity_bytes=s.f_blocks*s.f_frsize, available_bytes=s.f_bavail*s.f_frsize,
                    free_bytes=s.f_bfree*s.f_frsize, filesystem_id=str(os.fstat(self.fd).st_dev),
                    measurement='backup filesystem; available excludes privileged reserve')

    def close(self):
        pass


class RemoteStream(io.RawIOBase):
    def __init__(self, provider, handle, writable):
        super().__init__()
        self.provider, self.handle, self.position, self.writing = provider, handle, 0, writable

    def readable(self): return not self.writing
    def writable(self): return self.writing

    def readinto(self, buffer):
        from smbprotocol.exceptions import EndOfFile
        try:
            data = self.handle.read(self.position, min(len(buffer), self.provider.connection.max_read_size, CHUNK))
        except EndOfFile:
            return 0
        buffer[:len(data)] = data
        self.position += len(data)
        return len(data)

    def write(self, data):
        total = 0
        while total < len(data):
            size = min(len(data)-total, self.provider.connection.max_write_size, CHUNK)
            n = self.handle.write(bytes(data[total:total+size]), offset=self.position)
            if n <= 0: raise StorageError('NAS stopped accepting backup data')
            total += n; self.position += n
        return total

    def flush(self):
        if not self.closed and self.writing: self.handle.flush()

    def close(self):
        if not self.closed:
            try:
                super().close()
            finally:
                self.handle.close()


class SMB:
    kind = 'smb'

    def __init__(self, config, password, *, deadline=None):
        from smbprotocol.connection import Connection
        from smbprotocol.session import Session
        from smbprotocol.tree import TreeConnect
        relative(config.get('share', ''))
        if '/' in config['share'] or config['share'].endswith('$'):
            raise StorageError('Choose a regular backup share, not an administrative share')
        self.directory = relative(config.get('directory', ''), empty=True)
        self.config = config
        self.deadline = deadline
        self.stage = 'resolve'
        self.connection = None
        try:
            address = endpoint(config['host'], config.get('port', 445))
            self.connection = Connection(uuid.uuid4(), address, 445, require_signing=True)
            # Open/Session/Tree operations use this bounded receive path too.
            receive = self.connection.receive
            self.connection.receive = lambda request, **kw: receive(request, **dict(kw, timeout=self.remaining()))
            self.stage = 'connect'
            self.connection.connect(timeout=min(5,self.remaining()))
            self.stage = 'authenticate'
            username = (config.get('domain', '')+'\\' if config.get('domain') else '')+config['username']
            self.session = Session(self.connection, username=username, password=password,
                require_encryption=config.get('require_encryption', True), auth_protocol='ntlm')
            self.session.connect()
            self.stage = 'share'
            self.tree = TreeConnect(self.session, '\\\\'+address+'\\'+config['share'])
            self.tree.connect()
            self.stage = 'directory'
            if self.tree.is_dfs_share:
                raise StorageError('DFS referral shares are unsupported; choose a direct NAS share')
            self._check_directory(self.directory)
        except Exception as exc:
            self.close()
            error=mapped(exc)
            error.connection_stage=self.stage
            raise error from None

    def remaining(self):
        seconds=10 if self.deadline is None else min(10,self.deadline-time.monotonic())
        if seconds<=0:raise StorageError('NAS operation deadline reached; retry after checking connectivity')
        return seconds

    def _path(self, name=''):
        relative(name, empty=True)
        return '/'.join(p for p in (self.directory, name) if p).replace('/', '\\')

    def _handle(self, path, *, directory=False, create=False, delete=False):
        from smbprotocol.open import Open, ImpersonationLevel, FilePipePrinterAccessMask, FileAttributes, ShareAccess, CreateDisposition, CreateOptions
        h = Open(self.tree, path)
        access = FilePipePrinterAccessMask.FILE_READ_ATTRIBUTES | FilePipePrinterAccessMask.SYNCHRONIZE
        access |= (FilePipePrinterAccessMask.GENERIC_READ | (FilePipePrinterAccessMask.GENERIC_WRITE if create else 0))
        if delete: access |= FilePipePrinterAccessMask.DELETE
        options = CreateOptions.FILE_OPEN_REPARSE_POINT | (CreateOptions.FILE_DIRECTORY_FILE if directory else CreateOptions.FILE_NON_DIRECTORY_FILE)
        h.create(ImpersonationLevel.Impersonation, access, FileAttributes.FILE_ATTRIBUTE_DIRECTORY if directory else FileAttributes.FILE_ATTRIBUTE_NORMAL,
            ShareAccess.FILE_SHARE_READ, CreateDisposition.FILE_CREATE if create else CreateDisposition.FILE_OPEN, options)
        if h.file_attributes & FileAttributes.FILE_ATTRIBUTE_REPARSE_POINT:
            h.close()
            raise StorageError('Symbolic links and network reparse points are not permitted')
        return h

    def _check_directory(self, value):
        parts = relative(value, empty=True).split('/') if value else []
        for n in range(len(parts)+1):
            h = self._handle('\\'.join(parts[:n]), directory=True)
            h.close()

    def _query(self, h, cls, *, filesystem=False):
        from smbprotocol.open import SMB2QueryInfoRequest, SMB2QueryInfoResponse
        request = SMB2QueryInfoRequest()
        request['info_type'] = 2 if filesystem else 1
        request['file_info_class'] = cls.INFO_CLASS
        request['output_buffer_length'] = 65536
        request['file_id'] = h.file_id
        message = self.connection.send(request, sid=self.session.session_id, tid=self.tree.tree_connect_id)
        response = SMB2QueryInfoResponse(); response.unpack(self.connection.receive(message)['data'].get_value())
        value = cls(); value.unpack(response['buffer'].get_value())
        return value

    def _set(self, h, value):
        from smbprotocol.open import SMB2SetInfoRequest
        request = SMB2SetInfoRequest()
        request['info_type'] = 1; request['file_info_class'] = value.INFO_CLASS
        request['file_id'] = h.file_id; request['buffer'] = value.pack()
        message = self.connection.send(request, sid=self.session.session_id, tid=self.tree.tree_connect_id)
        self.connection.receive(message)

    def open(self, name, mode='rb'):
        h = self._handle(self._path(name), create=mode == 'xb')
        raw = RemoteStream(self, h, mode == 'xb')
        return io.BufferedWriter(raw, buffer_size=CHUNK) if mode == 'xb' else io.BufferedReader(raw, buffer_size=CHUNK)

    def info(self, name):
        from smbprotocol.file_info import FileStandardInformation, FileBasicInformation
        h = self._handle(self._path(name))
        try:
            standard = self._query(h, FileStandardInformation)
            basic = self._query(h, FileBasicInformation)
            if standard['number_of_links'].get_value() != 1:
                raise StorageError('Backup files with multiple links are refused')
            size = standard['end_of_file'].get_value()
            return dict(bytes=size, identity=['smb', size, basic['last_write_time'].get_value()])
        finally: h.close()

    def entries(self, directory='', *, maximum=MAX_ENTRIES):
        from smbprotocol.file_info import FileDirectoryInformation
        from smbprotocol.exceptions import NoMoreFiles
        h = self._handle(self._path(directory), directory=True)
        entries = []
        try:
            while True:
                try: batch = h.query_directory('*', FileDirectoryInformation.INFO_CLASS)
                except NoMoreFiles: break
                for entry in batch:
                    name = entry['file_name'].get_value().decode('utf-16-le')
                    if name in ('.', '..'): continue
                    attrs = entry['file_attributes'].get_value()
                    if attrs & 0x400: continue  # Never expose reparse points.
                    entries.append(dict(name=name, directory=bool(attrs & 0x10)))
                    if len(entries) > maximum:
                        raise StorageError('Directory exceeds the bounded listing limit; choose a smaller backup folder')
            return entries
        finally: h.close()

    def names(self): return [e['name'] for e in self.entries() if not e['directory']]

    def mkdir(self, directory):
        relative(directory)
        parent = directory.rsplit('/', 1)[0] if '/' in directory else ''
        self._check_directory('/'.join(p for p in (self.directory, parent) if p))
        h = self._handle(self._path(directory), directory=True, create=True)
        h.close()

    def remove(self, name, *, directory=False):
        from smbprotocol.file_info import FileDispositionInformation
        h = self._handle(self._path(name), directory=directory, delete=True)
        try:
            value = FileDispositionInformation(); value['delete_pending'] = True
            self._set(h, value)
        finally: h.close()

    def rename(self, source, target, *, replace=False):
        from smbprotocol.file_info import FileRenameInformation
        h = self._handle(self._path(source), delete=True)
        try:
            value = FileRenameInformation(); value['replace_if_exists'] = replace
            value['file_name'] = self._path(target).encode('utf-16-le')
            self._set(h, value)
        finally: h.close()

    def capacity(self):
        from smbprotocol.file_info import FileFsFullSizeInformation
        h = self._handle(self._path(), directory=True)
        try:
            s = self._query(h, FileFsFullSizeInformation, filesystem=True)
            unit = s['sectors_per_unit'].get_value()*s['bytes_per_sector'].get_value()
            return dict(capacity_bytes=s['total_allocation_units'].get_value()*unit,
                available_bytes=s['caller_available_units'].get_value()*unit,
                free_bytes=s['actual_available_units'].get_value()*unit,
                filesystem_id='nas', measurement='NAS share filesystem; account quota may limit available space')
        except Exception:
            return dict(capacity_bytes=None, available_bytes=None, free_bytes=None, filesystem_id='nas', measurement='NAS does not expose capacity information')
        finally: h.close()

    def close(self):
        if self.connection:
            try: self.connection.disconnect(close=False, timeout=2)
            except Exception: pass


def mapped(exc):
    if isinstance(exc, StorageError): return exc
    name = type(exc).__name__
    if name in ('LogonFailure','AccountDisabled','PasswordExpired','AccessDenied'):
        return StorageError('NAS authentication or permission denied; check the dedicated backup account and share permissions')
    if name in ('BadNetworkName',): return StorageError('Share was not found; enter a known share name')
    if name in ('ObjectNameNotFound','ObjectPathNotFound','NoSuchFile') or isinstance(exc, FileNotFoundError):
        return FileNotFoundError(errno.ENOENT, 'Backup file or destination directory is missing')
    if name in ('ObjectNameCollision',): return FileExistsError(errno.EEXIST, 'Destination already exists')
    if name in ('NotSupported','SMBException'):
        return StorageError('NAS protocol negotiation failed; use SMB 2/3 with signing and compatible encryption settings')
    return StorageError('NAS operation failed or timed out; check reachability and permissions. Existing backup metadata is preserved')


def guarded(method):
    from functools import wraps
    @wraps(method)
    def call(*args, **kwargs):
        try:return method(*args, **kwargs)
        except Exception as exc:raise mapped(exc) from None
    return call


for _method in ('open','info','entries','names','mkdir','remove','rename'):
    setattr(SMB,_method,guarded(getattr(SMB,_method)))
for _method in ('readinto','write','flush','close'):
    setattr(RemoteStream,_method,guarded(getattr(RemoteStream,_method)))
