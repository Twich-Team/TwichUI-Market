"""Authenticated immutable bridge exports. No collector, legacy pricing or saved-data writes."""
from collections import defaultdict
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from itertools import groupby
from fractions import Fraction
from types import SimpleNamespace
import base64
import hashlib
import hmac
import json
import os
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, insert, select, text, tuple_
from sqlalchemy.orm import Session

from . import canonical_pricing as cp, environment
from .bridge_contract import contract
from .db import now, session
from .market_api import MarketId, require_market
from .market_configuration import mapping_for
from .models import (BridgeDerivation, BridgeDerivedRecord, BridgeGeneration, BridgeRecord,
                     Listing, Observation, Snapshot, SnapshotStatistic, User)
from .pricing import ALGORITHM as LEGACY, rounded, summarize as legacy_summarize
from .security import aware, identity
from .sync_api import secret

router=APIRouter(prefix='/api/v1/bridge')
REVISION=1
MAX_PAGE_BYTES=1024*1024
MAX_PAGE_RECORDS=100
MAX_RECORDS=150_000
MAX_COLD_SNAPSHOTS=4
CACHE_HOURS=1
MAX_GENERATIONS=8


def utc(value):
    return aware(value).astimezone(timezone.utc)


def stamp(value):
    return utc(value).isoformat(timespec='microseconds').replace('+00:00','Z')


def lock(db):
    if db.bind.dialect.name=='postgresql':
        db.execute(text("SET LOCAL statement_timeout='10s'"))
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140232)')):
            raise HTTPException(409,'Collection or retention is busy; retry bridge export')


def market_identity(db,market):
    mapping=mapping_for(db,market)
    return {'game':'wow-forever','region':market.region,'player_ruleset':mapping.ruleset if mapping else None,
            'house_id':market.house_id,'source_kind':market.source_kind,'server_market_id':market.id,
            'transport_ruleset_id':market.ruleset_id,'mapping_verified':mapping is not None,
            'mapping_evidence_sha256':mapping.evidence_hash if mapping else None,'realm_scope':'ruleset_house'}


def observation_view(o,snapshot,at):
    upstream=None
    if o.upstream_modified:
        try:
            parsed=aware(parsedate_to_datetime(o.upstream_modified))
            if parsed<=at:upstream=stamp(parsed)
        except (ValueError,TypeError,OverflowError):pass
    return {'observation_id':str(o.id),'snapshot_id':str(o.snapshot_id),
            'utc_day':utc(o.retrieved_at).date().isoformat(),'observed_at':stamp(o.retrieved_at),
            'upstream_updated_at':upstream,'upstream_modified_raw':o.upstream_modified,
            'namespace':o.namespace,'payload_sha256':o.payload_hash,'snapshot_content_sha256':snapshot.content_hash,
            'synthetic':o.synthetic,'scope_complete':True}


def derivation(db,snapshot,algorithm):
    return db.get(BridgeDerivation,(snapshot.id,algorithm,REVISION))


def legacy_distribution(rows):
    prices=[];unpriced_supply=unpriced_count=0
    for row in rows:
        if row['unit_copper'] is not None:price=Fraction(int(row['unit_copper']))
        elif row['total_copper'] is not None:price=Fraction(int(row['total_copper']),row['quantity'])
        else:
            unpriced_supply+=row['quantity'];unpriced_count+=1;continue
        prices.append((price,row['quantity']))
    if not prices:return None
    low=min(p for p,_ in prices);high=max(p for p,_ in prices);bins=defaultdict(list)
    def half(p):return str((2*p.numerator+p.denominator)//(2*p.denominator))
    for price,q in prices:
        bucket=0 if low==high else min(31,int((price-low)/(high-low)*32))
        bins[bucket].append((price,q))
    bands=[{'minimum_copper':half(min(p for p,_ in group)),'maximum_copper':half(max(p for p,_ in group)),
            'supply':sum(q for _,q in group),'listing_count':len(group)} for _,group in sorted(bins.items())]
    return {'algorithm':'linear-unit-price-bands-v1','basis':'current_asking_listings','complete':True,'truncated':False,
        'priced_supply':sum(q for _,q in prices),'unpriced_supply':unpriced_supply,
        'priced_listing_count':len(prices),'unpriced_listing_count':unpriced_count,
        'quartiles':None,'tiers':[],'tail_quantity':0,'tail_listing_count':0,'bands':bands}


def prepare_snapshot(db,snapshot,algorithm,source):
    """At most 150k original rows, streamed/grouped by exact variant; atomically cached."""
    if derivation(db,snapshot,algorithm):return
    if not snapshot.raw_retained:
        raise HTTPException(409,'Canonical originals unavailable; request asking-v1-provisional explicitly')
    query=select(Listing).where(Listing.snapshot_id==snapshot.id).order_by(Listing.item_id,Listing.variant_key)
    count=records=0;pending=[]
    for (item,key),group in groupby(db.scalars(query.execution_options(yield_per=1000)),key=lambda x:(x.item_id,x.variant_key)):
        rows=[];descriptor=None
        for r in group:
            count+=1
            if count>cp.MAX_LISTINGS:raise HTTPException(413,'Snapshot listing bound')
            descriptor=r.variant
            rows.append({'item_id':item,'variant_key':key,'quantity':r.quantity,
                         'total_copper':str(r.buyout) if r.buyout is not None else None,
                         'unit_copper':str(r.unit_price) if r.unit_price is not None else None,
                         'bid_copper':str(r.bid) if r.bid is not None else None})
        result=cp.snapshot(rows,item_id=item,variant_key=key,source_kind=source)
        if algorithm==LEGACY:
            old=legacy_summarize([SimpleNamespace(quantity=r['quantity'],buyout=int(r['total_copper']) if r['total_copper'] is not None else None,
                unit_price=int(r['unit_copper']) if r['unit_copper'] is not None else None) for r in rows])
            result.update(minimum_listing_copper=str(old['lowest_buyout']) if old['lowest_buyout'] is not None else None,
                recent_copper=str(old['recent_price']) if old['recent_price'] is not None else None,
                quantity_weighted_ask_copper=str(old['recent_price']) if old['recent_price'] is not None else None,
                state='priced' if old['recent_price'] is not None else 'unpriced',distribution=legacy_distribution(rows))
        value={'variant_json':descriptor,'summary':result}
        pending.append({'snapshot_id':snapshot.id,'algorithm':algorithm,'revision':REVISION,'item_id':item,
                        'variant_key':key,'record_json':contract().canonical(value).decode()})
        records+=1
        if len(pending)==100:
            db.execute(insert(BridgeDerivedRecord),pending);pending=[]
    if pending:db.execute(insert(BridgeDerivedRecord),pending)
    if count!=snapshot.listing_count:raise HTTPException(409,'Incomplete retained snapshot')
    db.add(BridgeDerivation(snapshot_id=snapshot.id,algorithm=algorithm,revision=REVISION,record_count=records))
    db.flush()


def selected_observations(db,market,at,algorithm):
    watermark=db.scalar(select(func.max(Observation.id)).where(Observation.market_id==market.id,Observation.retrieved_at<=at))
    if watermark is None:raise HTTPException(409,'No observed market generation available')
    current=db.scalar(select(Observation).where(Observation.market_id==market.id,Observation.id<=watermark,Observation.retrieved_at<=at)
                      .order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
    start=datetime.combine(at.date()-timedelta(days=59),time(),tzinfo=timezone.utc)
    if algorithm==LEGACY:start=min(start,aware(current.retrieved_at)-timedelta(days=60))
    day=func.date(func.timezone('UTC',Observation.retrieved_at)) if db.bind.dialect.name=='postgresql' else func.date(Observation.retrieved_at)
    ranked=select(Observation.id,func.row_number().over(partition_by=day,
        order_by=(Observation.retrieved_at.desc(),Observation.id.desc())).label('n')).where(
        Observation.market_id==market.id,Observation.id<=watermark,Observation.retrieved_at>=start,Observation.retrieved_at<=at).subquery()
    daily=list(db.scalars(select(Observation).join(ranked,ranked.c.id==Observation.id).where(ranked.c.n==1)
                          .order_by(Observation.retrieved_at,Observation.id)))
    observations=sorted({o.id:o for o in [*daily,current]}.values(),key=lambda o:(aware(o.retrieved_at),o.id))
    return watermark,current,daily,observations


def record_batch(db,keys,snapshots,algorithm):
    if algorithm==cp.ALGORITHM:
        rows=db.scalars(select(BridgeDerivedRecord).where(BridgeDerivedRecord.snapshot_id.in_(snapshots),
            BridgeDerivedRecord.algorithm==algorithm,BridgeDerivedRecord.revision==REVISION,
            tuple_(BridgeDerivedRecord.item_id,BridgeDerivedRecord.variant_key).in_(keys)))
        return {(r.snapshot_id,r.item_id,r.variant_key):json.loads(r.record_json) for r in rows}
    rows=db.scalars(select(SnapshotStatistic).where(SnapshotStatistic.snapshot_id.in_(snapshots),
        tuple_(SnapshotStatistic.item_id,SnapshotStatistic.variant_key).in_(keys)))
    out={}
    for r in rows:
        if r.algorithm!=LEGACY:raise HTTPException(409,'Unsupported retained statistics algorithm')
        out[r.snapshot_id,r.item_id,r.variant_key]={'variant_json':None,'summary':{
            'supply':r.supply,'priced_supply':r.priced_supply,'listing_count':r.listing_count,
            'minimum_listing_copper':str(r.lowest_buyout) if r.lowest_buyout is not None else None,
            'recent_copper':str(r.recent_price) if r.recent_price is not None else None,
            'quantity_weighted_ask_copper':str(r.recent_price) if r.recent_price is not None else None,
            'state':'priced' if r.recent_price is not None else 'unpriced','distribution':None}}
    derived=db.scalars(select(BridgeDerivedRecord).where(BridgeDerivedRecord.snapshot_id.in_(snapshots),
        BridgeDerivedRecord.algorithm==algorithm,BridgeDerivedRecord.revision==REVISION,
        tuple_(BridgeDerivedRecord.item_id,BridgeDerivedRecord.variant_key).in_(keys)))
    for row in derived:
        key=(row.snapshot_id,row.item_id,row.variant_key);value=json.loads(row.record_json)
        if key not in out or any(out[key]['summary'][k]!=value['summary'][k] for k in ('recent_copper','minimum_listing_copper')):
            raise HTTPException(409,'Original and retained legacy derivation disagree')
        out[key]=value
    return out


def assemble_record(key,values,current,daily,refs,algorithm,at,days):
    item,variant=key;current_value=values.get((current.snapshot_id,*key))
    descriptor=next((v['variant_json'] for o in [current,*daily] if (v:=values.get((o.snapshot_id,*key))) is not None and v['variant_json'] is not None),None)
    priced=[];recent=[];points=[]
    for o in daily:
        value=values.get((o.snapshot_id,*key));s=value['summary'] if value else None
        p=s['recent_copper'] if s else None;age=(at.date()-utc(o.retrieved_at).date()).days
        if p is not None:
            priced.append((int(p),1))
            if age<14:recent.append((int(p),4 if age<=2 else 2 if age<=6 else 1))
        if o.id in days:
            points.append({'observation_ref':refs[o.id],'state':'listed' if s else 'absent','algorithm':algorithm,
                'minimum_copper':s['minimum_listing_copper'] if s else None,'recent_copper':p,
                'supply':s['supply'] if s else 0,'priced_supply':s['priced_supply'] if s else 0,
                'listing_count':s['listing_count'] if s else 0,
                'arithmetic_status':'unsupported' if s and s['state']=='unsupported' else 'exact'})
    def median(rows):return str(cp.lower_median(rows)) if rows else None
    if algorithm==cp.ALGORITHM:
        mv=median(recent);hv=median(priced) if len(priced)>=3 else None
    else:
        # The legacy reference windows are exact rolling durations, not the canonical UTC windows.
        full=[];last=[]
        for o in daily:
            if aware(o.retrieved_at)<aware(current.retrieved_at)-timedelta(days=60):continue
            v=values.get((o.snapshot_id,*key));p=v['summary']['recent_copper'] if v else None
            if p is not None:
                full.append(Decimal(p))
                if aware(o.retrieved_at)>=aware(current.retrieved_at)-timedelta(days=14):last.append(Decimal(p))
        mv=str(rounded(sum(last)/len(last))) if last else None;hv=str(rounded(sum(full)/len(full))) if full else None
        recent=[(int(x),1) for x in last];priced=[(int(x),1) for x in full]
    s=current_value['summary'] if current_value else None
    c={'state':'listed' if s else 'absent','algorithm':algorithm,
       'metric_basis':'lower_band_mean' if algorithm==cp.ALGORITHM else 'quantity_weighted_mean',
       'observation_ref':refs[current.id],'metrics':{
           'minimum_copper':s['minimum_listing_copper'] if s else None,
           'quantity_weighted_ask_copper':s['quantity_weighted_ask_copper'] if s else None,
           'recent_copper':s['recent_copper'] if s else None,'market_value_copper':mv,'historical_value_copper':hv},
       'supply':s['supply'] if s else 0,'priced_supply':s['priced_supply'] if s else 0,
       'listing_count':s['listing_count'] if s else 0,'complete':True,
       'arithmetic_status':'unsupported' if s and s['state']=='unsupported' else 'exact',
       'coverage':{'priced_days_14':len(recent),'priced_days_60':len(priced),'observed_days_60':len(daily),'references_complete':True}}
    dist=None
    if s and s['distribution'] and algorithm==LEGACY:
        dist=s['distribution']
    elif s and s['distribution']:
        d=s['distribution'];tail=bool(d['tail_quantity'])
        dist={'algorithm':'canonical-tiers-v1','basis':'current_asking_listings','complete':not tail,'truncated':tail,
              'priced_supply':s['priced_supply'],'unpriced_supply':s['supply']-s['priced_supply'],
              'priced_listing_count':s['priced_listing_count'],'unpriced_listing_count':s['listing_count']-s['priced_listing_count'],
              'quartiles':{k:d[k] for k in ['anchor_copper','q25_copper','q50_copper','q75_copper','high_copper']},
              'tiers':d['tiers'],'tail_quantity':d['tail_quantity'],'tail_listing_count':d['tail_listing_count'],'bands':[]}
    return {'item_id':item,'variant_key':variant,'variant_json':descriptor,
            'identity_basis':'exact_upstream' if descriptor else 'hash_only','current':c,'daily':points,
            'distribution':dist,'distribution_status':'available' if dist else 'unsupported' if s and s['state']=='unsupported' else 'unavailable'}


def build_generation(db,market,algorithm,at,history_days=60):
    at=utc(at)
    watermark,current,daily,observations=selected_observations(db,market,at,algorithm)
    history_from=at.date()-timedelta(days=history_days-1)
    delivered=[o for o in daily if utc(o.retrieved_at).date()>=history_from]
    snapshots={r.id:r for r in db.scalars(select(Snapshot).where(Snapshot.id.in_({o.snapshot_id for o in observations})))}
    if len(snapshots)!=len({o.snapshot_id for o in observations}) or any(not s.statistics_retained for s in snapshots.values()):
        raise HTTPException(409,'Retained source support unavailable')
    identity_value=market_identity(db,market)
    signature=contract().digest([2,algorithm,REVISION,watermark,at.date().isoformat(),history_days,identity_value,
        [[o.id,stamp(o.retrieved_at),o.synthetic,o.upstream_modified,snapshots[o.snapshot_id].content_hash] for o in observations]])
    cached=db.scalar(select(BridgeGeneration).where(BridgeGeneration.market_id==market.id,
        BridgeGeneration.algorithm==algorithm,BridgeGeneration.source_signature==signature,
        BridgeGeneration.created_at>at-timedelta(hours=CACHE_HOURS)))
    if cached:return cached
    missing=[s for s in snapshots.values() if derivation(db,s,algorithm) is None]
    if algorithm==cp.ALGORITHM and any(not s.raw_retained for s in missing):
        raise HTTPException(409,'Canonical originals unavailable; request asking-v1-provisional explicitly')
    possible=[s for s in missing if s.raw_retained]
    for snapshot in possible[:MAX_COLD_SNAPSHOTS]:prepare_snapshot(db,snapshot,algorithm,market.source_kind)
    if len(possible)>MAX_COLD_SNAPSHOTS:
        db.commit()
        return None
    if algorithm==cp.ALGORITHM:
        model=BridgeDerivedRecord
        query=select(model.item_id,model.variant_key).where(model.snapshot_id.in_(snapshots),model.algorithm==algorithm,model.revision==REVISION)
    else:
        model=SnapshotStatistic
        query=select(model.item_id,model.variant_key).where(model.snapshot_id.in_(snapshots))
    keys=list(db.execute(query.distinct().order_by(model.item_id,model.variant_key).limit(MAX_RECORDS+1)))
    if len(keys)>MAX_RECORDS:raise HTTPException(413,'Historical variant union exceeds bridge record limit')
    refs={o.id:i for i,o in enumerate(observations)}
    source=[observation_view(o,snapshots[o.snapshot_id],at) for o in observations]
    # Reference computation uses all support; delivery compaction removes oldest whole days uniformly.
    records=[];record_bytes=0
    for start in range(0,len(keys),100):
        batch=[tuple(k) for k in keys[start:start+100]];values=record_batch(db,batch,list(snapshots),algorithm)
        for key in batch:
            r=assemble_record(key,values,current,daily,refs,algorithm,at,{o.id for o in delivered})
            raw=contract().canonical(r)
            if len(raw)>contract().MAX_RECORD_BYTES:raise HTTPException(413,'Bridge record exceeds limit')
            record_bytes+=len(raw)
            if record_bytes>64*1024*1024:raise HTTPException(413,'Bridge build exceeds bounded working set; request a narrower history window')
            records.append(r)
    g={'format':'twichui-market-bridge','contract_version':1,'schema_version':2,'transport_version':1,
       'issuer_id':str(uuid.uuid5(uuid.NAMESPACE_URL,environment.SESSION_ORIGIN)),
       'producer':{'server_build':(os.environ.get('APP_COMMIT') or 'development-bridge-m1b')[:80],'desktop_build':'not-applicable-server-export'},
       'required_features':['exact_copper','current_summaries','daily_history'],'market':identity_value,
       'pricing_algorithm':algorithm,'history_basis':cp.HISTORY_BASIS if algorithm==cp.ALGORITHM else 'market_rolling_daily_means',
       'quality_policy':1,'watermark_observation_id':str(watermark),'current_observation_ref':refs[current.id],
       'as_of_utc_day':at.date().isoformat(),'generated_at':stamp(at),'desktop_sync_completed_at':None,
       'server_checked_at':stamp(market.last_success) if market.last_success and aware(market.last_success)<=at else None,
       'observations':source,'coverage':{'scope':'house_auctions' if market.source_kind=='auctions' else 'house_commodities',
          'generation_complete':True,'current_complete':True,'history_from_day':history_from.isoformat(),
          'history_through_day':at.date().isoformat(),'available_observed_days':len(delivered),'delivered_observed_days':len(delivered),
          'history_complete':True,'history_truncated':False,'distribution_complete':False,'omitted_sections':[]},
       'synthetic':any(o.synthetic for o in observations),'record_count':len(records),'records':records}
    while len(contract().canonical(g))+512>contract().MAX_BYTES:
        if any(r['distribution'] is not None for r in records):
            for r in records:
                if r['distribution'] is not None:r['distribution']=None;r['distribution_status']='omitted_budget'
            g['coverage']['omitted_sections'].append('distributions')
            continue
        included=sorted({p['observation_ref'] for r in records for p in r['daily']},key=lambda i:source[i]['utc_day'])
        if len(included)<=2:raise HTTPException(413,'Bridge cannot fit newest two observed dates')
        remove=included[0]
        for r in records:r['daily']=[p for p in r['daily'] if p['observation_ref']!=remove]
        # Omitted observation references are removed only after compaction; supporting provenance OR is retained.
        source[remove]['_omitted']=True
    # Reconcile global delivered references after dropping old history, preserving current.
    omitted={i for i,o in enumerate(source) if o.pop('_omitted',False)}
    if omitted:
        keep=[i for i in range(len(source)) if i not in omitted or i==refs[current.id]]
        remap={old:new for new,old in enumerate(keep)}
        g['observations']=[source[i] for i in keep];g['current_observation_ref']=remap[refs[current.id]]
        for r in records:
            r['current']['observation_ref']=g['current_observation_ref']
            for p in r['daily']:p['observation_ref']=remap[p['observation_ref']]
        g['coverage'].update(history_complete=False,history_truncated=True,
            delivered_observed_days=len({o['utc_day'] for o in g['observations'] if g['coverage']['history_from_day']<=o['utc_day']<=g['coverage']['history_through_day']}))
        g['coverage']['omitted_sections'].append('older_daily_history')
    g=contract().seal(g)
    contract().validate(g)
    header={k:v for k,v in g.items() if k!='records'}
    if len(contract().canonical(header))>64*1024:raise HTTPException(413,'Bridge transport manifest bound')
    row=BridgeGeneration(generation_id=g['generation_id'],market_id=market.id,algorithm=algorithm,
        source_signature=signature,manifest_json=contract().canonical(header).decode(),created_at=at)
    db.add(row);db.flush()
    for start in range(0,len(records),100):
        db.execute(insert(BridgeRecord),[{'generation_id':row.generation_id,'position':i,
            'record_json':contract().canonical(records[i]).decode()} for i in range(start,min(start+100,len(records)))])
    # Bounded disposable export cache only. Eviction produces an explicit restart, never mixed pages.
    old=list(db.scalars(select(BridgeGeneration).order_by(BridgeGeneration.created_at.desc(),BridgeGeneration.generation_id.desc())))
    counts=defaultdict(int)
    for i,entry in enumerate(old):
        counts[entry.market_id,entry.algorithm]+=1
        if entry.generation_id!=row.generation_id and (i>=MAX_GENERATIONS or counts[entry.market_id,entry.algorithm]>2 or aware(entry.created_at)<at-timedelta(hours=CACHE_HOURS)):
            db.execute(delete(BridgeRecord).where(BridgeRecord.generation_id==entry.generation_id));db.delete(entry)
    db.flush()
    return row


def cursor(row,user,credential,offset,at):
    payload={'v':1,'kind':'bridge-page','generation':row.generation_id,'market':row.market_id,
        'account':user.id,'credential':credential.id,'after':offset,'expires':int((at+timedelta(hours=CACHE_HOURS)).timestamp())}
    raw=base64.urlsafe_b64encode(contract().canonical(payload)).decode().rstrip('=')
    return raw+'.'+hmac.new(secret(),('bridge-v1:'+raw).encode(),hashlib.sha256).hexdigest()


def decode_cursor(value,market,user,credential,at):
    try:
        raw,signature=value.split('.')
        if not hmac.compare_digest(signature,hmac.new(secret(),('bridge-v1:'+raw).encode(),hashlib.sha256).hexdigest()):raise ValueError()
        p=json.loads(base64.b64decode(raw+'='*(-len(raw)%4),altchars=b'-_',validate=True))
        if (set(p)!={'v','kind','generation','market','account','credential','after','expires'} or p['v']!=1 or p['kind']!='bridge-page'
            or any(type(p[k]) is not int for k in ['v','market','account','credential','after','expires'])
            or (p['market'],p['account'],p['credential'])!=(market,user.id,credential.id)
            or not 0<=p['after']<=MAX_RECORDS or p['expires']<int(at.timestamp())
            or re.fullmatch('[0-9a-f]{64}',p['generation']) is None):raise ValueError()
        return p
    except (ValueError,TypeError,KeyError,UnicodeError):raise HTTPException(409,'Invalid or expired bridge cursor; restart generation download')


def device_identity(request:Request,user:User=Depends(identity)):
    if not request.headers.get('authorization','').startswith('Bearer '):raise HTTPException(403,'Use a desktop/device connection')
    return user


@router.get('/markets/{market_id}/manifest')
def manifest(market_id:MarketId,request:Request,algorithm:str=Query(cp.ALGORITHM,max_length=80),
             history_days:int=Query(60,ge=2,le=60),user:User=Depends(device_identity),db:Session=Depends(session)):
    if algorithm not in (cp.ALGORITHM,LEGACY):raise HTTPException(422,'Unsupported bridge pricing algorithm')
    market=require_market(db,market_id)
    if not market.verified:raise HTTPException(404,'Verified observed market required')
    lock(db);at=now()
    row=build_generation(db,market,algorithm,at,history_days)
    if row is None:return JSONResponse({'state':'preparing','retry_after_seconds':1},status_code=202,headers={'Retry-After':'1','Cache-Control':'no-store'})
    result={'format':'twichui-market-bridge-manifest','contract_version':1,'transport_version':1,
        'account_id':user.id,'manifest':json.loads(row.manifest_json),
        'cursor':cursor(row,user,request.state.credential,0,at)}
    db.commit()
    return JSONResponse(result,headers={'Cache-Control':'no-store'})


@router.get('/markets/{market_id}/records')
def records(market_id:MarketId,request:Request,cursor_value:str=Query(alias='cursor',min_length=1,max_length=2048),
            generation:str=Query(min_length=64,max_length=64),limit:int=Query(50,ge=1,le=100),
            user:User=Depends(device_identity),db:Session=Depends(session)):
    at=now();p=decode_cursor(cursor_value,market_id,user,request.state.credential,at)
    if generation!=p['generation']:raise HTTPException(409,'Bridge generation mismatch')
    row=db.get(BridgeGeneration,generation)
    if row is None or row.market_id!=market_id or aware(row.created_at)<at-timedelta(hours=CACHE_HOURS):raise HTTPException(409,'Bridge generation expired; restart download')
    header=json.loads(row.manifest_json);count=header['record_count'];offset=p['after']
    if offset>count:raise HTTPException(409,'Impossible bridge cursor offset')
    rows=list(db.scalars(select(BridgeRecord).where(BridgeRecord.generation_id==generation,BridgeRecord.position>=offset)
        .order_by(BridgeRecord.position).limit(min(limit,MAX_PAGE_RECORDS))))
    out=[];size=4096
    for r in rows:
        if r.position!=offset+len(out):raise HTTPException(409,'Bridge materialization incomplete; restart download')
        encoded=r.record_json.encode()
        if size+len(encoded)>MAX_PAGE_BYTES:break
        out.append(json.loads(r.record_json));size+=len(encoded)+1
    end=offset+len(out)
    if end<count and not out:raise HTTPException(409,'Bridge materialization incomplete; restart download')
    result={'format':'twichui-market-bridge-page','contract_version':1,'transport_version':1,'account_id':user.id,
        'market_id':market_id,'generation_id':generation,'offset':offset,'records':out,'has_more':end<count,
        'next_cursor':cursor(row,user,request.state.credential,end,at) if end<count else None}
    raw=contract().canonical(result)
    if len(raw)>MAX_PAGE_BYTES:raise HTTPException(413,'Bridge page byte limit')
    return JSONResponse(result,headers={'Cache-Control':'no-store'})
