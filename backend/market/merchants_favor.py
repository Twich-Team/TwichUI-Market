"""ForeverDB's exact Merchant's Favor catalogue and its last validated cache."""
import json
import os
import re

from .foreverdb import envelope, integer
from .item_attributes import QUALITIES
from .item_media import icon_url
from .metadata_providers import IdentityMismatch, plain, safe_link
from .models import MetadataResource

RESOURCE = 'merchants-favor'
CACHE_KEY = ('us', RESOURCE, 0)
DEFAULT_REFRESH_SECONDS = 86400
REFRESH_ENV = 'FOREVERDB_MERCHANTS_FAVOR_REFRESH_SECONDS'
TIERS = frozenset(('apprentice', 'journeyman', 'expert', 'artisan', 'elite'))
MAX_CRATES = 100
MAX_CHOICES = 30
MAX_CATALOGUE_ITEMS = 500
MAPPING_VERSION = 1


def records(value, limit):
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(row, dict) for row in value):
        raise ValueError('Invalid Merchant’s Favor list')
    return value


def item_record(row):
    item_id = integer(row.get('itemId'), minimum=1)
    safe_link(row.get('url'), 'foreverdb.net', f'/item/{item_id}')
    quality = plain(row['quality']).upper() if row.get('quality') is not None else None
    if quality is not None and quality not in QUALITIES:
        raise ValueError('Invalid Merchant’s Favor item quality')
    icon = row.get('icon')
    if icon is not None and (not isinstance(icon, str) or not icon.startswith('https://foreverdb.net/')
                             or not icon_url(icon, foreverdb=True)):
        raise ValueError('Untrusted Merchant’s Favor artwork')
    return {'item_id': item_id, 'name': plain(row.get('name')), 'quality': quality, 'icon_url': icon}


def crate_record(row, tier_vocabulary):
    crate = item_record(row)
    if not crate['name'].startswith('Waylaid Crate: '):
        raise IdentityMismatch('Unexpected Merchant’s Favor crate identity')
    words = re.findall(r'[a-z]+', crate['name'].removeprefix('Waylaid Crate: ').lower())
    tiers = tier_vocabulary.intersection(words)
    tier = next(iter(tiers)) if len(tiers) == 1 else None
    level = row.get('levelToUse')
    if level is not None:
        level = integer(level, maximum=100)
    choices = records(row['bundles'], MAX_CHOICES)
    bundles = []
    seen = set()
    for choice in choices:
        material = item_record(choice)
        ident = material['item_id']
        if ident in seen:
            raise ValueError('Duplicate Merchant’s Favor bundle item ID')
        seen.add(ident)
        material['quantity'] = integer(choice.get('count'), minimum=1, maximum=10000)
        bundles.append({'bundle_id': ident, 'materials': [material]})
    # The endpoint specifies the transformation generically, but several sealed
    # crate items share each tier name. None can be assigned to a specific crate.
    unavailable_reason = 'unsupported_tier' if tier is None else 'no_supported_bundles' if not bundles else None
    return {**crate, 'tier': tier, 'tier_source': 'provider_item_name' if tier else None,
            'required_level': level, 'sealed_item_id': None,
            'reward_unavailable_reason': None if crate['quality'] == 'COMMON' else 'unverified_reward_quality',
            'unavailable_reason': unavailable_reason, 'bundles': bundles}


def parse_catalogue(body, *, at=None):
    row, _, origin = envelope(body, at=at, resource=RESOURCE)
    if not isinstance(row, dict):
        raise ValueError('Invalid Merchant’s Favor catalogue')
    currency = row.get('currency')
    if not isinstance(currency, dict) or type(currency.get('id')) is not int or currency['id'] != 3402:
        raise IdentityMismatch('Unexpected Merchant’s Favor currency')
    safe_link(row.get('url'), 'foreverdb.net', '/merchants-favor')
    raw_crates = records(row.get('crates'), MAX_CRATES)
    counts = row.get('counts')
    if not isinstance(counts, dict) or integer(counts.get('crates')) != len(raw_crates) or not raw_crates:
        raise ValueError('Incomplete Merchant’s Favor catalogue')
    sealed = [item_record(crate) for crate in records(row.get('sealedCrates'), MAX_CRATES)]
    if 'sealedCrates' in counts and integer(counts['sealedCrates']) != len(sealed):
        raise ValueError('Incomplete sealed crate catalogue')
    # A sealed item's exact name may identify a new tier label, but same-name
    # items cannot establish which sealed item comes from a given crate.
    sealed_names = (re.fullmatch(r'Sealed ([A-Z][a-z]{1,46}) Crate', crate['name']) for crate in sealed)
    tier_vocabulary = TIERS | {match[1].lower() for match in sealed_names if match}
    crates = [crate_record(crate, tier_vocabulary) for crate in raw_crates]
    crate_ids = [crate['item_id'] for crate in crates + sealed]
    if len(set(crate_ids)) != len(crate_ids):
        raise ValueError('Duplicate Merchant’s Favor crate item ID')
    material_ids = {bundle['bundle_id'] for crate in crates for bundle in crate['bundles']}
    if material_ids.intersection(crate_ids):
        raise ValueError('Merchant’s Favor crate ID used as a fill material')
    item_count = len(sealed) + len(crates) + sum(len(crate['bundles']) for crate in crates)
    if item_count > MAX_CATALOGUE_ITEMS:
        raise ValueError('Merchant’s Favor catalogue item limit')
    transformation = row.get('howToEarn')
    if not isinstance(transformation, list) or len(transformation) > 10:
        raise ValueError('Invalid Merchant’s Favor transformation evidence')
    favour = row.get('favorPerCrate')
    if favour is not None:
        # No response-backed per-tier/item reward mapping has been seen.
        raise ValueError('Unsupported Merchant’s Favor reward structure')
    note = row.get('favorPerCrateNote')
    origin.update(mapping_version=MAPPING_VERSION, confidence='foreverdb_catalogue',
                  catalogue_url='https://foreverdb.net/merchants-favor')
    return {
        'schema_version': MAPPING_VERSION,
        'currency': {'id': currency['id'], 'name': plain(currency.get('name'))},
        'crates': crates,
        'sealed_crates': sealed,
        'transformation_evidence': [plain(line, limit=512) for line in transformation],
        'upstream_reward_note': plain(note, limit=512) if note is not None else None,
    }, origin


def metadata_item_ids(catalogue):
    """Prioritize exact crate and ingredient identities in observed order."""
    crates = catalogue['crates']
    choices = (material['item_id'] for crate in crates for bundle in crate['bundles']
               for material in bundle['materials'])
    return list(dict.fromkeys([*(crate['item_id'] for crate in crates), *choices]))


def refresh_seconds():
    """Use the daily default unless an explicit, bounded cadence is configured."""
    try:
        value = int(os.getenv(REFRESH_ENV, str(DEFAULT_REFRESH_SECONDS)))
    except ValueError:
        return DEFAULT_REFRESH_SECONDS
    return value if value == 0 or 3600 <= value <= 604800 else DEFAULT_REFRESH_SECONDS


def read_catalogue(db):
    """Return latest refresh diagnostics alongside the independently retained payload."""
    row = db.get(MetadataResource, CACHE_KEY)
    return row, json.loads(row.fields_json) if row and row.fields_json else None
