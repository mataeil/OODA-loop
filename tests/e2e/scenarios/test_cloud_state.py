"""E2E: cloud-routine state persistence across FRESH CLONES.

A `/schedule` cloud routine clones the default branch fresh every run with no
local state carried between runs. OODA-loop's claim is that committing
agent/state/ each cycle (Step 6-D) makes the loop's memory survive that. This
test proves the mechanism with REAL git: run 1 in one clone commits + pushes its
state; run 2 in a SEPARATE fresh clone of the same remote must SEE run 1's state
(cycle_count continuity, decision_log carried) — exactly what a cloud routine
relies on. If this passed only by reusing a working dir it would be meaningless,
so each "run" is a distinct clone of a bare remote.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json   # noqa: E402
from driver.sandbox import make_project        # noqa: E402


def git(*a, cwd):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


class CloudStatePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.remote = self.root / "remote.git"
        git("init", "--bare", "-b", "main", str(self.remote), cwd=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def _clone(self, name):
        d = self.root / name
        git("clone", str(self.remote), str(d), cwd=self.root)
        git("config", "user.email", "e2e@ooda.local", cwd=d)
        git("config", "user.name", "OODA E2E", cwd=d)
        return d

    def test_state_survives_fresh_clone(self):
        # --- Run 1: a fresh clone, seed the project, run a cycle, push state ---
        run1 = self._clone("run1")
        make_project(run1, safety={"min_cycle_interval_minutes": 0, "halt_file": "agent/safety/HALT",
                                   "lock_timeout_minutes": 30, "max_silent_failures": 99})
        git("add", "config.json", "agent", cwd=run1)
        git("commit", "-q", "-m", "seed", cwd=run1)
        git("push", "-q", "origin", "main", cwd=run1)

        e1 = Engine(run1)
        e1.run_cycle("2026-08-01T06:00:00", {"selected_domain": "test_coverage",
                                             "selected_skill": "/check-tests",
                                             "result": "success", "had_output": True})
        self.assertEqual(e1.state()["cycle_count"], 1)
        # 6-D committed agent/state; push it (what a cloud routine does at cycle end)
        git("add", "agent/state", cwd=run1)
        # commit may be a no-op if engine already committed; tolerate
        subprocess.run(["git", "commit", "-q", "-m", "cycle 1 state"], cwd=run1, capture_output=True)
        git("push", "-q", "origin", "main", cwd=run1)

        # --- Run 2: a SEPARATE fresh clone (a new cloud run) ---
        run2 = self._clone("run2")
        self.assertFalse((run2 / "run1").exists())  # genuinely separate working dir
        st2 = read_json(run2 / "agent" / "state" / "evolve" / "state.json")
        self.assertEqual(st2["cycle_count"], 1,
                         "run 2's fresh clone must SEE run 1's committed cycle_count")
        self.assertEqual(len(st2["decision_log"]), 1, "decision_log carried across the clone")
        self.assertEqual(st2["decision_log"][-1]["selected_domain"], "test_coverage")

        # run 2 continues the loop from the persisted state → cycle 2, not 1 again
        e2 = Engine(run2)
        e2.run_cycle("2026-08-01T12:00:00", {"selected_domain": "backlog",
                                             "selected_skill": "/plan-backlog",
                                             "result": "success", "had_output": True})
        self.assertEqual(e2.state()["cycle_count"], 2,
                         "the loop accumulates across fresh-clone runs (no reset)")
        # outcomes.json (the measurement memory) also carried + grew
        outc = read_json(run2 / "agent" / "state" / "evolve" / "outcomes.json")["entries"]
        self.assertEqual(len(outc), 2, "Outcome Record accumulated across the two cloud runs")


if __name__ == "__main__":
    unittest.main()
