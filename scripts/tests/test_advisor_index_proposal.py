import copy
import importlib.util
from pathlib import Path
import unittest
import jsonschema
spec=importlib.util.spec_from_file_location('advisor_index_feasibility',Path(__file__).resolve().parents[1]/'advisor_index_feasibility.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class AdvisorIndexProposal(unittest.TestCase):
    def test_summary_coverage_independent_of_detailed_selection_and_missing_not_zero(self):
        g=p.generate(10);self.assertTrue(p.validate(g))
        # No detailed-history member list is necessary for broad price evidence.
        self.assertNotIn('scope',g);self.assertEqual(g['coverage']['detailed_history'],'independent')
        self.assertEqual(p.lookup(g,10000,g['records'][0][1]),{'state':'priced','price':'10000'})
        self.assertEqual(p.lookup(g,999,'0'*64),{'state':'unavailable','price':None})
        self.assertEqual(p.lookup(g,10002,g['records'][2][1]),{'state':'absent','price':None})
        self.assertEqual(p.lookup(g,10004,g['records'][4][1]),{'state':'unsupported','price':None})
        self.assertEqual(p.lookup(g,10000,'0'*64)['state'],'unavailable')
    def test_provenance_cannot_impersonate_local_competition_and_future_version_refused(self):
        g=p.generate(10);self.assertEqual(g['confidence_ceiling'],'limited');self.assertFalse(g['can_satisfy_local_competition'])
        for key,value in [('schema_version',2),('can_satisfy_local_competition',True),('source_kind','local_scan')]:
            bad=copy.deepcopy(g);bad[key]=value
            with self.assertRaises(jsonschema.ValidationError):p.validate(bad)
    def test_zero_and_corrupt_price_are_refused(self):
        g=p.generate(10);g['records'][0][3]='0'
        with self.assertRaises(jsonschema.ValidationError):p.validate(g)
        g=p.generate(10);g['records'][0][3]='10100'
        with self.assertRaises(AssertionError):p.validate(g)
