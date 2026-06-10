"""E2E: cost ledger — daily UTC reset, 6-C8 gap backfill, corrupt ⇒ fail-closed
(SKILL.md Step 0-Pre / 6-C5b / 6-C8, v1.3.0 missing-vs-corrupt policy)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json   # noqa: E402
from driver.sandbox import make_project       # noqa: E402


class CostLedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = make_project(Path(self.tmp.name))
        self.e = Engine(self.p)
        self.lp = self.e.ev / "cost_ledger.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_entries_accumulate_and_daily_reset(self):
        self.e.run_cycle("2026-06-01T10:00:00")
        self.e.run_cycle("2026-06-01T12:00:00")
        led = read_json(self.lp)
        self.assertEqual(len(led["entries"]), 2)
        self.assertAlmostEqual(led["total_estimated_usd"], 0.04)
        # UTC date rolls over ⇒ reset, then today's entry only
        self.e.run_cycle("2026-06-02T01:00:00")
        led = read_json(self.lp)
        self.assertEqual(led["date"], "2026-06-02")
        self.assertAlmostEqual(led["total_estimated_usd"], 0.02)

    def test_gap_backfill(self):
        for h in (1, 2, 3, 4):
            self.e.run_cycle(f"2026-06-01T0{h}:00:00")
        led = read_json(self.lp)
        led["entries"] = [e for e in led["entries"] if e["cycle_id"] in (1, 4)]  # drop 2,3
        from driver.engine import write_json
        write_json(self.lp, led)
        r = self.e.run_cycle("2026-06-01T05:00:00")
        self.assertTrue(r.has_log("backfilled 2 cycle(s)"), r.logs)
        led = read_json(self.lp)
        self.assertEqual({e["cycle_id"] for e in led["entries"]}, {1, 2, 3, 4, 5})
        synth = [e for e in led["entries"] if e.get("synthetic")]
        self.assertEqual({e["cycle_id"] for e in synth}, {2, 3})

    def test_corrupt_ledger_fails_closed(self):
        self.e.run_cycle("2026-06-01T01:00:00")
        self.lp.write_text("{not json!!")
        r = self.e.run_cycle("2026-06-01T02:00:00")
        self.assertEqual(r.status, "halt_corrupt_ledger")
        self.assertTrue(self.e.halt_path.exists(), "corrupt ledger must HALT (fail closed)")
        self.assertTrue(self.lp.with_suffix(".json.corrupt").exists(), "evidence preserved")
        self.assertFalse(self.lp.exists(), "must NOT be recreated at $0.00 mid-day")
        self.assertFalse(self.e.lock_path.exists(), "no lock leak on this exit path")
        self.assertEqual(self.e.run_cycle("2026-06-01T03:00:00").status, "skip_halt")


if __name__ == "__main__":
    unittest.main()
