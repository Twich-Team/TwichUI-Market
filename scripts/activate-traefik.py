"""Activate the known rootless transport only AFTER administrator source filtering.
Refuses while a direct non-Traefik HTTP request can reach the private listener.
Does not install firewall rules, change Docker daemon settings or promote assets.
"""
import argparse,http.client,os,ssl,subprocess,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--administrator-confirmation',required=True,help='Non-secret change/ticket reference confirming the exact Traefik-only INPUT rule')
args=parser.parse_args()
if not 3<=len(args.administrator_confirmation)<=160:raise SystemExit('Provide a short non-secret administrator change reference')
# A Caddy 403 is NOT proof of source filtering: the TCP source must be rejected first.
connection=http.client.HTTPConnection('10.0.4.46',18780,timeout=5)
try:
 connection.request('GET','/api/v1/health',headers={'Host':'market.twich.gg'})
 response=connection.getresponse()
 raise SystemExit('Refusing activation: a non-Traefik request still reaches HTTP (status '+str(response.status)+'). Administrator source filtering is required.')
except (ConnectionResetError,ConnectionAbortedError,TimeoutError,ConnectionRefusedError):pass
finally:connection.close()
# Verify the independently retained local deployment before changing any configuration.
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ROOT/'artifacts/access-deployment/local-root.crt')))
with opener.open('https://localhost:18443/api/v1/health',timeout=5) as response:
 if response.status!=200:raise SystemExit('Local deployment is not healthy')
path=ROOT/'.env';previous=path.read_text();lines=[line for line in previous.splitlines() if not line.startswith('MARKET_TRANSPORT_PEER=')]
lines.append('MARKET_TRANSPORT_PEER=172.18.0.1')
def write(value):
 descriptor,name=tempfile.mkstemp(prefix='ingress-env-',dir=ROOT/'.local')
 with os.fdopen(descriptor,'w') as stream:stream.write(value)
 os.chmod(name,0o600);os.replace(name,path)
command=['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml','-f','compose.traefik.yaml','up','-d','--no-deps','proxy']
try:
 write('\n'.join(lines)+'\n');subprocess.run(command,cwd=ROOT,check=True)
 # The administrator confirmation is recorded locally without any token values.
 (ROOT/'.local/traefik-source-filter-confirmation.txt').write_text(args.administrator_confirmation+'\n')
 (ROOT/'.local/traefik-source-filter-confirmation.txt').chmod(0o600)
 print('Transport configured after source-filter precheck. Run scripts/verify-access-deployment.py --public-enabled; public success is not yet claimed.')
except BaseException:
 write(previous);subprocess.run(command,cwd=ROOT,check=False);raise
