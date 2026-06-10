"""E2E: 6-D git commit (real repo, explicit staging, #31 guard) + action-queue
lifecycle hygiene (SKILL.md 6-D / 6-C6, v1.3.0)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from driver.engine import Engine, read_json, write_json   # noqa: E402
from driver.sandbox import make_project                   # noqa: E402


def git_log(p):
    out = subprocess.run(["git", "log", "--oneline"], cwd=p, capture_output=True, text=True)
    return out.stdout.strip().splitlines()


class GitAndLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_6d_commits_state_with_explicit_staging(self):
        p = make_project(Path(self.tmp.name) / "ok", git=True)
        e = Engine(p)
        r = e.run_cycle("2026-06-01T01:00:00")
        self.assertTrue(r.committed, "state must be committed in a tracked repo")
        self.assertIn("evolve: cycle #1 state", git_log(p)[0])
        # untracked junk must NOT be swept in (explicit staging, never -A)
        (p / "SECRET.txt").write_text("hunter2")
        e.run_cycle("2026-06-01T02:00:00")
        shown = subprocess.run(["git", "show", "--stat", "HEAD"], cwd=p,
                               capture_output=True, text=True).stdout
        self.assertNotIn("SECRET.txt", shown)

    def test_6d_gitignored_state_warns_and_skips(self):
        p = make_project(Path(self.tmp.name) / "ignored", git=True, gitignore_state=True)
        e = Engine(p)
        before = len(git_log(p))
        r = e.run_cycle("2026-06-01T01:00:00")
        self.assertEqual(r.status, "completed")
        self.assertFalse(r.committed)
        self.assertTrue(r.has_log("gitignored — state commits are NO-OPs"), r.logs)
        self.assertEqual(len(git_log(p)), before, "no commit staged into the void")

    def test_action_lifecycle_hygiene(self):
        p = make_project(Path(self.tmp.name) / "aq")
        e = Engine(p)
        write_json(e.ev / "action_queue.json", {"pending": [
            {"id": "a1", "title": "orphan", "status": "in_progress", "claimed_cycle": 0},
            {"id": "a2", "title": "stuck", "status": "blocked"},
            {"id": "a3", "title": "fine", "status": "pending"},
        ], "completed": []})
        r = e.run_cycle("2026-06-01T01:00:00")
        q = read_json(e.ev / "action_queue.json")
        by_id = {i["id"]: i for i in q["pending"]}
        self.assertEqual(by_id["a1"]["status"], "pending", "orphaned in_progress re-queued")
        self.assertNotIn("a2", by_id, "blocked items leave pending[]")
        self.assertEqual(q["completed"][0]["id"], "a2")
        self.assertEqual(q["completed"][0]["status"], "blocked")
        self.assertTrue(r.has_log("Re-queued orphaned action"))


if __name__ == "__main__":
    unittest.main()
