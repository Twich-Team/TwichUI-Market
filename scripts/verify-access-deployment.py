"""Audited, temporary admin/member browser verification; no owner password or market changes."""
import os,secrets,subprocess,argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--public-enabled",action="store_true",help="Require the public route and full public authentication after source filtering is installed")
parser.add_argument("--usability-mode",choices=["baseline","verify"])
parser.add_argument("--local-only",action="store_true",help="Verify local/preview security without claiming public ingress verification")
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'.local').mkdir(exist_ok=True,mode=0o700);(ROOT/'.local').chmod(0o700)
env=os.environ.copy();env['MARKET_USABILITY_MODE']=args.usability_mode or '';env['MARKET_ACCESS_SKIP_PUBLIC']='true' if args.local_only else 'false';env['MARKET_ACCESS_PUBLIC_ENABLED']='true' if args.public_enabled else 'false';env['MARKET_ACCESS_NONCE']=secrets.token_hex(5)
for role in ('ADMIN','MEMBER'):env['MARKET_ACCESS_'+role+'_PASSWORD']=secrets.token_urlsafe(36)
command=['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml','-f','compose.traefik.yaml','run','--rm','-T','--no-deps']
for key in ('MARKET_ACCESS_NONCE','MARKET_ACCESS_ADMIN_PASSWORD','MARKET_ACCESS_MEMBER_PASSWORD'):command+=['-e',key]
command+=['local-api','python','-']
program='''
import os
from sqlalchemy import select,update
from market.db import Session
from market.models import User,Credential,SecurityEvent
from market.security import hasher
with Session.begin() as db:
 owner=db.scalar(select(User).where(User.username=='owner',User.role=='admin',User.active.is_(True)))
 assert owner is not None
 for role in ('admin','member'):
  name='market_access_'+os.environ['MARKET_ACCESS_NONCE']+'_'+role
  user=db.scalar(select(User).where(User.username==name))
  if ACTION=='create':
   assert user is None
   user=User(username=name,password_hash=hasher.hash(os.environ['MARKET_ACCESS_'+role.upper()+'_PASSWORD']),role=role)
   db.add(user);db.flush();db.add(SecurityEvent(actor_id=owner.id,action='operator.access_check.created',detail=f'temporary_{role}={user.id} operator=marketdev'))
  elif user is not None:
   assert user.role==role
   user.active=False;db.execute(update(Credential).where(Credential.user_id==user.id).values(revoked=True))
   db.add(SecurityEvent(actor_id=owner.id,action='operator.access_check.closed',detail=f'disabled_{role}={user.id} credentials_revoked'))
'''
def account(action):subprocess.run(command,input=('ACTION='+repr(action)+'\n'+program).encode(),env=env,cwd=ROOT,check=True)
path=ROOT/'.local'/('access-browser-'+secrets.token_hex(8)+'.env');created=False
try:
 account('create');created=True
 with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
  for key in ('MARKET_ACCESS_NONCE','MARKET_ACCESS_ADMIN_PASSWORD','MARKET_ACCESS_MEMBER_PASSWORD','MARKET_ACCESS_PUBLIC_ENABLED','MARKET_USABILITY_MODE','MARKET_ACCESS_SKIP_PUBLIC'):stream.write(key+'='+env[key]+'\n')
 subprocess.run(['docker','--context','rootless','run','--rm','--name','twichui-market-access-check','--memory','768m','--cpus','1','--network','twichui-market_default','--env-file',str(path),'-v',str(ROOT)+':/work','-w','/work','twichui-market-access-browser:dev','sh','-c',
  'set -e\nexport HOME=/tmp/market-access-home\nmkdir -p "$HOME/.pki/nssdb"\ncertutil -d "sql:$HOME/.pki/nssdb" -N --empty-password\ncertutil -d "sql:$HOME/.pki/nssdb" -A -n market-local -t "C,," -i artifacts/access-deployment/local-root.crt\ncertutil -d "sql:$HOME/.pki/nssdb" -A -n market-preview -t "C,," -i artifacts/access-deployment/preview-root.crt\ncat artifacts/access-deployment/local-root.crt artifacts/access-deployment/preview-root.crt > /tmp/market-ca-bundle.crt\nexport NODE_EXTRA_CA_CERTS=/tmp/market-ca-bundle.crt\nnode '+('scripts/verify-usability-browser.cjs' if args.usability_mode else 'scripts/verify-access-browser.cjs')],cwd=ROOT,check=True)
finally:
 path.unlink(missing_ok=True)
 if created:account('close')
