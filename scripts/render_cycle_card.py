#!/usr/bin/env python3
"""Reference renderer for the evolve Step 7 Cycle Card (and /ooda-status --share).

This is a deterministic, side-effect-free implementation of the Cycle Card
data-sourcing + LEARN-priority + graceful-degradation logic specified in
skills/evolve/SKILL.md Step 7. The canonical executor is Claude running the
SKILL.md, but this script proves the card renders end-to-end from real on-disk
state and lets `tests/verify.py`-style checks assert the output objectively.

Usage:
    python3 scripts/render_cycle_card.py <project_dir>

<project_dir> must contain config.json and agent/state/ (as a real project does).
Prints the Cycle Card and the plain-text share line. Exits 0 on success,
prints a "No cycle to card yet." notice (exit 0) if decision_log is empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


DASH = "—"


def fmt_num(x):
    if x is None:
        return DASH
    return f"{x:g}"


def render(project: Path) -> tuple[str, str]:
    cfg = load(project / "config.json", {}) or {}
    ev = project / "agent" / "state" / "evolve"
    state = load(ev / "state.json", {}) or {}
    conf = load(ev / "confidence.json", {}) or {}
    ledger = load(ev / "cost_ledger.json", {}) or {}
    reflections = (load(ev / "reflections.json", {}) or {}).get("reflections", [])

    log = state.get("decision_log", []) or []
    if not log:
        return ("No cycle to card yet. Run /evolve first.", "")
    d = log[-1]

    name = (cfg.get("project") or {}).get("name", "project")
    cyc = state.get("cycle_count", d.get("cycle", DASH))
    ts = (d.get("timestamp") or "").replace("T", " ").replace("Z", " UTC").strip() or DASH

    # OBSERVE: active domain count
    domains = cfg.get("domains", {}) or {}
    active = [n for n, dd in domains.items() if dd.get("status") == "active"]
    observe = f"{len(active)} domains scanned" if active else DASH

    # ORIENT
    orient = d.get("orient_summary") or DASH

    # DECIDE
    dom = d.get("domain", DASH)
    score = fmt_num(d.get("score"))
    confidence = d.get("confidence", conf.get(dom))
    gate = "OK" if (confidence is not None and confidence >= 0.6) else ("low" if confidence is not None else DASH)
    decide = f"{dom} won (score {score}) · confidence {fmt_num(confidence)} · gate {gate}"

    # ACT
    result = d.get("result", DASH)
    pr = d.get("pr_number")
    if pr:
        act = f"{result} → PR #{pr}"
        pr_detail = f"Risk Tier {d.get('risk_tier', DASH)} · draft — you merge"
    else:
        act = result
        pr_detail = ""

    # LEARN — priority order (Step 7)
    learn = []
    # 1) human-decision confidence change (pr_outcomes on this cycle)
    for o in d.get("pr_outcomes", []) or []:
        delta = o.get("confidence_delta")
        odom = o.get("domain")
        before = conf.get(odom)
        if before is not None and delta is not None:
            before_val = round(before - delta, 4)
        else:
            before_val = None
        if o.get("outcome") == "rejected":
            learn.append(
                f"you rejected PR #{o.get('pr')} → {odom} confidence "
                f"{fmt_num(before_val)} → {fmt_num(before)} ↓ (reject {fmt_num(delta)})"
            )
        elif o.get("outcome") == "merged":
            learn.append(
                f"you merged PR #{o.get('pr')} → {odom} confidence "
                f"{fmt_num(before_val)} → {fmt_num(before)} ↑ (merge {fmt_num(delta)})"
            )
    # 2) lens change (newest lens_changelog entry across domains for this cycle)
    state_root = project / "agent" / "state"
    newest = None
    if state_root.exists():
        for lc in state_root.glob("*/lens_changelog.json"):
            data = load(lc, {}) or {}
            for e in data.get("entries", []) or []:
                if e.get("cycle") == cyc:
                    if newest is None:
                        newest = e
    if newest:
        learn.append(
            f"lens re-aimed → {newest.get('item')} "
            f"{fmt_num(newest.get('before'))} → {fmt_num(newest.get('after'))}"
        )
    # 3) a new intervention written this cycle (memos.json)
    if not learn:
        memos = load(ev / "memos.json")
        for iv in (memos.get("interventions", []) or []):
            if iv.get("created_at_cycle") == cyc:
                learn.append(
                    f"{iv.get('type')} → {iv.get('domain')} {fmt_num(iv.get('delta'))} "
                    f"for {iv.get('expires_after_cycles')} cycle(s)"
                )
                break
    # 4) observation micro-adjustment (confidence delta vs previous cycle, same domain)
    if not learn and len(log) >= 2:
        prev = log[-2]
        if (prev.get("domain") == dom and prev.get("confidence") is not None
                and d.get("confidence") is not None):
            delta = round(d["confidence"] - prev["confidence"], 3)
            if abs(delta) >= 0.001:
                sign = "+" if delta > 0 else ""
                learn.append(
                    f"{dom} confidence {fmt_num(prev['confidence'])} → "
                    f"{fmt_num(d['confidence'])} ({sign}{delta})"
                )
    # 5) re-applied reflection lesson (fallback)
    if not learn and reflections:
        learn.append(f"recalled lesson: {reflections[-1].get('lesson', '')}")
    # 6) nothing
    if not learn:
        learn.append(f"no new orientation this cycle (observing)")

    # COST
    entries = ledger.get("entries", []) or []
    cyc_cost = next((e.get("estimated_usd") for e in entries if e.get("cycle_id") == cyc), None)
    total = ledger.get("total_estimated_usd")
    cap = (cfg.get("cost") or {}).get("daily_limit_usd")
    cost = (
        f"+${fmt_num(cyc_cost)} · ${fmt_num(total)} today · hard cap ${fmt_num(cap)} (auto-HALTs)"
        if total is not None else DASH
    )

    # footer level label from config (verbatim)
    lvl = (cfg.get("progressive_complexity") or {}).get("current_level")
    lvl_name = DASH
    levels = (cfg.get("progressive_complexity") or {}).get("levels", {}) or {}
    if str(lvl) in levels:
        lvl_name = levels[str(lvl)].get("name", DASH)
    halt = "ACTIVE" if (project / "agent" / "safety" / "HALT").exists() else "inactive"

    # ---- compose (clean labeled block; content correctness over ASCII-art) ----
    lines = [f"{name} · OODA-loop cycle #{cyc} — {ts}", ""]

    def row(label, text):
        lines.append(f"  {label:<8}{text}" if label else f"  {'':<8}{text}")

    row("OBSERVE", observe)
    row("ORIENT", orient)
    row("DECIDE", decide)
    row("ACT", act)
    if pr_detail:
        row("", "└ " + pr_detail)
    for i, ln in enumerate(learn):
        row("LEARN" if i == 0 else "", ("🔭 " if i == 0 else "   ") + ln)
    row("COST", cost)
    lines.append("")
    lines.append(f"  HALT: {halt} · Level {lvl} ({lvl_name})")
    card = "\n".join(lines)

    share = (
        f"{name} ran OODA-loop cycle #{cyc}: {dom} → {act}. "
        f"Learned: {learn[0].rstrip('.')}. Cost +${fmt_num(cyc_cost)}/cycle (${fmt_num(total)} today). "
        f"— github.com/mataeil/OODA-loop"
    )
    return card, share


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    project = Path(sys.argv[1]).resolve()
    card, share = render(project)
    print(card)
    if share:
        print()
        print(share)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
