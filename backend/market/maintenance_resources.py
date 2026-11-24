"""Small fail-closed resource checks for bounded production retention cycles."""
import json
import os
from pathlib import Path
import urllib.request
from sqlalchemy import text


def health_reason():
    if os.environ.get('RETENTION_PRODUCTION_HEALTH_GUARD')!='true':return None
    try:
        current=int(Path('/sys/fs/cgroup/memory.current').read_text())
        maximum=Path('/sys/fs/cgroup/memory.max').read_text().strip()
        if maximum!='max' and current>int(maximum)*.85:return 'Retention worker memory exceeds its safety threshold'
        request=urllib.request.Request('http://api:8000/api/v1/health')
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=3) as response:
            if response.status!=200:return 'Market API health check failed; cleanup paused'
            json.loads(response.read(16384))
    except Exception:return 'Market API or resource health could not be verified; cleanup paused'
    return None


def database_reason(db):
    row=db.execute(text("SELECT count(*) FILTER (WHERE state='active') AS active, count(*) FILTER (WHERE wait_event_type='Lock' AND query_start<clock_timestamp()-interval '1 second') AS waiting FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")).one()
    if row.active>8 or row.waiting>0:return 'Database activity or lock waits exceed the cleanup safety threshold'
    return None
