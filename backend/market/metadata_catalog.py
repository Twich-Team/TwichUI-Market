"""Versioned local normalized source data and deterministic field-level projection."""
import json
from datetime import timedelta
from sqlalchemy import select
from .db import now
from .models import ItemMetadata, MetadataSource, MetadataVersion
from .metadata_providers import PROVIDERS

PRECEDENCE = {'blizzard': 0, 'everloot': 1, 'foreverdb': 2, 'thewowdb': 3}
FIELDS = {'name', 'quality', 'class', 'subclass', 'slot', 'level', 'required_level', 'binding', 'vendor_sell', 'lines', 'icon_reference'}


def get_source(db, region, item_id, provider, locale='en_US'):
    row = db.get(MetadataSource, (region, item_id, locale, provider))
    if row is None:
        row = MetadataSource(region=region, item_id=item_id, locale=locale, provider=provider)
        db.add(row); db.flush()
    return row


def store_source(db, region, item_id, provider, fields, source, *, at=None, etag=None):
    at = at or now()
    if provider not in PRECEDENCE or source.get('provider') != provider or source.get('edition') != 'forever' or source.get('locale') != 'en_US':
        raise ValueError('Invalid catalog source identity')
    if region not in ('us', 'eu', 'kr', 'tw') or type(item_id) is not int or not 1 <= item_id <= 2**31-1:
        raise ValueError('Invalid catalog item')
    if not isinstance(fields, dict) or fields.keys() - FIELDS: raise ValueError('Unsupported catalog fields')
    from .metadata_providers import plain
    from .item_attributes import QUALITIES
    for key, value in fields.items():
        if value is None: continue
        if key in ('name','class','subclass','slot','binding'):
            plain(value)
        elif key == 'quality':
            if value not in QUALITIES: raise ValueError('Invalid quality')
        elif key in ('level','required_level'):
            if type(value) is not int or not 0 <= value <= 10000: raise ValueError('Invalid level')
        elif key == 'vendor_sell':
            if not isinstance(value,str) or not value.isdigit() or not 0 <= int(value) <= 2**63-1: raise ValueError('Invalid vendor value')
        elif key == 'lines':
            if not isinstance(value,list) or len(value)>40: raise ValueError('Invalid tooltip lines')
            for entry in value:
                if not isinstance(entry,dict) or entry.get('kind') not in ('attribute','stat','effect','flavor'): raise ValueError('Invalid tooltip line')
                line = entry.get('text')
                if not isinstance(line, str): raise ValueError('Invalid tooltip text')
                # Existing Blizzard tooltips allow paragraph breaks and tabs.
                # Validate their plain text without changing the stored layout;
                # HTML and every other control character remain rejected.
                plain(line.replace('\n', ' ').replace('\t', ' '),512)
        elif key == 'icon_reference':
            if not isinstance(value,str) or not value.startswith('/api/v1/items/'): raise ValueError('Only locally served artwork references')
    row = get_source(db, region, item_id, provider)
    # Null/missing fields and partial responses never erase previously valid fields.
    previous = json.loads(row.fields_json) if row.fields_json else {}
    merged = {**previous, **{k: v for k, v in fields.items() if v is not None and v != []}}
    field_sources = json.loads(row.source_json).get('field_sources', {}) if row.source_json else {}
    field_sources.update({k: source for k, v in fields.items() if v is not None and v != []})
    provenance = {**source, 'field_sources': field_sources}
    fields_json, source_json = json.dumps(merged, sort_keys=True), json.dumps(provenance, sort_keys=True)
    if row.fields_json != fields_json or not row.source_json or json.loads(row.source_json).get('payload_hash') != source.get('payload_hash'):
        row.revision += 1
        db.add(MetadataVersion(region=region, item_id=item_id, locale='en_US', provider=provider,
            revision=row.revision, fields_json=fields_json, source_json=source_json))
    row.fields_json, row.source_json = fields_json, source_json
    row.status, row.http_status, row.etag = 'available', 200, etag
    row.checked_at = row.retrieved_at = at
    row.refresh_at = row.retry_at = at + timedelta(seconds=PROVIDERS[provider].refresh_seconds)
    db.flush()
    return project(db, region, item_id)


def project(db, region, item_id):
    row = db.get(ItemMetadata, (region, item_id))
    if row is None:
        row = ItemMetadata(region=region, item_id=item_id, namespace=f'static-forever-{region}', catalog_revision=0)
        db.add(row); db.flush()
    fields, provenance, conflicts = {}, {}, []
    sources = list(db.scalars(select(MetadataSource).where(MetadataSource.region == region,
        MetadataSource.item_id == item_id, MetadataSource.locale == 'en_US', MetadataSource.fields_json.is_not(None))))
    for record in sorted(sources, key=lambda r: PRECEDENCE[r.provider]):
        values, source = json.loads(record.fields_json), json.loads(record.source_json)
        for field, value in values.items():
            if value is None or value == []: continue
            origin = source.get('field_sources', {}).get(field, source)
            if field not in fields:
                fields[field], provenance[field] = value, origin
            elif fields[field] != value:
                conflicts.append({'field': field, 'selected': provenance[field]['provider'], 'alternative_provider': record.provider, 'alternative': value})
    # Existing primary fields are authoritative even before one-time backfill runs.
    primary = json.loads(row.details) if row.details else {}
    if row.name: primary['name'] = row.name
    primary_source = {'provider': 'blizzard', 'edition': 'forever', 'locale': 'en_US', 'build': row.resolved_namespace or row.namespace,
        'confidence': 'synthetic' if row.synthetic else 'blizzard_base_item', 'retrieved_at': row.resolved_at.isoformat() if row.resolved_at else None,
        'payload_hash': row.payload_hash, 'attribution': None}
    for field, value in primary.items():
        if field in FIELDS and value is not None and value != []:
            if field in fields and fields[field] != value:
                conflicts.append({'field': field, 'selected': 'blizzard', 'alternative_provider': provenance[field]['provider'], 'alternative': fields[field]})
            fields[field], provenance[field] = value, primary_source
    projection = {'schema_version': 1, 'locale': 'en_US', 'edition': 'forever', 'fields': fields, 'provenance': provenance, 'conflicts': conflicts}
    encoded = json.dumps(projection, sort_keys=True)
    if row.catalog_json != encoded:
        row.catalog_revision += 1
        row.catalog_json = encoded
    supplemental = {k: v for k, v in fields.items() if provenance[k]['provider'] != 'blizzard'}
    if supplemental:
        origin = provenance.get('name') if 'name' in supplemental else next(provenance[k] for k in supplemental)
        attrs = {k: v for k, v in fields.items() if k != 'name'}
        row.fallback = json.dumps({'name': fields.get('name'), 'attributes': {'scope': 'base_item', 'lines': [], **attrs}, 'source': {**origin, 'observed_at': origin.get('retrieved_at')}})
        row.fallback_name = supplemental.get('name')
    db.flush()
    return projection


def sync_blizzard(db, row, *, at=None):
    attrs = json.loads(row.details) if row.details else {}
    fields = {key: value for key, value in attrs.items() if key in FIELDS and value is not None}
    if row.name: fields['name'] = row.name
    return store_source(db, row.region, row.item_id, 'blizzard', fields,
        {'provider': 'blizzard', 'edition': 'forever', 'locale': 'en_US',
        'build': row.resolved_namespace or row.namespace, 'confidence': 'synthetic' if row.synthetic else 'blizzard_base_item',
        'payload_hash': row.payload_hash, 'retrieved_at': (at or now()).isoformat(), 'attribution': None}, at=at)


def import_everloot_page(db, region, body, *, at=None):
    from .metadata_providers import parse_everloot_page
    records, next_offset = parse_everloot_page(body, at=at)
    # Validate the whole page before any writes. Caller owns the transaction.
    for ident, fields, source in records: store_source(db, region, ident, 'everloot', fields, source, at=at)
    return len(records), next_offset


def backfill_legacy(db, *, limit=25):
    """Bounded local-only upgrade of existing good metadata and negative caches."""
    rows=list(db.scalars(select(ItemMetadata).where(ItemMetadata.catalog_json.is_(None)).order_by(ItemMetadata.region,ItemMetadata.item_id).limit(limit)))
    for row in rows:
        if row.name or row.details: sync_blizzard(db,row,at=row.resolved_at or row.checked_at)
        else:
            src=get_source(db,row.region,row.item_id,'blizzard')
            src.status,src.http_status=row.status,row.http_status
            src.checked_at,src.retry_at=row.checked_at,row.retry_after if row.http_status is not None else None
        if row.fallback and not row.catalog_json:
            old=json.loads(row.fallback)
            if old.get('source',{}).get('provider')=='thewowdb':
                fields={k:v for k,v in old.get('attributes',{}).items() if k in FIELDS}
                if old.get('name'):fields['name']=old['name']
                origin={**old['source'],'edition':'forever','locale':'en_US','retrieved_at':old['source'].get('observed_at')}
                store_source(db,row.region,row.item_id,'thewowdb',fields,origin,at=row.checked_at)
        project(db,row.region,row.item_id)
    return len(rows)
