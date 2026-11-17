"""Current stored coverage, with explicit identity and recovery-state denominators."""
from sqlalchemy import JSON, and_, cast, func, or_, select, case
from .models import ItemMetadata, ItemMedia, MetadataSource, MetadataTask
from .metadata_catalog import FIELDS


def populated(value):
    return value.is_not(None) & value.not_in(('', '[]', '{}', 'null'))


def summary(db, ids):
    """One row per distinct (region,item_id); never sum provider overlap."""
    from sqlalchemy.dialects.postgresql import JSONB
    json_type = JSONB if db.bind.dialect.name == 'postgresql' else JSON
    stored = select(ItemMetadata.region, ItemMetadata.item_id, ItemMetadata.name,
                    ItemMetadata.fallback_name, ItemMetadata.http_status,
                    cast(cast(ItemMetadata.catalog_json, JSON)['fields'], json_type).label('catalog'),
                    cast(ItemMetadata.details, json_type).label('details')).join(ids,
        (ItemMetadata.region == ids.c.region) & (ItemMetadata.item_id == ids.c.item_id)).cte('coverage_metadata')
    if db.bind.dialect.name == 'postgresql': stored = stored.prefix_with('MATERIALIZED')
    catalog = stored.c.catalog
    legacy = stored.c.details
    fields = sorted(FIELDS - {'name', 'icon_reference'})
    attributes = or_(*[populated(root[field].as_string()) for root in (catalog, legacy) for field in fields])
    named = or_(stored.c.name.is_not(None), stored.c.fallback_name.is_not(None))
    source_states = (select(MetadataSource.region, MetadataSource.item_id,
        func.max(case((MetadataSource.http_status.is_not(None),1),else_=0)).label('checked'),
        func.max(case((MetadataSource.http_status==404,1),else_=0)).label('missing'),
        func.max(case((MetadataSource.http_status.not_in((200,304,404)),1),else_=0)).label('error'))
        .join(ids,(MetadataSource.region==ids.c.region)&(MetadataSource.item_id==ids.c.item_id))
        .where(MetadataSource.locale=='en_US').group_by(MetadataSource.region,MetadataSource.item_id).cte('coverage_recovery'))
    checked = source_states.c.checked == 1
    missing = source_states.c.missing == 1
    error = source_states.c.error == 1
    attempted = checked | stored.c.http_status.is_not(None)
    has_error = error | (stored.c.http_status.is_not(None) & stored.c.http_status.not_in((200,304,404)))
    has_missing = missing | (stored.c.http_status == 404)
    # COALESCE avoids SQL's unknown NULL truth value dropping uncreated metadata.
    unnamed = ~func.coalesce(named, False)
    conditions = {
        'attributes_available': attributes,
        'scoped_pending_items': select(MetadataTask.id).where(
            MetadataTask.region == ids.c.region, MetadataTask.item_id == ids.c.item_id,
            MetadataTask.state.in_(('queued','running'))).exists(),
        'unknown_not_tried': unnamed & ~func.coalesce(attempted, False),
        'tried_unavailable': unnamed & func.coalesce(has_missing, False) & ~func.coalesce(has_error, False),
        'failed_or_blocked': unnamed & func.coalesce(has_error, False),
        'checked_unresolved': unnamed & func.coalesce(attempted, False) & ~func.coalesce(has_missing, False) & ~func.coalesce(has_error, False),
    }
    values = db.execute(select(*[func.count().filter(condition) for condition in conditions.values()])
        .select_from(ids).outerjoin(stored, and_(stored.c.region == ids.c.region, stored.c.item_id == ids.c.item_id)).outerjoin(source_states,
            (source_states.c.region == ids.c.region) & (source_states.c.item_id == ids.c.item_id))).one()
    result = dict(zip(conditions, values))
    result['coverage_identity'] = 'Distinct regional base-item IDs in latest recorded snapshots; variants count once. Locale en_US.'
    result['attributes_definition'] = 'At least one nonempty stored base-item or relationship field beyond name and icon; presence does not imply complete attributes.'
    result['recovery_notice'] = 'Unknown is not failed. Pending items may already have names. Missing fields are not guaranteed recoverable; provider access, quotas and retry windows still apply.'
    return result
