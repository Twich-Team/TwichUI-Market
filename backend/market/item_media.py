"""Independent bounded icon resolution; never forwards OAuth to artwork hosts."""
import hashlib,json,re,struct,time
from datetime import timedelta
from time import monotonic
from urllib.parse import urlsplit
from urllib.request import Request
from urllib.error import HTTPError
from sqlalchemy import JSON, cast, func,or_,select,text
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


def fetch_icon(url,*,community=False,foreverdb=False,factory=Session,region=None,item_id=None,attempt_id=None):
    if not icon_url(url,community=community,foreverdb=foreverdb):raise ValueError('Untrusted icon destination')
    def download():
        # No token, credentials, cookies or redirects, including on artwork hosts.
        try:response=opener.open(Request(url,headers={'User-Agent':'TwichUI-Market/0.1','Accept':'image/jpeg,image/png,image/webp'}),timeout=5)
        except HTTPError as error:response=error
        with response:
            meta={'status':response.status,'mime':response.headers.get_content_type(),
                'headers':{k:response.headers.get(k) for k in ('Retry-After','Date','X-RateLimit-Remaining','RateLimit-Remaining','RateLimit-Reset','RateLimit-Limit')}}
            return meta,response.read(MAX_ICON_BYTES+1) if response.status==200 else b''
    from .models import MetadataAttempt
    from .provider_rates import ProviderWaiting,reserved_request
    # Each image download is a separate invocation from media metadata. The
    # caller may supply the already committed missing-artwork reservation.
    if attempt_id is None:
        with factory.begin() as db:
            attempt=MetadataAttempt(provider='foreverdb' if foreverdb else 'thewowdb' if community else 'blizzard',
                region=region or 'us',item_id=item_id,kind='artwork',state='reserved',started_at=now())
            db.add(attempt);db.flush();attempt_id=attempt.id
    status=None;deferred=False
    try:
        if urlsplit(url).hostname in ('thewowdb.com','foreverdb.net'):
            meta,data=reserved_request(factory,'foreverdb' if foreverdb else 'thewowdb',download)
        else:
            # Public Blizzard artwork CDN is separate from its authenticated pool.
            meta,data=download()
        status=meta['status']
    except ProviderWaiting:
        deferred=True;raise
    finally:
        with factory.begin() as db:
            attempt=db.get(MetadataAttempt,attempt_id)
            attempt.state='deferred' if deferred else 'finished'
            attempt.completed_at,attempt.http_status=now(),status
            attempt.outcome='quota_deferred' if deferred else 'image_returned' if status==200 else 'missing' if status==404 else 'rate_limited' if status==429 else 'unavailable'
            attempt.returned_json,attempt.new_json='["icon"]' if status==200 else '[]','[]'
    if meta['status']!=200:raise ValueError('Icon HTTP status')
    mime=image_type(data)
    if meta['mime']!=mime:raise ValueError('Icon type mismatch')
    return data,mime


def resolve_media_once(factory=Session,client=None,*,at=None,image_fetch=fetch_icon,budget_guard=None,failure_guard=None):
    from .worker import BlizzardClient,retry_seconds
    from .models import MetadataProvider, MetadataAttempt
    from .provider_rates import reserve_budget,observe,cooldown,ProviderWaiting,rate_view
    at=at or now();client=client or BlizzardClient()
    candidate=None
    with factory.begin() as db:
        if db.bind.dialect.name=='postgresql' and not db.scalar(text('SELECT pg_try_advisory_xact_lock(7140235)')):return False
        from .metadata_recovery import ensure_providers
        ensure_providers(db)
        settings={p.provider:p for p in db.scalars(select(MetadataProvider))}
        ready={ident for ident,p in settings.items() if p.enabled and p.automatic and rate_view(p,at)['next_eligible_at']<=at}
        blizzard_ready='blizzard' in ready and getattr(client,'blocked_until',0)<=time.monotonic()
        artwork_ready=ready & {'foreverdb','thewowdb'}
        for market in db.scalars(select(Market).where(Market.enabled.is_(True),Market.verified.is_(True)).order_by(Market.id)):
            latest=db.scalar(select(Observation).where(Observation.market_id==market.id).order_by(Observation.retrieved_at.desc(),Observation.id.desc()).limit(1))
            if not latest:continue
            stat=SnapshotStatistic
            cached_reference=select(MetadataSource.item_id).where(MetadataSource.region==market.region,MetadataSource.item_id==stat.item_id,MetadataSource.locale=='en_US',MetadataSource.provider.in_(artwork_ready),cast(MetadataSource.source_json,JSON)['icon_url'].as_string().is_not(None)).exists()
            # Missing current artwork first; valid cached bytes refresh only when
            # their own interval is due. A committed short lease prevents races.
            item=db.scalar(select(stat.item_id).outerjoin(ItemMedia,(ItemMedia.region==market.region)&(ItemMedia.item_id==stat.item_id))
                .outerjoin(ItemMetadata,(ItemMetadata.region==market.region)&(ItemMetadata.item_id==stat.item_id))
                .where(stat.snapshot_id==latest.snapshot_id,or_(ItemMedia.item_id.is_(None),ItemMedia.retry_after.is_(None),ItemMedia.retry_after<=at),True if blizzard_ready else ItemMedia.data.is_(None)&cached_reference)
                .group_by(stat.item_id,ItemMetadata.requested_at,ItemMedia.asset_hash).order_by(ItemMedia.asset_hash.is_not(None),ItemMetadata.requested_at.desc().nulls_last(),stat.item_id).limit(1))
            if item is not None:candidate=(market.region,item);break
        if candidate is None:return False
        region,item=candidate
        row=db.get(ItemMedia,(region,item))
        had_icon=bool(row and row.data)
        used=db.scalar(select(func.coalesce(func.sum(ItemMedia.byte_count),0)))
        if not had_icon and used>=MAX_CACHE_BYTES:
            if row is None:row=ItemMedia(region=region,item_id=item);db.add(row)
            row.status='budget';row.retry_after=at+timedelta(hours=1)
            return True
        cached=None
        # A valid primary icon is never replaced by a supplemental image.
        if not had_icon:
            for ident in ('foreverdb','thewowdb'):
                provider=db.get(MetadataProvider,ident)
                src=db.get(MetadataSource,(region,item,'en_US',ident))
                origin=json.loads(src.source_json) if src and src.source_json else {}
                if provider and ident in artwork_ready and icon_url(origin.get('icon_url'),foreverdb=ident=='foreverdb',community=ident=='thewowdb'):
                    cached=(ident,origin);break
        if not cached:
            if not blizzard_ready:return False
            if budget_guard:
                if not budget_guard(db,at):return False
            else:
                provider=db.get(MetadataProvider,'blizzard',with_for_update=True)
                if not provider.enabled or reserve_budget(provider,at):return False
        if row is None:row=ItemMedia(region=region,item_id=item);db.add(row)
        row.retry_after=at+timedelta(seconds=120)
        attempt=MetadataAttempt(provider=cached[0] if cached else 'blizzard',region=region,item_id=item,
            kind='artwork' if cached else 'media',started_at=at,state='reserved',
            decision_json=json.dumps({'policy_version':1,'priority':5 if had_icon else 2,
                'explanation':'Stored verified source artwork reference; metadata lookup avoided.' if cached else 'Current item artwork missing or its independent refresh is due.'}))
        db.add(attempt);db.flush();attempt_id=attempt.id
    # External I/O remains bounded; no SQL transaction holds the global image
    # lock. The committed retry timestamp owns this item across worker restarts.
    data,mime,origin,status,headers=None,None,None,None,{}
    started=monotonic();failure=None;sent=False
    try:
        if cached:
            ident,origin=cached;url=origin['icon_url']
            # fetch_icon owns the artwork provider's shared reservation. A quota
            # deferral is not an outbound request.
            sent=True
            if image_fetch is fetch_icon:data,mime=fetch_icon(url,foreverdb=ident=='foreverdb',community=ident=='thewowdb',factory=factory,region=region,item_id=item,attempt_id=attempt_id)
            else:data,mime=image_fetch(url)
            namespace=origin.get('build');metadata_hash=origin.get('payload_hash');status=200
        else:
            sent=True
            meta,body=client.fetch_item_media(region,item);status,headers=meta['status'],meta.get('headers',{})
            if status!=200:raise ValueError('Media unavailable')
            if len(body)>262144:raise ValueError('Media metadata limit')
            payload=json.loads(body)
            if payload.get('id')!=item:raise ValueError('Media identity mismatch')
            namespace=headers.get('Battlenet-Namespace',f'static-forever-{region}')
            if not valid_namespace(namespace,region):raise ValueError('Media edition mismatch')
            assets=payload.get('assets')
            if not isinstance(assets,list) or len(assets)>20:raise ValueError('Invalid media assets')
            url=next((a.get('value') for a in assets if isinstance(a,dict) and a.get('key')=='icon'),None)
            if not icon_url(url):raise ValueError('Untrusted icon URL')
            if image_fetch is fetch_icon:data,mime=fetch_icon(url,factory=factory,region=region,item_id=item)
            else:data,mime=image_fetch(url)
            ident,metadata_hash='blizzard',hashlib.sha256(body).hexdigest()
        if image_type(data)!=mime:raise ValueError('Icon cache/type limit')
    except ProviderWaiting as error:
        sent=False;failure='quota_deferred';waiting=error.until
    except Exception:
        failure='missing' if status==404 else 'rate_limited' if status==429 else 'unavailable'
    with factory.begin() as db:
        row=db.get(ItemMedia,(region,item),with_for_update=True)
        attempt=db.get(MetadataAttempt,attempt_id)
        received=at+timedelta(seconds=max(0,monotonic()-started))
        if not cached:
            provider=db.get(MetadataProvider,'blizzard',with_for_update=True)
            observe(provider,status,headers,received,reserved_at=at)
            if status in (401,402,403,429,503):cooldown(provider,status,headers,received)
        attempt.state,attempt.completed_at,attempt.http_status='finished' if sent else 'deferred',received,status
        row.checked_at,row.http_status=at,status
        if data is not None and not failure:
            used=db.scalar(select(func.coalesce(func.sum(ItemMedia.byte_count),0)))
            if used-(row.byte_count or 0)+len(data)>MAX_CACHE_BYTES:failure='cache_budget'
        if failure:
            # Both bytes and availability survive a failed refresh.
            row.status='available' if row.data else 'missing' if status==404 else 'error'
            row.retry_after=waiting if failure=='quota_deferred' and waiting else at+timedelta(seconds=604800 if status==404 else max(900,retry_seconds(headers.get('Retry-After'),at)))
            if failure_guard and not cached:failure_guard(db,status,headers,at)
            attempt.outcome=failure;attempt.new_json='[]';attempt.returned_json='[]'
        else:
            row.status,row.source,row.namespace='available',ident,namespace
            row.source_url,row.metadata_hash=url,metadata_hash
            row.asset_hash,row.data,row.byte_count=hashlib.sha256(data).hexdigest(),data,len(data)
            row.content_type,row.http_status,row.resolved_at=mime,200,at
            row.retry_after=at+timedelta(days=30 if ident=='blizzard' else 7)
            attempt.outcome='already_known' if had_icon else 'icon_recovered'
            attempt.new_json='[]' if had_icon else '["icon"]';attempt.returned_json='["icon"]'
        return True
