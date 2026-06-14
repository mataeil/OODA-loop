#!/usr/bin/env python3
"""Loop Scorecard — does this loop actually WORK? (evolve / `/ooda-status --scorecard`)

The headline measurement artifact of OODA-loop v1.4.0. Where the Cycle Card
answers "what did this one cycle do?", the Scorecard answers the loop-engineering
question "is the loop *improving the project*, or just running?" — computed from
the Outcome Record (outcomes.json, Step 6-C9), metrics counters, the cost ledger,
and the action queue. Side-effect free; renders the same whether called by the
engine, `/ooda-status --scorecard`, or tests.

KPIs implement the measurement canon (Anthropic + loop-engineering practitioner
sources): Loop Value Score, Task Completion Rate, PR merge & hold rate, Futile
Cycle Rate, Action Queue Resolution Rate, Cost per Successful Cycle.

Usage: python3 scripts/loop_scorecard.py <project_dir> [--window N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DASH = "—"
SUCCESS_RT = {"pr_merged_held", "pr_merged"}     # cycles that delivered accepted value
WORKING_RT = SUCCESS_RT | {"pr_created", "action_extracted"}  # produced real output


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def compute(project: Path, window: int | None = None) -> dict:
    ev = Path(project) / "agent" / "state" / "evolve"
    outcomes = (_load(ev / "outcomes.json", {}) or {}).get("entries", []) or []
    metrics = _load(ev / "metrics.json", {}) or {}
    counters = metrics.get("counters", {}) or {}
    ledger = _load(ev / "cost_ledger.json", {}) or {}
    queue = _load(ev / "action_queue.json", {}) or {}

    scope = outcomes[-window:] if window else outcomes
    n = len(scope)
    qsum = sum(e.get("quality_multiplier", 0.0) for e in scope)
    rt_count = {}
    for e in scope:
        rt_count[e.get("result_type")] = rt_count.get(e.get("result_type"), 0) + 1

    success = sum(rt_count.get(rt, 0) for rt in SUCCESS_RT)
    futile = rt_count.get("futile", 0) + rt_count.get("error", 0)

    prs_created = counters.get("total_prs_created", 0)
    prs_merged = counters.get("total_prs_merged", 0)
    held = rt_count.get("pr_merged_held", 0)
    actions_added = counters.get("actions_added", 0)
    actions_resolved = counters.get("actions_resolved", 0)

    # cost: lifetime if tracked in metrics, else today's ledger
    cost_total = (metrics.get("cost", {}) or {}).get("total_estimated_usd")
    if cost_total in (None, 0.0):
        cost_total = ledger.get("total_estimated_usd", 0.0)

    return {
        "window": window or "all",
        "cycles_scored": n,
        # headline single number: mean quality across scored cycles (0..1)
        "loop_value_score": round(qsum / n, 3) if n else None,
        # canon metrics
        "task_completion_rate_pct": _pct(success, n),
        "futile_cycle_rate_pct": _pct(futile, n),
        "pr_merge_rate_pct": _pct(prs_merged, prs_created),
        "pr_merge_and_hold_rate_pct": _pct(held, prs_merged),
        "action_resolution_rate_pct": _pct(actions_resolved, actions_added),
        "cost_per_successful_cycle": (round(cost_total / success, 4) if success else None),
        # raw context
        "pending_actions": len(queue.get("pending", []) or []),
        "result_breakdown": rt_count,
        "totals": {"prs_created": prs_created, "prs_merged": prs_merged,
                   "prs_rejected": counters.get("total_prs_rejected", 0),
                   "actions_added": actions_added, "actions_resolved": actions_resolved,
                   "cost_usd": round(cost_total, 4)},
    }


def _fmt(v, suffix=""):
    return DASH if v is None else f"{v}{suffix}"


def _verdict(s: dict) -> str:
    lv = s["loop_value_score"]
    if lv is None:
        return "no outcomes recorded yet — run more cycles"
    if lv >= 0.6:
        return "working — the loop is delivering accepted value"
    if lv >= 0.3:
        return "partial — producing output, low acceptance; review scoring/level"
    return "stalled — mostly futile cycles; check domains, goals, or HALT"


def render(project: Path, window: int | None = None) -> str:
    s = compute(project, window)
    lv = s["loop_value_score"]
    bar = ""
    if lv is not None:
        filled = round(lv * 10)
        bar = "█" * filled + "░" * (10 - filled)
    lines = [
        f"┌─ OODA-loop Scorecard ── {s['cycles_scored']} cycles ({s['window']}) ──────────────┐",
        f"│  Loop Value Score   {_fmt(lv):<5} {bar}   │",
        f"│  Task Completion    {_fmt(s['task_completion_rate_pct'],'%'):<6}  (merged & accepted)        │",
        f"│  Futile Cycle Rate  {_fmt(s['futile_cycle_rate_pct'],'%'):<6}  (ran, changed nothing)     │",
        f"│  PR Merge Rate      {_fmt(s['pr_merge_rate_pct'],'%'):<6}  · hold {_fmt(s['pr_merge_and_hold_rate_pct'],'%')}            │",
        f"│  Queue Resolution   {_fmt(s['action_resolution_rate_pct'],'%'):<6}  (resolved/added)         │",
        f"│  Cost / Success     ${_fmt(s['cost_per_successful_cycle']):<7}                       │",
        f"│  Verdict: {_verdict(s)[:44]:<44} │",
        f"└──────────────────────────────────────────────────────┘",
    ]
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    window = None
    if "--window" in args:
        i = args.index("--window")
        window = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    print(render(Path(args[0]), window))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
