#!/usr/bin/env python3
"""Owner-authorized bounded operator diagnostics. Run inside the existing API.

No configuration changes. Credential reads use the encrypted server store. Every
outbound attempt reserves persistent quota and is recorded before network I/O.
"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import re
from urllib.error import HTTPError
from urllib.request import Request
from market.probe import opener
from sqlalchemy import JSON, cast, func, select, text
from market.db import Session, now
from market.metadata_catalog import get_source, store_source
from market.metadata_providers import PARSERS, build_identity, fetch, parse_everloot_page
from market.metadata_recovery import credential_value, reserve_budget, worker_lock, cooldown
from market.models import ItemMetadata, ItemMedia, Market, MetadataJob, MetadataProvider, MetadataSource, MetadataTask, Observation, SnapshotStatistic
from market.security import audit, aware

INVESTIGATION = 'admin-provider-investigation-20261115'
CAP = 200


def diagnostic_request(url, *, authorization=None, conditional=None, timeout=8, max_bytes=1048576):
    headers={'Accept':'application/json','User-Agent':'TwichUI-Market/0.1 feasibility'}
    if authorization: headers['Authorization']=authorization
    if conditional and conditional.get('If-None-Match'): headers['If-None-Match']=conditional['If-None-Match']
    try: response=opener.open(Request(url,headers=headers),timeout=timeout)
    except HTTPError as error: response=error
    with response:
        body=response.read(max_bytes+1)
        if len(body)>max_bytes:raise ValueError('Response exceeds diagnostic size cap')
        allowed=('ETag','Cache-Control','Retry-After','Content-Type','Server','CF-Mitigated','X-RateLimit-Limit','X-RateLimit-Remaining','X-RateLimit-Reset','RateLimit-Limit','RateLimit-Remaining','RateLimit-Reset','X-Everloot-Licence','X-Everloot-Credit')
        return {'status':response.status,'headers':{key:response.headers.get(key) for key in allowed}},body


def baseline(snapshot_id=None):
    with Session() as db:
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
        observation=db.scalar(select(Observation).where(Observation.market_id==2).order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
        snapshot=snapshot_id or observation.snapshot_id
        stats=list(db.execute(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id==snapshot).order_by(SnapshotStatistic.item_id,SnapshotStatistic.variant_key)).scalars())
        ids=sorted({s.item_id for s in stats})
        items={r.item_id:r for r in db.scalars(select(ItemMetadata).where(ItemMetadata.region=='us',ItemMetadata.item_id.in_(ids)))}
        icons={r.item_id for r in db.scalars(select(ItemMedia).where(ItemMedia.region=='us',ItemMedia.item_id.in_(ids),ItemMedia.asset_hash.is_not(None)))}
        sources={}
        for source in db.scalars(select(MetadataSource).where(MetadataSource.region=='us',MetadataSource.item_id.in_(ids))):
            fields=json.loads(source.fields_json) if source.fields_json else {}
            sources.setdefault(source.item_id,[]).append({'provider':source.provider,'status':source.status,'http_status':source.http_status,'has_name':bool(fields.get('name')),'has_attributes':bool(fields.keys()-{'name'}),'retry_at':source.retry_at})
        records=[]
        for ident in ids:
            row=items.get(ident)
            records.append({'item_id':ident,'name':(row.name or row.fallback_name) if row else None,'primary_http':row.http_status if row else None,'quality':row.quality if row else None,
                'icon':ident in icons,'sources':sources.get(ident,[]),'currently_active':True})
        price_rows=[[getattr(s,key) for key in ('snapshot_id','item_id','variant_key','algorithm','recent_price','lowest_buyout','supply','priced_supply','listing_count')] for s in stats]
        named=sum(bool(r['name']) for r in records)
        return {'investigation':INVESTIGATION,'at':now(),'snapshot_id':snapshot,'observation_id':observation.id,'total':len(ids),'named':named,'unresolved':len(ids)-named,
            'name_percent':round(100*named/len(ids),4) if ids else None,'id_hash':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            'price_supply_hash':hashlib.sha256(json.dumps(price_rows).encode()).hexdigest(),'items':records,
            'markets':[{'id':m.id,'enabled':m.enabled,'house_id':m.house_id,'interval':m.interval_seconds} for m in db.scalars(select(Market))]}


def probe(provider,item_id,deadline,kind='item',store_validated=False,etag=None):
    if now()>=deadline: raise ValueError('Diagnostic window has ended')
    with worker_lock(Session) as locked:
        if not locked: return {'blocked':'Metadata worker is using its normal request lock; retry later'}
        with Session.begin() as db:
            # Serializes the shared investigation cap without changing worker controls.
            db.execute(text('SELECT pg_advisory_xact_lock(7140243)'))
            used=db.scalar(select(func.coalesce(func.sum(MetadataJob.requests_used),0)).where(MetadataJob.dedupe_key==INVESTIGATION))
            if used>=CAP: return {'blocked':'Overall 200-attempt investigation cap reached'}
            duplicate=db.scalar(select(MetadataTask.id).join(MetadataJob).where(MetadataJob.dedupe_key==INVESTIGATION, MetadataTask.provider==provider,MetadataTask.item_id==item_id,cast(MetadataTask.result_json,JSON)['kind'].as_string()==kind).limit(1))
            if duplicate:return {'blocked':'Already probed this item and endpoint in this investigation'}
            row=db.get(MetadataProvider,provider,with_for_update=True)
            if not row: raise ValueError('Provider must already be configured')
            src=get_source(db,'us',item_id,provider)
            if kind=='item' and src.retry_at and aware(src.retry_at)>now():return {'blocked':'Source retry window has not expired','next_retry':src.retry_at}
            # Connection diagnostics may run while recovery is disabled, just like Test Connection.
            # An explicit owner window is required; automatic recovery is never enabled here.
            credential=credential_value(db,row)
            if provider=='everloot' and not (credential and row.validated_at):raise ValueError('Validated Everloot credential required')
            waiting=reserve_budget(row,now())
            if waiting: return {'blocked':'Existing provider quota/cooldown applies','next_retry':waiting}
            job=MetadataJob(actor_id=1,market_id=2,mode='diagnostic',state='paused',dedupe_key=INVESTIGATION,providers_json=json.dumps([provider]),total=1,request_budget=1,requests_used=1)
            db.add(job);db.flush()
            task=MetadataTask(job_id=job.id,provider=provider,region='us',item_id=item_id,state='running',attempts=1)
            db.add(task);db.flush();task_id=task.id
            audit(db,1,'metadata.diagnostic.started',f'job={job.id}; provider={provider}; kind={kind}; item={item_id}; cap=200')
        raw=None;meta={};fields={};origin=None;category=None;fixture=None
        try:
            meta,raw=(diagnostic_request('https://everloot.app/api/corpus/public?kinds=item_seen,item_fact&limit=100',authorization=f'Bearer {credential}') if kind=='corpus' else fetch(provider,item_id,credential=credential,validate=kind=='attributes',transport=diagnostic_request,etag=etag))
            status=meta['status']
            if status==200:
                if kind=='corpus':
                    value=json.loads(raw)
                    if value.get('ok') is not True or not isinstance(value.get('records'),list):raise ValueError('Unexpected public corpus shape')
                    category='observations_only'
                    fixture={key:value[key] for key in ('ok','uploads','dataAsOf','kinds','offset','limit','total','next','attribution') if key in value}
                    fixture['record_count']=len(value['records'])
                    fixture['named_observation_count']=sum(bool(r.get('name')) for r in value['records'] if isinstance(r,dict))
                    fixture['record_field_names']=sorted({k for r in value['records'] if isinstance(r,dict) for k in r})
                elif kind=='attributes':
                    records,_=parse_everloot_page(raw)
                    category='attributes_only';fields={};value=json.loads(raw)
                    fixture={key:value[key] for key in ('generatedAt','gameData','offset','limit','total','next') if key in value}
                    fixture['items']=[{key:row[key] for key in ('itemId','class','subclass','slot','quality') if key in row} for row in value['items']]
                else:
                    fields,origin=PARSERS[provider](raw,item_id)
                    if provider=='thewowdb':build_identity(origin.get('build'))
                    category='named_record' if fields.get('name') else 'no_usable_name'
                    value=json.loads(raw)
                    # Provider fields validated first; keep only the public metadata contract.
                    keys=('ok','type','id','title','url','attribution','gameData') if provider=='everloot' else ('id','kind','version','name','build','quality','item_level','required_level','binding','slot','item_subtype','stats','flavor','vendor_sell','attribution','links')
                    fixture={key:value[key] for key in keys if key in value}
            elif status==304:category='not_modified'
            else: category={401:'credentials_invalid',403:'access_blocked',404:'missing',429:'rate_limited'}.get(status,'unavailable')
        except Exception:
            category='payload_validation_rejected' if meta.get('status')==200 else 'transport_failed'
        with Session.begin() as db:
            task=db.get(MetadataTask,task_id);job=db.get(MetadataJob,task.job_id);row=db.get(MetadataProvider,provider)
            task.state='completed';job.state='completed';task.updated_at=job.updated_at=now()
            status=meta.get('status')
            if status in (401,402,403,429):cooldown(row,status,meta.get('headers',{}),now())
            if category in ('missing','access_blocked','rate_limited','credentials_invalid','payload_validation_rejected','transport_failed'):
                src=get_source(db,'us',item_id,provider)
                src.status={'missing':'metadata_unavailable','access_blocked':'forbidden','credentials_invalid':'authorization','payload_validation_rejected':'transport_or_schema','transport_failed':'transport_or_schema'}.get(category,category)
                src.checked_at,src.http_status=now(),status
                src.retry_at=now()+timedelta(days=7) if status==404 else now()+timedelta(minutes=15)
                if row.cooldown_until and aware(row.cooldown_until)>src.retry_at:src.retry_at=aware(row.cooldown_until)
            new_names=0;new_fields=[]
            if store_validated and category=='named_record' and origin and kind=='item':
                previous=db.get(ItemMetadata,('us',item_id))
                before=json.loads(previous.catalog_json).get('fields',{}) if previous and previous.catalog_json else {}
                had_name=bool(previous and (previous.name or previous.fallback_name))
                projected=store_source(db,'us',item_id,provider,fields,origin,etag=meta.get('headers',{}).get('ETag'))
                new_fields=[f for f,v in projected['fields'].items() if v is not None and v!=[] and before.get(f) in (None,[])]
                new_names=int(not had_name and bool(projected['fields'].get('name')))
            result={'kind':kind,'status':category,'http_status':status,'provider':provider,'recovered_fields':[],'fields_returned':list(fields),'outcome':{'not_modified':'already_known','named_record':'metadata_returned','attributes_only':'metadata_returned','observations_only':'no_usable_data','no_usable_name':'no_usable_data','access_blocked':'access_blocked','missing':'missing','rate_limited':'rate_limited','credentials_invalid':'credentials_invalid','payload_validation_rejected':'invalid_response'}.get(category,'unavailable')}
            result['new_fields']=new_fields
            result['recovered_fields']=list(fields)
            if origin:result['source']=origin
            if new_names:result['outcome']='name_recovered'
            elif new_fields:result['outcome']='attributes_recovered'
            task.result_json=json.dumps(result)
            audit(db,1,'metadata.diagnostic.completed',f'job={job.id}; provider={provider}; category={category}; http={status}')
        return {'investigation':INVESTIGATION,'attempt_number':used+1,'task_id':task_id,'provider':provider,'item_id':item_id,'kind':kind,'category':category,
            'http_status':meta.get('status'),'headers':meta.get('headers',{}),'body_sha256':hashlib.sha256(raw).hexdigest() if raw else None,
            'body_bytes':len(raw) if raw else 0,'fields_returned':list(fields),'fixture':fixture,'new_names_committed':new_names,'new_fields_committed':new_fields}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['baseline','probe'])
    parser.add_argument('--snapshot',type=int)
    parser.add_argument('--provider',choices=['everloot','thewowdb'])
    parser.add_argument('--item',type=int,default=25)
    parser.add_argument('--kind',choices=['item','attributes','corpus','conditional'],default='item')
    parser.add_argument('--etag',help='Public response ETag for one bounded conditional check')
    parser.add_argument('--store-validated',action='store_true',help='Manually store only valid named responses; preserve precedence and existing data')
    parser.add_argument('--deadline',help='Owner-approved verification-window end, ISO UTC')
    args=parser.parse_args()
    if args.action=='baseline':value=baseline(args.snapshot)
    else:
        if not args.provider or not args.deadline:parser.error('Probe needs provider and explicit deadline')
        deadline=aware(datetime.fromisoformat(args.deadline))
        if deadline>now()+timedelta(minutes=45):parser.error('Window must end within 45 minutes')
        if not 1<=args.item<=2**31-1:parser.error('Invalid item ID')
        if args.kind in ('attributes','corpus') and args.provider!='everloot':parser.error('Attributes contract is Everloot only')
        if args.kind=='conditional' and (not args.etag or len(args.etag)>255 or any(ord(c)<32 for c in args.etag)):parser.error('Conditional check needs a valid public ETag')
        value=probe(args.provider,args.item,deadline,args.kind,args.store_validated,args.etag)
    print(json.dumps(value,default=str,sort_keys=True))

if __name__=='__main__':main()
