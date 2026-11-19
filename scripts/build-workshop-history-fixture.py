"""Build explicitly synthetic cross-language history fixtures with the producer."""
import json
from pathlib import Path
from market.workshop_summary import seal
root=Path(__file__).resolve().parents[1]
fixture=json.loads((root/'contracts/workshop-summary/v1/fixtures/synthetic.json').read_text())
h=fixture['manifest']
metadata={k:v for k,v in h.items() if k in ('issuer_id','market','pricing_algorithm','history_basis','source_kind','source_watermark','source_observation','generated_at','synthetic')}
metadata['observations']=[dict(observation_id='100',observed_at='2026-11-13T12:00:00Z',scope_complete=True,synthetic=True),dict(observation_id=h['source_observation']['observation_id'],observed_at=h['generated_at'],scope_complete=True,synthetic=True)]
rows=[]
for bucket,raw in fixture['parts'].items():
    for r in json.loads(raw):
        # A calendar gap, a real priced close, known absence and an unknown day.
        history=[[0,'100','90',5],[r[2],r[3] if r[2]==0 else None,r[5] if r[2]==0 else None,r[6]]]
        if r[2]==1:history[0]=[3,None,None,None]
        r.append(history);rows.append(r)
manifest,parts=seal(metadata,sorted(rows,key=lambda r:(r[0],r[1])),2)
print(json.dumps(dict(manifest=manifest,parts={str(k):v.decode() for k,v in parts.items()}),indent=2))
