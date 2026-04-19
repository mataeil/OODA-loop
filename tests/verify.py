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


def main() -> int:
    r = Runner()
    r.section("principles-extraction", lambda: check_principles_extraction(r))
    r.section("memo-intervention", lambda: check_memo_intervention(r))
    r.section("cost-ledger-autopatch", lambda: check_cost_ledger_autopatch(r))
    r.section("lens-pre-init", lambda: check_lens_pre_init(r))
    r.section("season-mode-toggle", lambda: check_season_mode_toggle(r))
    r.section("rotation-cursor", lambda: check_rotation_cursor(r))
    r.section("active-context-read", lambda: check_active_context_read(r))
    return r.report()


if __name__ == "__main__":
    sys.exit(main())
