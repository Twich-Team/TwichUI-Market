"""Compatibility fixture stays tied to the frozen, strictly validated generation schemas."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from jsonschema import ValidationError
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('contract',ROOT/'contracts/bridge/v1/validate.py')
contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
class CompatibilityPolicy(unittest.TestCase):
    def test_frozen_generations_and_future_contract_refusal(self):
        policy=json.loads((ROOT/'contracts/bridge/compatibility/v1.json').read_text())
        self.assertFalse(policy['marketing_versions_control_compatibility'])
        self.assertEqual(policy['desktop_build_source'],'delivery_receipt.desktop_build')
        for name in ['canonical-generation.json','source-canonical-generation.json']:
            generation=json.loads((ROOT/'contracts/bridge/v1'/name).read_text())
            contract.validate(generation)
            case=next(c for c in policy['cases'] if c['schema']==generation['schema_version'] and c['compatible'])
            self.assertIn(generation['transport_version'],policy['supported_transport_versions'])
            self.assertIn(generation['contract_version'],policy['supported_contract_versions'])
            self.assertEqual(policy['schemas'][str(generation['schema_version'])]['minimum_reader_version'],case['minimum_reader_version'])
            for field in ['transport_version','contract_version','schema_version']:
                changed=copy.deepcopy(generation);changed[field]=99
                with self.assertRaises((ValueError,AssertionError,KeyError,ValidationError)):contract.validate(changed)
