"""Website-only guidance on comparisons between observed asking prices."""


def reference_quality(reference, current, lowest, highest, days):
    if reference is None or reference <= 0:
        return {'state': 'unavailable', 'reason': 'No positive reference is available for this window.'}
    if lowest == 0 or current == 0:
        return {'state': 'needs_review', 'reason': 'A unit ask rounds to zero copper. Check the individual stack costs.'}
    if lowest is not None and highest is not None and highest > 0 and highest >= 100 * lowest:
        return {'state': 'needs_review', 'reason': 'Daily unit asks vary by at least 100×. Check the price history before using this average.'}
    if current is not None and (current >= 10 * reference or reference >= 10 * current):
        return {'state': 'needs_review', 'reason': 'Current unit asks average at least 10× above or below this reference. Check the price history.'}
    if days < 3:
        return {'state': 'limited', 'reason': f'This reference uses only {days} priced UTC day' + ('s.' if days != 1 else '.')}
    return {'state': 'available', 'reason': f'This reference uses asking prices from {days} observed UTC days.'}


def qualify_valuation(valuation):
    # values() orders the final priced observation of each UTC day. Its own
    # market_coverage_days counts exactly those inside the trailing 14 days.
    prices = [row['recent_price'] for row in valuation['history'] if row['recent_price'] is not None]
    for key, field, count in (
        ('reference_quality', 'market_value', valuation['market_coverage_days']),
        ('historical_reference_quality', 'historical_value', valuation['coverage_days']),
    ):
        window = prices[-count:] if count else []
        valuation[key] = reference_quality(valuation[field], valuation['recent_price'],
                                           min(window, default=None), max(window, default=None), count)
