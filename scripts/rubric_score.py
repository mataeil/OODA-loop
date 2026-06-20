#!/usr/bin/env python3
"""Artifact-quality scoring — the missing axis (OODA-loop v1.7.0).

The F1-game dogfood proved the loop measured *process* (did a PR/commit advance?)
and was blind to the *artifact* (is the thing good?). Every cycle scored 0.5 and
graded A while the game was dismal. This module is the deterministic half of the
fix: given per-dimension scores produced by the independent Artifact Critic
(evolve Step 5-G), it aggregates a single `artifact_score`, decides whether the
artifact clears its mission `bar`, raises the **Goodhart Guard** (process green
but artifact below bar = the scoreboard is lying), and detects a **plateau** in
the artifact-quality series (the trigger for a LEAP cycle).

Side-effect free. The single source of truth shared by the engine (Steps 5-G,
2-G, 6-C9), scripts/score_outcome.py, scripts/loop_scorecard.py, and the tests —
exactly as score_outcome.py is the single source of truth for the process axis.

The MODEL half (looking at the artifact, scoring each dimension) lives in the
engine's Step 5-G; this script never calls a model. It only does the arithmetic
on the dimension scores the critic recorded, so every consumer agrees.

Usage: python3 scripts/rubric_score.py <project_dir>   (scores the latest cycle)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Defaults used when config.quality_rubric omits a field. A rubric that clears
# `bar` on average is "good enough to keep adding features"; below it, the loop
# should LEAP on the weakest dimension instead of bolting on more.
DEFAULT_BAR = 0.70
DEFAULT_PLATEAU_WINDOW = 4      # build cycles to look back over
DEFAULT_PLATEAU_EPS = 0.05      # min artifact_score gain over the window to count as progress
# v1.9.0 "Ambition": dual thresholds. The single `bar` made the loop COAST the
# instant it cleared a prototype-level number, so it never pushed toward a real
# product. bar_leap = below this, ALWAYS leap; bar_coast = until this, never coast
# (the forcing zone in between alternates leap/feature). Set bar_coast high
# (~0.85) so "it exists and works" can't masquerade as "it's genuinely good".
DEFAULT_BAR_COAST = 0.85
DEFAULT_PROTOTYPE_CEILING = 0.20  # below this, the critic is likely grading vs a prototype, not best-in-class


def _load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def rubric_of(config: dict, domain: str | None = None) -> dict:
    """Resolve the active quality rubric from config, with safe defaults.

    Resolution order (v1.7.0): the per-domain rubric
    `config.domains[domain].quality_rubric` (the canonical, domain-agnostic
    location — evolve is domain-agnostic), then a named-domain fallback if
    `domain` is None, then top-level `config.quality_rubric` (simple single-domain
    projects). Accepts either `dimensions` or `axes` as the key (the per-domain
    config uses `axes`)."""
    config = config or {}
    r = {}
    domains = config.get("domains") or {}
    if domain and isinstance(domains.get(domain), dict):
        r = (domains[domain].get("quality_rubric") or {})
    if not r:
        for d in domains.values():
            if isinstance(d, dict) and d.get("quality_rubric"):
                r = d["quality_rubric"]
                break
    if not r:
        r = config.get("quality_rubric") or {}
    dims = r.get("dimensions") or r.get("axes") or []
    bar = r.get("bar", DEFAULT_BAR)
    return {
        "dimensions": dims,
        "bar": bar,
        # v1.9.0 dual thresholds. Back-compat: a project with only `bar` set gets
        # bar_leap == bar_coast == bar (old single-bar behaviour). To open the
        # forcing zone, the project sets bar_coast (e.g. 0.85) above bar_leap.
        "bar_leap": r.get("bar_leap", bar),
        "bar_coast": r.get("bar_coast", bar),
        "prototype_ceiling": r.get("prototype_ceiling", DEFAULT_PROTOTYPE_CEILING),
        "plateau_window": r.get("plateau_window", DEFAULT_PLATEAU_WINDOW),
        "plateau_eps": r.get("plateau_eps", DEFAULT_PLATEAU_EPS),
        "enabled": bool(dims),     # no dimensions defined → artifact axis is off (back-compat)
    }


def aggregate(dimension_scores: dict, rubric: dict) -> dict:
    """Weighted-mean the per-dimension scores into one artifact_score.

    dimension_scores: { name: score(0..1) } as recorded by the critic (5-G).
    rubric.dimensions: [ { name, weight, bar? } ].
    Returns { artifact_score, weakest_dimension, weakest_score, covered, missing }.
    A dimension the critic did not score is treated as MISSING (not 0) — but if it
    is missing it cannot be hidden: it is reported so the critic is forced to cover
    the whole rubric (an un-scored dimension is a critic failure, not a free pass).
    """
    dims = rubric.get("dimensions") or []
    if not dims:
        return {"artifact_score": None, "weakest_dimension": None,
                "weakest_score": None, "covered": 0, "missing": []}
    num = 0.0
    den = 0.0
    weakest = None
    weakest_score = 2.0
    covered = 0
    missing = []
    for d in dims:
        name = d.get("name")
        w = float(d.get("weight", 1.0))
        if name in (dimension_scores or {}):
            s = float(dimension_scores[name])
            num += w * s
            den += w
            covered += 1
            if s < weakest_score:
                weakest_score, weakest = s, name
        else:
            missing.append(name)
    artifact_score = round(num / den, 3) if den else None
    return {
        "artifact_score": artifact_score,
        "weakest_dimension": weakest,
        "weakest_score": None if weakest_score > 1.5 else round(weakest_score, 3),
        # v1.7.1: the dimension a LEAP should target — the one whose improvement
        # most raises the OVERALL (weighted-mean) artifact_score, i.e. largest
        # weight × gap-to-bar, NOT merely the lowest raw score. Surfaced by the F1
        # dogfood: visual_fidelity (gap .24 × weight .28) outranks fun_challenge
        # (gap .27 × weight .20) — fixing it moves the headline more and matches
        # what a player perceives as "crap". Falls back to the lowest raw score.
        "leap_target": _weighted_gap_target(dimension_scores or {}, dims, rubric),
        "covered": covered,
        "missing": missing,
    }


def _weighted_gap_target(dimension_scores: dict, dims: list, rubric: dict) -> str | None:
    """Pick the dimension with the largest weight × max(0, bar − score). Ties
    break to the lower raw score (the more broken one). v1.9.0: gap is measured to
    the COAST bar (distance to "good"), not the leap bar, so targeting reflects
    distance to the real goal."""
    bar = rubric.get("bar_coast", rubric.get("bar", DEFAULT_BAR))
    best, best_key = None, None
    for d in dims:
        name = d.get("name")
        if name not in dimension_scores:
            continue
        s = float(dimension_scores[name])
        w = float(d.get("weight", 1.0))
        impact = w * max(0.0, bar - s)
        key = (round(impact, 6), -s)   # max impact, then lowest score
        if best is None or key > best:
            best, best_key = key, name
    return best_key


def meets_bar(artifact_score, rubric: dict) -> bool:
    """'Good enough to stop leaping' = cleared the COAST bar (v1.9.0). Back-compat:
    when bar_coast defaults to bar, this is the old behaviour."""
    if artifact_score is None:
        return True   # no artifact axis configured → don't block (back-compat)
    return artifact_score >= rubric.get("bar_coast", rubric.get("bar", DEFAULT_BAR))


def goodhart_flag(process_green: bool, artifact_score, rubric: dict) -> dict:
    """The 'measurement is lying' detector. process_green := futile≈0 and goal high.
    If the process scoreboard is green but the artifact is below bar, the headline
    grade must be capped and the operator warned."""
    coast = rubric.get("bar_coast", rubric.get("bar", DEFAULT_BAR))
    lying = bool(process_green) and artifact_score is not None and not meets_bar(artifact_score, rubric)
    # v1.9.0 anchor warning: a very low artifact_score suggests the critic is
    # grading vs a prototype, not best-in-class (re-anchor the rubric references).
    ceil = rubric.get("prototype_ceiling", DEFAULT_PROTOTYPE_CEILING)
    anchor_warn = artifact_score is not None and artifact_score < ceil
    msg = ""
    if lying:
        msg = ("MEASUREMENT WARNING: process green but artifact %.2f < coast bar %.2f — "
               "the scoreboard is lying; cap grade and LEAP." % (artifact_score, coast))
    elif anchor_warn:
        msg = ("ANCHOR WARNING: artifact %.2f below prototype_ceiling %.2f — this is "
               "prototype-level vs best-in-class; keep leaping (don't trust a high process grade)." % (artifact_score, ceil))
    return {"lying": lying, "anchor_warn": bool(anchor_warn), "message": msg}


def artifact_series(outcomes: list) -> list:
    """The chronological artifact_score series from cycles that actually had one."""
    return [e.get("artifact_score") for e in outcomes
            if e.get("artifact_score") is not None]


def detect_plateau(outcomes: list, rubric: dict) -> dict:
    """A plateau = artifact quality is NOT improving despite cycles shipping.
    Trigger for a LEAP. Two independent signals (either fires):
      (1) over the last `window` artifact-scored cycles, max - first < eps, OR
      (2) the same `weakest_dimension` has stayed weakest for `window` cycles.
    Also reports `below_bar` so a never-yet-good artifact leaps even before a
    full window exists."""
    window = int(rubric.get("plateau_window", DEFAULT_PLATEAU_WINDOW))
    eps = float(rubric.get("plateau_eps", DEFAULT_PLATEAU_EPS))
    scored = [e for e in outcomes if e.get("artifact_score") is not None]
    series = [e["artifact_score"] for e in scored]
    latest = series[-1] if series else None
    below_bar = latest is not None and not meets_bar(latest, rubric)

    stagnant = False
    if len(series) >= window:
        tail = series[-window:]
        stagnant = (max(tail) - tail[0]) < eps

    weak_stuck = False
    weak_dims = [e.get("weakest_dimension") for e in scored if e.get("weakest_dimension")]
    if len(weak_dims) >= window:
        tail = weak_dims[-window:]
        weak_stuck = len(set(tail)) == 1 and tail[0] is not None

    # v1.9.0 dual-bar plateau: leap if (stagnant OR weak-stuck OR below bar_leap),
    # as long as we are not yet at bar_coast. Below bar_leap ALWAYS leaps (don't
    # wait for a full stagnation window when quality is still prototype-level);
    # the forcing zone (bar_leap..bar_coast) leaps on stagnation. This is the fix
    # for "the loop coasted the instant it cleared a prototype bar".
    bar_leap = rubric.get("bar_leap", rubric.get("bar", DEFAULT_BAR))
    bar_coast = rubric.get("bar_coast", rubric.get("bar", DEFAULT_BAR))
    below_coast = latest is not None and latest < bar_coast
    below_leap = latest is not None and latest < bar_leap
    plateau = (stagnant or weak_stuck or below_leap) and below_coast
    reasons = []
    if below_leap:
        reasons.append("artifact %.2f below leap bar %.2f (always leap)" % (latest, bar_leap))
    if stagnant:
        reasons.append("artifact_score flat over last %d cycles (<=%.2f gain)" % (window, eps))
    if weak_stuck:
        reasons.append("'%s' weakest for %d cycles running" % (weak_dims[-1], window))
    if below_coast and not (stagnant or weak_stuck or below_leap):
        reasons.append("artifact %.2f in forcing zone (< coast %.2f)" % (latest, bar_coast))
    # v1.7.1: the LEAP target is the largest weighted gap on the latest critique,
    # not just the running weakest_dimension (impact on the headline metric).
    latest_dims = (scored[-1].get("dimension_scores") if scored else None) or {}
    leap_target = (_weighted_gap_target(latest_dims, rubric.get("dimensions") or [], rubric)
                   or (weak_dims[-1] if weak_dims else None))
    return {
        "plateau": bool(plateau),
        "below_bar": bool(below_bar),
        "latest": latest,
        "weakest_dimension": weak_dims[-1] if weak_dims else None,
        "leap_target": leap_target,
        "reason": "; ".join(reasons) if reasons else "improving",
    }


def failed_leaps(outcomes: list, dimension: str, min_delta: float) -> int:
    """v1.8.0 thrashing-guard count (deterministic ground truth for evolve 2-G).
    Counts leap cycles whose `leap_attempts` on `dimension` failed to clear
    `min_delta`. The v1.7.x engine read a nonexistent field `leap_delta` and
    matched the raw weakest_dimension, so this was ALWAYS 0 and the guard never
    fired — the loop could thrash forever. The real ledger field is
    `leap_attempts[].delta_score`, keyed on the dimension actually leapt."""
    n = 0
    for e in outcomes:
        if e.get("cycle_mode") != "leap":
            continue
        for a in (e.get("leap_attempts") or []):
            if a.get("dimension") == dimension and a.get("delta_score", 1.0) < min_delta:
                n += 1
    return n


def asset_ceiling(dimension: dict):
    """v1.10.0 asset hand-off: the score above which CODE-ONLY work can't climb.
    Returns None (no ceiling) once the OPERATOR has supplied `asset_sources` for the
    dimension — the v1.9.0 `human_required` hand-off is fulfilled, so the loop may
    keep leaping toward bar_coast with the authored assets (models/textures/HDRIs/
    audio). Otherwise returns `ceiling_without_assets` (or None if unset). This is
    what closes the v1.9.0 ceiling concept: the loop stops at the code-only limit,
    flags human_required, and — once assets arrive — resumes."""
    if dimension.get("asset_sources"):
        return None
    c = dimension.get("ceiling_without_assets")
    return float(c) if isinstance(c, (int, float)) else None


def asset_ceiling_hit(dimension: dict, score) -> bool:
    """True iff a code-only leap has topped out: at/above the ceiling AND no assets
    supplied yet. evolve 2-G records a `human_required` skill_gap instead of leaping
    again; supplying `asset_sources` clears it and re-opens leaping."""
    ceil = asset_ceiling(dimension)
    return ceil is not None and score is not None and score >= ceil


def lock_target(outcomes: list, rubric: dict, leap_target: str | None) -> str | None:
    """v1.8.0 dimension-lock: after a SUCCESSFUL leap whose target is still below
    (bar − eps), return that target so evolve 2-G keeps the plateau active on it
    (drive-to-bar) instead of coasting through feature cycles and re-rotating.
    Returns None when nothing should be locked (no leap last, regressed, or the
    target is at/near bar — the tolerance band stops critic variance from locking
    the loop forever; the max_attempts HALT is the genuine-stuck backstop)."""
    if not leap_target or not outcomes:
        return None
    last = outcomes[-1]
    if last.get("cycle_mode") != "leap" or last.get("result_type") == "leap_regressed":
        return None
    bar = rubric.get("bar_coast", rubric.get("bar", DEFAULT_BAR))  # v1.9.0: lock until COAST (good), not prototype bar
    eps = float(rubric.get("plateau_eps", DEFAULT_PLATEAU_EPS))
    score = (last.get("dimension_scores") or {}).get(leap_target)
    if score is None:
        return None
    return leap_target if score < bar - eps else None


def compute(project: Path) -> dict:
    ev = Path(project) / "agent" / "state" / "evolve"
    config = _load(Path(project) / "config.json", {}) or {}
    rubric = rubric_of(config)
    outcomes = (_load(ev / "outcomes.json", {}) or {}).get("entries", []) or []
    latest = outcomes[-1] if outcomes else {}
    agg = aggregate(latest.get("dimension_scores") or {}, rubric)
    plateau = detect_plateau(outcomes, rubric)
    return {
        "enabled": rubric["enabled"],
        "bar": rubric["bar"],
        "latest_artifact_score": agg["artifact_score"],
        "weakest_dimension": agg["weakest_dimension"],
        "missing_dimensions": agg["missing"],
        "meets_bar": meets_bar(agg["artifact_score"], rubric),
        "plateau": plateau,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    s = compute(Path(sys.argv[1]))
    if not s["enabled"]:
        print("No quality_rubric configured — artifact axis off (process-only scoring).")
        return 0
    a = s["latest_artifact_score"]
    print("artifact_score=%s  bar=%.2f  meets_bar=%s  weakest=%s" % (
        "—" if a is None else a, s["bar"], s["meets_bar"], s["weakest_dimension"]))
    if s["missing_dimensions"]:
        print("  ⚠ critic did not score: %s" % ", ".join(s["missing_dimensions"]))
    p = s["plateau"]
    print("plateau=%s (%s)" % (p["plateau"], p["reason"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
