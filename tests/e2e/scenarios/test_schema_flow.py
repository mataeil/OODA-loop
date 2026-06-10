"""E2E: multi-cycle state flow — canonical decision_log keys, working-memory
cap, weekly episodes exactly-once, cross-tier reference reuse
(SKILL.md Step 6 / Tier 2 episodes, v1.3.0 canonicalization)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine   # noqa: E402
from driver.sandbox import make_project   # noqa: E402

REPO = Path(__file__).resolve().parents[3]


class SchemaFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = make_project(Path(self.tmp.name), memory={"working_memory_size": 5})
        self.e = Engine(self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_decision_log_canonical_keys_and_cap(self):
        for d in range(8):   # strictly monotonic clock — one cycle per day
            self.e.run_cycle(f"2026-06-{d + 1:02d}T06:00:00",
                             {"selected_domain": "test_coverage"})
        log = self.e.state()["decision_log"]
        self.assertEqual(len(log), 5, "working_memory_size cap enforced")
        for entry in log:
            self.assertIn("selected_domain", entry)
            self.assertIn("selected_skill", entry)
            self.assertNotIn("domain", entry, "bare legacy key must not be written")
        self.assertEqual(self.e.state()["cycle_count"], 8, "cap trims the log, not the count")

    def test_weekly_episode_exactly_once(self):
        # week 2026-W23: Mon Jun 1 .. Sun Jun 7 ; W24 starts Mon Jun 8
        for d in (1, 3, 5):
            self.e.run_cycle(f"2026-06-0{d}T06:00:00")
        for d in (8, 9, 10, 11):                       # four cycles in the NEXT week
            self.e.run_cycle(f"2026-06-{d:02d}T06:00:00")
        eps = json.loads((self.e.ev / "episodes.json").read_text())["episodes"]
        w23 = [e for e in eps if e["id"] == "EP-2026-W23"]
        self.assertEqual(len(w23), 1, "exactly ONE episode per completed week — "
                                      "the v1.3.0 duplicate-generation fix")
        self.assertEqual(w23[0]["total_cycles"], 3)
        self.assertEqual(w23[0]["domains_selected"], {"test_coverage": 3})

    def test_cross_tier_reference_reuse(self):
        """The deterministic Tier-0 references must be importable and agree
        inside the same isolated environment (auto-merge gate spot-check)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "amg", REPO / "scripts" / "auto_merge_gate.py")
        amg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(amg)
        cfg = json.loads((REPO / "tests" / "auto-merge-gating" / "seed" / "config.json").read_text())
        ok, _ = amg.eligible(cfg, {"isDraft": False, "files": ["src/x.py"],
                                   "changedFiles": 1, "additions": 3, "deletions": 0,
                                   "tests": "passed"})
        self.assertTrue(ok)
        held, why = amg.eligible(cfg, {"isDraft": False, "files": ["src/x.py"],
                                       "changedFiles": 1, "additions": 3, "deletions": 0,
                                       "tests": "passed", "protected_blocked": True})
        self.assertFalse(held, why)


if __name__ == "__main__":
    unittest.main()
