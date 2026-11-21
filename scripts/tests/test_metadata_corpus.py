"""Corpus inspection must require independent public consensus, never import names."""
import importlib.util,json
from pathlib import Path
import unittest
from unittest.mock import patch
from datetime import timedelta
spec=importlib.util.spec_from_file_location('metadata_operator',Path(__file__).resolve().parents[1]/'investigate-metadata-providers.py')
operator=importlib.util.module_from_spec(spec);spec.loader.exec_module(operator)

class ReadOnlyPopulation:
    def __init__(self):self.calls=0
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def scalars(self,query):
        self.calls+=1
        return [3283,25] if self.calls==1 else [25]

class CorpusConsensus(unittest.TestCase):
    def record(self,install,name='Battle Chain Tunic',**values):
        return {'kind':'item_seen','itemId':3283,'name':name,'installId':f'pub-{install:032x}',**values}
    def scan(self,records):
        def fetch(*args,**kwargs):
            kwargs['corpus_sink']({'ok':True,'records':records,'offset':0,'total':len(records),'dataAsOf':'2026-11-15T02:10:16Z'})
            return {'attempt_number':1,'category':'observations_only','fixture':{'record_count':len(records),'next':None}}
        with patch.object(operator,'Session',return_value=ReadOnlyPopulation()),patch.object(operator,'probe',side_effect=fetch):
            return operator.scan_corpus(operator.now()+timedelta(minutes=1),27)
    def test_three_distinct_public_contributors_are_required(self):
        result=self.scan([self.record(1),self.record(2),self.record(3)])
        self.assertEqual(result['potential_new_names'][0]['item_id'],3283)
        self.assertEqual(result['new_names_committed'],0)
        self.assertNotIn('pub-',json.dumps(result))
    def test_repeated_install_does_not_establish_consensus(self):
        self.assertEqual(self.scan([self.record(1)]*10)['quorum_items'],0)
    def test_missing_or_nonpublic_identity_is_rejected(self):
        result=self.scan([self.record(1,installId='private-id'),self.record(2,installId=None),self.record(3,installId='other')])
        self.assertEqual(result['rejected_observations'],3);self.assertEqual(result['quorum_items'],0)
    def test_wrong_build_is_not_published(self):
        result=self.scan([self.record(i,clientBuild='12.1.5.70783') for i in (1,2,3)])
        self.assertEqual(result['quorum_items'],0)
    def test_competing_name_quorums_stay_unknown(self):
        result=self.scan([self.record(i,name=name) for i in (1,2,3) for name in ('First name','Second name')])
        self.assertEqual(result['potential_new_names'],[])

if __name__=='__main__':unittest.main()
