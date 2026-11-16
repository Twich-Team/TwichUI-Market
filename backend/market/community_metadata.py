"""Optional attributed Forever beta metadata. Never imports third-party prices."""
import hashlib,json,os,re
from datetime import timedelta
from urllib.parse import urlsplit
from .db import now
from .item_attributes import QUALITIES,text
from .probe import request


def parse_community(body,item_id,*,at=None,etag=None):
    if len(body)>65536:raise ValueError('Community metadata limit')
    value=json.loads(body)
    if not isinstance(value,dict):raise ValueError('Expected community item object')
    if type(value.get('id')) is not int or value.get('id')!=item_id or value.get('version')!='forever' or value.get('kind')!='item':raise ValueError('Community identity/edition mismatch')
    build=value.get('build')
    if not isinstance(build,str) or not re.fullmatch(r'wow_classic_beta-[0-9._]+',build):raise ValueError('Unrecognized community build')
    name=text(value.get('name'),255)
    if name is None:raise ValueError('Community name missing')
    credit=value.get('attribution')
    if not isinstance(credit,dict) or not text(credit.get('text'),255):raise ValueError('Required attribution missing')
    url=credit.get('url');parts=urlsplit(url) if isinstance(url,str) else None
    if not parts or parts.scheme!='https' or parts.hostname!='thewowdb.com' or parts.username or parts.password or parts.port not in (None,443) or parts.query or parts.fragment or not parts.path.startswith('/wow-forever/item/'):
        raise ValueError('Untrusted attribution')
    quality=value.get('quality')
    quality=quality.upper() if isinstance(quality,str) else None
    if quality is not None and quality not in QUALITIES:raise ValueError('Community quality')
    lines=[]
    for key in ['binding','slot','item_subtype','flavor']:
        content=text(value.get(key))
        if content:lines.append({'text':content,'kind':'flavor' if key=='flavor' else 'attribute'})
    # Structured facts only. No tooltip HTML, external scripts, market prices or guessed bonuses.
    for entry in (value.get('stats') or [])[:20]:
        if isinstance(entry,dict):
            content=text(entry.get('display_string'))
            if content:lines.append({'text':content,'kind':'stat'})
    attrs={'scope':'base_item','quality':quality,'lines':lines}
    for src,dst in [('item_level','level'),('required_level','required_level')]:
        number=value.get(src)
        if type(number) is int and 0<=number<=10000:attrs[dst]=number
    vendor=value.get('vendor_sell')
    if type(vendor) is int and 0<=vendor<=2**63-1:attrs['vendor_sell']=str(vendor)
    return {'name':name,'attributes':attrs,'icon_url':value.get('icon_url'),
            'source':{'provider':'thewowdb','confidence':'community_beta','build':build,
                      'url':f'https://thewowdb.com/api/v1/forever/item/{item_id}',
                      'observed_at':(at or now()).isoformat(),'payload_hash':hashlib.sha256(body).hexdigest(),
                      'attribution':{'text':credit['text'],'url':url},'etag':etag}}


def enrich_missing(row,*,at=None,transport=request):
    from .security import aware
    from .worker import retry_seconds
    at=at or now()
    if os.environ.get('ITEM_COMMUNITY_FALLBACK_ENABLED','false').lower()!='true' or row.name is not None:return False
    if row.fallback_retry_after and aware(row.fallback_retry_after)>at:return False
    previous=json.loads(row.fallback) if row.fallback else None
    conditional={'If-None-Match':previous['source'].get('etag')} if previous else None
    try:
        from sqlalchemy.orm import object_session,sessionmaker
        from .provider_rates import reserved_request,ProviderWaiting
        db=object_session(row)
        if db is None:return False
        meta,body=reserved_request(sessionmaker(db.get_bind(),expire_on_commit=False),'thewowdb',lambda:transport(f'https://thewowdb.com/api/v1/forever/item/{row.item_id}',timeout=5,max_bytes=65536,conditional=conditional),at=at)
        if meta['status']==304 and previous:
            row.fallback_retry_after=at+timedelta(hours=1);return True
        if meta['status']==200:
            parsed=parse_community(body,row.item_id,at=at,etag=meta['headers'].get('ETag'))
            row.fallback,row.fallback_name=json.dumps(parsed),parsed['name']
            row.fallback_retry_after=at+timedelta(hours=1)
        else:row.fallback_retry_after=at+timedelta(seconds=604800 if meta['status']==404 else max(3600,retry_seconds(meta['headers'].get('Retry-After'),at)))
    except ProviderWaiting as waiting:
        if waiting.until:row.fallback_retry_after=waiting.until
        return False
    except Exception:row.fallback_retry_after=at+timedelta(hours=1)
    return True


def resolve_community_once(factory=None,*,at=None):
    from sqlalchemy import or_,select,text as sqltext
    from .db import Session
    from .models import ItemMedia,ItemMetadata,Market,Observation,SnapshotStatistic
    if os.environ.get('ITEM_COMMUNITY_FALLBACK_ENABLED','false').lower()!='true':return False
    at=at or now();factory=factory or Session
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql' and not db.scalar(sqltext('SELECT pg_try_advisory_xact_lock(7140236)')):return False
        for market in db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)):
            latest=db.scalar(select(Observation).where(Observation.market_id==market.id).order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
            if not latest:continue
            observed=select(SnapshotStatistic.item_id).where(SnapshotStatistic.snapshot_id==latest.snapshot_id)
            row=db.scalar(select(ItemMetadata).where(ItemMetadata.region==market.region,ItemMetadata.name.is_(None),
                ItemMetadata.status=='missing',ItemMetadata.item_id.in_(observed),
                or_(ItemMetadata.fallback_retry_after.is_(None),ItemMetadata.fallback_retry_after<=at))
                .order_by(ItemMetadata.requested_at.desc().nulls_last(),ItemMetadata.item_id).limit(1))
            if row:
                done=enrich_missing(row,at=at)
                media=db.get(ItemMedia,(row.region,row.item_id))
                if done and row.fallback and media and not media.data:media.retry_after=at
                return done
    return False
