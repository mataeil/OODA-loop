#!/usr/bin/env python3
"""Deterministic long-horizon simulator for the time/cycle-threshold behaviors
that a short live run can't reach: observation **saturation** (warn/boost/HALT),
the **contrarian** check cadence, and **action-queue decay** over many days.

This is a *logic* reference — it mirrors the exact arithmetic in
`skills/evolve/SKILL.md` (Step 2-A2 saturation, Step 6-C6 decay, the
`cycle % contrarian_check_interval` trigger) so tests/verify.py can assert the
documented thresholds fire at the right cycles/ages without a real 20-cycle,
14-day wall-clock run. It does NOT execute /evolve; the canonical executor is
Claude running the spec. Wall-clock accumulation still happens only in real use.

Usage: python3 scripts/sim_longhorizon.py [config.json]   (prints a 20-cycle trace)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path


def saturation_events(n_cycles, warn, boost, halt):
    """Mirror Step 2-A2: N = consecutive observe-only cycles (1..n_cycles).
    warn fires when N == warn; boost when N == boost; HALT when N >= halt."""
    events = []
    for n in range(1, n_cycles + 1):
        if n == warn:
            events.append((n, "warn"))
        if n == boost:
            events.append((n, "boost"))
        if n >= halt:
            events.append((n, "halt"))
    return events


def contrarian_cycles(n_cycles, interval):
    """Mirror `if cycle_count % contrarian_check_interval == 0`."""
    return [c for c in range(1, n_cycles + 1) if interval and c % interval == 0]


def decay_factor(age_days, decay_days, decay_amount):
    """Mirror Step 6-C6: 0 below the threshold; otherwise
    min((floor((age - decay_days)/decay_days) + 1) * decay_amount, 1.0)."""
    if age_days < decay_days:
        return 0.0
    periods_overdue = math.floor((age_days - decay_days) / decay_days) + 1
    return min(periods_overdue * decay_amount, 1.0)


def _cfg(config):
    sat = (config or {}).get("saturation", {}) or {}
    mem = (config or {}).get("memory", {}) or {}
    return {
        "warn": sat.get("warn_threshold", 5),
        "boost": sat.get("boost_threshold", 10),
        "halt": sat.get("halt_threshold", 15),
        "interval": mem.get("contrarian_check_interval", 10),
        "decay_days": mem.get("action_queue_decay_days", 14),
        "decay_amount": mem.get("action_queue_decay_amount", 0.05),
    }


def main() -> int:
    config = {}
    if len(sys.argv) > 1:
        config = json.loads(Path(sys.argv[1]).read_text())
    c = _cfg(config)
    N = 20
    print(f"thresholds: saturation warn={c['warn']} boost={c['boost']} halt={c['halt']} "
          f"· contrarian every {c['interval']} · decay {c['decay_amount']}/{c['decay_days']}d")
    print(f"\n{N}-cycle observe-only trace (saturation counter):")
    sat = dict(saturation_events(N, c["warn"], c["boost"], c["halt"]))
    contr = set(contrarian_cycles(N, c["interval"]))
    for n in range(1, N + 1):
        tags = []
        if n in [e[0] for e in saturation_events(N, c["warn"], c["boost"], c["halt"]) if e[1] == "warn"]:
            tags.append("⚠ saturation warn")
        if n == c["boost"]:
            tags.append(f"⚠ boost +{(config.get('saturation') or {}).get('implementation_boost', 5.0)}")
        if n >= c["halt"]:
            tags.append("🛑 HALT")
        if n in contr:
            tags.append("contrarian check")
        print(f"  cycle {n:>2}: streak={n:<2} {'· '.join(tags)}")
    print("\ndecay schedule (rice_score=100):")
    for age in [13, 14, 27, 28, 280]:
        f = decay_factor(age, c["decay_days"], c["decay_amount"])
        print(f"  age {age:>3}d → factor {f:.2f} → effective_rice {100 * (1 - f):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
