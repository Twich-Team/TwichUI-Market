"""Create missing local secrets without overwriting configured values or printing them."""
from pathlib import Path
import secrets

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.env'
lines=path.read_text().splitlines() if path.exists() else []
defaults={'INGRESS_PROXY_TOKEN':lambda:secrets.token_urlsafe(48),'POSTGRES_PASSWORD':lambda:secrets.token_urlsafe(32),'SYNC_CURSOR_SECRET':lambda:secrets.token_urlsafe(48),
          'APP_ORIGIN':lambda:'http://127.0.0.1:18780','COOKIE_SECURE':lambda:'false','MARKET_PORT':lambda:'18780'}
for key,generate in defaults.items():
    matches=[index for index,line in enumerate(lines) if line.startswith(key+'=')]
    if not matches:
        lines.append(key+'='+generate())
    elif lines[matches[-1]].split('=',1)[1].strip() in ('','""',"''"):
        lines[matches[-1]]=key+'='+generate()
path.write_text('\n'.join(lines)+'\n')
path.chmod(0o600)
print('Local configuration is ready; existing values preserved and no secrets printed.')
