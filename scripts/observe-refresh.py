"""Bounded read-only observation of scheduled live collection; never polls Blizzard itself."""
import argparse
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
SQL="""SELECT json_build_object('checked_at',now(),'snapshots',(SELECT json_agg(json_build_object('snapshot_id',o.snapshot_id,'retrieved_at',o.retrieved_at,'upstream_modified',o.upstream_modified,'listing_count',s.listing_count,'payload_hash',o.payload_hash)) FROM (SELECT snapshot_id,retrieved_at,upstream_modified,payload_hash FROM observations WHERE market_id=1 AND NOT synthetic ORDER BY id DESC LIMIT 64) o JOIN snapshots s ON s.id=o.snapshot_id),'runs',(SELECT json_agg(json_build_object('checked_at',checked_at,'status',status,'http_status',http_status,'error',error)) FROM (SELECT checked_at,status,http_status,error FROM collection_runs WHERE market_id=1 ORDER BY id DESC LIMIT 64) r),'database_bytes',pg_database_size(current_database()));"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minutes',type=int,default=20,choices=range(1,61),metavar='1..60')
    args=parser.parse_args()
    output=ROOT/'artifacts'/'live'/'refresh-watch.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    started=datetime.now(timezone.utc).isoformat()
    deadline=time.monotonic()+args.minutes*60
    while True:
        raw=subprocess.check_output(['docker','--context','rootless','compose','-f','compose.yaml','-f','compose.tls.yaml',
            'exec','-T','db','psql','-U','market','-d','market','-Atc',SQL],cwd=ROOT,text=True,timeout=20)
        data=json.loads(raw)
        rows=data['snapshots'] or []
        distinct={r['snapshot_id'] for r in rows}
        modified=sorted({parsedate_to_datetime(r['upstream_modified']) for r in rows if r['upstream_modified']})
        changed=len(distinct)>1 and len(modified)>1
        result={'started_at':started,'latest':data,'content_change_observed':changed,
                'distinct_snapshot_count':len(distinct),
                'observed_header_gaps_seconds':[(b-a).total_seconds() for a,b in zip(modified,modified[1:])],
                'scope':'Observed header gaps are evidence, not a guaranteed refresh schedule. No new upstream requests are generated.'}
        temporary=output.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,indent=2)+'\n')
        temporary.replace(output)
        print(json.dumps({'checked_at':data['checked_at'],'live_checks':len(data['runs'] or []),
                          'distinct_snapshots':len(distinct),'content_change_observed':changed}),flush=True)
        if changed or time.monotonic()>=deadline:return
        time.sleep(min(60,max(0,deadline-time.monotonic())))


if __name__=='__main__':main()
