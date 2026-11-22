"""Synthetic split projection made by the production sealer; stdout only."""
import json
from pathlib import Path
from market.workshop_summary import seal

root = Path(__file__).resolve().parents[1]
fixture = json.loads((root / 'contracts/workshop-summary/v2/fixtures/synthetic.json').read_text())
metadata = {k:v for k,v in fixture['manifest'].items() if k in (
    'issuer_id','market','pricing_algorithm','history_basis','source_kind',
    'source_watermark','source_observation','generated_at','synthetic','observations')}
rows = sorted((row for raw in fixture['parts'].values() for row in json.loads(raw)),
              key=lambda row:(row[0],row[1]))
manifest, parts = seal(metadata, rows, 3)
print(json.dumps(dict(manifest=manifest,parts={str(k):v.decode() for k,v in parts.items()}),indent=2))
