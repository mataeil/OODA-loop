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

# Step 6-C9 table — the PROCESS axis (did the PR/commit machinery advance?).
# This is the unbiased process signal. It is NOT the quality of the artifact —
# that is the second axis, folded in by score() below (v1.7.0, fixes D2).
PROCESS = {
    "pr_merged_held": 1.0,   # a prior PR merged and survived (no revert) — confirmed value
    "pr_merged": 0.8,        # merged this cycle, hold not yet confirmed
    "pr_created": 0.5,       # PR opened, awaiting human merge
    "action_extracted": 0.2, # no PR but produced actionable output
    "observe": 0.1,          # observe-only that still recorded state
    "futile": 0.0,           # ran, changed nothing (had_output == false)
    "error": 0.0,            # skill errored
    "pr_rejected": 0.0,      # a prior PR was closed unmerged — negative outcome
    "leap_regressed": 0.0,   # a LEAP cycle that lowered the targeted dimension and was reverted (v1.7.0)
}
QUALITY = PROCESS  # back-compat alias for older importers


def classify(cycle: dict) -> str:
    """Map a decision_log-style cycle dict to a result_type.

    Inputs it reads (all already produced by the cycle):
      result            "success" | "error" | "skip" | "observe_only"
      pr_number         int | null
      pr_outcome        "merged" | "merged_held" | "rejected" | null (from 2-B)
      had_output        bool
      leap_regressed    bool — a LEAP that lowered its targeted dimension (v1.7.0)
    """
    result = cycle.get("result")
    pr_outcome = cycle.get("pr_outcome")
    if cycle.get("leap_regressed"):
        return "leap_regressed"
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


def artifact_factor(cycle: dict) -> float:
    """The ARTIFACT axis (v1.7.0, fixes D2): is the thing the cycle produced
    actually GOOD? `artifact_score` (0..1) is written by the independent critic
    (evolve Step 5-G). When present it MULTIPLIES the process score — a created PR
    whose artifact scores 0.4 no longer counts the same as one that scores 0.9.
    Absent (no rubric, or an observe/futile cycle that built nothing) → 1.0, so
    process-only loops are unchanged (back-compat)."""
    a = cycle.get("artifact_score")
    if a is None:
        return 1.0
    try:
        return max(0.0, min(1.0, float(a)))
    except (TypeError, ValueError):
        return 1.0


def score(cycle: dict) -> tuple[str, float]:
    """quality_multiplier = process_factor × artifact_factor.
    Process alone said "a PR exists"; the artifact axis asks "is it any good?".
    Folding them is the fix for the F1 dogfood's 22-cycles-all-0.5 collapse."""
    rt = classify(cycle)
    q = PROCESS[rt] * artifact_factor(cycle)
    return rt, round(q, 3)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    ev = Path(sys.argv[1]) / "agent" / "state" / "evolve"
    # Prefer outcomes.json (carries artifact_score); fall back to decision_log.
    try:
        entries = json.loads((ev / "outcomes.json").read_text()).get("entries", [])
    except Exception:
        entries = []
    if entries:
        cyc = entries[-1]
        cid = cyc.get("cycle_id")
    else:
        state = json.loads((ev / "state.json").read_text())
        log = state.get("decision_log", [])
        if not log:
            print("No cycles yet.")
            return 0
        cyc = log[-1]
        cid = cyc.get("cycle")
    rt, q = score(cyc)
    a = cyc.get("artifact_score")
    extra = "" if a is None else f"  (process {PROCESS[rt]} × artifact {a})"
    print(f"cycle #{cid}: result_type={rt} quality_multiplier={q}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
