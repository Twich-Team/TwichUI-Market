"""Inspection tests for operator safeguards; no live calls or keys."""
from pathlib import Path
import ast
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'investigate-metadata-providers.py'

class InvestigationGuards(unittest.TestCase):
    def test_fixed_cap_and_no_configuration_writes(self):
        tree=ast.parse(SCRIPT.read_text())
        assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign)]
        self.assertTrue(any(any(isinstance(t,ast.Name) and t.id=='CAP' for t in n.targets) and isinstance(n.value,ast.Constant) and n.value.value==200 for n in assignments))
        for node in assignments:
            for target in node.targets:
                if isinstance(target,ast.Attribute):
                    self.assertNotIn(target.attr,('enabled','automatic','hourly_budget','daily_budget','hour_used','day_used','credential','credential_key_id'))
    def test_secrets_and_io_use_existing_safeguards(self):
        source=SCRIPT.read_text()
        for required in ('worker_lock(Session)','reserve_budget(row,now())','credential_value(db,row)','cooldown(row,status','SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY','if now()>=deadline','if used>=CAP'):
            self.assertIn(required,source)
        self.assertNotIn('print(credential',source)
        self.assertNotIn("'Authorization':",source)
    def test_no_raw_response_persistence(self):
        source=SCRIPT.read_text()
        self.assertNotIn("'raw':raw",source)
        self.assertIn("'new_names_committed':new_names",source)
        self.assertIn("if store_validated and category=='named_record' and origin and kind=='item':",source)
        self.assertIn("task.result_json=json.dumps(result)",source)

if __name__=='__main__':unittest.main()
