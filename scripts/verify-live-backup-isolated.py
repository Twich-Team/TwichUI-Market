"""Explicit owner-authorized isolated restoration of a named existing recovery archive."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,'/app')
from management import Manager
assert os.environ['RESTORE_PGHOST']=='nas-restore'
assert os.environ['PGDATABASE']=='market'
key=os.environ['REHEARSAL_BACKUP_ID']
assert len(key)==32 and all(c in '0123456789abcdef' for c in key)
manager=Manager(state='/verification-state')
try:
    job=manager.restore_queue('admin:1',key)
    result=manager.restore_test('admin:1',job['id'])
    print(json.dumps(result,indent=2),flush=True)
    if result['status']!='succeeded':raise SystemExit(1)
finally:manager.close()
