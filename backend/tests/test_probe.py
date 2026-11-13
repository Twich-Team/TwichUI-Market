import json
import unittest
from market.probe import summarize, targets


class ProbeTests(unittest.TestCase):
    def test_trailing_slash_and_scoped_commodities(self):
        paths = targets(2, 113)
        self.assertIn('/data/wow/ruleset/2/auctions/', paths)
        self.assertEqual(paths[-1], '/data/wow/ruleset/2/auctions/113/commodities')

    def test_synthetic_summary(self):
        body = json.dumps({'auctions': [{'id': 1, 'item': {'id': 2}, 'quantity': 4, 'unit_price': 90}]}).encode()
        result = summarize(body)
        self.assertEqual(result['auctions_count'], 1)
        self.assertEqual(result['auction_fields'], ['id', 'item', 'quantity', 'unit_price'])
        self.assertNotIn('90', json.dumps(result))

    def test_empty_house_and_invalid_payload(self):
        self.assertEqual(summarize(b'{"id":112}'), {'keys': ['id']})
        with self.assertRaises(ValueError):
            summarize(b'[]')
