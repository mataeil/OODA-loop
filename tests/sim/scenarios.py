"""A/B/C sandbox scenarios — three "real projects" an OODA-loop would operate.

Each scenario has a MISSION (what the project is for), a set of domains with a
per-domain `mission_alignment` (0..1 — how much working that domain advances the
mission), one verifiable goal, and a per-cycle environment: what work is
available and how a simulated human/CI responds to the loop's choice.

The point of the simulation is to measure whether the loop DRIVES TOWARD THE
MISSION — the capability a self-improving, mission-installed loop must have. A
loop that picks by staleness alone will wander; a mission-aware loop will not.
"""
from __future__ import annotations


def _domain(weight, alignment, kind):
    return {"weight": weight, "mission_alignment": alignment, "kind": kind}


# Each scenario: mission, domains{name: {...}}, goal (advances when an on-mission
# domain produces accepted output), and events(cycle) -> dict of per-cycle
# environment signals: {alerts:{domain:sev}, work:{domain:bool}, human:"merge|reject|none"}.

SCENARIOS = {
    # A — shipping a live web app: mission is reliability + the launch backlog.
    "A_webapp": {
        "mission": "Keep the live app healthy and ship the launch backlog to v1.",
        "domains": {
            "service_health": _domain(2.0, 0.7, "observe"),   # health matters
            "test_coverage": _domain(0.5, 0.4, "observe"),
            "backlog": _domain(1.0, 1.0, "strategize"),       # the backlog IS the mission
            "competitors": _domain(0.3, 0.0, "observe"),      # off-mission distraction
        },
        "goal": {"id": "ship_v1", "domain": "backlog", "target_cycles": 6},
        "events": lambda c: {
            "alerts": ({"service_health": "warning"} if c in (3, 7) else {}),
            "work": {"backlog": True, "service_health": c in (3, 7),
                     "test_coverage": c in (5,), "competitors": True},
            # human merges on-mission work, rejects off-mission noise
        },
    },
    # B — a library: mission is correctness; health is irrelevant (no endpoints).
    "B_library": {
        "mission": "Keep the test suite green and grow coverage; correctness over features.",
        "domains": {
            "test_coverage": _domain(1.0, 1.0, "observe"),    # the mission
            "backlog": _domain(0.8, 0.6, "strategize"),
            "service_health": _domain(2.0, 0.0, "observe"),   # high weight, ZERO mission value (no endpoints)
        },
        "goal": {"id": "green_suite", "domain": "test_coverage", "target_cycles": 5},
        "events": lambda c: {
            "alerts": ({"test_coverage": "critical"} if c in (2,) else {}),  # a real regression
            "work": {"test_coverage": True, "backlog": c % 2 == 0, "service_health": False},
        },
    },
    # C — greenfield with a sharp mission and a distractor domain that's always stale.
    "C_greenfield": {
        "mission": "Build the core data pipeline; ignore everything not on the critical path.",
        "domains": {
            "backlog": _domain(1.0, 1.0, "strategize"),       # critical path
            "implementation": _domain(1.5, 1.0, "execute"),   # building it
            "ux_evolution": _domain(1.0, 0.1, "observe"),     # tempting but off-path
            "competitors": _domain(0.5, 0.0, "observe"),      # pure distraction, ages fast
        },
        "goal": {"id": "pipeline_mvp", "domain": "implementation", "target_cycles": 7},
        "events": lambda c: {
            "alerts": {},
            "work": {"backlog": c < 3, "implementation": c >= 2,
                     "ux_evolution": True, "competitors": True},
        },
    },
}


def respond(scenario: dict, cycle: int, winner: str, ev: dict) -> dict:
    """Simulated environment/human response to the loop picking `winner`.

    Returns an outcome dict for the engine driver:
      result, had_output, pr_number, pr_outcome, on_mission, goal_advanced
    """
    dom = scenario["domains"].get(winner, {})
    alignment = dom.get("mission_alignment", 0.0)
    has_work = ev.get("work", {}).get(winner, False)
    on_mission = alignment >= 0.5

    # no real work in the chosen domain → futile (the loop wandered)
    if not has_work:
        return {"result": "success", "had_output": False, "pr_number": None,
                "on_mission": on_mission, "goal_advanced": False}

    # work exists: strategize/observe produce actionable output; execute produces a PR
    kind = dom.get("kind")
    goal = scenario["goal"]
    advances = (winner == goal["domain"] and on_mission)

    if kind == "execute":
        # a PR; the simulated human merges on-mission work, rejects off-mission
        merged = on_mission
        return {"result": "success", "had_output": True, "pr_number": 100 + cycle,
                "pr_outcome": "merged" if merged else "rejected",
                "on_mission": on_mission, "goal_advanced": advances and merged}
    # observe/strategize with work → actionable output
    return {"result": "success", "had_output": True, "pr_number": None,
            "on_mission": on_mission, "goal_advanced": advances}
