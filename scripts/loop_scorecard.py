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
DEFAULT_BAR = 0.65   # artifact quality bar when config.quality_rubric omits one (v1.7.0)


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _resolve_bar(config: dict) -> float:
    """The "genuinely good" bar the scorecard grades against. v1.9.0: prefer
    `bar_coast` (the real-quality ceiling) over `bar`/`bar_leap`, so the headline
    grade reflects distance to a good product, not a cleared prototype bar.
    Top-level quality_rubric first, then the first domain that declares one."""
    def pick(r):
        for key in ("bar_coast", "bar"):
            v = (r or {}).get(key)
            if isinstance(v, (int, float)):
                return float(v)
        return None
    top = pick(config.get("quality_rubric"))
    if top is not None:
        return top
    for d in (config.get("domains") or {}).values():
        b = pick((d or {}).get("quality_rubric"))
        if b is not None:
            return b
    return DEFAULT_BAR


def _pct(n, d):
    return None if not d else round(100.0 * n / d, 1)


def compute(project: Path, window: int | None = None) -> dict:
    ev = Path(project) / "agent" / "state" / "evolve"
    config = _load(Path(project) / "config.json", {}) or {}
    outcomes = (_load(ev / "outcomes.json", {}) or {}).get("entries", []) or []
    metrics = _load(ev / "metrics.json", {}) or {}
    counters = metrics.get("counters", {}) or {}
    ledger = _load(ev / "cost_ledger.json", {}) or {}
    queue = _load(ev / "action_queue.json", {}) or {}
    goals = (_load(ev / "goals.json", {}) or {}).get("goals", []) or []
    gaps = (_load(ev / "skill_gaps.json", {}) or {}).get("gaps", []) or []
    refl = (_load(ev / "reflections.json", {}) or {}).get("reflections", []) or []

    scope = outcomes[-window:] if window else outcomes
    n = len(scope)
    qsum = sum(e.get("quality_multiplier", 0.0) for e in scope)
    rt_count = {}
    for e in scope:
        rt_count[e.get("result_type")] = rt_count.get(e.get("result_type"), 0) + 1

    success = sum(rt_count.get(rt, 0) for rt in SUCCESS_RT)
    futile = rt_count.get("futile", 0) + rt_count.get("error", 0)
    # mission-hit rate: of the value-producing cycles (quality > 0), how many were
    # on-mission? (the loop staying on purpose, not just busy). Iteration 8.
    producing = [e for e in scope if e.get("quality_multiplier", 0) > 0]
    on_mission_n = sum(1 for e in producing if e.get("on_mission"))
    mission_hit_pct = _pct(on_mission_n, len(producing))

    # ARTIFACT QUALITY (v1.7.0, headline KPI) — the axis the F1 dogfood proved was
    # missing. Mean of the independent critic's artifact_score (Step 5-G) over the
    # scored cycles that actually produced an artifact. None ⇒ artifact axis off.
    bar = _resolve_bar(config)
    art_scores = [e.get("artifact_score") for e in scope if e.get("artifact_score") is not None]
    artifact_quality = round(sum(art_scores) / len(art_scores), 3) if art_scores else None

    prs_created = counters.get("total_prs_created", 0)
    prs_merged = counters.get("total_prs_merged", 0)
    held = rt_count.get("pr_merged_held", 0)
    actions_added = counters.get("actions_added", 0)
    actions_resolved = counters.get("actions_resolved", 0)

    # cost: lifetime if tracked in metrics, else today's ledger
    cost_total = (metrics.get("cost", {}) or {}).get("total_estimated_usd")
    if cost_total in (None, 0.0):
        cost_total = ledger.get("total_estimated_usd", 0.0)

    # verifiable done-conditions (loop-engineering canon #1): mean progress of
    # active goals — the loop runs until its written goals are met.
    active_goals = [g for g in goals if g.get("status") == "active"]
    goal_progress_pct = (
        round(100.0 * sum(g.get("progress", 0.0) for g in active_goals) / len(active_goals), 1)
        if active_goals else None)
    # learning-loop health: are self-diagnosed gaps and lessons acted on?
    gap_resolution_pct = _pct(sum(1 for g in gaps if g.get("resolved")), len(gaps))
    lesson_application_pct = _pct(sum(1 for x in refl if x.get("status") == "applied"), len(refl))

    return {
        "window": window or "all",
        "cycles_scored": n,
        # ARTIFACT QUALITY — the new headline: is the thing the loop builds GOOD?
        "artifact_quality": artifact_quality,
        "artifact_bar": bar,
        "artifact_cycles": len(art_scores),
        # headline single number: mean quality across scored cycles (0..1)
        "loop_value_score": round(qsum / n, 3) if n else None,
        # canon metrics
        "task_completion_rate_pct": _pct(success, n),
        "futile_cycle_rate_pct": _pct(futile, n),
        "pr_merge_rate_pct": _pct(prs_merged, prs_created),
        "pr_merge_and_hold_rate_pct": _pct(held, prs_merged),
        "action_resolution_rate_pct": _pct(actions_resolved, actions_added),
        "cost_per_successful_cycle": (round(cost_total / success, 4) if success else None),
        # done-conditions + learning-loop health
        "active_goals": len(active_goals),
        "goal_progress_pct": goal_progress_pct,
        "mission_hit_pct": mission_hit_pct,
        "skill_gap_resolution_pct": gap_resolution_pct,
        "lesson_application_pct": lesson_application_pct,
        # raw context
        "pending_actions": len(queue.get("pending", []) or []),
        "result_breakdown": rt_count,
        "totals": {"prs_created": prs_created, "prs_merged": prs_merged,
                   "prs_rejected": counters.get("total_prs_rejected", 0),
                   "actions_added": actions_added, "actions_resolved": actions_resolved,
                   "cost_usd": round(cost_total, 4)},
    }


def _letter(composite: float) -> str:
    return ("A" if composite >= 0.8 else "B" if composite >= 0.65
            else "C" if composite >= 0.5 else "D" if composite >= 0.35 else "F")


def goodhart_guard(s: dict) -> dict:
    """The 'measurement is lying' detector (v1.7.0). The F1 dogfood graded A while
    the artifact was broken because NO term measured the artifact. This guard is
    ARTIFACT-ONLY: it does not care whether process metrics are green (a loop
    could keep one metric amber to dodge an AND-gate — gaming-resistance finding).
    If artifact quality is below bar, the headline grade is capped, graduated by
    HOW far below — so a 0.40 artifact against a 0.65 bar reads D, not C."""
    a = s.get("artifact_quality")
    bar = s.get("artifact_bar") or DEFAULT_BAR
    if a is None or a >= bar:
        return {"lying": False, "cap": None, "message": ""}
    if a >= 0.75 * bar:
        cap = "C"
    elif a >= 0.50 * bar:
        cap = "D"
    else:
        cap = "F"
    return {
        "lying": True,
        "cap": cap,
        "message": ("MEASUREMENT WARNING: artifact_quality %.2f < bar %.2f — "
                    "the scoreboard was lying; grade capped at %s. LEAP, don't add features."
                    % (a, bar, cap)),
    }


def grade(s: dict) -> tuple[str, float]:
    """A single loop-engineering letter grade. v1.7.0: artifact quality is the
    dominant term and a self-declared goal is discounted by artifact reality, so a
    feature-checklist loop over a broken artifact can no longer score an A.
    Returns (letter, composite). DASH if no data."""
    lv = s.get("loop_value_score")
    if lv is None:
        return DASH, None
    goal = (s.get("goal_progress_pct") or 0) / 100.0
    futile = (s.get("futile_cycle_rate_pct") or 0) / 100.0
    a = s.get("artifact_quality")
    bar = s.get("artifact_bar") or DEFAULT_BAR

    if a is not None:
        # Evidence-weight the self-declared goal by the artifact reality: a 100%
        # checklist over a 0.40 artifact (bar 0.65) only counts 0.40/0.65 ≈ 0.62
        # of its weight. This is what kills D1 even before the cap fires.
        goal_ev = goal * (1.0 if a >= bar else a / bar)
        composite = 0.45 * a + 0.25 * goal_ev + 0.20 * (1 - futile) + 0.10 * min(lv / 0.5, 1.0)
    else:
        # Back-compat: no artifact axis configured → original process-only formula.
        composite = 0.5 * goal + 0.3 * (1 - futile) + 0.2 * min(lv / 0.5, 1.0)
    composite = round(composite, 3)
    letter = _letter(composite)

    # Apply the artifact-only Goodhart cap: letter may not be BETTER than the cap.
    g = goodhart_guard(s)
    if g["cap"] and "FEDCBA".index(letter) > "FEDCBA".index(g["cap"]):
        letter = g["cap"]
    return letter, composite


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


def _meter(v):
    if v is None:
        return DASH * 10
    filled = round(v * 10)
    return "█" * filled + "░" * (10 - filled)


def render(project: Path, window: int | None = None) -> str:
    s = compute(project, window)
    lv = s["loop_value_score"]
    bar = _meter(lv) if lv is not None else ""
    aq = s.get("artifact_quality")
    aqbar = s.get("artifact_bar") or DEFAULT_BAR
    g = goodhart_guard(s)
    _grade_letter, _grade_score = grade(s)
    aq_label = (DASH if aq is None
                else f"{aq} {'✓≥bar' if aq >= aqbar else '✗<bar %.2f' % aqbar}")
    lines = [
        f"┌─ OODA-loop Scorecard ── {s['cycles_scored']} cycles ({s['window']}) ──────────────┐",
        f"│  ★ Artifact Quality {_fmt(aq_label):<13} {_meter(aq)}  │   ← is the thing GOOD?",
        f"│  Loop Value Score   {_fmt(lv):<5} {bar}   │",
        f"│  Task Completion    {_fmt(s['task_completion_rate_pct'],'%'):<6}  (merged & accepted)        │",
        f"│  Futile Cycle Rate  {_fmt(s['futile_cycle_rate_pct'],'%'):<6}  (ran, changed nothing)     │",
        f"│  PR Merge Rate      {_fmt(s['pr_merge_rate_pct'],'%'):<6}  · hold {_fmt(s['pr_merge_and_hold_rate_pct'],'%')}            │",
        f"│  Queue Resolution   {_fmt(s['action_resolution_rate_pct'],'%'):<6}  (resolved/added)         │",
        f"│  Cost / Success     ${_fmt(s['cost_per_successful_cycle']):<7}                       │",
        f"├─ done-conditions + learning ──────────────────────────┤",
        f"│  Goal Progress      {_fmt(s['goal_progress_pct'],'%'):<6}  ({s['active_goals']} active goals)      │",
        f"│  Mission-hit Rate   {_fmt(s['mission_hit_pct'],'%'):<6}  (value cycles on-mission)  │",
        f"│  Gap Resolution     {_fmt(s['skill_gap_resolution_pct'],'%'):<6}  (skill gaps closed)       │",
        f"│  Lesson Application  {_fmt(s['lesson_application_pct'],'%'):<6} (reflexions re-applied)    │",
        f"├───────────────────────────────────────────────────────┤",
        f"│  Loop grade: {_grade_letter} ({_fmt(_grade_score)})  ·  {_verdict(s)[:30]:<30} │",
        f"└──────────────────────────────────────────────────────┘",
    ]
    if g["lying"]:
        lines.append(f"⚠  {g['message']}")
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
