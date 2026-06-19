# OODA-loop v1.8.0 — driving quality to "good", not "passable"

**Date:** 2026-06-19
**Purpose reminder:** the f1-racing game is a **probe**, not the product. Its job
is to expose what OODA-loop still gets wrong. This release is about the loop.

## The probe's verdict (why we believe the loop is still the bottleneck)

v1.7.0 fixed *measurement* (artifact axis) and *anti-incrementalism* (leap
cycles). It worked — the loop went from a flat, lying A to a climbing, honest D.
But after **three** real leap cycles the owner's verdict is unchanged: *still too
crappy.* The data says why:

| | artifact_quality | note |
|---|---|---|
| 22 feature cycles (old loop) | **0.394** (flat) | Goodhart collapse |
| + leap 1 (visual) | 0.447 | +0.053 |
| + leap 2 (track) | 0.472 | +0.025 |
| + leap 3 (car/cockpit) | 0.522 | +0.050 |
| bar (shippable) | 0.65 | not reached |
| "genuinely good" | ~0.80 | far off |

Average **~+0.04 per leap**. At that rate "good" is ~7 leaps away. The loop
*climbs* but it climbs **too slowly and stops too low**. Three concrete failures
observed during the campaign point at the loop, not the game:

1. **It settles for "+0.05 better."** A leap's success test is
   `min_dimension_delta` (0.05) — so the moment a dimension nudges up, the loop
   declares victory and moves the weighted-gap target elsewhere, abandoning a
   dimension while it is still *bad* (visual went 0.22→0.41→0.59 across two
   separate leaps with other work in between; it was never driven to the bar in
   one sustained push).
2. **It accepts partial implementation of its own plan.** Leap 3's design panel
   specced car/cockpit **and** materials/lighting **and** environment; only
   car/cockpit shipped. The dropped materials/lighting (shadows, tone-mapping,
   textures) was the *single most-repeated* critic complaint at every leap — and
   it silently vanished. The act step under-delivers with no completion check.
3. **It can't see motion, feel, or fun.** The critic scores one still
   screenshot, so `driving_feel` and `fun_challenge` are unmeasurable and
   unimprovable — they sit at 0.38–0.51 and cap the weighted mean.

## Root cause (from a 13-agent, adversarially-verified diagnosis)

> The loop **detects** a quality gap and takes *a* step at it, but is not built to
> **close** it. It (1) can't see ~45% of its own rubric — `driving_feel` + `fun_challenge`
> were scored from a still screenshot and sat frozen across all 25 cycles; (2)
> abandons a dimension after a +0.05 nudge and rotates targets instead of driving
> one to the bar; (3) had a **silently broken thrashing guard** (read a nonexistent
> `leap_delta` field → never fired → could thrash forever); and (4) accepts partial
> implementation of its own leap plans, orphaning the rest. It optimizes to
> "better," never to "good."

The devil's-advocate agent confirmed the leap *routing* is sound — the binding
constraint is **perception** (the critic can't measure feel/fun), not more leap
machinery. That reframed the fix.

## The v1.8.0 upgrades (ranked by leverage)

1. **Fix the thrashing guard (prerequisite, real bug).** 2-G now counts
   `leap_attempts[].delta_score` on the `leap_target` (was: nonexistent `leap_delta`
   on `weakest_dimension`). The HALT safety valve actually fires now —
   `rubric_score.failed_leaps()` is the deterministic ground truth.
2. **Per-dimension `capture_method` (5-G).** Each rubric axis declares how its
   evidence is captured; experiential axes use `gameplay_metrics` — a
   HUMAN-AUTHORED, hash-verified, protected harness (same independence invariant
   as the rubric hash). Missing/unverified harness → the axis scores `null`
   (capture_failure) + a skill_gap, never a faked or screenshot-fallback score.
   Unlocks the frozen 45% of rubric weight.
3. **Dimension lock until bar (2-G).** After a successful leap whose target is
   still below `bar − eps`, keep the plateau active on the SAME target so 3-K
   leaps it again next cycle — drive-to-bar, not detect-and-nudge. A tolerance
   band + the (now-working) max-attempts HALT prevent infinite lock.
   `rubric_score.lock_target()` is the deterministic ground truth;
   `config.leap.lock_until_bar` (default true) toggles it.
4. **Auto-queue the remainder (5-G).** If a leap passes its delta gate but the
   dimension is still below bar, the *independent critic's* score (not the
   maker's self-report) queues a high-RICE remainder so dropped scope can't
   vanish. Records `leap_dim_still_below_bar`.

All four are deterministic where possible (`scripts/rubric_score.py`), config-
driven, and gaming-resistant. `tests/verify.py` 59 → **61**.

## What we deliberately did NOT change (rejected / devil's-advocate-validated)

- **Don't raise the bar to 0.80 yet.** It only re-points the weighted-gap target
  at an unmeasurable dimension and (pre-fix) would HALT the loop. Raise only after
  a `gameplay_metrics` leap proves feel/fun are responsive. Stage 0.65→0.75→0.80.
- **No inner multi-pass refine loop (yet).** The 3 completed leaps each landed
  substantial single-pass deltas (+0.19/+0.27/+0.18); the cap was perception, not
  pass-count. Adding passes on unmeasurable dimensions = cost with no signal.
- **No LLM-component-coverage gate.** Gameable (touch one file per "component" →
  100%). Change 4's critic-driven remainder is the robust substitute.
- **No `multi_probe` still-sequence.** A burst of stills still can't tell
  responsive steering from sluggish; `gameplay_metrics` is the right instrument.

## Validation (leap 4 under the upgraded loop)

<!-- run a leap with the new loop; show visual_fidelity driven toward the bar in a
     sustained push (dimension lock) and the previously-dropped materials/lighting
     actually shipped -->
