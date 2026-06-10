"""E2E: interval skip, HALT gates, saturation + silent-failure breakers
(SKILL.md 0-A / 0-D / 2-A2 / 4-A / 4-B r4 — the "fails stopped" rails)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json, write_json   # noqa: E402
from driver.sandbox import make_project                   # noqa: E402


def hours(n):  # injected clock helper
    return f"2026-06-{1 + n // 24:02d}T{n % 24:02d}:00:00"


class Breakers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = make_project(Path(self.tmp.name))
        self.e = Engine(self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_halt_stops_everything_until_deleted(self):
        self.e._create_halt("operator stop")
        r = self.e.run_cycle(hours(0))
        self.assertEqual(r.status, "skip_halt")
        self.assertFalse(self.e.lock_path.exists(), "0-A exits before 0-B — no lock to leak")
        self.e.halt_path.unlink()
        self.assertEqual(self.e.run_cycle(hours(1)).status, "completed")

    def test_interval_skip_releases_lock(self):
        p2 = make_project(Path(self.tmp.name) / "p2",
                          safety={"min_cycle_interval_minutes": 30,
                                  "halt_file": "agent/safety/HALT",
                                  "lock_timeout_minutes": 30,
                                  "max_silent_failures": 3})
        e2 = Engine(p2)
        self.assertEqual(e2.run_cycle("2026-06-01T00:00:00").status, "completed")
        r = e2.run_cycle("2026-06-01T00:10:00")        # 10m < 30m interval
        self.assertEqual(r.status, "skip_interval")
        self.assertFalse(e2.lock_path.exists(), "v1.3.0 fix: 0-D must delete the lock")
        # next on-time tick proceeds immediately (no 30m stale-lock stall)
        self.assertEqual(e2.run_cycle("2026-06-01T00:31:00").status, "completed")

    def test_interval_bypassed_by_critical_alert(self):
        p3 = make_project(Path(self.tmp.name) / "p3",
                          safety={"min_cycle_interval_minutes": 30,
                                  "halt_file": "agent/safety/HALT",
                                  "lock_timeout_minutes": 30,
                                  "max_silent_failures": 3})
        e3 = Engine(p3)
        e3.run_cycle("2026-06-01T00:00:00")
        write_json(p3 / "agent/state/test_coverage.json",
                   {"status": "critical", "alerts": [{"severity": "critical", "type": "down"}]})
        r = e3.run_cycle("2026-06-01T00:05:00")
        self.assertEqual(r.status, "completed", "critical alert bypasses the interval")

    def test_saturation_warn_boost_halt_and_midcycle_exit(self):
        # seed one pending action so the boost has a target
        write_json(self.e.ev / "action_queue.json",
                   {"pending": [{"id": "a1", "title": "t", "status": "pending",
                                 "rice_score": 10.0, "effective_rice": 10.0}],
                    "completed": []})
        results = []
        for i in range(17):
            results.append(self.e.run_cycle(hours(i), {"had_output": False}))
        # counter evaluates the PREVIOUS cycle ⇒ warn fires on the run after streak hits 5
        warn = [r for r in results if r.has_log("Saturation warning")]
        self.assertTrue(warn, "warn@5 must fire")
        boosted = read_json(self.e.ev / "action_queue.json")["pending"][0]["effective_rice"]
        self.assertEqual(boosted, 15.0, "boost@10 adds implementation_boost (+5.0) once")
        halts = [r for r in results if r.status == "halt_midcycle"]
        self.assertTrue(halts, "saturation HALT must stop the cycle via the 4-A re-check")
        self.assertTrue(self.e.halt_path.exists())
        self.assertFalse(self.e.lock_path.exists(), "v1.3.0 fix: 4-A exit releases the lock")
        # fails stopped: subsequent runs skip at 0-A
        self.assertEqual(self.e.run_cycle(hours(20)).status, "skip_halt")

    def test_silent_failure_breaker(self):
        for i in range(2):
            r = self.e.run_cycle(hours(i), {"result": "error"})
            self.assertEqual(r.status, "completed")
            self.assertFalse(r.halt_created)
        r3 = self.e.run_cycle(hours(2), {"result": "error"})   # 3rd consecutive
        self.assertTrue(r3.halt_created, "max_silent_failures=3 must HALT")
        self.assertEqual(r3.status, "completed", "the HALTing cycle still completes cleanly")
        self.assertEqual(self.e.state()["cycle_count"], 3, "failure was recorded, not lost")
        self.assertFalse(self.e.lock_path.exists())
        self.assertEqual(self.e.run_cycle(hours(3)).status, "skip_halt", "fails stopped")
        gaps = read_json(self.e.ev / "skill_gaps.json")["gaps"]
        self.assertEqual(len(gaps), 3)

    def test_success_resets_silent_failure_counter(self):
        self.e.run_cycle(hours(0), {"result": "error"})
        self.e.run_cycle(hours(1), {"result": "error"})
        self.e.run_cycle(hours(2), {"result": "success"})      # reset
        r = self.e.run_cycle(hours(3), {"result": "error"})
        self.assertFalse(r.halt_created, "counter must reset on success")


if __name__ == "__main__":
    unittest.main()
