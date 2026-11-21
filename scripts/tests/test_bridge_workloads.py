"""Independent schema/semantic checks for opt-in synthetic capacity workloads."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"scripts"))
import bridge_workloads as w

spec = importlib.util.spec_from_file_location("capacity_contract", ROOT/"contracts/bridge/v1/validate.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class Workloads(unittest.TestCase):
    def test_all_shapes_conform_without_inventing_prices(self):
        for profile in w.PROFILES:
            with self.subTest(profile=profile):
                g, metadata = w.generate(20, profile)
                contract.validate(g)
                self.assertTrue(g["synthetic"])
                self.assertTrue(all(o["synthetic"] for o in g["observations"]))
                self.assertEqual(metadata["canonical_bytes"], len(w.canonical(g)))
                for r in g["records"]:
                    for d in r["daily"]:
                        self.assertEqual(d["recent_copper"], "100" if d["state"]=="listed" else None)
        g,_ = w.generate(20,"historical-only")
        self.assertTrue(all(r["current"]["state"]=="absent" and r["distribution"] is None for r in g["records"]))
        g,_ = w.generate(20,"mixed-provisional")
        self.assertTrue(any(d["state"]=="unknown" for r in g["records"] for d in r["daily"]))

    def test_dates_and_variants_are_deterministic(self):
        a,ma = w.generate(25,"two-gap")
        b,mb = w.generate(25,"two-gap")
        self.assertEqual(w.canonical(a),w.canonical(b))
        self.assertEqual(ma,mb)
        self.assertEqual(ma["observation_dates"],["2026-11-13","2026-11-15"])
        self.assertEqual(len({r["variant_key"] for r in a["records"]}),25)
        g,_ = w.generate(20,"sixty")
        self.assertEqual(len(g["records"][-1]["daily"]),60)

    def test_oversized_workload_is_refused_not_pruned(self):
        # Exercise the exact preflight boundary with a small workload. This
        # changes the generator's test-only budget, never a producer contract.
        old = w.MAX_BYTES
        try:
            w.MAX_BYTES = 3000
            g,metadata = w.generate(20,"sixty")
        finally:
            w.MAX_BYTES = old
        self.assertIsNone(g)
        self.assertEqual(metadata["eligible_records"],20)
        self.assertEqual(metadata["materialized_export_records"],0)
        self.assertEqual(metadata["status"],"refused_contract_bytes")
        self.assertGreater(metadata["canonical_bytes"],old//1000)


if __name__=="__main__":
    unittest.main()
