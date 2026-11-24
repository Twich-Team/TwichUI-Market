"""Bootstrap ONLY the disposable NAS browser service; no production path accepted."""
import base64
import json
import os
from pathlib import Path
import sys
assert os.environ['PGDATABASE']=='market_test'
sys.path[:0]=['/app','/secrets-code']
Path('/backups').chmod(0o700)
Path('/state').chmod(0o700)
path=Path('/state/keyring.json')
if not path.exists():
    path.write_text(json.dumps({'active':'fixture','keys':{'fixture':base64.b64encode(os.urandom(32)).decode()}}));path.chmod(0o600)
from service import main
main()
