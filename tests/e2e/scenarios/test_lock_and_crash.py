"""E2E: lock lifecycle + crash self-healing (SKILL.md 0-B / 0-C, v1.3.0)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json   # noqa: E402
from driver.sandbox import make_project       # noqa: E402

T0 = "2026-06-01T00:00:00"


class LockAndCrash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = make_project(Path(self.tmp.name))
        self.e = Engine(self.p)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_cycles_leave_no_lock(self):
        for h in range(3):
            r = self.e.run_cycle(f"2026-06-01T0{h}:00:00")
            self.assertEqual(r.status, "completed")
            self.assertFalse(self.e.lock_path.exists(), "lock must be released at end of Step 6")
        self.assertEqual(self.e.state()["cycle_count"], 3)

    def test_live_lock_blocks_without_deletion(self):
        self.e.simulate_crash(T0)                      # lock created at T0
        r = self.e.run_cycle("2026-06-01T00:10:00")    # 10m < 30m timeout
        self.assertEqual(r.status, "skip_locked")
        self.assertTrue(self.e.lock_path.exists(), "a LIVE lock must never be deleted")

    def test_stale_lock_self_heals_with_crash_recovery(self):
        self.e.run_cycle(T0)                           # one completed cycle for context
        self.e.simulate_crash("2026-06-01T01:00:00")
        r = self.e.run_cycle("2026-06-01T02:00:00")    # 60m > 30m timeout
        self.assertEqual(r.status, "completed", "self-heal must not require manual rm")
        self.assertTrue(r.stale_lock_removed)
        self.assertTrue(r.crash_recovered)
        # 0-C diagnostics fix: the CRASHED cycle is cycle_count+1, not the last completed
        self.assertTrue(r.has_log("Cycle #2 did not complete"), r.logs)
        memos = read_json(self.e.ev / "memos.json")
        rec = [m for m in memos["history"] if m.get("type") == "crash_recovery"]
        self.assertEqual(rec[-1]["cycle"], 2)
        self.assertEqual(rec[-1]["last_completed"], 1)
        self.assertFalse(self.e.lock_path.exists())

    def test_real_sigkill_then_recovery(self):
        """Real child process acquires the lock, is SIGKILL'd, debris recovered."""
        self.e.run_cycle(T0)
        self.e.spawn_and_kill_real_cycle("2026-06-01T01:00:00")
        self.assertTrue(self.e.lock_path.exists(), "killed process leaves the lock")
        self.assertTrue(self.e.state()["cycle_in_progress"])
        r = self.e.run_cycle("2026-06-01T01:31:00")    # past the 30m timeout
        self.assertEqual(r.status, "completed")
        self.assertTrue(r.crash_recovered)
        self.assertFalse(self.e.lock_path.exists())


if __name__ == "__main__":
    unittest.main()
