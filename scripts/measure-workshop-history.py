"""Emit bounded explicitly synthetic 60-day reader stress input; no DB/provider access."""
import argparse,hashlib,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
from market.workshop_summary import seal
p=argparse.ArgumentParser();p.add_argument('--variants',type=int,default=26342)
p.add_argument('--contract',type=int,choices=[2,3],default=2)
p.add_argument('--days',type=int,choices=[2,60],default=60)
p.add_argument('--distribution',choices=['uniform','uneven','variants'],default='uniform')
a=p.parse_args()
if not 1<=a.variants<=45125:p.error('bounded synthetic fixture count')
root=Path(__file__).resolve().parents[1]
f=json.loads((root/'contracts/workshop-summary/v1/fixtures/synthetic.json').read_text());h=f['manifest']
metadata={k:v for k,v in h.items() if k in ('issuer_id','market','pricing_algorithm','history_basis','source_kind','source_watermark','source_observation','generated_at','synthetic')}
end=datetime(2026,11,15,12,tzinfo=timezone.utc)
metadata['observations']=[dict(observation_id=str(100+i),observed_at=(end-timedelta(days=a.days-1-i)).isoformat().replace('+00:00','Z'),scope_complete=True,synthetic=True) for i in range(a.days)]
metadata['source_observation']={k:metadata['observations'][-1][k] for k in ('observation_id','observed_at','scope_complete')};metadata['source_watermark']=str(99+a.days)
base=json.loads(next(iter(f['parts'].values())))[0]
def rows():
 identities=[]
 if a.distribution=='uniform':
  identities=[(10000+i,{'id':10000+i}) for i in range(a.variants)]
 else:
  hot=a.variants if a.distribution=='variants'else min(768,a.variants)
  identities=[(10000,{'id':10000,**({'synthetic_variant':i}if i else{})})for i in range(hot)]
  item=20000
  while len(identities)<a.variants:
   if item%64!=10000%64:identities.append((item,{'id':item}))
   item+=1
 exact=sorted((item,hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest())for item,identity in identities)
 for item,variant in exact:
  r=base.copy();r[0]=item;r[1]=variant
  r[9]='100'if a.days>=3 else None;r[10:13]=[min(14,a.days),a.days,a.days]
  r.append([[0,'100','90',10] for _ in range(a.days-1)]+[[0,'120','120',10]])
  yield r
manifest,parts=seal(metadata,rows(),a.contract)
json.dump(dict(manifest=manifest,parts={str(k):v.decode() for k,v in parts.items()}),sys.stdout,separators=(',',':'));print()
