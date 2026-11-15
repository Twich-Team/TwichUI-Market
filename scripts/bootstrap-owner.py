"""Provision the initial owner through environment-only credentials, never stdout."""
import os
from pathlib import Path
import secrets
import subprocess

ROOT=Path(__file__).resolve().parents[1]
command=['docker','--context','rootless','compose']
query="from market.db import Session; from market.models import User; from sqlalchemy import select,func; db=Session(); print(db.scalar(select(func.count()).select_from(User))); db.close()"
count=int(subprocess.check_output(command+['exec','-T','api','python','-c',query],cwd=ROOT).strip())
if count:
    print('Initial owner provisioning skipped: users already exist.')
    raise SystemExit(0)
directory=ROOT/'.local'
directory.mkdir(mode=0o700,exist_ok=True)
directory.chmod(0o700)
target=directory/'bootstrap.env'
if not target.exists():
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        stream.write('MARKET_ADMIN_USERNAME=owner\nMARKET_ADMIN_PASSWORD='+secrets.token_urlsafe(32)+'\n')
env=os.environ.copy()
for line in target.read_text().splitlines():
    key,value=line.split('=',1)
    if key in ('MARKET_ADMIN_USERNAME','MARKET_ADMIN_PASSWORD'):
        env[key]=value
subprocess.run(command+['exec','-T','-e','MARKET_ADMIN_USERNAME','-e','MARKET_ADMIN_PASSWORD','api','python','-m','market.bootstrap'],cwd=ROOT,env=env,check=True)
print('Owner created. Initial credentials are in .local/bootstrap.env (mode 600). Read privately and change the password after first sign-in.')
