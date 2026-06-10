"""Sandbox project builder — writes the minimal downstream project that
/ooda-setup would produce (canonical init shapes, per ooda-setup SKILL.md)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .engine import write_json


def make_project(root: Path, *, git: bool = False, gitignore_state: bool = False,
                 **cfg_overrides) -> Path:
    p = Path(root)
    ev = p / "agent" / "state" / "evolve"
    ev.mkdir(parents=True, exist_ok=True)
    (p / "agent" / "safety").mkdir(parents=True, exist_ok=True)

    cfg = {
        "schema_version": "1.2.0",
        "project": {"name": "e2e-sandbox", "locale": "en", "timezone": "UTC"},
        "domains": {
            "test_coverage": {"weight": 1.0, "status": "active", "enabled": True,
                              "primary_skill": "/check-tests", "fallback": True,
                              "state_file": "agent/state/test_coverage.json"},
        },
        "implementation": {"enabled": False},
        "progressive_complexity": {"current_level": 1, "levels": {}},
        "safety": {
            "halt_file": "agent/safety/HALT",
            "min_cycle_interval_minutes": 0,
            "lock_timeout_minutes": 30,
            "max_silent_failures": 3,
            "max_prs_per_cycle": 1,
            "protected_paths": ["agent/safety/*", "skills/evolve/*"],
        },
        "saturation": {"warn_threshold": 5, "boost_threshold": 10,
                       "halt_threshold": 15, "auto_halt": True,
                       "implementation_boost": 5.0},
        "memory": {"working_memory_size": 20},
        "cost": {"daily_limit_usd": 10.0, "max_backfill_cycles": 100},
    }
    for key, val in cfg_overrides.items():        # shallow section overrides
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(val)
        else:
            cfg[key] = val
    write_json(p / "config.json", cfg)

    # canonical init files (ooda-setup "Initialize state files" list)
    write_json(ev / "state.json", {"schema_version": "1.0.0", "cycle_count": 0,
                                   "last_cycle": None, "cycle_in_progress": False,
                                   "decision_log": []})
    write_json(ev / "memos.json", {"schema_version": "1.1.0", "score_adjustments": {},
                                   "interventions": [], "history": []})
    write_json(ev / "action_queue.json", {"pending": [], "completed": []})
    write_json(ev / "skill_gaps.json", {"schema_version": "1.0.0", "gaps": []})
    write_json(ev / "episodes.json", {"schema_version": "1.0.0", "episodes": []})
    write_json(ev / "reflections.json", {"schema_version": "1.0.0", "reflections": []})
    write_json(p / "agent" / "state" / "test_coverage.json",
               {"schema_version": "1.0.0", "status": "unknown", "alerts": []})

    if git:
        run = lambda *a: subprocess.run(a, cwd=p, capture_output=True, check=True)
        run("git", "init", "-q")
        run("git", "config", "user.email", "e2e@ooda.local")
        run("git", "config", "user.name", "OODA E2E")
        ignore = "agent/safety/HALT\nagent/state/**/*.lock\nagent/state/evolve/.lock\n"
        if gitignore_state:
            ignore += "agent/state/\n"            # the #31 misconfiguration
        (p / ".gitignore").write_text(ignore)
        run("git", "add", ".gitignore", "config.json", "agent")
        run("git", "commit", "-q", "-m", "seed")
    return p
