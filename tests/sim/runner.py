"""Sandbox simulation runner — drive a scenario through N OODA cycles and
measure loop-engineering quality.

This is the empirical instrument for the self-improvement exercise: it runs the
ACTUAL decision logic (the 3-A scoring spec, re-implemented here and kept in
sync) against a scripted real-project scenario, records real outcomes via the
E2E engine driver, and reports the Loop Scorecard plus loop-engineering quality
metrics (mission-hit rate, goal completion, futile rate, loop value).

The `mission_aware` flag toggles whether scoring includes the mission-alignment
term — so an improvement can be A/B-measured before/after. Each iteration of the
improvement loop updates the spec AND this scorer together, then re-runs.

Usage: python3 tests/sim/runner.py [scenario] [--cycles N] [--no-mission]
"""
from __future__ import annotations

import importlib.util
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
from sim.scenarios import SCENARIOS, respond   # noqa: E402

from e2e.driver.engine import Engine, write_json, read_json   # noqa: E402
from e2e.driver.sandbox import make_project                   # noqa: E402


def _load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


SCORECARD = _load_mod("sc", REPO / "scripts" / "loop_scorecard.py")

# Mission-alignment weight in scoring — the lever the mission-capture feature adds.
MISSION_WEIGHT = 6.0
BALANCE_WEIGHT = 5.0


DRY_DAMPEN = 0.3           # staleness x for a dry WORK domain (strategize/execute)
DRY_DAMPEN_OBSERVE = 0.6  # milder x for a quiet MONITOR (observe) — still polled
OFF_MISSION_DAMPEN = 0.2  # x for a near-zero-alignment domain when a mission is set
OFF_MISSION_THRESHOLD = 0.2


def _score(domains, hours, confidence, execs, total_execs, ev, mission_aware,
           last_output=None, work_aware=True):
    """Mirror of evolve 3-A scoring (+ mission term + dry-domain dampener).

    Returns {domain: score}. work_aware: when a *work* domain (strategize/execute)
    produced no actionable output the last time it ran, dampen its staleness so it
    stops winning empty cycles. Monitoring (observe) domains keep their cadence —
    a quiet monitor still needs polling — unless they are themselves off-mission.
    An active alert always exempts a domain from the dampener.
    """
    last_output = last_output or {}
    scores = {}
    n = len(domains)
    for name, d in domains.items():
        staleness = d["weight"] * 10.0 * math.log(1 + hours[name] / 4.0)
        is_work_domain = d.get("kind") in ("strategize", "execute")
        ran_dry = last_output.get(name) is False
        alerting = bool(ev.get("alerts", {}).get(name))
        if work_aware and ran_dry and not alerting:
            # work domains: hard dampen (nothing to do). monitors: mild dampen
            # (still poll periodically, just don't dominate every cycle).
            staleness *= DRY_DAMPEN if is_work_domain else DRY_DAMPEN_OBSERVE
        conf_term = confidence.get(name, 0.7) * 0.2
        share = execs.get(name, 0) / max(total_execs, 1)
        balance = max(-BALANCE_WEIGHT * (share - 1.0 / n), -10.0)
        alert = 5.0 if alerting else 0.0
        mission = (MISSION_WEIGHT * d.get("mission_alignment", 0.0)) if mission_aware else 0.0
        if mission_aware and d.get("mission_alignment", 0.0) < OFF_MISSION_THRESHOLD and not alerting:
            staleness *= OFF_MISSION_DAMPEN   # off-mission distraction: don't steal cycles
        scores[name] = staleness + conf_term + balance + alert + mission
    return scores


def run(scenario_key: str, cycles: int = 12, mission_aware: bool = True,
        work_aware: bool = True) -> dict:
    sc = SCENARIOS[scenario_key]
    domains = sc["domains"]
    tmp = tempfile.TemporaryDirectory()
    proj = make_project(Path(tmp.name),
                        safety={"min_cycle_interval_minutes": 0, "halt_file": "agent/safety/HALT",
                                "lock_timeout_minutes": 30, "max_silent_failures": 99})
    eng = Engine(proj)
    # seed the scenario's domains/goal into config + state
    cfg = read_json(proj / "config.json")
    cfg["domains"] = {name: {"weight": d["weight"], "status": "active", "enabled": True,
                             "primary_skill": f"/{name}", "state_file": f"agent/state/{name}.json",
                             "mission_alignment": d.get("mission_alignment", 0.0)}
                      for name, d in domains.items()}
    cfg["mission"] = sc["mission"]
    write_json(proj / "config.json", cfg)
    write_json(eng.ev / "goals.json", {"schema_version": "1.0.0", "goals": [
        {"id": sc["goal"]["id"], "title": sc["mission"], "status": "active",
         "progress": 0.0, "domain": sc["goal"]["domain"]}]})

    hours = {n: 24.0 for n in domains}      # all start stale
    confidence = {n: 0.7 for n in domains}
    execs = {n: 0 for n in domains}
    last_output = {}                         # domain -> bool (had_output last run)
    goal_hits = 0
    goal_done = False
    skipped_idle = 0
    ran = 0
    trace = []
    on_mission_opportunities = 0
    on_mission_hits = 0

    for c in range(1, cycles + 1):
        ev = sc["events"](c)
        scores = _score(domains, hours, confidence, execs, sum(execs.values()), ev,
                        mission_aware, last_output, work_aware)
        winner = max(scores, key=scores.get)
        out = respond(sc, c, winner, ev)
        # Goal-completion gate (Iter 5): once the mission goal is met, don't burn
        # a full cycle on nothing — if there's no alert and no actionable output,
        # SKIP (idle), like the min-interval skip. The loop ran UNTIL the goal.
        alert_now = bool(ev.get("alerts"))
        if goal_done and not out["had_output"] and not alert_now:
            skipped_idle += 1
            for n in domains:
                hours[n] += 4.0
            trace.append((c, "(idle)", None, False, False))
            continue
        ran += 1
        last_output[winner] = out["had_output"]

        # was there an on-mission opportunity this cycle? (work in any aligned domain)
        opp = any(domains[d].get("mission_alignment", 0) >= 0.5 and ev.get("work", {}).get(d)
                  for d in domains)
        if opp:
            on_mission_opportunities += 1
            if out.get("on_mission") and out.get("had_output"):
                on_mission_hits += 1

        # confidence feedback (merge/reject), goal progress
        if out.get("pr_outcome") == "merged":
            confidence[winner] = min(confidence[winner] + 0.1, 1.0)
        elif out.get("pr_outcome") == "rejected":
            confidence[winner] = max(confidence[winner] - 0.2, 0.1)
        if out.get("goal_advanced"):
            goal_hits += 1
            g = read_json(eng.ev / "goals.json")
            g["goals"][0]["progress"] = min(goal_hits / sc["goal"]["target_cycles"], 1.0)
            write_json(eng.ev / "goals.json", g)
            if g["goals"][0]["progress"] >= 1.0:
                goal_done = True

        # record the cycle through the real engine (writes outcomes.json etc.)
        eng.run_cycle(f"2026-07-{c:02d}T06:00:00", {
            "selected_domain": winner, "selected_skill": f"/{winner}",
            "result": out["result"], "had_output": out["had_output"],
            "pr_number": out.get("pr_number"), "pr_outcome": out.get("pr_outcome")})
        execs[winner] = execs.get(winner, 0) + 1
        for n in domains:                    # advance staleness clocks
            hours[n] = 0.0 if n == winner else hours[n] + 4.0
        trace.append((c, winner, out.get("on_mission"), out["had_output"], out.get("goal_advanced")))

    card = SCORECARD.compute(proj)
    goal_progress = read_json(eng.ev / "goals.json")["goals"][0]["progress"]
    tmp.cleanup()
    return {
        "scenario": scenario_key, "cycles": cycles, "mission_aware": mission_aware,
        "loop_value_score": card["loop_value_score"],
        "futile_rate_pct": card["futile_cycle_rate_pct"],
        "mission_hit_rate_pct": round(100.0 * on_mission_hits / on_mission_opportunities, 1)
        if on_mission_opportunities else None,
        "goal_progress_pct": round(100.0 * goal_progress, 1),
        "skipped_idle": skipped_idle,
        "winners": [t[1] for t in trace],
    }


def run_all(cycles: int = 12, mission_aware: bool = True, work_aware: bool = True) -> list:
    return [run(k, cycles, mission_aware, work_aware) for k in SCENARIOS]


def _print(rows, label):
    print(f"\n=== {label} ===")
    print(f"{'scenario':<14} {'loopVal':>7} {'futile%':>7} {'mission%':>8} {'goal%':>6}")
    for r in rows:
        print(f"{r['scenario']:<14} {str(r['loop_value_score']):>7} "
              f"{str(r['futile_rate_pct']):>7} {str(r['mission_hit_rate_pct']):>8} "
              f"{str(r['goal_progress_pct']):>6}")


def main() -> int:
    args = sys.argv[1:]
    cycles = 12
    if "--cycles" in args:
        i = args.index("--cycles"); cycles = int(args[i + 1]); args = args[:i] + args[i + 2:]
    mission = "--no-mission" not in args
    work = "--no-work" not in args
    args = [a for a in args if a not in ("--no-mission","--no-work")]
    if args and args[0] in SCENARIOS:
        r = run(args[0], cycles, mission, work)
        print(json.dumps(r, indent=2))
    else:
        _print(run_all(cycles, mission, work), f"mission={mission} work={work}, {cycles} cycles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
