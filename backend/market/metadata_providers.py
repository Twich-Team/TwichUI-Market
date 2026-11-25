"""Fixed, documented provider endpoints. No market prices or remote executable content."""
from dataclasses import dataclass
import hashlib
import json
import re
from urllib.parse import urlencode, urlsplit
from .db import now
from .item_attributes import QUALITIES, text
from .probe import request


class IdentityMismatch(ValueError):
    """Item, edition or client-build evidence disagrees with the requested record."""


@dataclass(frozen=True)
class ProviderSpec:
    label: str
    key_required: bool
    hourly_limit: int
    daily_limit: int
    interval: int
    refresh_seconds: int
    url: str
    note: str


PROVIDERS = {
    'blizzard': ProviderSpec('Blizzard Forever', True, 240, 2000, 15, 2592000,
        'https://develop.battle.net', 'Authoritative Forever base-item fields. OAuth uses existing server secrets.'),
    'everloot': ProviderSpec('Everloot', False, 20, 100, 180, 3600,
        'https://everloot.app', 'Forever consensus names with attribution. Bulk client attributes are unconfirmed and do not supply names.'),
    'foreverdb': ProviderSpec('ForeverDB', True, 60, 500, 3, 86400,
        'https://foreverdb.net', 'Authenticated Forever client item details and source-qualified recipes, vendors and sets. Key scope and website verification require account confirmation.'),
    'thewowdb': ProviderSpec('TheWoWDB', False, 60, 500, 60, 3600,
        'https://thewowdb.com', 'Optional Forever beta data. Access restrictions are never bypassed.'),
}


def plain(value, limit=255):
    result = text(value, limit)
    if result is None or '<' in result or '>' in result or any(ord(c) < 32 for c in result):
        raise ValueError('Invalid plain metadata text')
    return result


def build_identity(build):
    # Accept only Forever's documented 1.60 client family, never Retail/Classic.
    if not isinstance(build, str) or not re.fullmatch(r'(?:wow_classic(?:_beta)?-)?1\.60\.[0-9]+[._][0-9]+', build):
        raise IdentityMismatch('Unverified Forever build')
    return build


def safe_link(url, host, path=None):
    if not isinstance(url, str) or len(url) > 512: raise ValueError('Invalid source link')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname != host or parts.username or parts.password or parts.port not in (None, 443) or parts.query or parts.fragment or (path and parts.path != path):
        raise ValueError('Untrusted source link')
    return url


def source(provider, body, *, build=None, confidence='supplemental', attribution=None, at=None, url=None):
    return {'provider': provider, 'edition': 'forever', 'build': build, 'locale': 'en_US',
        'confidence': confidence, 'attribution': attribution,
        'url': url or PROVIDERS[provider].url, 'retrieved_at': (at or now()).isoformat(),
        'payload_hash': hashlib.sha256(body).hexdigest()}


def decode(body):
    if len(body) > 1048576: raise ValueError('Metadata response too large')
    value = json.loads(body)
    if not isinstance(value, dict) or value.get('unreachable') or value.get('ok') is False:
        raise ValueError('Unavailable provider response')
    return value


def everloot_attribution(value):
    if not isinstance(value, dict) or value.get('licence') != 'CC BY-SA 4.0':
        raise ValueError('Missing Everloot licence')
    return {'text': plain(value.get('credit')), 'url': safe_link(value.get('source'), 'everloot.app'),
        'license': 'CC BY-SA 4.0', 'license_url': 'https://creativecommons.org/licenses/by-sa/4.0/'}


def parse_everloot(body, item_id, *, at=None):
    value = decode(body)
    if value.get('ok') is not True or value.get('type') != 'item' or type(value.get('id')) is not int or value['id'] != item_id:
        raise IdentityMismatch('Everloot item identity mismatch')
    credit = everloot_attribution(value.get('attribution'))
    safe_link(value.get('url'), 'everloot.app')
    title = plain(value.get('title'))
    fields = {}
    # The documented placeholder is explicitly not a recovered item name.
    if not re.fullmatch(r'Item\s*#?\s*[0-9]+', title, re.I): fields['name'] = title
    game = value.get('gameData')
    build = build_identity(game.get('build')) if isinstance(game, dict) else None
    # Tooltip strings mix client/game and player layers. Store only the agreed name;
    # use the separately labelled /items contract for structured base attributes.
    src = source('everloot', body, build=build, confidence='player_consensus', attribution=credit, at=at, url=value['url'])
    return fields, src


def parse_everloot_page(body, *, at=None):
    value = decode(body)
    rows = value.get('items')
    if not isinstance(rows, list) or len(rows) > 5000: raise ValueError('Invalid Everloot page')
    game = value.get('gameData')
    if not isinstance(game, dict): raise ValueError('Missing game build')
    build = build_identity(game.get('build'))
    credit = {'text': plain(game.get('credit')), 'url': 'https://everloot.app', 'notice': 'Found in game files, unconfirmed'}
    # Large authenticated pages share one envelope/hash; avoid hashing up to
    # 1 MiB once per record when an administrator permits 5,000-row pages.
    origin = source('everloot', body, build=build, confidence='game_file_unconfirmed', attribution=credit, at=at)
    records = []
    seen = set()
    for row in rows:
        ident = row.get('itemId') if isinstance(row, dict) else None
        if type(ident) is not int or not 1 <= ident <= 2**31-1 or ident in seen: raise ValueError('Invalid/duplicate bulk item ID')
        seen.add(ident)
        fields = {}
        for key in ('class', 'subclass', 'slot'):
            entry = row.get(key)
            if entry is not None:
                if not isinstance(entry, dict): raise ValueError('Invalid item category')
                fields[key] = plain(entry.get('label') or entry.get('name'))
        quality = row.get('quality')
        if quality is not None:
            if not isinstance(quality, dict): raise ValueError('Invalid item quality')
            quality = plain(quality.get('name')).upper()
            if quality not in QUALITIES: raise ValueError('Invalid item quality')
            fields['quality'] = quality
        records.append((ident, fields, origin.copy()))
    offset, limit, total = (value.get(k) for k in ('offset', 'limit', 'total'))
    if any(type(n) is not int or n < 0 for n in (offset, limit, total)) or not 1 <= limit <= 5000 or len(rows) > limit or offset+len(rows)>total:
        raise ValueError('Invalid pagination')
    next_offset = None
    if value.get('next') is not None:
        # Never follow a provider URL. Reconstruct the next fixed endpoint ourselves.
        next_offset = offset + limit
        if not rows or next_offset <= offset or next_offset >= total: raise ValueError('Nonadvancing page')
    return records, next_offset


def parse_foreverdb(body, item_id, *, at=None):
    from .foreverdb import item
    return item(body, item_id, at=at)


def parse_thewowdb(body, item_id, *, at=None):
    from .community_metadata import parse_community
    try: value = parse_community(body, item_id, at=at)
    except ValueError as error:
        if str(error) in ('Community identity/edition mismatch','Unrecognized community build'): raise IdentityMismatch('TheWoWDB identity or build rejected') from None
        raise
    build_identity(value['source']['build'])
    attrs = value['attributes']
    fields = {k: v for k, v in attrs.items() if k != 'scope' and v is not None and v != []}
    fields['name'] = value['name']
    origin=source('thewowdb', body, build=value['source']['build'], confidence='community_beta',
        attribution=value['source']['attribution'], at=at, url=value['source']['url'])
    from .item_media import icon_url
    if icon_url(value.get('icon_url'),community=True):origin['icon_url']=value['icon_url']
    return fields,origin


def fetch(provider, item_id, *, credential=None, etag=None, offset=None, validate=False, transport=request, client=None, region='us', page_size=500, resource=None):
    if provider not in PROVIDERS or type(item_id) is not int or not 1 <= item_id <= 2**31-1: raise ValueError('Invalid provider identity')
    if provider == 'blizzard':
        from .worker import BlizzardClient
        return (client or BlizzardClient()).fetch_item(region, item_id)
    if provider == 'everloot':
        if type(page_size) is not int or not 1 <= page_size <= (5000 if credential else 500): raise ValueError('Invalid provider page size')
        url = 'https://everloot.app/api/items?' + urlencode({'offset': offset or 0, 'limit': 1 if validate else page_size}) if validate or offset is not None else f'https://everloot.app/api/tooltip/item/{item_id}'
    elif provider == 'foreverdb':
        if not credential: raise ValueError('Provider key required')
        if resource is not None:
            from .foreverdb import RELATED
            from .merchants_favor import RESOURCE
            if validate or (resource != RESOURCE and not RELATED.fullmatch(resource)):
                raise ValueError('Invalid ForeverDB resource')
            if type(offset) is not int or not 0 <= offset <= 100000:
                raise ValueError('Invalid resource offset')
            url = 'https://foreverdb.net/api/v1/' + resource
            if resource == RESOURCE:
                if offset != 0: raise ValueError('Merchant’s Favor catalogue is unpaginated')
            else:
                url += '?' + urlencode({'limit':20,'offset':offset})
        else:
            url = 'https://foreverdb.net/api/v1/meta' if validate else f'https://foreverdb.net/api/v1/items/{item_id}'
    else:
        url = f'https://thewowdb.com/api/v1/forever/item/{item_id}'
    return transport(url, authorization=f'Bearer {credential}' if credential else None,
        conditional={'If-None-Match': etag} if etag else None, timeout=8, max_bytes=1048576)


PARSERS = {'everloot': parse_everloot, 'foreverdb': parse_foreverdb, 'thewowdb': parse_thewowdb}
