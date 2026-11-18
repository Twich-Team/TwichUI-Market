"""Prepare only disposable CI build inputs for a distinct unsigned DEV executable."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
old = 'name = "twichui-market-companion"'
new = 'name = "twichui-market-companion-dev"'
for relative in ['desktop/src-tauri/Cargo.toml', 'desktop/src-tauri/Cargo.lock']:
    path = root / relative
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'Unexpected DEV build input: {relative}')
    path.write_text(text.replace(old, new))
# Visible in the real embedded frontend, not just the installer name.
path = root / 'desktop/ui/index.html'
text = path.read_text().replace('<h1>Companion</h1>', '<h1>Companion DEV</h1>').replace('TWICHUI MARKET</span>', 'UNSIGNED PRIVATE TEST</span>')
path.write_text(text)
config = json.loads((root / 'desktop/src-tauri/tauri.dev.conf.json').read_text())
assert config['identifier'] == 'team.twich.market.dev'
assert config['productName'] == 'TwichUI Market Companion DEV'
print('Prepared isolated DEV binary, application identity, and visible unsigned label.')
