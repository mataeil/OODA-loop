#!/usr/bin/env python3
"""Scenario fixture verifier for tests/.

Walks each fixture under tests/ and asserts the seed state is internally
consistent with the evolve SKILL.md logic that the fixture's README claims
to exercise. This is a static, semantic walkthrough — it does NOT invoke
/evolve; run /evolve --dry-run separately from a fixture's seed/ directory
for runtime verification.

Exit code 0 iff every check passes. Run from repo root:

    python3 tests/verify.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent

STOP_WORDS = {
    "the", "a", "an", "is", "for", "in", "to", "of", "and", "was", "on",
}


def jaccard(a: str, b: str) -> float:
    def toks(s: str) -> set[str]:
        return {w for w in re.findall(r"\w+", s.lower()) if w not in STOP_WORDS}

    A, B = toks(a), toks(b)
    return len(A & B) / len(A | B) if (A | B) else 0.0


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


class Runner:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name: str, ok: bool, detail: str) -> None:
        self.results.append((name, ok, detail))

    def section(self, name: str, body: Callable[[], None]) -> None:
        try:
            body()
        except Exception as exc:  # pragma: no cover — fixture I/O errors
            self.check(f"{name} (setup)", False, f"{type(exc).__name__}: {exc}")

    def report(self) -> int:
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = len(self.results) - passed
        print("=" * 72)
        print(
            f"Fixture semantic walkthrough: {passed}/{len(self.results)} "
            f"passed, {failed} failed"
        )
        print("=" * 72)
        for name, ok, detail in self.results:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {name}")
            print(f"         {detail}")
        return 0 if failed == 0 else 1


def check_principles_extraction(r: Runner) -> None:
    base = ROOT / "principles-extraction" / "seed" / "agent" / "state" / "evolve"
    ep = load_json(base / "episodes.json")
    w15 = ep["episodes"][0]["lessons"]
    w16 = ep["episodes"][1]["lessons"]
    lessons_total = sum(len(e["lessons"]) for e in ep["episodes"])
    j = max(jaccard(w15[0], l) for l in w16)
    r.check(
        "principles-extraction: primary Jaccard >= 0.5",
        j >= 0.5,
        f"max Jaccard W15[0] vs W16 = {j:.2f}",
    )
    r.check(
        "principles-extraction: total lessons >= 10 for fallback",
        lessons_total >= 10,
        f"total lessons = {lessons_total}",
    )
    pr = load_json(base / "principles.json")
    r.check(
        "principles-extraction: principles seed is empty",
        pr["principles"] == [],
        f"seed count = {len(pr['principles'])}",
    )


def check_memo_intervention(r: Runner) -> None:
    base = ROOT / "memo-intervention" / "seed" / "agent" / "state" / "evolve"
    st = load_json(base / "state.json")
    log = st["decision_log"]
    last10 = [e for e in log if e["cycle"] >= st["cycle_count"] - 9]
    ux = sum(1 for e in last10 if e["selected_domain"] == "ux_evolution")
    r.check(
        "memo-intervention: ux_evolution has 0 execs in last 10 (starvation)",
        ux == 0,
        f"ux_evolution count in last 10 = {ux}",
    )
    c1 = log[-1]["selected_domain"]
    c2 = log[-2]["selected_domain"]
    r.check(
        "memo-intervention: last 2 cycles same domain (monopoly candidate)",
        c1 == c2,
        f"last 2 domains = {c1}, {c2}",
    )
    memos = load_json(base / "memos.json")
    r.check(
        "memo-intervention: memos.interventions starts empty",
        memos["interventions"] == [],
        f"count = {len(memos['interventions'])}",
    )
    r.check(
        "memo-intervention: memos.json schema_version is 1.1.0",
        memos["schema_version"] == "1.1.0",
        f"schema_version = {memos['schema_version']}",
    )


def check_cost_ledger_autopatch(r: Runner) -> None:
    base = ROOT / "cost-ledger-autopatch" / "seed" / "agent" / "state" / "evolve"
    st = load_json(base / "state.json")
    cl = load_json(base / "cost_ledger.json")
    last_entry_cycle = cl["entries"][-1]["cycle_id"]
    r.check(
        "cost-ledger-autopatch: last entry cycle != state.cycle_count",
        last_entry_cycle != st["cycle_count"],
        f"last entry cycle = {last_entry_cycle}, state.cycle_count = {st['cycle_count']}",
    )
    sg = load_json(base / "skill_gaps.json")
    r.check(
        "cost-ledger-autopatch: skill_gaps seed empty",
        sg["gaps"] == [],
        f"gap count = {len(sg['gaps'])}",
    )
    # 6-C8 sequence-gap detection: the holes 6-C8 would backfill.
    recorded = sorted({e["cycle_id"] for e in cl["entries"]})
    expected = st["cycle_count"]
    missing = [c for c in range(recorded[0], expected + 1) if c not in recorded]
    r.check(
        "cost-ledger-autopatch: 6-C8 would backfill the 3-cycle gap [40,41,42]",
        missing == [40, 41, 42],
        f"recorded={recorded}, missing={missing}",
    )


def check_lens_pre_init(r: Runner) -> None:
    base = ROOT / "lens-pre-init" / "seed"
    cfg = load_json(base / "config.json")
    active = [n for n, d in cfg["domains"].items() if d.get("status") == "active"]
    present = [
        n for n in active if (base / "agent" / "state" / n / "lens.json").exists()
    ]
    r.check(
        "lens-pre-init: 3 active domains configured",
        len(active) == 3,
        f"active domains = {active}",
    )
    r.check(
        "lens-pre-init: 0 pre-existing lens files (init must create them)",
        len(present) == 0,
        f"lens files present = {present}",
    )


def check_season_mode_toggle(r: Runner) -> None:
    base = ROOT / "season-mode-toggle" / "seed"
    d1 = load_json(base / "config.default.json")
    d2 = load_json(base / "config.preparation.json")
    r.check(
        "season-mode-toggle: default mode has no overrides",
        d1["season_modes"]["modes"]["default"]["weight_overrides"] == {},
        "default weight_overrides empty",
    )
    ov = d2["season_modes"]["modes"]["preparation"]["weight_overrides"]
    r.check(
        "season-mode-toggle: preparation overrides service_health->1.0, backlog->2.0",
        ov.get("service_health") == 1.0 and ov.get("backlog") == 2.0,
        f"preparation overrides = {ov}",
    )
    sb = d2["season_modes"]["modes"]["preparation"]["signal_bonuses"]
    r.check(
        "season-mode-toggle: preparation signal_bonuses set",
        bool(sb),
        f"signal_bonuses = {sb}",
    )
    # Objective Decide-scoring check: the weight_overrides must flip the winner.
    import importlib.util

    ds_path = ROOT.parent / "scripts" / "dryrun_score.py"
    spec = importlib.util.spec_from_file_location("ds", ds_path)
    ds = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ds)
    drank = ds.score_domains(base / "config.default.json")
    prank = ds.score_domains(base / "config.preparation.json")
    r.check(
        "season-mode-toggle: default mode → service_health wins (Decide scoring)",
        bool(drank) and drank[0][0] == "service_health",
        f"default ranking = {[x[0] for x in drank]}",
    )
    r.check(
        "season-mode-toggle: preparation overrides flip winner → backlog",
        bool(prank) and prank[0][0] == "backlog",
        f"preparation ranking = {[x[0] for x in prank]}",
    )


def check_rotation_cursor(r: Runner) -> None:
    base = ROOT / "rotation-cursor" / "seed"
    cfg = load_json(base / "config.json")
    rot = cfg["domains"]["ux_evolution"].get("rotation")
    cur = load_json(base / "agent" / "state" / "ux_evolution" / "rotation_cursor.json")
    r.check(
        "rotation-cursor: ux_evolution has 3-item rotation list",
        isinstance(rot, list) and len(rot) == 3,
        f"rotation = {rot}",
    )
    r.check(
        "rotation-cursor: cursor starts at 0",
        cur.get("cursor") == 0,
        f"cursor = {cur.get('cursor')}",
    )


def check_active_context_read(r: Runner) -> None:
    base = ROOT / "active-context-read" / "seed"
    cfg = load_json(base / "config.json")
    ac = cfg.get("active_context", {})
    r.check(
        "active-context-read: active_context.path is set",
        ac.get("path") == "contexts/persona-demo.json",
        f"path = {ac.get('path')}",
    )
    persona = base / "contexts" / "persona-demo.json"
    ok = persona.exists() and bool(load_json(persona))
    r.check(
        "active-context-read: persona file exists and is valid JSON",
        ok,
        str(persona.relative_to(ROOT.parent)),
    )


def check_cycle_card(r: Runner) -> None:
    base = ROOT / "cycle-card" / "seed"
    ev = base / "agent" / "state" / "evolve"
    conf = load_json(ev / "confidence.json")
    r.check(
        "cycle-card: service_health confidence 0.54 (= 0.74 - 0.2 reject)",
        abs(conf["service_health"] - 0.54) < 1e-9,
        f"service_health = {conf['service_health']}",
    )
    lcl = load_json(base / "agent" / "state" / "service_health" / "lens_changelog.json")
    last = lcl["entries"][-1]
    r.check(
        "cycle-card: lens_changelog flaky-alert threshold 0.30 -> 0.25 (LEARN #2)",
        last["before"] == 0.30 and last["after"] == 0.25,
        f"before={last['before']}, after={last['after']}",
    )
    cl = load_json(ev / "cost_ledger.json")
    e152 = [e for e in cl["entries"] if e["cycle_id"] == 152]
    r.check(
        "cycle-card: cost_ledger has cycle 152 entry @ $0.04, total $0.38",
        len(e152) == 1 and e152[0]["estimated_usd"] == 0.04
        and cl["total_estimated_usd"] == 0.38,
        f"entry={e152}, total={cl['total_estimated_usd']}",
    )
    refl = load_json(ev / "reflections.json")
    r.check(
        "cycle-card: reflections non-empty with verdict hit (Step 5-F ran)",
        len(refl["reflections"]) >= 1 and refl["reflections"][-1]["verdict"] == "hit",
        f"count={len(refl['reflections'])}",
    )
    cfg = load_json(base / "config.json")
    lvl2 = cfg["progressive_complexity"]["levels"]["2"]["name"]
    active = [n for n, d in cfg["domains"].items() if d.get("status") == "active"]
    r.check(
        "cycle-card: level 2 name 'Full observation' (footer reads from config)",
        lvl2 == "Full observation",
        f"levels[2].name = {lvl2}",
    )
    r.check(
        "cycle-card: 4 active domains (OBSERVE count)",
        len(active) == 4,
        f"active = {active}",
    )
    st = load_json(ev / "state.json")
    last_dec = st["decision_log"][-1]
    outcomes = last_dec.get("pr_outcomes", [])
    rejected28 = any(
        o.get("pr") == 28 and o.get("outcome") == "rejected" for o in outcomes
    )
    r.check(
        "cycle-card: cycle 152 logged PR #28 rejection + opened PR #29 (LEARN #1)",
        last_dec["cycle"] == 152 and rejected28 and last_dec.get("pr_number") == 29,
        f"cycle={last_dec['cycle']}, pr={last_dec.get('pr_number')}, outcomes={outcomes}",
    )


def check_cycle_card_render(r: Runner) -> None:
    """Runtime check: execute the reference Cycle Card renderer on the fixture
    and assert the rendered output carries the differentiating LEARN content."""
    import importlib.util

    rcc_path = ROOT.parent / "scripts" / "render_cycle_card.py"
    spec = importlib.util.spec_from_file_location("rcc", rcc_path)
    rcc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rcc)
    card, share = rcc.render(ROOT / "cycle-card" / "seed")
    must = [
        "fwd.page · OODA-loop cycle #152",
        "you rejected PR #28",
        "0.74 → 0.54",
        "PR #29",
        "Full observation",
    ]
    missing = [m for m in must if m not in card]
    r.check(
        "cycle-card render: card contains reject→re-aim LEARN + PR #29 + level name",
        not missing,
        f"missing={missing}" if missing else "all key fields present",
    )
    r.check(
        "cycle-card render: LEARN did NOT fall back to 'no new orientation'",
        "no new orientation" not in card,
        "real LEARN line fired (priority 1 human-reject)",
    )
    r.check(
        "cycle-card render: share line carries the repo handle",
        "github.com/mataeil/OODA-loop" in share,
        "share line present",
    )


def check_auto_merge_gating(r: Runner) -> None:
    """Objective check of the safety-critical auto-merge gate (evolve 4-C)."""
    import importlib.util

    amg_path = ROOT.parent / "scripts" / "auto_merge_gate.py"
    spec = importlib.util.spec_from_file_location("amg", amg_path)
    amg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(amg)
    cfg = load_json(ROOT / "auto-merge-gating" / "seed" / "config.json")

    low_risk = {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1,
                "additions": 3, "deletions": 1, "tests": "passed"}
    ok, _ = amg.eligible(cfg, low_risk)
    r.check("auto-merge-gating: low-risk green PR is eligible", ok, "eligible")

    # stack-agnostic: the gate reads gh-pr facts (files/lines/draft/tests), never
    # language — a low-risk green change is eligible regardless of stack.
    stacks = {
        "go": "pkg/calc.go", "rust": "src/lib.rs", "node": "src/index.ts",
        "ruby": "lib/calc.rb", "java": "src/Main.java",
    }
    elig = [s for s, f in stacks.items()
            if amg.eligible(cfg, {"isDraft": False, "files": [f], "changedFiles": 1,
                                  "additions": 3, "deletions": 1, "tests": "passed"})[0]]
    r.check(
        "auto-merge-gating: gate is stack-agnostic (go/rust/node/ruby/java eligible)",
        len(elig) == len(stacks),
        f"eligible={elig}",
    )

    holds = {
        "protected path": {"isDraft": False, "files": ["skills/evolve/SKILL.md"], "changedFiles": 1, "additions": 2, "deletions": 0, "tests": "passed"},
        "too many files": {"isDraft": False, "files": list("abcdef"), "changedFiles": 6, "additions": 5, "deletions": 0, "tests": "passed"},
        "too many lines": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 200, "deletions": 0, "tests": "passed"},
        "draft": {"isDraft": True, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 0, "tests": "passed"},
        "tests red": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 0, "tests": "failed"},
        "protected skipped": {"isDraft": False, "files": ["src/calc.py"], "changedFiles": 1, "additions": 3, "deletions": 0, "tests": "passed", "protected_blocked": True},
    }
    blocked = [name for name, pr in holds.items() if not amg.eligible(cfg, pr)[0]]
    r.check(
        "auto-merge-gating: protected/large/draft/red/partial-protected all held",
        len(blocked) == len(holds),
        f"held={blocked}",
    )

    # opt-out: with enable_auto_merge false, even a low-risk PR must hold
    cfg_off = json.loads(json.dumps(cfg))
    cfg_off["safety"]["enable_auto_merge"] = False
    ok_off, why_off = amg.eligible(cfg_off, low_risk)
    r.check(
        "auto-merge-gating: default (enable_auto_merge off) holds everything",
        not ok_off,
        why_off,
    )


def check_outcome_scoring(r: Runner) -> None:
    """Outcome Record (Step 6-C9): result_type → quality_multiplier is the atomic
    'did this cycle help?' signal. Verify the reference matches the spec table."""
    import importlib.util

    so_path = ROOT.parent / "scripts" / "score_outcome.py"
    spec = importlib.util.spec_from_file_location("so", so_path)
    so = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(so)

    cases = {
        "pr_merged_held": ({"pr_outcome": "merged_held"}, 1.0),
        "pr_merged": ({"pr_outcome": "merged"}, 0.8),
        "pr_created": ({"result": "success", "pr_number": 7}, 0.5),
        "action_extracted": ({"result": "success", "had_output": True}, 0.2),
        "observe": ({"result": "observe_only"}, 0.1),
        "futile": ({"result": "success", "had_output": False}, 0.0),
        "error": ({"result": "error"}, 0.0),
        "pr_rejected": ({"pr_outcome": "rejected"}, 0.0),
    }
    mismatches = []
    for expect_rt, (cyc, expect_q) in cases.items():
        rt, q = so.score(cyc)
        if rt != expect_rt or q != expect_q:
            mismatches.append(f"{expect_rt}→({rt},{q})")
    r.check(
        "outcome-scoring: all 8 result_types map to the spec quality_multiplier",
        not mismatches,
        f"mismatches={mismatches}" if mismatches else "8/8 match Step 6-C9 table",
    )
    # ordering invariant: merged_held > merged > created > extracted > observe > futile
    ladder = [so.QUALITY[k] for k in
              ("pr_merged_held", "pr_merged", "pr_created", "action_extracted", "observe", "futile")]
    r.check(
        "outcome-scoring: quality ladder is strictly decreasing (held>merged>created>extracted>observe>futile)",
        all(ladder[i] > ladder[i + 1] for i in range(len(ladder) - 1)),
        f"ladder={ladder}",
    )


def check_halt_hook(r: Runner) -> None:
    """The shipped PreToolUse HALT guard (hooks/halt-guard.sh) must deterministically
    block tools while HALT exists, allow clearing it, and never touch non-OODA repos."""
    import subprocess
    import tempfile

    script = ROOT.parent / "hooks" / "halt-guard.sh"
    r.check("halt-hook: hooks.json is valid + guard script present", script.exists()
            and (json.loads((ROOT.parent / "hooks" / "hooks.json").read_text()).get("hooks", {}).get("PreToolUse")) is not None,
            "hooks/hooks.json wires PreToolUse → halt-guard.sh")

    def run(env_dir, stdin):
        return subprocess.run(["bash", str(script)], input=stdin, text=True,
                              capture_output=True, env={**os.environ, "CLAUDE_PROJECT_DIR": env_dir}).returncode

    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "config.json").write_text("{}")
        (Path(d) / "agent" / "safety").mkdir(parents=True)
        rc_noh = run(d, "{}")
        (Path(d) / "agent" / "safety" / "HALT").write_text("stop")
        rc_block = run(d, '{"tool_input":{"command":"npm test"}}')
        rc_clear = run(d, '{"tool_input":{"command":"rm agent/safety/HALT"}}')
    with tempfile.TemporaryDirectory() as nonp:   # no config.json → not an OODA repo
        rc_nonp = run(nonp, "{}")

    r.check("halt-hook: allows tools when no HALT (exit 0)", rc_noh == 0, f"rc={rc_noh}")
    r.check("halt-hook: BLOCKS tools while HALT exists (exit 2)", rc_block == 2, f"rc={rc_block}")
    r.check("halt-hook: allows the HALT-clearing action (exit 0)", rc_clear == 0, f"rc={rc_clear}")
    r.check("halt-hook: no-ops in a non-OODA repo (exit 0)", rc_nonp == 0, f"rc={rc_nonp}")


def check_eval_config(r: Runner) -> None:
    """The opt-in maker/checker (config.eval) must be SAFE by default and never
    waste a model call on a no-value cycle."""
    cfg = load_json(ROOT.parent / "config.example.json")
    ev = cfg.get("eval", {})
    r.check(
        "eval-config: maker/checker is OFF by default (deterministic score stands alone)",
        ev.get("enabled") is False,
        f"eval.enabled={ev.get('enabled')}",
    )
    bad = [g for g in ev.get("grade_on", []) if g in ("futile", "error", "observe")]
    r.check(
        "eval-config: grade_on never includes no-value cycle types (futile/error/observe)",
        not bad and bool(ev.get("grade_on")),
        f"grade_on={ev.get('grade_on')} bad={bad}",
    )


def check_scorecard(r: Runner) -> None:
    """Loop Scorecard (scripts/loop_scorecard.py): the headline measurement
    artifact. Verify the canon KPIs compute correctly from a seeded outcome set."""
    import importlib.util

    sc_path = ROOT.parent / "scripts" / "loop_scorecard.py"
    spec = importlib.util.spec_from_file_location("sc", sc_path)
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    s = sc.compute(ROOT / "scorecard" / "seed")

    expect = {
        "loop_value_score": 0.433,            # (0.1+0.2+0.5+0.8+1.0+0.0)/6
        "task_completion_rate_pct": 33.3,     # 2/6 merged+held
        "futile_cycle_rate_pct": 16.7,        # 1/6
        "pr_merge_rate_pct": 100.0,           # 1/1
        "action_resolution_rate_pct": 50.0,   # 2/4
        "cost_per_successful_cycle": 0.15,     # 0.30/2
        "goal_progress_pct": 75.0,            # mean(0.5, 1.0)
        "skill_gap_resolution_pct": 50.0,     # 2/4 resolved
        "lesson_application_pct": 66.7,       # 2/3 applied
        "mission_hit_pct": 60.0,              # 3 of 5 value-producing cycles on-mission
    }
    mismatches = [k for k, v in expect.items() if s.get(k) != v]
    r.check(
        "scorecard: all canon KPIs compute to the expected values",
        not mismatches,
        f"mismatches={[(k, s.get(k), expect[k]) for k in mismatches]}" if mismatches
        else "loop_value=0.433, TCR=33.3%, futile=16.7%, merge=100%, queue=50%, $/success=0.15",
    )
    # graceful degradation: empty project → all None, never crash
    empty = sc.compute(ROOT / "scorecard")   # dir with no seed/state
    r.check(
        "scorecard: empty/missing state degrades to None (never crashes)",
        empty["loop_value_score"] is None and empty["cycles_scored"] == 0,
        f"empty loop_value={empty['loop_value_score']}",
    )
    # loop-engineering letter grade (Iteration 7)
    letter, comp = sc.grade(s)
    r.check(
        "scorecard: loop-engineering grade computes (fixture → B, 0.798)",
        letter == "B" and comp == 0.798,
        f"grade={letter} composite={comp}",
    )
    r.check(
        "scorecard: grade is DASH on empty state (no data, no false grade)",
        sc.grade(empty)[0] == "—",
        f"empty grade={sc.grade(empty)}",
    )


def check_longhorizon(r: Runner) -> None:
    """Long-horizon thresholds (saturation / contrarian / decay) fire where the
    spec says — verified against the SHIPPED config.example.json values."""
    import importlib.util

    sim_path = ROOT.parent / "scripts" / "sim_longhorizon.py"
    spec = importlib.util.spec_from_file_location("sim", sim_path)
    sim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sim)
    cfg = load_json(ROOT.parent / "config.example.json")
    c = sim._cfg(cfg)

    evs = sim.saturation_events(20, c["warn"], c["boost"], c["halt"])
    warn = [n for n, e in evs if e == "warn"]
    boost = [n for n, e in evs if e == "boost"]
    halt = [n for n, e in evs if e == "halt"]
    r.check(
        "long-horizon: saturation warn@5, boost@10, HALT@15+ (config.example)",
        warn == [5] and boost == [10] and halt and halt[0] == 15,
        f"warn={warn} boost={boost} first_halt={halt[0] if halt else None}",
    )

    contr = sim.contrarian_cycles(20, c["interval"])
    r.check(
        "long-horizon: contrarian check fires at cycles 10 and 20",
        contr == [10, 20],
        f"contrarian cycles = {contr}",
    )

    dd, da = c["decay_days"], c["decay_amount"]
    cases = {13: 0.0, 14: 0.05, 27: 0.05, 28: 0.10, 280: 1.0}
    got = {age: round(sim.decay_factor(age, dd, da), 2) for age in cases}
    r.check(
        "long-horizon: action-queue decay factor matches Step 6-C6 schedule",
        got == cases,
        f"expected={cases} got={got}",
    )


def main() -> int:
    r = Runner()
    r.section("principles-extraction", lambda: check_principles_extraction(r))
    r.section("memo-intervention", lambda: check_memo_intervention(r))
    r.section("cost-ledger-autopatch", lambda: check_cost_ledger_autopatch(r))
    r.section("lens-pre-init", lambda: check_lens_pre_init(r))
    r.section("season-mode-toggle", lambda: check_season_mode_toggle(r))
    r.section("rotation-cursor", lambda: check_rotation_cursor(r))
    r.section("active-context-read", lambda: check_active_context_read(r))
    r.section("cycle-card", lambda: check_cycle_card(r))
    r.section("cycle-card-render", lambda: check_cycle_card_render(r))
    r.section("auto-merge-gating", lambda: check_auto_merge_gating(r))
    r.section("outcome-scoring", lambda: check_outcome_scoring(r))
    r.section("halt-hook", lambda: check_halt_hook(r))
    r.section("eval-config", lambda: check_eval_config(r))
    r.section("long-horizon", lambda: check_longhorizon(r))
    return r.report()


if __name__ == "__main__":
    sys.exit(main())
