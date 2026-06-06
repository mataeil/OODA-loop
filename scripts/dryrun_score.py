#!/usr/bin/env python3
"""Deterministic reference for evolve's Decide scoring (Step 3-A), used to
objectively verify domain ordering — e.g. that a season mode's weight_overrides
flip the winner. Side-effect free.

This implements the documented formula:
    score = staleness + dampened_alert + goals*goal_weight + confidence*conf_weight
            + memo + balance_penalty
    staleness = weight * K * ln(1 + hours/T)   (logarithmic; K=10, T=4)

Scope/assumptions (stated honestly — this is a ranking reference, not the engine):
- "hours since last_run" comes from a domain's state_file if it has `last_run` and
  a --now is supplied; otherwise `scoring.hours_if_never_run` (default 168) is used.
- Season `weight_overrides` for `season_modes.current_mode` are applied when
  `season_modes.enabled`.
- goals / alerts / one-shot memos are read from state if present, else 0.
- balance_penalty is omitted: with equal/unknown execution shares it is equal
  across domains and does not affect ordering (the case these fixtures test).

Usage:
    python3 scripts/dryrun_score.py <config.json> [--now ISO8601]
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path


def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return {}


def score_domains(config_path, now_iso=None, project_root=None):
    cfg = load(config_path)
    root = Path(project_root) if project_root else Path(config_path).resolve().parent
    scoring = cfg.get("scoring", {}) or {}
    K = scoring.get("staleness_k", 10)
    T = scoring.get("staleness_t", 4)
    never = scoring.get("hours_if_never_run", 168)
    conf_weight = scoring.get("conf_weight", 0.2)
    goal_weight = scoring.get("goal_weight", 0.3)
    conf_initial = (cfg.get("confidence", {}) or {}).get("initial", 0.7)

    # season weight overrides
    overrides = {}
    sm = cfg.get("season_modes", {}) or {}
    if sm.get("enabled"):
        mode = sm.get("current_mode")
        overrides = ((sm.get("modes", {}) or {}).get(mode, {}) or {}).get("weight_overrides", {}) or {}

    now = None
    if now_iso:
        try:
            now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
        except Exception:
            now = None

    confs = load(root / "agent" / "state" / "evolve" / "confidence.json")

    results = []
    for name, d in (cfg.get("domains", {}) or {}).items():
        status = d.get("status", "active")
        if status not in ("active", "degraded"):
            continue
        weight = overrides.get(name, d.get("weight", 1.0))

        # hours since last_run
        hours = never
        sf = d.get("state_file")
        if sf and now is not None:
            st = load(root / sf)
            lr = st.get("last_run")
            if lr:
                try:
                    t = datetime.fromisoformat(lr.replace("Z", "+00:00"))
                    hours = max(0.0, (now - t).total_seconds() / 3600.0)
                except Exception:
                    hours = never

        staleness = weight * K * math.log(1 + hours / T)
        confidence = confs.get(name, conf_initial) if isinstance(confs, dict) else conf_initial
        score = staleness + confidence * conf_weight
        results.append((name, round(score, 3), round(weight, 3), round(staleness, 3)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    now_iso = None
    if "--now" in sys.argv:
        now_iso = sys.argv[sys.argv.index("--now") + 1]
    ranked = score_domains(sys.argv[1], now_iso)
    print(f"{'domain':<18}{'score':>10}{'weight':>9}{'staleness':>12}")
    for name, score, weight, stale in ranked:
        print(f"{name:<18}{score:>10}{weight:>9}{stale:>12}")
    if ranked:
        print(f"\nwinner: {ranked[0][0]} (score {ranked[0][1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
