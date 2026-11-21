"""Bounded SQL candidates and shared policy used by the worker and read-only tracker."""
import json
import os
from sqlalchemy import JSON, and_, cast, func, or_, select
from .models import ItemMetadata, ItemMedia, MetadataSource, MetadataProvider
from .provider_rates import rate_view
from .recovery_policy import gaps, goal_for, provider_action, choose, explain


def fields_sql():
    return cast(ItemMetadata.catalog_json, JSON)['fields']


def essential_missing_sql(capabilities=None, *, facts=None, legacy_quality=None):
    f = fields_sql() if facts is None else facts
    quality = ItemMetadata.quality if legacy_quality is None else legacy_quality
    capabilities=set(capabilities) if capabilities is not None else {'quality','class','slot','level'}
    checks=[]
    if 'quality' in capabilities: checks.append(func.coalesce(f['quality'].as_string(), quality).is_(None))
    if 'class' in capabilities: checks.append(f['class'].as_string().is_(None))
    equipment=[f[field].as_string().is_(None) for field in ('level','slot') if field in capabilities]
    if equipment: checks.append(and_(f['class'].as_string().in_(('Weapon','Armor')),or_(*equipment)))
    return or_(*checks) if checks else False


def phase_sql(priority):
    f = fields_sql()
    return {1: func.coalesce(ItemMetadata.name, ItemMetadata.fallback_name).is_(None),
            2: ItemMedia.data.is_(None), 3: essential_missing_sql(),
            4: f['class'].as_string().in_(('Weapon','Armor')), 5: True}[priority]


def source_due_sql(source, at, *, build=None):
    """Mirror source cache eligibility to keep bounded candidates moving."""
    from datetime import timedelta
    evidence = cast(source.recovery_json, JSON)
    from .foreverdb import MAPPING_VERSION
    origin = cast(source.source_json, JSON)
    upgrade = and_(source.provider == 'foreverdb', source.status == 'available',
        or_(func.coalesce(origin['item_mapping_version'].as_integer(), 0) < MAPPING_VERSION,
            func.coalesce(origin['item_build'].as_string(), '') != build if build else False))
    return or_(source.item_id.is_(None), upgrade,
        and_(or_(source.retry_at.is_(None), source.retry_at <= at),
             or_(source.recovery_json.is_(None), source.http_status.not_in((200,304)),
                 evidence['new_fields'].as_string().not_in(('[]','null')),evidence['updated_fields'].as_string().not_in(('[]','null')), source.checked_at <= at-timedelta(days=7))))


def provider_context(db, at, *, execution=False, allow_mock=False):
    context = {}
    for row in db.scalars(select(MetadataProvider).order_by(MetadataProvider.provider)):
        credentials = True
        if row.provider == 'foreverdb':
            credentials = bool(row.credential)
        elif row.provider == 'blizzard':
            credentials = allow_mock or (bool(os.environ.get('BLIZZARD_CLIENT_ID') and os.environ.get('BLIZZARD_CLIENT_SECRET')) if execution else row.credential_status == 'oauth_connected')
        context[row.provider] = (row, rate_view(row, at)['next_eligible_at'], credentials)
    return context


def load_items(db, identities):
    from sqlalchemy import tuple_
    if not identities:
        return {}, {}, {}
    metadata = {(r.region,r.item_id): r for r in db.scalars(select(ItemMetadata).where(tuple_(ItemMetadata.region, ItemMetadata.item_id).in_(identities)))}
    media = {(r.region,r.item_id): r for r in db.scalars(select(ItemMedia).where(tuple_(ItemMedia.region, ItemMedia.item_id).in_(identities)))}
    sources = {}
    for r in db.scalars(select(MetadataSource).where(tuple_(MetadataSource.region, MetadataSource.item_id).in_(identities), MetadataSource.locale == 'en_US')):
        sources.setdefault((r.region,r.item_id), {})[r.provider] = r
    return metadata, media, sources


def plan_item(row, media, sources, context, at, *, automatic=False, force=False, build=None, priority=None, providers=None, allow_refresh=True):
    gap = gaps(row, media, sources, build=build)
    priorities = [priority] if priority else [1,2,3,4,5] if allow_refresh else [1,2,3,4]
    plans = []
    for p in priorities:
        goals = goal_for(gap,p)
        if not goals:
            continue
        actions = [provider_action(provider, sources.get(ident), goals, at, provider_due=due,
                                  credentials=credentials, automatic=automatic, force=force, build=build)
                   for ident,(provider,due,credentials) in context.items() if not providers or ident in providers]
        chosen = choose(actions,p)
        plan = {'policy_version':1, 'automatic':automatic, 'priority':p, 'missing':gap, 'actions':actions,
                'chosen':chosen, 'explanation':explain(actions,chosen)}
        plans.append(plan)
        if chosen:
            return plan
    # Explain the highest missing priority if nothing is currently eligible.
    return plans[0] if plans else {'policy_version':1,'missing':gap,'actions':[], 'chosen':None, 'explanation':'Applicable metadata is complete; no refresh is due.'}


def remember_decision(db, identity, plan, at):
    from datetime import datetime
    from .models import MetadataRecoveryItem
    encoded=json.dumps(plan,sort_keys=True)
    row=db.get(MetadataRecoveryItem,(*identity,'en_US'))
    if row and row.decision_json==encoded:
        row.decided_at=at
        return
    times=[a['next_at'] for a in plan.get('actions',[]) if a['next_at']]
    status='eligible' if plan['chosen'] else 'waiting' if times else 'no_eligible_provider'
    if row is None:
        row=MetadataRecoveryItem(region=identity[0],item_id=identity[1],locale='en_US');db.add(row)
    row.status,row.decided_at,row.next_at,row.decision_json=status,at,datetime.fromisoformat(min(times)) if times else None,encoded
