"""Crafting Writ pricing with exact asking prices and explicit game eligibility."""
from collections import Counter
from datetime import timedelta
from fractions import Fraction
from itertools import product

import pytest

from market import writ_pricing
from market.db import now
from market.waylaid_pricing import ItemQuote, QuoteBook, load_quotes
from market.writ_pricing import price_writ
from test_waylaid_pricing import auction, market, snapshot


def current(unit, lots, source='auctions'):
    lots = Counter(lots)
    return ItemQuote(
        unit=Fraction(unit), exact_minimum=Fraction(unit), status='available', source_kind=source,
        depth_known=True, lots=lots, priced_quantity=sum(size * count for size, count in lots.items()),
    )


def book(items, basis='current', **kwargs):
    return QuoteBook(basis, items, freshness=kwargs.pop('freshness', 'current'),
                     verified=kwargs.pop('verified', True), **kwargs)


def recipe(recipe_id, item_id, output, ingredients, skill=25, craft_allowed=True, **kwargs):
    return dict(
        recipe_id=recipe_id, item_id=item_id, output_quantity=output, skill=skill,
        ingredients=[dict(item_id=item, quantity=amount) for item, amount in ingredients.items()],
        craft_allowed=craft_allowed, **kwargs,
    )


def writ(objectives, recipes=(), *, hand_in_allowed=True, buy_allowed=True):
    return dict(
        item_id=1,
        objectives=[dict(item_id=item, quantity=quantity, buy_allowed=buy_allowed)
                    for item, quantity in objectives.items()],
        recipes=list(recipes), hand_in_allowed=hand_in_allowed,
    )


def test_combined_baskets_choose_recipes_using_correct_batch_counts_and_shared_ingredients():
    definition = writ({2: 5, 3: 2}, [
        recipe(102, 2, 5, {11: 1}),
        recipe(101, 2, 3, {10: 1}),
        recipe(201, 3, 2, {10: 3}),
    ])
    quotes = book({
        1: current(3, {3: 1}),
        2: current(30, {5: 1}),
        3: current(15, {2: 1}),
        10: current(2, {5: 1}),
        11: current(6, {1: 1}),
    })
    result = price_writ(definition, 7, quotes, confirmed_recipes=[101, 102, 201], max_skill=25)
    assert result['selected_method'] == 'craft' and result['selected_recipe_ids'] == [101, 201]
    assert result['purchase_cost_copper'] == '9' and result['completion_cost_copper'] == '10'
    assert result['total_cost_copper'] == '19' and result['cost_per_reputation'] == {
        'numerator_copper': '19', 'denominator': 7,
    }
    assert result['valuation_total_cost_copper'] == '13'
    craft = result['craft']
    assert [(r['craft_count'], r['output_quantity']) for r in craft['recipes']] == [(2, 3), (1, 2)]
    assert [(r['item_id'], r['quantity']) for r in craft['materials']] == [(10, 5)]
    assert craft['materials'][0]['stacks'] == [{'quantity': 5, 'count': 1}]
    assert result['purchase_quote']['leftover_quantity'] == 2
    assert result['buy']['completion_cost_copper'] == '180'


def test_a_whole_stack_can_supply_the_writ_and_a_reagent_only_once():
    definition = writ({2: 1}, [recipe(101, 2, 1, {1: 3})])
    quotes = book({1: current(8, {5: 1})})
    result = price_writ(definition, 20, quotes, method='craft', confirmed_recipes=[101])
    assert result['purchase_cost_copper'] == '40' and result['completion_cost_copper'] == '0'
    assert result['total_cost_copper'] == '40' and result['eligible']
    basket, = result['craft']['basket']
    assert (basket['quantity'], basket['purchased_quantity'], basket['leftover_quantity']) == (4, 5, 1)
    material, = result['craft']['materials']
    assert material['purchased_quantity'] == 0 and material['covered_by_writ_quantity'] == 3
    assert material['minimum_purchase_copper'] == '0' and result['purchase_quote']['leftover_quantity'] == 1

    quotes.items[1] = current(8, {3: 1})
    shortage = price_writ(definition, 20, quotes, method='craft', confirmed_recipes=[101])
    assert shortage['purchase_cost_copper'] == '24' and shortage['total_cost_copper'] is None
    assert shortage['valuation_total_cost_copper'] == '32'
    assert shortage['reasons'] == ['insufficient_at_minimum'] and not shortage['eligible']

    owned = price_writ(definition, 20, quotes, owned=True, method='craft', confirmed_recipes=[101])
    assert owned['purchase_cost_copper'] == '0' and owned['completion_cost_copper'] == '24'
    assert owned['cost_per_reputation'] == {'numerator_copper': '6', 'denominator': 5}


def test_current_supports_partial_commodities_and_never_uses_additional_units_above_the_minimum(database):
    at = now() - timedelta(seconds=1)
    with database.begin() as db:
        auctions = market(db)
        snapshot(db, auctions, at, [
            auction(1, 1, 2),
            auction(2, 4, 10), auction(2, 5, 100),
            {'item': {'id': 2}, 'quantity': 50, 'bid': 1},
            {'item': {'id': 2, 'bonus_lists': [1]}, 'quantity': 100, 'buyout': 100},
        ], 'writ-auction-depth')
        quotes = load_quotes(db, auctions, [1, 2], 'current', at=at)
        overshoot = price_writ(writ({2: 3}), 10, quotes, method='buy')
        line, = overshoot['buy']['materials']
        assert line['stock_status'] == 'whole_stack_overshoot' and line['purchased_quantity'] == 4
        assert line['leftover_quantity'] == 1 and line['minimum_purchase_copper'] == '10'
        assert line['subtotal_exact'] == {'numerator_copper': '15', 'denominator': 2}
        assert overshoot['total_cost_copper'] == '12' and overshoot['valuation_total_cost_copper'] == '10'
        assert 'synthetic_observations' in overshoot['reasons'] and not overshoot['eligible']
        low_stock = price_writ(writ({2: 5}), 10, quotes, method='buy')
        assert low_stock['total_cost_copper'] is None and low_stock['valuation_total_cost_copper'] == '15'
        assert low_stock['buy']['materials'][0]['available_at_minimum'] == 4
        assert low_stock['buy']['materials'][0]['current_priced_quantity'] == 9
        assert 'insufficient_at_minimum' in low_stock['reasons']

        commodities = market(db, house=101, kind='commodities')
        snapshot(db, commodities, at, [
            {'item': {'id': 2}, 'quantity': 9, 'unit_price': 3},
            {'item': {'id': 2}, 'quantity': 15, 'unit_price': 4},
        ], 'writ-commodity-depth')
        quotes = load_quotes(db, commodities, [2], 'current', at=at)
        partial = price_writ(writ({2: 5}), 10, quotes, owned=True, method='buy')
        line, = partial['buy']['materials']
        assert line['purchased_quantity'] == 5 and line['stacks'] is None
        assert line['minimum_purchase_copper'] == '15' and line['available_at_minimum'] == 9


def test_reference_can_change_the_winner_and_reuses_market_price_quality():
    definition = writ({2: 1}, [recipe(101, 2, 1, {3: 1})])
    live = book({1: current(2, {1: 1}), 2: current(9, {1: 1}), 3: current(5, {5: 1})})
    history = book({i: ItemQuote(unit=unit, status='available', coverage_days=4)
                    for i, unit in {1: 2, 2: 50, 3: 3}.items()}, basis='14d')
    regional = book({i: ItemQuote(status='regional_unavailable') for i in [1, 2, 3]}, basis='regional')

    current_result = price_writ(definition, 10, live, confirmed_recipes=[101])
    assert current_result['selected_method'] == 'buy' and current_result['total_cost_copper'] == '11'
    current_craft = price_writ(definition, 10, live, method='craft', confirmed_recipes=[101])
    assert current_craft['selected_method'] == 'craft' and current_craft['total_cost_copper'] == '27'

    historical = price_writ(definition, 10, history, confirmed_recipes=[101])
    assert historical['selected_method'] == 'craft' and historical['total_cost_copper'] == '5'
    assert historical['craft']['materials'][0]['stock_status'] == 'reference'
    assert historical['craft']['materials'][0]['minimum_purchase_copper'] is None
    history.items[3].status = 'limited'
    assert price_writ(definition, 10, history, confirmed_recipes=[101])['selected_method'] == 'buy'
    limited = price_writ(definition, 10, history, method='craft', confirmed_recipes=[101])
    assert limited['total_cost_copper'] == '5' and not limited['eligible'] and limited['reasons'] == ['limited']

    unavailable = price_writ(definition, 10, regional, confirmed_recipes=[101])
    assert unavailable['selected_method'] is None and unavailable['total_cost_copper'] is None
    assert 'regional_unavailable' in unavailable['reasons']


def test_random_yield_unknown_skill_or_restrictions_and_unconfirmed_recipe_cannot_win():
    definition = writ({2: 1}, [
        recipe(101, 2, 1, {3: 1}, output_min=1, output_max=3),
        recipe(102, 2, 1, {3: 1}, skill=None),
        recipe(103, 2, 1, {3: 1}, craft_allowed=None),
        recipe(104, 2, 1, {3: 1}, skill=75),
        recipe(105, 2, 1, {3: 1}, skill=50),
        recipe(106, 2, 1, {3: 1}, output_min=2, output_max=2),
    ])
    quotes = book({1: current(1, {1: 1}), 2: current(15, {1: 1}), 3: current(2, {1: 1})})
    result = price_writ(definition, 10, quotes, confirmed_recipes=[101, 102, 103, 104], max_skill=70)
    assert result['selected_method'] == 'buy'
    assert result['craft']['total_cost_copper'] == '3'
    assert [option['reasons'] for option in result['craft']['recipe_options']] == [
        ['recipe_output_random'], ['recipe_skill_unknown'], ['recipe_restrictions_unknown'],
        ['recipe_skill_above_maximum'], ['recipe_unconfirmed'], ['recipe_output_unknown'],
    ]
    assert result['craft']['recipe_options'][0]['craft_count'] is None
    assert price_writ(definition, 10, quotes, confirmed_recipes=[105])['selected_recipe_ids'] == [105]

    definition['objectives'][0]['buy_allowed'] = None
    restricted_buy = price_writ(definition, 10, quotes, method='buy')
    assert restricted_buy['display_method'] == 'buy' and restricted_buy['selected_method'] is None
    assert restricted_buy['total_cost_copper'] == '16' and restricted_buy['reasons'] == ['buyability_unknown']
    definition['hand_in_allowed'] = False
    restricted_quest = price_writ(definition, 10, quotes, confirmed_recipes=[105], method='craft')
    assert restricted_quest['selected_method'] is None and restricted_quest['reasons'] == ['hand_in_restricted']


def test_missing_prices_stale_quotes_and_unknown_base_reward_never_create_a_rank():
    definition = writ({2: 1}, [recipe(101, 2, 1, {3: 1})])
    quotes = book({2: current(2**53 + 7, {1: 1})})
    unowned = price_writ(definition, 3, quotes, method='buy')
    assert unowned['completion_cost_copper'] == str(2**53 + 7) and unowned['total_cost_copper'] is None
    no_reward = price_writ(definition, None, quotes, owned=True)
    assert no_reward['selected_method'] == 'buy' and no_reward['total_cost_copper'] == str(2**53 + 7)
    assert no_reward['cost_per_reputation'] is None and no_reward['reasons'] == ['unknown_reputation']
    exact = price_writ(definition, 7, quotes, owned=True)['cost_per_reputation']
    assert Fraction(int(exact['numerator_copper']), exact['denominator']) == Fraction(2**53 + 7, 7)
    quotes.freshness = 'stale'
    quotes.verified = False
    old = price_writ(definition, 3, quotes, owned=True, method='buy')
    assert old['total_cost_copper'] == str(2**53 + 7) and old['cost_per_reputation'] is None
    assert old['reasons'] == ['stale_freshness', 'unverified_market']


def test_stack_optimization_uses_the_minimum_feasible_quantity_and_respects_multiplicities():
    for sizes in [(2, 3, 4), (3, 4, 20), (3, 11, 17), (6, 9, 27)]:
        for counts in product(range(1, 4), repeat=3):
            lots = dict(zip(sizes, counts))
            possible = [sum(size * units for size, units in zip(sizes, selected))
                        for selected in product(*(range(count + 1) for count in counts))]
            for demand in range(1, max(possible) + 1):
                basket = writ_pricing._minimum_stacks(lots, demand)
                assert sum(size * count for size, count in basket) == min(q for q in possible if q >= demand)
                assert all(lots[size] >= count > 0 for size, count in basket)


def test_basket_search_limit_displays_valuation_without_claiming_purchase(monkeypatch):
    monkeypatch.setattr(writ_pricing, 'MAX_BASKET_STATES', 100)
    quotes = book({2: current(1, {49: 3, 86: 2, 200: 1})})
    result = price_writ(writ({2: 154}), 10, quotes, owned=True, method='buy')
    assert result['reasons'] == ['basket_search_limit'] and result['total_cost_copper'] is None
    assert result['valuation_total_cost_copper'] == '154' and not result['eligible']


def test_cheapest_view_displays_caveated_baskets_before_unit_valuations():
    definition = writ({2: 5}, [recipe(101, 2, 5, {3: 2})], buy_allowed=None)
    quotes = book({1: current(1, {1: 1}), 2: current(10, {5: 1}), 3: current(1, {1: 1})})
    result = price_writ(definition, 10, quotes, confirmed_recipes=[101])
    assert result['selected_method'] is None and result['display_method'] == 'buy'
    assert result['total_cost_copper'] == '51' and result['cost_per_reputation'] is None
    assert result['reasons'] == ['buyability_unknown']

    quotes.items.pop(2)
    result = price_writ(definition, 10, quotes, confirmed_recipes=[101])
    assert result['selected_method'] is None and result['display_method'] == 'craft'
    assert result['total_cost_exact'] is None and result['valuation_total_cost_exact'] == {
        'numerator_copper': '3', 'denominator': 1,
    }
    assert result['reasons'] == ['insufficient_at_minimum']


def test_recipe_search_limit_preserves_a_fully_confirmed_combination(monkeypatch):
    monkeypatch.setattr(writ_pricing, 'MAX_RECIPE_COMBINATIONS', 1)
    definition = writ({2: 1}, [recipe(101, 2, 1, {3: 1}), recipe(102, 2, 1, {3: 1})])
    quotes = book({3: current(1, {1: 1})})
    result = price_writ(definition, 30, quotes, owned=True, confirmed_recipes=[101])
    assert result['selected_recipe_ids'] == [101]
    bounded = price_writ(definition, 30, quotes, owned=True, confirmed_recipes=[101, 102], method='craft')
    assert bounded['reasons'] == ['recipe_combination_limit'] and not bounded['eligible']


@pytest.mark.parametrize('skill, expected', [(25, [102]), (50, [101])])
def test_multiple_recipes_choose_actual_cheapest_with_skill_filter(skill, expected):
    definition = writ({2: 1}, [
        recipe(101, 2, 1, {3: 1}, skill=50),
        recipe(102, 2, 1, {4: 1}, skill=25),
    ])
    quotes = book({3: current(20, {1: 1}), 4: current(25, {1: 1})})
    result = price_writ(definition, 30, quotes, owned=True, max_skill=skill, confirmed_recipes=[101, 102])
    assert result['selected_recipe_ids'] == expected
