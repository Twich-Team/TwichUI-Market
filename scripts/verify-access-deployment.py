"""Audited, temporary admin/member browser verification; no owner password or market changes."""
import os,secrets,subprocess,argparse,json
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--public-enabled",action="store_true",help="Require the public route and full public authentication after source filtering is installed")
parser.add_argument("--usability-mode",choices=["baseline","verify"])
parser.add_argument("--local-only",action="store_true",help="Verify local/preview security without claiming public ingress verification")
parser.add_argument("--promotion",action="store_true",help="Keep temporary public/local sessions alive across the approved deployment, then verify production")
parser.add_argument('--companion-promotion',action='store_true',help='After final owner approval, verify Companion v2 across its separately authorized deployment')
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
if args.companion_promotion:
 if args.promotion or args.usability_mode or args.local_only:parser.error('Use the separate companion promotion verification mode alone')
 proof=json.loads((ROOT/'docs/evidence/companion-v2-signed-candidate.json').read_text())
 final_record=ROOT/'docs/evidence/companion-v2-final-owner-approval.json'
 if not final_record.is_file():parser.error('Final owner publication/deployment approval is required; no accounts or services changed')
 approval=json.loads(final_record.read_text())
 prepared=json.loads((ROOT/'docs/evidence/combined-release-preflight.json').read_text())
 if (approval.get('owner_approved_publication') is not True or approval.get('owner_approved_deployment') is not True
     or approval.get('source_commit')!=proof['payload_source_commit'] or approval.get('installer_sha256')!=proof['installer_sha256']
     or approval.get('deployment_source_commit')!=prepared['source_commit']):
  parser.error('Exact candidate and deployment need final owner approval before production verification')
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
 browser_script='scripts/verify-companion-production-browser.cjs' if args.companion_promotion else ('scripts/verify-production-promotion-browser.cjs' if args.promotion else ('scripts/verify-usability-browser.cjs' if args.usability_mode else 'scripts/verify-access-browser.cjs'))
 if args.companion_promotion:
  # Trust only the existing project CA inside this disposable rootless browser.
  # Its image defaults to /root; never change host trust or repurpose HOME.
  browser_setup='set -e\nmkdir -p /root/.pki/nssdb\ncertutil -d sql:/root/.pki/nssdb -N --empty-password\ncertutil -d sql:/root/.pki/nssdb -A -n market-local -t "C,," -i artifacts/access-deployment/local-root.crt\nexport NODE_EXTRA_CA_CERTS=/work/artifacts/access-deployment/local-root.crt\nnode '+browser_script
 else:
  browser_setup='set -e\nmkdir -p /root/.pki/nssdb\ncertutil -d sql:/root/.pki/nssdb -N --empty-password\ncertutil -d sql:/root/.pki/nssdb -A -n market-local -t "C,," -i artifacts/access-deployment/local-root.crt\ncertutil -d sql:/root/.pki/nssdb -A -n market-preview -t "C,," -i artifacts/access-deployment/preview-root.crt\ncat artifacts/access-deployment/local-root.crt artifacts/access-deployment/preview-root.crt > /tmp/market-ca-bundle.crt\nexport NODE_EXTRA_CA_CERTS=/tmp/market-ca-bundle.crt\nnode '+browser_script
 subprocess.run(['docker','--context','rootless','run','--rm','--name','twichui-market-access-check','--memory','768m','--cpus','1','--log-opt','max-size=5m','--log-opt','max-file=2','--network','twichui-market_default','--env-file',str(path),'-v',str(ROOT)+':/work','-w','/work','twichui-market-access-browser:dev','sh','-c',browser_setup],cwd=ROOT,check=True)
finally:
 path.unlink(missing_ok=True)
 if created:account('close')
