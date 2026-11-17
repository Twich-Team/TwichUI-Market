"""Shared, side-effect-free item goals and provider choice. No network or quotas consumed.

Capabilities describe the existing adapter endpoint, not a provider's entire site.
Everloot's item card supplies names only; bulk categories never satisfy a name goal.
"""
from datetime import timedelta
import json
from .security import aware

POLICY_VERSION = 1
ESSENTIAL = {'quality', 'class'}
EQUIPMENT = {'Weapon', 'Armor'}
CAPABILITIES = {
    'blizzard': {'name', 'quality', 'class', 'subclass', 'slot', 'level', 'required_level', 'binding', 'vendor_sell', 'lines'},
    'everloot': {'name'},
    'foreverdb': {'name', 'quality', 'class', 'subclass', 'slot', 'level', 'required_level', 'binding', 'vendor_sell', 'details', 'artwork'},
    'thewowdb': {'name', 'quality', 'class', 'subclass', 'slot', 'level', 'required_level', 'binding', 'vendor_sell', 'lines', 'artwork'},
}
ORDER = {'blizzard': 0, 'foreverdb': 1, 'thewowdb': 2, 'everloot': 3}


def populated(value):
    return value is not None and value not in ('', [], {})


def known_fields(row):
    fields = json.loads(row.catalog_json).get('fields', {}) if row and row.catalog_json else {}
    if row:
        fields = {**(json.loads(row.details) if row.details else {}), **fields}
        if row.name or row.fallback_name:
            fields['name'] = row.name or row.fallback_name
        if row.quality:
            fields['quality'] = row.quality
    return {k: v for k, v in fields.items() if populated(v)}


def gaps(row, media, sources, *, build=None):
    fields = known_fields(row)
    essential = ESSENTIAL | ({'level', 'slot'} if fields.get('class') in EQUIPMENT else set())
    missing = sorted(essential - fields.keys())
    # Detail verification is applicable to known equipment only. Empty/absent
    # optional stats/effects in a verified detail response are not endless gaps.
    detail = False
    if fields.get('class') in EQUIPMENT:
        from .foreverdb import needs_detail
        record = sources.get('foreverdb')
        detail = not record or record.status != 'available' or not record.fields_json or needs_detail(record, build)
    return {'name': 'name' not in fields, 'icon': not bool(media and media.data),
            'essential': missing, 'details': detail}


def goal_for(gap, priority):
    return ({1: ['name'] if gap['name'] else [], 2: ['artwork'] if gap['icon'] else [],
             3: gap['essential'], 4: ['details'] if gap['details'] else [], 5: ['refresh']})[priority]


def provider_action(provider, source, goals, at, *, provider_due=None, credentials=True, automatic=False, force=False, build=None):
    """Return actual eligibility reasons without mutating source/provider state."""
    ident = provider.provider
    matched = sorted(set(goals) & CAPABILITIES[ident])
    refresh = 'refresh' in goals
    result = {'provider': ident, 'goals': list(goals), 'capable_fields': matched,
              'eligible': False, 'next_at': None, 'reason': None,
              'last_attempt_at': source.checked_at.isoformat() if source and source.checked_at else None}
    if not provider.enabled or automatic and not provider.automatic:
        result['reason'] = 'provider_disabled' if not provider.enabled else 'automatic_disabled'
        return result
    if not credentials or provider.expires_at and aware(provider.expires_at) <= at:
        result['reason'] = 'credential_unavailable'
        return result
    if provider.last_error in ('authorization', 'forbidden', 'subscription_required', 'credential_unavailable', 'secret_unavailable'):
        result['reason'] = 'access_blocked' if provider.last_error in ('authorization','forbidden','subscription_required') else 'credential_unavailable'
        return result
    if not matched and not refresh:
        result['reason'] = 'incapable'
        return result
    if refresh and (not source or not source.fields_json):
        result['reason'] = 'no_refresh_record'
        return result
    # Artwork with a stored allowlisted reference is handled by the independent
    # image resolver, never by repeating this item metadata endpoint.
    if matched == ['artwork'] and source and source.source_json and json.loads(source.source_json).get('icon_url'):
        result['reason'] = 'local_artwork_reference'
        return result
    waits = [(at, 'eligible')]
    if provider_due and provider_due > at:
        waits.append((provider_due, 'provider_cooldown'))
    if source:
        from .foreverdb import needs_detail
        upgrade = ident == 'foreverdb' and needs_detail(source, build)
        # Mapping/build changes can justify a refresh, but never bypass errors,
        # 404/429 caches or the shared provider quota/cooldown.
        if source.retry_at and not (upgrade and source.status == 'available'):
            if not (force and source.status == 'available'):
                waits.append((aware(source.retry_at), 'negative_cache' if source.http_status == 404 else 'waiting_for_refresh' if source.http_status in (200,304) else 'temporarily_unavailable'))
        evidence = json.loads(source.recovery_json) if getattr(source, 'recovery_json', None) else None
        if source.checked_at and source.http_status in (200,304) and not force and not upgrade:
            # Static base metadata is not usefully polled hourly when the last
            # response supplied no missing field. New mapping/build can override.
            if evidence and not evidence.get('new_fields'):
                waits.append((aware(source.checked_at) + timedelta(days=7), 'recently_unproductive'))
    until, reason = max(waits, key=lambda pair: pair[0])
    result.update(next_at=until.isoformat(), eligible=until <= at, reason=reason)
    return result


def choose(actions, priority):
    eligible = [a for a in actions if a['eligible']]
    if not eligible:
        return None
    # Prefer the endpoint covering more current gaps, then one not tried recently.
    # Blizzard remains field-authoritative irrespective of who is queried first.
    return min(eligible, key=lambda a: (-len(a['capable_fields']), a['last_attempt_at'] or '', ORDER[a['provider']]))


def explain(actions, chosen):
    if chosen:
        earlier = [a for a in actions if a['reason'] in ('recently_unproductive','waiting_for_refresh','negative_cache','provider_cooldown')]
        prefix = '; '.join(f"{a['provider']} is waiting ({a['reason'].replace('_',' ')})" for a in earlier)
        target = ', '.join(chosen['capable_fields']) or 'a justified refresh'
        return (prefix + '. ' if prefix else '') + f"{chosen['provider']} is eligible for {target}."
    timed = [a['next_at'] for a in actions if a['next_at']]
    return 'No provider is currently eligible.' + (f' Next known eligibility: {min(timed)}.' if timed else ' Provider access or capabilities need attention.')
