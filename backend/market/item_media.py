"""Independent bounded icon resolution; never forwards OAuth to artwork hosts."""
import hashlib,json,re,struct,time
from datetime import timedelta
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.error import HTTPError
from sqlalchemy import func,or_,select,text
from .db import Session,now
from .models import ItemMedia,ItemMetadata,MetadataSource,Market,Observation,SnapshotStatistic
from .probe import opener
from .item_attributes import valid_namespace

MAX_ICON_BYTES=32768
MAX_CACHE_BYTES=32*1024*1024


def icon_url(value,*,community=False,foreverdb=False):
    if not isinstance(value,str) or len(value)>512:return False
    url=urlsplit(value)
    if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or url.query or url.fragment:return False
    if url.hostname=='render.worldofwarcraft.com':
        return re.fullmatch(r'/(?:forever-)?(?:us|eu|kr|tw)/icons/56/[A-Za-z0-9_-]+\.(?:jpg|png)',url.path) is not None
    if foreverdb and url.hostname=='foreverdb.net':return re.fullmatch(r'/icons/[0-9]+\.webp',url.path) is not None
    return community and url.hostname=='thewowdb.com' and re.fullmatch(r'/assets/icons/[A-Za-z0-9_-]+\.(?:jpg|png)',url.path) is not None


def image_type(data):
    if not 24<=len(data)<=MAX_ICON_BYTES:raise ValueError('Icon byte limit')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        if len(data)<45 or data[-12:]!=b'\x00\x00\x00\x00IEND\xaeB\x60\x82' or data[12:16]!=b'IHDR':raise ValueError('PNG dimensions unavailable')
        width,height=struct.unpack('>II',data[16:24])
        if not 1<=width<=256 or not 1<=height<=256:raise ValueError('Icon dimensions')
        return 'image/png'
    if len(data)>=30 and data[:4]==b'RIFF' and data[8:12]==b'WEBP' and int.from_bytes(data[4:8],'little')==len(data)-8:
        chunk=data[12:16]
        if chunk==b'VP8L' and data[20]==0x2f:
            bits=int.from_bytes(data[21:25],'little');width=1+(bits&0x3fff);height=1+((bits>>14)&0x3fff)
        elif chunk==b'VP8 ' and data[23:26]==b'\x9d\x01\x2a':
            width=int.from_bytes(data[26:28],'little')&0x3fff;height=int.from_bytes(data[28:30],'little')&0x3fff
        elif chunk==b'VP8X' and not data[20]&2:
            width=1+int.from_bytes(data[24:27],'little');height=1+int.from_bytes(data[27:30],'little')
        else:raise ValueError('Unsupported animated/corrupt WebP')
        if not 1<=width<=256 or not 1<=height<=256:raise ValueError('Icon dimensions')
        return 'image/webp'
    if data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9'):
        position=2
        while position+4<len(data):
            if data[position]!=255:break
            marker=data[position+1];position+=2
            if marker in (0xd8,0xd9) or 0xd0<=marker<=0xd7:continue
            size=int.from_bytes(data[position:position+2],'big')
            if size<2 or position+size>len(data):break
            if marker in (0xc0,0xc1,0xc2):
                if size<8:break
                height,width=struct.unpack('>HH',data[position+3:position+7])
                if not 1<=width<=256 or not 1<=height<=256:raise ValueError('Icon dimensions')
                return 'image/jpeg'
            position+=size
    raise ValueError('Unsupported/corrupt icon')


def fetch_icon(url,*,community=False,foreverdb=False,factory=Session):
    if not icon_url(url,community=community,foreverdb=foreverdb):raise ValueError('Untrusted icon destination')
    def download():
        # No token, credentials, cookies or redirects, including on artwork hosts.
        try:response=opener.open(Request(url,headers={'User-Agent':'TwichUI-Market/0.1','Accept':'image/jpeg,image/png,image/webp'}),timeout=5)
        except HTTPError as error:response=error
        with response:
            meta={'status':response.status,'mime':response.headers.get_content_type(),
                'headers':{k:response.headers.get(k) for k in ('Retry-After','Date','X-RateLimit-Remaining','RateLimit-Remaining','RateLimit-Reset','RateLimit-Limit')}}
            return meta,response.read(MAX_ICON_BYTES+1) if response.status==200 else b''
    if urlsplit(url).hostname in ('thewowdb.com','foreverdb.net'):
        from .provider_rates import reserved_request
        meta,data=reserved_request(factory,'foreverdb' if foreverdb else 'thewowdb',download)
    else:
        # Public Blizzard artwork CDN is separate from its authenticated API pool.
        meta,data=download()
    if meta['status']!=200:raise ValueError('Icon HTTP status')
    mime=image_type(data)
    if meta['mime']!=mime:raise ValueError('Icon type mismatch')
    return data,mime


def resolve_media_once(factory=Session,client=None,*,at=None,image_fetch=fetch_icon,budget_guard=None,failure_guard=None):
    from .worker import BlizzardClient,retry_seconds
    at=at or now();client=client or BlizzardClient()
    if getattr(client,'blocked_until',0)>time.monotonic():return False
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140235)')):return False
        candidate=None
        for market in db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)):
            latest=db.scalar(select(Observation).where(Observation.market_id==market.id).order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
            if not latest:continue
            stat=SnapshotStatistic
            item=db.scalar(select(stat.item_id).outerjoin(ItemMedia,(ItemMedia.region==market.region)&(ItemMedia.item_id==stat.item_id))
                .outerjoin(ItemMetadata,(ItemMetadata.region==market.region)&(ItemMetadata.item_id==stat.item_id))
                .where(stat.snapshot_id==latest.snapshot_id,or_(ItemMedia.item_id.is_(None),ItemMedia.retry_after.is_(None),ItemMedia.retry_after<=at))
                .group_by(stat.item_id,ItemMetadata.requested_at).order_by(ItemMetadata.requested_at.desc().nulls_last(),stat.item_id).limit(1))
            if item is not None:candidate=(market.region,item);break
        if candidate is None:return False
        region,item=candidate
        if budget_guard:
            if not budget_guard(db,at):return False
        else:
            from .metadata_recovery import ensure_providers
            from .models import MetadataProvider
            from .provider_rates import reserve_budget
            ensure_providers(db)
            provider=db.get(MetadataProvider,'blizzard',with_for_update=True)
            if not provider.enabled or reserve_budget(provider,at):return False
    # Quota is committed before any I/O, including artwork. Crashes remain charged.
    with factory.begin() as db:
        row=db.get(ItemMedia,(region,item))
        if row is None:row=ItemMedia(region=region,item_id=item);db.add(row)
        row.checked_at=at
        try:
            used=db.scalar(select(func.coalesce(func.sum(ItemMedia.byte_count),0)))
            if used>=MAX_CACHE_BYTES:
                row.status='budget';row.retry_after=at+timedelta(hours=1);return True
            started=monotonic()
            meta,body=client.fetch_item_media(region,item)
            from .models import MetadataProvider
            from .provider_rates import observe,cooldown
            provider=db.get(MetadataProvider,'blizzard',with_for_update=True)
            if provider:
                received=at+timedelta(seconds=max(0,monotonic()-started))
                observe(provider,meta['status'],meta.get('headers',{}),received,reserved_at=at)
                if meta['status'] in (401,402,403,429,503):cooldown(provider,meta['status'],meta.get('headers',{}),received)
            row.http_status=meta['status']
            if meta['status']!=200:
                if failure_guard:failure_guard(db,meta['status'],meta['headers'],at)
                if meta['status']==404:
                    primary=db.get(ItemMetadata,(region,item))
                    fallback=json.loads(primary.fallback) if primary and primary.fallback else None
                    supplemental=db.get(MetadataSource,(region,item,'en_US','thewowdb'))
                    if supplemental and supplemental.source_json:
                        origin=json.loads(supplemental.source_json)
                        fallback={'icon_url':origin.get('icon_url'),'source':origin}
                    url=fallback.get('icon_url') if fallback else None
                    from .models import MetadataProvider
                    settings=db.get(MetadataProvider,'thewowdb')
                    if fallback and (settings is None or settings.enabled) and icon_url(url,community=True):
                        data,mime=fetch_icon(url,community=True,factory=factory)
                        if used-(row.byte_count or 0)+len(data)>MAX_CACHE_BYTES:raise ValueError('Icon budget')
                        row.status,row.source,row.namespace='available','thewowdb',fallback['source']['build']
                        row.source_url,row.metadata_hash=url,fallback['source']['payload_hash']
                        row.asset_hash,row.data,row.byte_count=hashlib.sha256(data).hexdigest(),data,len(data)
                        row.content_type,row.http_status,row.resolved_at=mime,200,at
                        row.retry_after=at+timedelta(days=7)
                        return True
                if meta['status']==404:
                    supplemental=db.get(MetadataSource,(region,item,'en_US','foreverdb'))
                    origin=json.loads(supplemental.source_json) if supplemental and supplemental.source_json else {}
                    url=origin.get('icon_url')
                    if icon_url(url,foreverdb=True):
                        data,mime=fetch_icon(url,foreverdb=True,factory=factory)
                        if used-(row.byte_count or 0)+len(data)>MAX_CACHE_BYTES:raise ValueError('Icon budget')
                        row.status,row.source,row.namespace='available','foreverdb',origin['build']
                        row.source_url,row.metadata_hash=url,origin['payload_hash']
                        row.asset_hash,row.data,row.byte_count=hashlib.sha256(data).hexdigest(),data,len(data)
                        row.content_type,row.http_status,row.resolved_at=mime,200,at
                        row.retry_after=at+timedelta(days=7)
                        return True
                row.status='missing' if meta['status']==404 else 'error'
                row.retry_after=at+timedelta(seconds=604800 if meta['status']==404 else max(900,retry_seconds(meta['headers'].get('Retry-After'),at)))
                return True
            if len(body)>262144:raise ValueError('Media metadata limit')
            payload=json.loads(body)
            if payload.get('id')!=item:raise ValueError('Media identity mismatch')
            namespace=meta['headers'].get('Battlenet-Namespace',f'static-forever-{region}')
            if not valid_namespace(namespace,region):raise ValueError('Media edition mismatch')
            assets=payload.get('assets')
            if not isinstance(assets,list) or len(assets)>20:raise ValueError('Invalid media assets')
            url=next((asset.get('value') for asset in assets if isinstance(asset,dict) and asset.get('key')=='icon'),None)
            if not icon_url(url):raise ValueError('Untrusted icon URL')
            data,mime=image_fetch(url)
            if image_type(data)!=mime or used-(row.byte_count or 0)+len(data)>MAX_CACHE_BYTES:raise ValueError('Icon cache/type limit')
            row.status,row.source,row.namespace='available','blizzard',namespace
            row.source_url,row.metadata_hash=url,hashlib.sha256(body).hexdigest()
            row.asset_hash,row.data,row.byte_count=hashlib.sha256(data).hexdigest(),data,len(data)
            row.content_type,row.retry_after=mime,at+timedelta(days=30)
            row.resolved_at=at
        except Exception:
            # Preserve prior good icon; transport details can include sensitive headers.
            row.status='error';row.retry_after=at+timedelta(minutes=15)
        return True
