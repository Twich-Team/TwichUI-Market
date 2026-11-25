"""Read the published Forever catalogue as data, without executing addon Lua."""
from base64 import b64decode
from hashlib import sha1
import json
import re
from urllib.parse import quote

from .probe import request

ATT_URL = 'https://github.com/ATTWoWAddon/AllTheThings'
ATT_PATH = ".contrib/.db/forever/expansion features/craftsman's writs.lua"
ATT_API = 'https://api.github.com/repos/ATTWoWAddon/AllTheThings/contents/' + quote(ATT_PATH)
FACTION_URL = 'https://foreverchanges.pro/quests/crafting'

_PROFESSION = r'^\t{5}prof\(([A-Z_]+), \{\n'
_QUEST = re.compile(
    r"^\t{6}q\((\d+), \{[ \t]*-- (Craftsman's Writ: .+?) \[(Journeyman|Expert|Artisan)\]\n"
    r'(.*?)^\t{6}\}\),', re.M | re.S,
)
_COST = re.compile(r'\{\s*"i"\s*,\s*(\d+)\s*,\s*(\d+)\s*\}')
_FACTIONS = {'alliance': {'id': 2586, 'name': 'Azeroth Commerce Authority'},
             'horde': {'id': 2587, 'name': 'Durotar Supply and Logistics'}}


def parse_factions(body):
    rows = re.findall(
        r'<a href="/quest/(\d+)/craftsmans-writ-[^"]+">[^<]+</a><em[^>]+>New</em></span>'
        r'<span class="qs-side">(<img[^>]+>)?</span>', body.decode(),
    )
    sides = {}
    for quest, element in rows:
        if quest in sides:
            raise ValueError('Duplicate quest in faction index')
        side = re.search(r'alt="(Alliance|Horde)"', element)
        if element and not side:
            raise ValueError('Unrecognized writ faction')
        sides[quest] = side[1].lower() if side else None
    if not sides:
        raise ValueError('Missing writ faction index')
    return sides


def parse_writ_export(body, sides, previous=None):
    package = json.loads(body)
    if (not isinstance(package, dict) or package.get('path') != ATT_PATH
            or package.get('encoding') != 'base64' or not isinstance(package.get('content'), str)):
        raise ValueError('Unexpected writ export identity')
    source = b64decode(''.join(package['content'].split()), validate=True)
    blob = sha1(f'blob {len(source)}\0'.encode() + source, usedforsecurity=False).hexdigest()
    if len(source) != package.get('size') or blob != package.get('sha'):
        raise ValueError('Incomplete writ export')
    data = source.decode()
    groups = re.split(_PROFESSION, data, flags=re.M)
    tiers = {}
    rows = {}
    prior = {row['item_id']: row for row in (previous or {}).get('writs', [])}
    for profession, group in zip(groups[1::2], groups[2::2], strict=True):
        for match in _QUEST.finditer(group):
            quest, title, tier, fields = match.groups()
            item = re.search(r'^\s*qs\s*=\s*(\d+),', fields, re.M)
            cost = re.search(r'^\s*cost\s*=\s*\{(.*)\},[ \t]*-- ([^\n]+)', fields, re.M)
            objective = _COST.fullmatch(cost[1].strip()) if cost else None
            if not item or not objective or quest not in sides:
                raise ValueError('Incomplete writ objectives')
            item_id = int(item[1])
            delivery, quantity = map(int, objective.groups())
            side = re.search(r'^\s*races\s*=\s*(ALLIANCE|HORDE)_ONLY,', fields, re.M)
            if 'races =' in fields and not side:
                raise ValueError('Unexpected exporter faction rule')
            allowed = {value for value in (sides[quest], side[1].lower() if side else None) if value}
            if len(allowed) > 1:
                raise ValueError('Sources disagree on faction for writ')
            if item_id in rows:
                raise ValueError('Duplicate writ in export')
            old = prior.get(item_id, {})
            old_objectives = [(obj['item_id'], obj['quantity']) for obj in old.get('objectives', [])]
            same_quest = old.get('quest_id') == int(quest) and old_objectives == [(delivery, quantity)]
            recipes = old.get('recipes', []) if same_quest else []
            level = old.get('required_level') if same_quest else None
            restrictions = ['Writ must be in possession at hand-in']
            if type(level) is int and level > 0:
                restrictions.append(f'Writ use requires level {level}')
            restrictions.append('Daily quest' if re.search(r'^\s*isDaily\s*=\s*true,', fields, re.M)
                                else 'Repeatability unknown')
            tiers[item_id] = tier.lower()
            rows[item_id] = {
                'item_id': item_id, 'quest_id': int(quest), 'name': title, 'tier': tier.lower(),
                'profession': profession.lower(), 'faction': None, 'factions': _FACTIONS,
                'allowed_sides': sorted(allowed),
                'objectives': [{'item_id': delivery, 'name': cost[2].strip(), 'quantity': quantity, 'buy_allowed': True}],
                'hand_in_allowed': True, 'recipes': recipes, 'required_level': level,
                'provider_reward': old.get('provider_reward') if same_quest else None,
                'restrictions': restrictions,
                'incomplete_reason': None if any(r.get('craft_allowed') is True for r in recipes) else 'recipe_unverified',
            }
    envelope_items = {}
    envelopes = re.findall(
        r"^\t{4}i\(\d+, \{[ \t]*-- Sealed (Journeyman|Expert|Artisan)'s Writ\n(.*?)^\t{4}\}\),",
        data, re.M | re.S,
    )
    for tier, fields in envelopes:
        for item in re.findall(r'^\t{5}i\((\d+)\),', fields, re.M):
            item_id = int(item)
            if item_id in envelope_items:
                raise ValueError('Writ appears in duplicate envelopes')
            envelope_items[item_id] = tier.lower()
    if len(envelopes) != 3 or not tiers or tiers != envelope_items or len(rows) != len(sides):
        raise ValueError('Writ export and envelope membership differ')
    return {
        'schema_version': 1, 'source': 'all_the_things',
        'source_label': 'AllTheThings',
        'source_url': ATT_URL, 'source_revision': blob, 'faction_source_url': FACTION_URL,
        'writs': [rows[key] for key in sorted(rows)],
    }


class WritSourceUnavailable(ValueError):
    def __init__(self, response):
        self.headers = response.get('headers', {})


def fetch_writ_export(previous=None, *, fetcher=request):
    response, body = fetcher(ATT_API, timeout=8, max_bytes=256 * 1024)
    if response['status'] != 200:
        raise WritSourceUnavailable(response)
    side_response, side_body = fetcher(FACTION_URL, timeout=8, max_bytes=768 * 1024)
    if side_response['status'] != 200:
        raise WritSourceUnavailable(side_response)
    return parse_writ_export(body, parse_factions(side_body), previous)
