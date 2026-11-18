"""Allocation and physical capacity are independent collection safeguards."""
import os
from sqlalchemy import text

GIB = 1024**3


def filesystem():
    path = os.environ.get('DATABASE_FILESYSTEM_PATH')
    reserve = int(os.environ.get('MIN_DATABASE_FREE_BYTES', str(2*GIB)))
    if reserve <= 0:
        raise ValueError('A positive PostgreSQL filesystem reserve is required')
    try:
        if not path:
            return {'available_bytes': None, 'total_bytes': None, 'reserve_bytes': reserve}
        stat = os.statvfs(path)
        return {'available_bytes': stat.f_bavail*stat.f_frsize,
                'total_bytes': stat.f_blocks*stat.f_frsize, 'reserve_bytes': reserve}
    except OSError:
        return {'available_bytes': None, 'total_bytes': None, 'reserve_bytes': reserve}


def status(db, *, limit=None):
    limit = int(limit if limit is not None else os.environ.get('MAX_DATABASE_BYTES', str(16*GIB)))
    if limit <= 0:
        raise ValueError('A positive database allocation limit is required')
    allocated = db.scalar(text('SELECT pg_database_size(current_database())')) if db.bind.dialect.name == 'postgresql' else None
    disk = filesystem()
    reason = None
    if allocated is not None and allocated >= limit:
        reason = 'Database disk budget reached (allocation guard); collection paused'
    elif disk['available_bytes'] is None:
        reason = 'PostgreSQL filesystem capacity unavailable; collection paused'
    elif disk['available_bytes'] <= disk['reserve_bytes']:
        reason = 'PostgreSQL filesystem free-space reserve reached; collection paused'
    return {'database_allocated_bytes': allocated, 'database_limit_bytes': limit,
            'filesystem': disk, 'paused_reason': reason}
