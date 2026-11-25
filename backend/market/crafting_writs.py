"""Validate and persist the last successful Forever writ catalogue."""
from datetime import timedelta
import json
import hashlib

from sqlalchemy import text

from .db import now
from .models import MetadataResource
from .provider_rates import retry_delay
from .security import audit, aware

RESOURCE = 'crafting-writs'
CACHE_KEY = ('us', RESOURCE, 0)

_PROFESSIONS = ('alchemy', 'blacksmithing', 'engineering', 'leatherworking', 'tailoring', 'cooking', 'enchanting')
_REFRESH_INTERVAL = timedelta(days=1)
_RETRY_INTERVAL = timedelta(minutes=15)


def producing_professions(writ):
    return writ.get('professions', [writ['profession']] if writ.get('profession') else [])


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
        professions = producing_professions(writ)
        if (not isinstance(professions, list) or not 1 <= len(professions) <= len(_PROFESSIONS)
                or any(profession not in _PROFESSIONS for profession in professions)
                or professions[0] != writ.get('profession') or len(set(professions)) != len(professions)):
            raise ValueError('Invalid profession')
        sides = writ.get('allowed_sides', [])
        if not isinstance(sides, list) or len(sides) > 2 or any(side not in ('alliance', 'horde') for side in sides):
            raise ValueError('Invalid faction restriction')
        objectives = writ.get('objectives')
        recipes = writ.get('recipes')
        if not isinstance(objectives, list) or not 1 <= len(objectives) <= 10 or not isinstance(recipes, list) or len(recipes) > 30:
            raise ValueError('Invalid objectives or recipes')
        objective_ids = set()
        for obj in objectives:
            if not isinstance(obj, dict): raise ValueError('Invalid objective')
            positive(obj.get('item_id')); positive(obj.get('quantity'))
            if obj['quantity'] > 10000: raise ValueError('Objective quantity limit')
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
                if ingredient['quantity'] > 10000: raise ValueError('Ingredient quantity limit')
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
    """Read only committed, validated data. Fail closed on malformed cache rows."""
    row = db.get(MetadataResource, CACHE_KEY) if db is not None else None
    if row and row.fields_json:
        try:
            return row, validate_catalogue(json.loads(row.fields_json))
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            pass
    return row, None


def _locked_resource(db):
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(7140242)'))
    row = db.get(MetadataResource, CACHE_KEY, with_for_update=True)
    if row is None:
        row = MetadataResource(region=CACHE_KEY[0], resource=RESOURCE, offset=CACHE_KEY[2])
        db.add(row)
        db.flush()
    return row


def queue_catalogue_refresh(db, user_id, *, at=None):
    at = at or now()
    row = _locked_resource(db)
    if row.status in ('queued', 'running'):
        return
    if row.status == 'available' and row.checked_at:
        earliest = aware(row.checked_at) + _RETRY_INTERVAL
        if earliest > at:
            row.retry_at = earliest
    row.status, row.refresh_at = 'queued', at
    audit(db, user_id, 'metadata.crafting_writs.queued')


def refresh_catalogue(factory, *, at, fetcher):
    """Refresh with a durable retry deadline and one atomic catalogue update."""
    with factory.begin() as db:
        row = _locked_resource(db)
        if any(stamp and aware(stamp) > at for stamp in (row.refresh_at, row.retry_at)):
            return False
        _, previous = read_catalogue(db)
        row.status, row.checked_at, row.retry_at = 'running', at, at + _RETRY_INTERVAL
    try:
        candidate = validate_catalogue(fetcher(previous))
        if previous and len(candidate['writs']) < len(previous['writs']):
            raise ValueError('Writ catalogue unexpectedly shrank')
        fields = json.dumps(candidate, sort_keys=True, separators=(',', ':'))
        source = json.dumps({
            'kind': 'api_import', 'revision': candidate['source_revision'],
            'catalogue_url': candidate['source_url'], 'faction_source_url': candidate['faction_source_url'],
            'confirmed_at': at.isoformat(), 'sha256': hashlib.sha256(fields.encode()).hexdigest(),
        }, sort_keys=True)
    except (KeyError, TypeError, ValueError, OSError, RecursionError) as error:
        headers = getattr(error, 'headers', {})
        delay = retry_delay(headers.get('Retry-After'), at, headers.get('Date'))
        with factory.begin() as db:
            row = _locked_resource(db)
            if aware(row.checked_at) == at:
                row.status = 'error'
                row.retry_at = at + max(_RETRY_INTERVAL, timedelta(seconds=delay))
        return False
    with factory.begin() as db:
        row = _locked_resource(db)
        if aware(row.checked_at) != at:
            return False
        row.status, row.fields_json, row.source_json = 'available', fields, source
        row.retry_at, row.refresh_at = None, at + _REFRESH_INTERVAL
    return True
