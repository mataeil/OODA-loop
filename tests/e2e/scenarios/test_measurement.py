"""E2E: the v1.4.0 measurement stack end-to-end — Outcome Record accumulates
across real cycles and the Loop Scorecard computes correct KPIs from it
(SKILL.md Step 6-C9 + scripts/loop_scorecard.py)."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json   # noqa: E402
from driver.sandbox import make_project        # noqa: E402

REPO = Path(__file__).resolve().parents[3]


def _scorecard():
    spec = importlib.util.spec_from_file_location("sc", REPO / "scripts" / "loop_scorecard.py")
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    return sc


class Measurement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = make_project(Path(self.tmp.name))
        self.e = Engine(self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def _h(self, n):
        return f"2026-06-{1 + n:02d}T06:00:00"

    def test_outcome_record_accumulates_per_cycle(self):
        # mix of outcomes across real driver cycles
        self.e.run_cycle(self._h(0), {"result": "success", "had_output": True})   # action_extracted
        self.e.run_cycle(self._h(1), {"result": "success", "had_output": False})  # futile
        self.e.run_cycle(self._h(2), {"result": "success", "pr_number": 9, "had_output": True})  # pr_created
        outc = read_json(self.e.ev / "outcomes.json")["entries"]
        self.assertEqual([o["result_type"] for o in outc],
                         ["action_extracted", "futile", "pr_created"])
        self.assertEqual([o["quality_multiplier"] for o in outc], [0.2, 0.0, 0.5])
        # cycle_log.jsonl is append-only, one line per cycle
        lines = (self.e.ev / "cycle_log.jsonl").read_text().strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(json.loads(lines[-1])["result_type"], "pr_created")

    def test_scorecard_computes_from_real_outcomes(self):
        for n, o in enumerate([
            {"result": "success", "had_output": True},                 # 0.2
            {"result": "success", "pr_number": 9, "had_output": True},  # 0.5
            {"result": "success", "had_output": False},                 # 0.0
        ]):
            self.e.run_cycle(self._h(n), o)
        sc = _scorecard()
        s = sc.compute(self.p)
        self.assertEqual(s["cycles_scored"], 3)
        self.assertAlmostEqual(s["loop_value_score"], round((0.2 + 0.5 + 0.0) / 3, 3))
        self.assertEqual(s["futile_cycle_rate_pct"], 33.3)
        # render must not crash and carries the headline
        self.assertIn("Loop Value Score", sc.render(self.p))

    def test_scorecard_graceful_on_fresh_project(self):
        sc = _scorecard()
        s = sc.compute(self.p)   # no cycles run
        self.assertIsNone(s["loop_value_score"])
        self.assertEqual(s["cycles_scored"], 0)
        self.assertIn("no outcomes recorded yet", sc.render(self.p))


if __name__ == "__main__":
    unittest.main()
