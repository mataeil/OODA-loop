#!/usr/bin/env python3
"""Deterministic reference for the per-cycle Outcome Record (evolve Step 6-C9).

The atomic "did this cycle help?" signal of OODA-loop's measurement stack
(v1.4.0). Side-effect free. Mirrors the Step 6-C9 table exactly so the engine,
tests/verify.py, the Docker E2E driver, and scripts/loop_scorecard.py all agree
on one definition of `result_type` → `quality_multiplier`.

A cycle is scored from FACTS already recorded that cycle — never from the
agent's self-report of "success". `result: success` only means the skill ran;
whether it *helped* is what quality_multiplier captures.

Usage: python3 scripts/score_outcome.py <project_dir>   (scores the latest cycle)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Step 6-C9 table — the single source of truth.
QUALITY = {
    "pr_merged_held": 1.0,   # a prior PR merged and survived (no revert) — confirmed value
    "pr_merged": 0.8,        # merged this cycle, hold not yet confirmed
    "pr_created": 0.5,       # PR opened, awaiting human merge
    "action_extracted": 0.2, # no PR but produced actionable output
    "observe": 0.1,          # observe-only that still recorded state
    "futile": 0.0,           # ran, changed nothing (had_output == false)
    "error": 0.0,            # skill errored
    "pr_rejected": 0.0,      # a prior PR was closed unmerged — negative outcome
}


def classify(cycle: dict) -> str:
    """Map a decision_log-style cycle dict to a result_type.

    Inputs it reads (all already produced by the cycle):
      result            "success" | "error" | "skip" | "observe_only"
      pr_number         int | null
      pr_outcome        "merged" | "merged_held" | "rejected" | null (from 2-B)
      had_output        bool
    """
    result = cycle.get("result")
    pr_outcome = cycle.get("pr_outcome")
    if pr_outcome == "merged_held":
        return "pr_merged_held"
    if pr_outcome == "merged":
        return "pr_merged"
    if pr_outcome == "rejected":
        return "pr_rejected"
    if result == "error":
        return "error"
    if cycle.get("pr_number"):
        return "pr_created"
    if result == "observe_only":
        return "observe"
    if cycle.get("had_output"):
        return "action_extracted"
    return "futile"


def score(cycle: dict) -> tuple[str, float]:
    rt = classify(cycle)
    return rt, QUALITY[rt]


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ev = Path(sys.argv[1]) / "agent" / "state" / "evolve"
    state = json.loads((ev / "state.json").read_text())
    log = state.get("decision_log", [])
    if not log:
        print("No cycles yet.")
        return 0
    rt, q = score(log[-1])
    print(f"cycle #{log[-1].get('cycle')}: result_type={rt} quality_multiplier={q}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
