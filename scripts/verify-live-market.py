"""Audited temporary member browser check; never resets owner or seeds market data."""
import os
import argparse
from pathlib import Path
import secrets
import subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--script',choices=['verify-live-browser.cjs','benchmark-browser.cjs'],default='verify-live-browser.cjs')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
command=['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml','run','--rm','-T','--no-deps','-e','MARKET_LIVE_CHECK_USERNAME','-e','MARKET_LIVE_CHECK_PASSWORD','worker','python','-']
env=os.environ.copy()
env['MARKET_LIVE_CHECK_USERNAME']='market_live_check_'+secrets.token_hex(4)
env['MARKET_LIVE_CHECK_PASSWORD']=secrets.token_urlsafe(32)
program='''
import os
from sqlalchemy import select,update
from market.db import Session
from market.models import User,Credential,SecurityEvent
from market.security import hasher
with Session.begin() as db:
    owner=db.scalar(select(User).where(User.username=='owner',User.role=='admin',User.active.is_(True)))
    if owner is None:raise RuntimeError('Active owner required')
    username=os.environ['MARKET_LIVE_CHECK_USERNAME']
    assert username.startswith('market_live_check_')
    user=db.scalar(select(User).where(User.username==username))
    if ACTION=='create':
        if user is not None:raise RuntimeError('Refusing existing user')
        user=User(username=username,password_hash=hasher.hash(os.environ['MARKET_LIVE_CHECK_PASSWORD']),role='member')
        db.add(user);db.flush()
        db.add(SecurityEvent(actor_id=owner.id,action='operator.live_check.created',detail=f'temporary_member={user.id} operator=marketdev'))
    elif user is not None:
        assert user.role=='member'
        user.active=False
        db.execute(update(Credential).where(Credential.user_id==user.id).values(revoked=True))
        db.add(SecurityEvent(actor_id=owner.id,action='operator.live_check.closed',detail=f'disabled_member={user.id} credentials_revoked'))
'''
def account(action):subprocess.run(command,input=(f'ACTION={action!r}\n'+program).encode(),cwd=ROOT,env=env,check=True)
path=ROOT/'.local'/('live-browser-'+secrets.token_hex(8)+'.env')
path.parent.mkdir(mode=0o700,exist_ok=True)
created=False
try:
    account('create')
    created=True
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as stream:
        for key in ('MARKET_LIVE_CHECK_USERNAME','MARKET_LIVE_CHECK_PASSWORD','MARKET_LIVE_CHECK_PROXY'):stream.write(key+'='+env.get(key,'proxy')+'\n')
    subprocess.run(['docker','--context','rootless','run','--rm','--name','twichui-market-live-browser','--memory','768m','--cpus','1','--network','twichui-market_default','--env-file',str(path),'-v',str(ROOT)+':/work','-w','/work','mcr.microsoft.com/playwright:v1.65.1-noble','node','scripts/'+args.script],cwd=ROOT,check=True)
finally:
    path.unlink(missing_ok=True)
    if created:account('close')
