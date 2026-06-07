#!/usr/bin/env python3
"""Deterministic reference for the auto-merge eligibility gate (evolve 4-C /
dev-cycle). Side-effect free. Used by tests/verify.py to objectively confirm the
safety-critical gate accepts ONLY low-risk, opted-in PRs.

A PR is auto-merge-eligible iff ALL hold:
  safety.enable_auto_merge == true            (opt-in; default false)
  progressive_complexity.current_level >= 3
  PR is not a draft
  no changed file matches safety.protected_paths
  changedFiles <= safety.auto_merge_max_files   (default 5)
  additions + deletions <= safety.auto_merge_max_lines (default 100)
  tests green

Usage: python3 scripts/auto_merge_gate.py <config.json>   (runs a self-demo)
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path


def eligible(config: dict, pr: dict):
    """Return (bool, reason). The order of checks mirrors evolve 4-C."""
    safety = config.get("safety", {}) or {}
    if not safety.get("enable_auto_merge", False):
        return False, "enable_auto_merge is off (default)"
    level = (config.get("progressive_complexity", {}) or {}).get("current_level", 0)
    if level < 3:
        return False, f"level {level} < 3"
    if pr.get("isDraft", False):
        return False, "PR is a draft"
    protected = safety.get("protected_paths", []) or []
    for f in pr.get("files", []) or []:
        for pat in protected:
            if fnmatch.fnmatch(f, pat) or fnmatch.fnmatch(f, pat.rstrip("/*") + "/" + "*"):
                return False, f"protected path touched: {f} (~ {pat})"
    max_files = safety.get("auto_merge_max_files", 5)
    max_lines = safety.get("auto_merge_max_lines", 100)
    changed = pr.get("changedFiles", len(pr.get("files", []) or []))
    if changed > max_files:
        return False, f"changedFiles {changed} > auto_merge_max_files {max_files}"
    lines = pr.get("additions", 0) + pr.get("deletions", 0)
    if lines > max_lines:
        return False, f"lines {lines} > auto_merge_max_lines {max_lines}"
    if pr.get("tests") != "green":
        return False, f"tests not green (got {pr.get('tests')!r})"
    return True, "eligible (opt-in, low-risk, non-protected, green)"


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cfg = json.loads(Path(sys.argv[1]).read_text())
    demos = {
        "low-risk green PR": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 1, "tests": "green"},
        "protected path": {"isDraft": False, "files": ["skills/evolve/SKILL.md"], "changedFiles": 1, "additions": 2, "deletions": 0, "tests": "green"},
        "too many files": {"isDraft": False, "files": ["a", "b", "c", "d", "e", "f"], "changedFiles": 6, "additions": 10, "deletions": 0, "tests": "green"},
        "too many lines": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 200, "deletions": 0, "tests": "green"},
        "draft": {"isDraft": True, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 0, "tests": "green"},
        "tests red": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 0, "tests": "red"},
    }
    for name, pr in demos.items():
        ok, why = eligible(cfg, pr)
        print(f"  {'AUTO-MERGE' if ok else 'hold     '} | {name:<18} | {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
