"""Curated Forever writ relationships; see docs/crafting-writs-sources.md.

No network calls are made by readers. The published ForeverDB API has no writ
catalogue endpoint, so this seed is deliberately not represented as a provider
refresh or as evidence of complete coverage.
"""
from copy import deepcopy
import json

from .models import MetadataResource

RESOURCE = 'crafting-writs'
CACHE_KEY = ('us', RESOURCE, 0)

# Source-backed exact quest objectives. Recipe client data predates launch;
# trainer skill is addon-observed; the player's learned recipes remain unknown.
_SEED = {
    'schema_version': 1,
    'source': 'wowhead_forever_quests_and_forever_client_70532',
    'source_label': 'Curated WoW Forever quest and client evidence',
    'source_url': 'https://www.wowhead.com/forever/quest=94218/craftsmans-writ-elixir-of-defense',
    'source_observed_at': None,
    'build': None,
    'source_build': '1.60.1.70532 (recipe); quest pages current as of 2026-11-25',
    'reputation_factions': {'alliance': 'Azeroth Commerce Authority', 'horde': 'Durotar Supply and Logistics'},
    'writs': [{
        'item_id': 264018,
        'name': "Craftsman's Writ: Elixir of Defense",
        'quest_id': 94218,
        'tier': 'journeyman',
        'profession': 'alchemy',
        'faction': None,
        'objectives': [{'item_id': 8951, 'name': 'Elixir of Defense', 'quantity': 1, 'buy_allowed': True}],
        'hand_in_allowed': True,
        'recipes': [{
            'recipe_id': 11450, 'item_id': 8951, 'output_quantity': 1,
            'source_build': '1.60.1.70532',
            'skill': 195, 'craft_allowed': True,
            'ingredients': [{'item_id': 3355, 'name': 'Wild Steelbloom', 'quantity': 1},
                            {'item_id': 3821, 'name': 'Goldthorn', 'quantity': 1},
                            {'item_id': 3372, 'name': 'Leaded Vial', 'quantity': 1}],
            'restrictions': ['Requires Alchemy 195 and the learned recipe; player eligibility is unknown'],
        }],
        'provider_reward': None,
        'restrictions': ['Writ must be in possession at hand-in', 'Repeatability unknown'],
        'incomplete_reason': None,
    }],
}

# Each exact link is documented in docs/crafting-writs-sources.md; no ID
# arithmetic or name-based joining is used.
for item_id, quest_id, delivery_id, name, profession, quantity, tier in (
    (264027, 94227, 3848, 'Big Bronze Knife', 'blacksmithing', 1, 'journeyman'),
    (264036, 94236, 4380, 'Big Bronze Bomb', 'engineering', 1, 'journeyman'),
    (264037, 94237, 8069, 'Crafted Solid Shot', 'engineering', 200, 'journeyman'),
    (264038, 94238, 18662, 'Heavy Leather Ball', 'leatherworking', 1, 'journeyman'),
    (264045, 94245, 4254, 'Barbaric Gloves', 'leatherworking', 1, 'journeyman'),
    (264053, 94253, 10048, 'Colorful Kilt', 'tailoring', 1, 'journeyman'),
    (264063, 94263, 6049, 'Fire Protection Potion', 'alchemy', 1, 'expert'),
    (264118, 94318, 13457, 'Greater Fire Protection Potion', 'alchemy', 1, 'artisan'),
):
    _SEED['writs'].append({
        'item_id': item_id, 'name': "Craftsman's Writ: " + name,
        'quest_id': quest_id, 'tier': tier, 'profession': profession,
        'faction': None,
        'objectives': [{'item_id': delivery_id, 'name': name, 'quantity': quantity, 'buy_allowed': True}],
        'hand_in_allowed': True, 'recipes': [], 'provider_reward': None,
        'restrictions': ['Writ must be in possession at hand-in', 'Repeatability unknown'],
        'incomplete_reason': 'recipe_unverified',
    })


# The reward recipient depends on the player's faction, not on which
# profession produces the requested item.
for _writ in _SEED['writs']:
    _writ['factions'] = dict(_SEED['reputation_factions'])

# ForeverDB confirms the batch/reagents; GoldCap reports trainer skill seen in Forever.
for _writ in _SEED['writs']:
    if _writ['item_id'] == 264027:
        _writ['recipes'] = [{
            'recipe_id': 3491, 'item_id': 3848, 'output_quantity': 1,
            'skill': 80, 'craft_allowed': True,
            'ingredients': [{'item_id': 2841, 'name': 'Bronze Bar', 'quantity': 6},
                            {'item_id': 2880, 'name': 'Weak Flux', 'quantity': 4},
                            {'item_id': 2862, 'name': 'Rough Grinding Stone', 'quantity': 2},
                            {'item_id': 818, 'name': 'Tigerseye', 'quantity': 1},
                            {'item_id': 2319, 'name': 'Medium Leather', 'quantity': 1}],
            'restrictions': ['Requires Blacksmithing 80, the learned recipe, a Blacksmith Hammer and an anvil'],
        }]
        _writ['incomplete_reason'] = None
    if _writ['item_id'] == 264036:
        _writ['recipes'] = [{
            'recipe_id': 3950, 'item_id': 4380, 'output_quantity': None,
            'output_min': 2, 'output_max': 4, 'skill': None, 'craft_allowed': None,
            'ingredients': [{'item_id': 4377, 'name': 'Heavy Blasting Powder', 'quantity': 2},
                            {'item_id': 2841, 'name': 'Bronze Bar', 'quantity': 3},
                            {'item_id': 4404, 'name': 'Silver Contact', 'quantity': 1}],
            'restrictions': ['Random output; requires Blacksmith Hammer, Arclight Spanner and anvil'],
        }]
    if _writ['item_id'] == 264037:
        _writ['recipes'] = [{
            'recipe_id': 3947, 'item_id': 8069, 'output_quantity': 200,
            'skill': 125, 'craft_allowed': True,
            'ingredients': [{'item_id': 4377, 'name': 'Heavy Blasting Powder', 'quantity': 1},
                            {'item_id': 2841, 'name': 'Bronze Bar', 'quantity': 1}],
            'restrictions': ['Requires Engineering 125 and the learned recipe; player eligibility is unknown'],
        }]
        _writ['incomplete_reason'] = None


def validate_catalogue(data):
    """Reject malformed bounded relationships before cache replacement."""
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Invalid writ catalogue')
    rows = data.get('writs')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ValueError('Invalid writ count')
    seen, quests, graph = set(), set(), {}
    def positive(value):
        if type(value) is not int or not 1 <= value <= 2**31 - 1:
            raise ValueError('Invalid ID or quantity')
    for writ in rows:
        if not isinstance(writ, dict):
            raise ValueError('Invalid writ')
        positive(writ.get('item_id')); positive(writ.get('quest_id'))
        if writ['item_id'] in seen or writ['quest_id'] in quests or writ.get('tier') not in ('journeyman', 'expert', 'artisan'):
            raise ValueError('Duplicate or invalid writ')
        seen.add(writ['item_id']); quests.add(writ['quest_id'])
        if writ.get('profession') not in ('alchemy', 'blacksmithing', 'engineering', 'leatherworking', 'tailoring', 'cooking', 'enchanting'):
            raise ValueError('Invalid profession')
        objectives = writ.get('objectives')
        recipes = writ.get('recipes')
        if not isinstance(objectives, list) or not 1 <= len(objectives) <= 10 or not isinstance(recipes, list) or len(recipes) > 30:
            raise ValueError('Invalid objectives or recipes')
        objective_ids = set()
        for obj in objectives:
            if not isinstance(obj, dict): raise ValueError('Invalid objective')
            positive(obj.get('item_id')); positive(obj.get('quantity'))
            if obj['item_id'] in objective_ids or obj['item_id'] == writ['item_id']:
                raise ValueError('Duplicate or cyclic objective')
            if obj.get('buy_allowed') is not None and type(obj['buy_allowed']) is not bool: raise ValueError('Invalid buy eligibility')
            objective_ids.add(obj['item_id'])
        recipe_ids = set()
        for recipe in recipes:
            if not isinstance(recipe, dict): raise ValueError('Invalid recipe')
            positive(recipe.get('recipe_id')); positive(recipe.get('item_id'))
            if recipe['recipe_id'] in recipe_ids or recipe['item_id'] not in objective_ids:
                raise ValueError('Invalid recipe relationship')
            recipe_ids.add(recipe['recipe_id'])
            if recipe.get('craft_allowed') is not None and type(recipe['craft_allowed']) is not bool: raise ValueError('Invalid craft eligibility')
            if recipe.get('output_quantity') is not None:
                positive(recipe['output_quantity'])
            elif recipe.get('output_min') is not None or recipe.get('output_max') is not None:
                positive(recipe.get('output_min')); positive(recipe.get('output_max'))
                if recipe['output_min'] > recipe['output_max']:
                    raise ValueError('Reversed random output')
            if recipe.get('skill') is not None:
                positive(recipe['skill'])
                if recipe['skill'] > 1000: raise ValueError('Invalid skill')
            ingredients = recipe.get('ingredients')
            if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= 30:
                raise ValueError('Invalid ingredients')
            ingredient_ids = set()
            for ingredient in ingredients:
                if not isinstance(ingredient, dict): raise ValueError('Invalid ingredient')
                positive(ingredient.get('item_id')); positive(ingredient.get('quantity'))
                if ingredient['item_id'] in ingredient_ids:
                    raise ValueError('Duplicate ingredient')
                ingredient_ids.add(ingredient['item_id'])
            graph.setdefault(recipe['item_id'], set()).update(ingredient_ids)
    def visit(node, active, done):
        if node in active: raise ValueError('Cyclic recipe graph')
        if node in done: return
        active.add(node)
        for child in graph.get(node, ()): visit(child, active, done)
        active.remove(node); done.add(node)
    done = set()
    for node in graph: visit(node, set(), done)
    return data


def read_catalogue(db):
    """Read a validated last good cache, falling back to the curated seed."""
    row = db.get(MetadataResource, CACHE_KEY) if db is not None else None
    if row and row.fields_json:
        try:
            return row, validate_catalogue(json.loads(row.fields_json))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            pass
    return row, deepcopy(validate_catalogue(_SEED))


def persist_seed(db):
    """Insert the seed once, never replace an existing last-good cache."""
    row = db.get(MetadataResource, CACHE_KEY)
    if row is None:
        row = MetadataResource(region='us', resource=RESOURCE, offset=0,
            status='curated_seed', fields_json=json.dumps(validate_catalogue(_SEED), sort_keys=True),
            source_json=json.dumps({'kind': 'curated_seed', 'url': _SEED['source_url']}))
        db.add(row)
    return row


def refresh_seconds():
    # No documented endpoint returns the quest objectives in this seed.
    return 0
