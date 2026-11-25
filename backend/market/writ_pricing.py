"""Compare verified direct crafting and finished-item purchases for a writ."""
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from itertools import product
from math import gcd, prod
from typing import Literal

from .waylaid_pricing import display_price, exact_price, quote_line, quote_reasons

Method = Literal['cheapest', 'craft', 'buy']
AVAILABLE_STOCK = ('sufficient_at_minimum', 'whole_stack_overshoot')
MAX_BASKET_STATES = 100_000
MAX_BASKET_CHUNKS = 512
MAX_RECIPE_COMBINATIONS = 256


def _ceiling(numerator, denominator):
    return (numerator + denominator - 1) // denominator


def _minimum_stacks(lots, required):
    """Find the lowest whole-stack quantity covering the request, at one unit price."""
    single = next((size for size in sorted(lots) if size >= required), None)
    smaller = sorted((size, count) for size, count in lots.items() if size < required)
    total = sum(size * count for size, count in smaller)
    if total < required:
        return ((single, 1),) if single is not None else None
    if len(smaller) == 1:
        size, _ = smaller[0]
        count = _ceiling(required, size)
        return ((single, 1),) if single is not None and single <= size * count else ((size, count),)

    factor = gcd(*(size for size, _ in smaller))
    target = _ceiling(required, factor)
    # A minimal cover built from the smaller stacks overshoots by less than its largest stack.
    upper = min(total // factor, target + smaller[-1][0] // factor - 1)
    if single is not None:
        upper = min(upper, (single - 1) // factor)
    if upper < target:
        return ((single, 1),)
    if target > MAX_BASKET_STATES:
        return None
    bound = min(upper, MAX_BASKET_STATES)
    mask = (1 << (bound + 1)) - 1
    reachable = 1
    previous = []
    for size, count in smaller:
        weight = size // factor
        remaining = min(count, bound // weight)
        chunk = 1
        # Binary splitting represents an arbitrary count with logarithmically many bitset steps.
        while remaining and not (reachable >> target) & 1:
            if len(previous) == MAX_BASKET_CHUNKS:
                return None
            used = min(remaining, chunk)
            previous.append((reachable, size, used))
            reachable |= (reachable << (weight * used)) & mask
            remaining -= used
            chunk *= 2
        if (reachable >> target) & 1:
            break
    covers = reachable >> target
    if not covers:
        return ((single, 1),) if single is not None and bound == upper else None

    quantity = target + (covers & -covers).bit_length() - 1
    selected = Counter()
    for before, size, used in reversed(previous):
        if not (before >> quantity) & 1:
            selected[size] += used
            quantity -= size // factor * used
    return tuple(sorted(selected.items()))


def _set_purchase(line, cost, bought, leftover, stacks):
    line.update(
        minimum_purchase_copper=display_price(cost),
        purchased_quantity=bought,
        leftover_quantity=leftover,
        stacks=[{'quantity': size, 'count': count} for size, count in stacks] if stacks is not None else None,
    )


def _price_line(item_id, quantity, quotes):
    valuation, line = quote_line(item_id, quantity, quotes, check_exact_stack=False)
    _set_purchase(line, None, None, None, None)
    if quotes.basis != 'current':
        line.update(stock_status='reference', available_at_minimum=None, current_priced_quantity=None)
        return valuation, valuation, line
    if line['available_at_minimum'] is None or line['quote_status'] != 'available':
        return None, valuation, line
    if line['available_at_minimum'] < quantity:
        return None, valuation, line
    quote = quotes.items[item_id]
    if quote.source_kind == 'commodities':
        purchased = quantity
        stacks = None
    else:
        stacks = _minimum_stacks(quote.lots, quantity)
        if stacks is None:
            line['stock_status'] = 'basket_search_limit'
            return None, valuation, line
        purchased = sum(size * count for size, count in stacks)
    cost = quote.exact_minimum * purchased
    line['stock_status'] = 'whole_stack_overshoot' if purchased > quantity else 'sufficient_at_minimum'
    _set_purchase(line, cost, purchased, purchased - quantity, stacks)
    return cost, valuation, line


def _allocate_shared_purchase(quotes, material, purchase_quote, shared):
    """Assign one included lot to the writ and apply its remaining units to the delivery."""
    if shared['stacks'] is None:
        size = 1
        writ_stacks = material_stacks = None
    else:
        size = shared['stacks'][0]['quantity']
        writ_stacks = [(size, 1)]
        material_stacks = [(stack['quantity'], stack['count'] - int(index == 0))
                           for index, stack in enumerate(shared['stacks'])
                           if index or stack['count'] > 1]
    unit = quotes.items[shared['item_id']].exact_minimum
    writ_cost = unit * size
    material_count = shared['purchased_quantity'] - size
    material_cost = unit * material_count
    covered = min(size - 1, material['quantity'])
    _set_purchase(purchase_quote, writ_cost, size, size - 1 - covered, writ_stacks)
    _set_purchase(material, material_cost, material_count, material_count + covered - material['quantity'], material_stacks)
    material['covered_by_writ_quantity'] = covered
    material['stock_status'] = purchase_quote['stock_status'] = shared['stock_status']
    return writ_cost, material_cost


def _quantities(lines):
    quantities = Counter()
    for line in lines:
        quantities[line['item_id']] += line['quantity']
    return quantities


def _sum_costs(costs):
    return sum(costs, Fraction()) if all(cost is not None for cost in costs) else None


def _money(purchase, completion, total, valuation_completion=None, valuation_total=None):
    return {
        'purchase_cost_copper': display_price(purchase), 'purchase_cost_exact': exact_price(purchase),
        'completion_cost_copper': display_price(completion), 'completion_cost_exact': exact_price(completion),
        'total_cost_copper': display_price(total), 'total_cost_exact': exact_price(total),
        'valuation_completion_cost_copper': display_price(valuation_completion),
        'valuation_completion_cost_exact': exact_price(valuation_completion),
        'valuation_total_cost_copper': display_price(valuation_total),
        'valuation_total_cost_exact': exact_price(valuation_total),
    }


@dataclass
class _Route:
    details: dict
    total: Fraction | int | None
    valuation: Fraction | int | None


def _route(writ_id, quantities, recipes, restrictions, quotes, line_for, owned):
    purchase, purchase_valuation, original_purchase_quote = line_for(writ_id, 1)
    purchase_quote = original_purchase_quote.copy()
    if owned:
        purchase = purchase_valuation = Fraction()
    materials, basket = [], []
    completion = total = valuation_completion = valuation_total = None
    if quantities is not None:
        combined = quantities.copy()
        if not owned:
            combined[writ_id] += 1
        current = quotes.basis == 'current'
        basket = [line_for(item, quantity)[2] for item, quantity in sorted(combined.items())]
        material_costs, values = [], []
        for item, quantity in sorted(quantities.items()):
            cost, valuation, original = line_for(item, quantity)
            material = original.copy()
            if current and not owned and item == writ_id:
                combined_purchase, _, shared = line_for(item, quantity + 1)
                if combined_purchase is None:
                    cost = None
                    _set_purchase(material, None, None, None, None)
                    material['stock_status'] = shared['stock_status']
                else:
                    purchase, cost = _allocate_shared_purchase(quotes, material, purchase_quote, shared)
            materials.append(material)
            material_costs.append(cost)
            values.append(valuation)
        completion = _sum_costs(material_costs)
        total = _sum_costs([purchase, completion])
        valuation_completion = _sum_costs(values)
        valuation_total = _sum_costs([purchase_valuation, valuation_completion])
    priced_lines = basket if basket or owned else [purchase_quote]
    reasons = list(dict.fromkeys([*restrictions, *quote_reasons(quotes, priced_lines, accepted_stock=AVAILABLE_STOCK)]))
    return _Route({
        **_money(purchase, completion, total, valuation_completion, valuation_total),
        'eligible': total is not None and not reasons,
        'reasons': reasons,
        'purchase_quote': purchase_quote,
        'materials': materials,
        'basket': basket,
        'recipes': recipes,
    }, total, valuation_total)


def _permission_reasons(value, unknown, denied):
    return [] if value is True else [denied] if value is False else [unknown]


def _recipe_option(recipe, quantity, max_skill, confirmed):
    output = recipe.get('output_quantity')
    output_min, output_max = recipe.get('output_min'), recipe.get('output_max')
    random_output = recipe.get('output_random') or output_min != output_max
    bounds_agree = output_min is None or (type(output_min) is int and type(output_max) is int and output_min == output)
    deterministic = type(output) is int and output > 0 and not random_output and bounds_agree
    skill = recipe.get('skill')
    skill_known = type(skill) is int and skill > 0
    ingredients = recipe.get('ingredients') or []
    reasons = _permission_reasons(recipe.get('craft_allowed'), 'recipe_restrictions_unknown', 'recipe_restricted')
    if not deterministic:
        reasons.append('recipe_output_random' if random_output else 'recipe_output_unknown')
    if not ingredients:
        reasons.append('recipe_ingredients_unknown')
    if not skill_known:
        reasons.append('recipe_skill_unknown')
    elif max_skill is not None and skill > max_skill:
        reasons.append('recipe_skill_above_maximum')
    if not reasons and recipe['recipe_id'] not in confirmed:
        reasons.append('recipe_unconfirmed')
    return {
        **recipe,
        'ingredients': ingredients,
        'restrictions': recipe.get('restrictions') or [],
        'craft_count': _ceiling(quantity, output) if deterministic and ingredients else None,
        'reasons': reasons,
    }


def _craft_route(writ, required, restrictions, quotes, line_for, owned, max_skill, confirmed):
    options = [
        _recipe_option(recipe, required[recipe['item_id']], max_skill, confirmed)
        for recipe in sorted(writ.get('recipes') or [], key=lambda recipe: (recipe['item_id'], recipe['recipe_id']))
        if recipe['item_id'] in required
    ]
    by_item = {item: [] for item in sorted(required)}
    for option in options:
        if option['craft_count'] is not None:
            by_item[option['item_id']].append(option)
    candidates = list(by_item.values())
    if prod(len(group) for group in candidates) > MAX_RECIPE_COMBINATIONS:
        ready = [[option for option in group if not option['reasons']] for group in candidates]
        if all(ready):
            candidates = ready
    if not by_item or not all(candidates):
        recipe_reasons = [reason for option in options for reason in option['reasons']]
        if any(not any(option['item_id'] == item for option in options) for item in required):
            recipe_reasons.append('recipe_unverified')
        route = _route(writ['item_id'], None, [], [*restrictions, *recipe_reasons], quotes, line_for, owned)
    elif prod(len(group) for group in candidates) > MAX_RECIPE_COMBINATIONS:
        route = _route(writ['item_id'], None, [], [*restrictions, 'recipe_combination_limit'], quotes, line_for, owned)
    else:
        best = None
        for recipes in product(*candidates):
            materials = Counter()
            reasons = list(restrictions)
            for recipe in recipes:
                reasons.extend(recipe['reasons'])
                for ingredient in recipe['ingredients']:
                    materials[ingredient['item_id']] += ingredient['quantity'] * recipe['craft_count']
            candidate = _route(writ['item_id'], materials, list(recipes), reasons, quotes, line_for, owned)
            cost = candidate.total if candidate.total is not None else candidate.valuation
            key = (not candidate.details['eligible'], candidate.total is None, cost is None,
                   len(reasons) - len(restrictions), cost or 0)
            if best is None or key < best:
                route = candidate
                best = key
    route.details['recipe_options'] = options
    return route


def price_writ(writ, reputation, quotes, *, owned=False, method: Method = 'cheapest', max_skill=None, confirmed_recipes=()):
    """Choose a supported route before display rounding. Reward eligibility governs ranking only."""
    if method not in ('cheapest', 'craft', 'buy'):
        raise ValueError('Unknown completion method')

    @cache
    def line_for(item, quantity):
        return _price_line(item, quantity, quotes)

    objectives = writ.get('objectives') or []
    required = _quantities(objectives)
    restrictions = _permission_reasons(writ.get('hand_in_allowed'), 'hand_in_unknown', 'hand_in_restricted')
    if not required:
        restrictions.append('no_delivery')
    buy_reasons = [
        reason for objective in objectives for reason in _permission_reasons(
            objective.get('buy_allowed'), 'buyability_unknown', 'buying_not_allowed')
    ]
    buy = _route(writ['item_id'], required or None, [], [*restrictions, *buy_reasons], quotes, line_for, owned)
    craft = _craft_route(writ, required, restrictions, quotes, line_for, owned, max_skill, set(confirmed_recipes))
    routes = {'buy': buy, 'craft': craft}
    considered = routes if method == 'cheapest' else {method: routes[method]}
    selected_method = min(
        (name for name, route in considered.items() if route.details['eligible']),
        key=lambda name: routes[name].total,
        default=None,
    )
    display_method = selected_method if method == 'cheapest' else method
    if display_method is None:
        # Keep priced scenarios visible even if a game or quote safeguard prevents a recommendation.
        estimates = ((name, route.total is None, route.total if route.total is not None else route.valuation)
                     for name, route in considered.items())
        display_method, _, _ = min((entry for entry in estimates if entry[2] is not None),
                                  key=lambda entry: (entry[1], entry[2]), default=(None, None, None))
    displayed = routes.get(display_method)
    if displayed:
        visible = displayed.details
    else:
        purchase, _, purchase_quote = line_for(writ['item_id'], 1)
        visible = {
            **_money(Fraction() if owned else purchase, None, None),
            'purchase_quote': purchase_quote,
            'reasons': list(dict.fromkeys(reason for route in considered.values() for reason in route.details['reasons'])),
        }
    reasons = list(visible['reasons'])
    ratio = None
    if type(reputation) is not int or reputation <= 0:
        reasons.append('unknown_reputation')
    elif selected_method:
        ratio = exact_price(Fraction(routes[selected_method].total) / reputation)
    return {
        **{key: value for key, value in visible.items() if '_cost_' in key or key == 'purchase_quote'},
        'craft': craft.details,
        'buy': buy.details,
        'selected_method': selected_method,
        'selected_recipe_ids': [recipe['recipe_id'] for recipe in craft.details['recipes']] if selected_method == 'craft' else [],
        'display_method': display_method,
        'cost_per_reputation': ratio,
        'eligible': ratio is not None,
        'reasons': reasons,
    }
