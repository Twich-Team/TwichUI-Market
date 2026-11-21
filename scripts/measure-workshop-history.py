"""Emit bounded explicitly synthetic 60-day reader stress input; no DB/provider access."""
import argparse,hashlib,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from market.workshop_summary import seal
p=argparse.ArgumentParser();p.add_argument('--variants',type=int,default=26342);a=p.parse_args()
if not 1<=a.variants<=45125:p.error('bounded synthetic fixture count')
root=Path(__file__).resolve().parents[1]
f=json.loads((root/'contracts/workshop-summary/v1/fixtures/synthetic.json').read_text());h=f['manifest']
metadata={k:v for k,v in h.items() if k in ('issuer_id','market','pricing_algorithm','history_basis','source_kind','source_watermark','source_observation','generated_at','synthetic')}
end=datetime(2026,11,15,12,tzinfo=timezone.utc)
metadata['observations']=[dict(observation_id=str(100+i),observed_at=(end-timedelta(days=59-i)).isoformat().replace('+00:00','Z'),scope_complete=True,synthetic=True) for i in range(60)]
metadata['source_observation']={k:metadata['observations'][-1][k] for k in ('observation_id','observed_at','scope_complete')};metadata['source_watermark']='159'
base=json.loads(next(iter(f['parts'].values())))[0]
def rows():
 for i in range(a.variants):
  r=base.copy();r[0]=10000+i;r[1]=hashlib.sha256(json.dumps({'id':r[0]},separators=(',',':')).encode()).hexdigest()
  r[9]='100';r[10:13]=[14,60,60];r.append([[0,'100','90',10] for _ in range(59)]+[[0,'120','120',10]])
  yield r
manifest,parts=seal(metadata,rows(),2)
json.dump(dict(manifest=manifest,parts={str(k):v.decode() for k,v in parts.items()}),sys.stdout,separators=(',',':'));print()
