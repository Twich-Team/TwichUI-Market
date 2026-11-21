"""Capture current served static files for an explicitly separate production image.
No modernized source is built or promoted. Run before first ingress deployment.
"""
import hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
command=['docker','--context','rootless']
if subprocess.run(command+['image','inspect','twichui-market-web:production-approved'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
 print('Existing production image retained.');raise SystemExit(0)
(ROOT/'.local').mkdir(exist_ok=True,mode=0o700);(ROOT/'.local').chmod(0o700)
folder=ROOT/'.local'/'production-web';folder.mkdir(parents=True,exist_ok=True,mode=0o700)
with (folder/'srv.tar').open('wb') as stream:subprocess.run(command+['exec','twichui-market-proxy-1','tar','-C','/','-cf','-','srv'],stdout=stream,check=True)
with tarfile.open(folder/'srv.tar') as archive:archive.extractall(folder,filter='data')
(folder/'srv.tar').unlink()
manifest={str(p.relative_to(folder/'srv')):hashlib.sha256(p.read_bytes()).hexdigest() for p in (folder/'srv').rglob('*') if p.is_file()}
(folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
subprocess.run(command+['build','-f',str(ROOT/'deploy'/'production-web.Dockerfile'),'-t','twichui-market-web:production-approved',str(folder)],cwd=ROOT,check=True)
print('Production static files pinned separately; modernization remains unpromoted.')
