"""Independent bounded icon resolution; never forwards OAuth to artwork hosts."""
import hashlib,json,re,struct,time
from datetime import timedelta
from urllib.parse import urlsplit
from urllib.request import Request
from sqlalchemy import func,or_,select,text
from .db import Session,now
from .models import ItemMedia,ItemMetadata,Market,Observation,SnapshotStatistic
from .probe import opener
from .item_attributes import valid_namespace

MAX_ICON_BYTES=32768
MAX_CACHE_BYTES=32*1024*1024


def icon_url(value,*,community=False):
    if not isinstance(value,str) or len(value)>512:return False
    url=urlsplit(value)
    if url.scheme!='https' or url.username or url.password or url.port not in (None,443) or url.query or url.fragment:return False
    if url.hostname=='render.worldofwarcraft.com':
        return re.fullmatch(r'/(?:forever-)?(?:us|eu|kr|tw)/icons/56/[A-Za-z0-9_-]+\.(?:jpg|png)',url.path) is not None
    return community and url.hostname=='thewowdb.com' and re.fullmatch(r'/assets/icons/[A-Za-z0-9_-]+\.(?:jpg|png)',url.path) is not None


def image_type(data):
    if not 24<=len(data)<=MAX_ICON_BYTES:raise ValueError('Icon byte limit')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        if len(data)<45 or data[-12:]!=b'\x00\x00\x00\x00IEND\xaeB\x60\x82' or data[12:16]!=b'IHDR':raise ValueError('PNG dimensions unavailable')
        width,height=struct.unpack('>II',data[16:24])
        if not 1<=width<=256 or not 1<=height<=256:raise ValueError('Icon dimensions')
        return 'image/png'
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


def fetch_icon(url,*,community=False):
    if not icon_url(url,community=community):raise ValueError('Untrusted icon destination')
    # No token, credentials, cookies or redirects; separate bounded public-image request.
    with opener.open(Request(url,headers={'User-Agent':'TwichUI-Market/0.1','Accept':'image/jpeg,image/png'}),timeout=5) as response:
        if response.status!=200:raise ValueError('Icon HTTP status')
        data=response.read(MAX_ICON_BYTES+1)
        mime=image_type(data)
        if response.headers.get_content_type()!=mime:raise ValueError('Icon type mismatch')
        return data,mime


def resolve_media_once(factory=Session,client=None,*,at=None,image_fetch=fetch_icon):
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
        row=db.get(ItemMedia,(region,item))
        if row is None:row=ItemMedia(region=region,item_id=item);db.add(row)
        row.checked_at=at
        try:
            used=db.scalar(select(func.coalesce(func.sum(ItemMedia.byte_count),0)))
            if used>=MAX_CACHE_BYTES:
                row.status='budget';row.retry_after=at+timedelta(hours=1);return True
            meta,body=client.fetch_item_media(region,item)
            row.http_status=meta['status']
            if meta['status']!=200:
                if meta['status']==404:
                    primary=db.get(ItemMetadata,(region,item))
                    fallback=json.loads(primary.fallback) if primary and primary.fallback else None
                    url=fallback.get('icon_url') if fallback else None
                    if fallback and icon_url(url,community=True):
                        data,mime=fetch_icon(url,community=True)
                        if used-(row.byte_count or 0)+len(data)>MAX_CACHE_BYTES:raise ValueError('Icon budget')
                        row.status,row.source,row.namespace='available','thewowdb',fallback['source']['build']
                        row.source_url,row.metadata_hash=url,fallback['source']['payload_hash']
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
