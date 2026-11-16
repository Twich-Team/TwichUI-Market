#!/usr/bin/env python3
"""Bounded official API evidence capture inside the existing server container.

Uses the current encrypted key, worker lock and durable shared request accounting.
Never raises quotas or changes provider configuration. Output is structural only;
sanitized successful response samples stay in an operator-selected private folder.
"""
import argparse
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import re
from time import monotonic
from urllib.parse import urlencode
from sqlalchemy import func, select
from market.db import Session, now
from market.metadata_providers import decode
from market.metadata_recovery import credential_value, worker_lock
from market.models import MetadataJob, MetadataProvider, MetadataTask
from market.probe import request
from market.provider_rates import cooldown, observe, reserve_budget
from market.security import audit

CAMPAIGN = 'foreverdb-capabilities-20261116'
CAP = 40
# Only documented resources. No arbitrary hosts, pagination URLs or API routes.
PATH = re.compile(r'(?:meta|items(?:/[1-9][0-9]*)?|spells(?:/[1-9][0-9]*)?|vendors(?:/[1-9][0-9]*)?|itemsets(?:/[1-9][0-9]*)?|professions(?:/(?:alchemy|blacksmithing|enchanting|engineering|leatherworking|tailoring|herbalism|mining|skinning|cooking|first-aid|fishing))?|disenchant|builds(?:/(?:latest|1\.60\.[0-9]+\.[0-9]+))?|gathering/(?:herbalism|mining|skinning|fishing)|changes-seen)')


def shape(value, depth=0):
    if depth > 8: return 'nested'
    if isinstance(value, dict): return {k:shape(v,depth+1) for k,v in value.items()}
    if isinstance(value, list): return {'type':'array','length':len(value),'samples':[shape(v,depth+1) for v in value[:2]]}
    return 'null' if value is None else type(value).__name__


def probe(resource, output, *, limit=1, offset=0):
    if not PATH.fullmatch(resource) or not 1 <= limit <= 100 or not 0 <= offset <= 100000:
        raise ValueError('Only documented bounded ForeverDB resources are permitted')
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    if output.is_symlink() or output.stat().st_mode & 0o077:
        raise ValueError('Evidence directory must be private (0700)')
    url = 'https://foreverdb.net/api/v1/' + resource
    if resource != 'meta': url += '?' + urlencode({'limit':limit,'offset':offset})
    with worker_lock(Session) as locked:
        if not locked: return {'blocked':'worker_busy'}
        at = now()
        with Session.begin() as db:
            used = db.scalar(select(func.coalesce(func.sum(MetadataJob.requests_used),0)).where(MetadataJob.dedupe_key==CAMPAIGN))
            if used >= CAP: return {'blocked':'campaign_budget','cap':CAP}
            row = db.get(MetadataProvider,'foreverdb',with_for_update=True)
            if not row or not row.enabled or not row.credential or not row.validated_at:
                return {'blocked':'validated_enabled_server_key_required'}
            waiting = reserve_budget(row,at)
            if waiting: return {'blocked':'shared_provider_budget','next_eligible_at':waiting.isoformat()}
            key = credential_value(db,row,at=at)
            job = MetadataJob(actor_id=1,market_id=None,mode='diagnostic',state='paused',dedupe_key=CAMPAIGN,
                providers_json='["foreverdb"]',total=1,request_budget=1,requests_used=1)
            db.add(job);db.flush()
            task = MetadataTask(job_id=job.id,provider='foreverdb',region='us',item_id=1,state='running',attempts=1,
                lease_until=at+timedelta(seconds=120))
            db.add(task);db.flush();task_id=task.id
            audit(db,1,'metadata.diagnostic.started',f'provider=foreverdb; resource={resource}; cap={CAP}')
        status, headers, body, payload, error = None, {}, None, None, None
        started = monotonic()
        try:
            meta, body = request(url,authorization=f'Bearer {key}',timeout=12,max_bytes=1048576)
            status, headers = meta['status'], meta['headers']
            if status == 200:
                payload = decode(body)
                if 'data' not in payload or not isinstance(payload.get('meta'),dict): raise ValueError()
                # Refuse to persist anything that contains the credential, even on success.
                if key.encode() in body: raise ValueError()
        except Exception:
            payload = None; error = 'transport_or_schema'
        received = at+timedelta(seconds=monotonic()-started)
        result = {'resource':resource,'status':status,'at':received.isoformat(),'error':error,
                  'shape':shape(payload) if payload is not None else None}
        if payload is not None:
            filename = f'{task_id}-{resource.replace("/","-")}.json'
            target = output/filename
            # Fresh exclusive private file. No headers, credentials or error bodies.
            with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:
                json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
            result.update(sample=filename,body_sha256=hashlib.sha256(body).hexdigest())
        with Session.begin() as db:
            row=db.get(MetadataProvider,'foreverdb',with_for_update=True)
            observe(row,status,headers,received,reserved_at=at)
            if status in (401,402,403,429,503):cooldown(row,status,headers,received)
            task=db.get(MetadataTask,task_id);job=db.get(MetadataJob,task.job_id)
            task.state='completed' if payload is not None else 'failed';task.lease_until=None
            task.result_json=json.dumps({'provider':'foreverdb','resource':resource,'http_status':status,
                'status':error or ('available' if status==200 else 'unavailable'),'recovered_fields':[],
                'outcome':'metadata_returned' if payload is not None else 'unavailable'})
            job.state='completed';job.updated_at=task.updated_at=received
            audit(db,1,'metadata.diagnostic.completed',f'provider=foreverdb; resource={resource}; http={status}')
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('resource');p.add_argument('--output',required=True);p.add_argument('--limit',type=int,default=1);p.add_argument('--offset',type=int,default=0)
    args=p.parse_args()
    try: print(json.dumps(probe(args.resource,args.output,limit=args.limit,offset=args.offset)))
    except Exception: p.exit(1,'ForeverDB probe failed; details suppressed to protect server credentials.\n')
