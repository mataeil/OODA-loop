# OODA-loop v1.9.0 — "Ambition": why the loop couldn't make radical jumps

**Date:** 2026-06-19
**Probe:** the f1 game still looked like a 1980s title after v1.7/v1.8 — the
artifact axis worked, the loop climbed honestly to a 0.687 "A"… and an independent
re-grade **against real racing games scored it 0.09 (F+)**.

## Why the loop plateaus at "prototype" (the radical-jump question)

A loop's output quality ceiling is `min(standard, medium, leap-scope)`. All three
were pinned to prototype level:

1. **The standard.** `bar` was 0.65 = "shippable prototype", and the critic graded
   *relative to the artifact's own past* ("better than last cycle"), not against
   best-in-class. So the loop genuinely believed a flat-shaded box-car had
   "cleared the bar" and coasted. **The bar number and the critic's scale were both
   anchored to prototype expectations.** (Re-grade vs real games: 0.09, not 0.69.)
2. **The medium.** Everything was hand-coded Three.js primitives + canvas
   textures. The loop never reached for the techniques that actually make a game
   look modern — post-processing (bloom/tone-map/SSAO/motion-blur), PBR + IBL,
   particle systems, a real sky, shaders, audio design — because the rubric never
   demanded them and the leap prompt only said "overhaul the dimension", so the
   agent took the cheapest path: *more BoxGeometry*.
3. **The leap scope.** Even leaps were single-dimension, additive, ≤1500 lines.
   No cycle ever *re-platformed* (replace the whole rendering pipeline). Radical
   jumps require foundational rewrites the loop structurally avoided. And the
   per-cycle revert gate (`min_dimension_delta`) would kill a cross-cutting rewrite
   that regresses mid-transformation before it pays off.

Net: the loop optimized a coarse proxy that **saturated at "competent prototype"**;
+0.05 felt like progress while the absolute level vs real games was ~0.1.

## The method (v1.9.0)

1. **Dual thresholds** `bar_leap` / `bar_coast`. Below `bar_leap` → always leap;
   coast only above `bar_coast` (set high, ~0.85, anchored to a real product); the
   forcing zone between keeps leaping on stagnation. The loop can no longer declare
   victory at prototype quality. (Back-compat: a lone `bar` sets both equal.)
2. **Benchmark anchors.** Each rubric dimension names what `score_0.10..0.90` look
   like in REAL products; the 5-G critic scores against those, not the artifact's
   past — a flat prototype reads ~0.10, not 0.6. `prototype_ceiling` raises an
   ANCHOR WARNING when the critic is grading on a curve.
3. **Technique menu.** Each dimension lists modern `techniques` + pre-approved
   `technique_cdns`; the leap is told to pick ONE and implement it completely — so
   it reaches for EffectComposer/PMREM/particles instead of more primitives.
4. **Mega-leap.** A human-approved, multi-cycle RE-PLATFORM (bigger budget, atomic
   final-gate rollback) for radical rewrites a bounded leap can't make.
5. **Asset ceilings.** `ceiling_without_assets` per dimension → a `human_required`
   skill_gap instead of thrashing when code-only work tops out.

## Honest limit (the ceiling the loop must respect)

Code + CDN Three.js (no authored 3D models / textures / audio samples) tops out
around **visual ~0.35, audio ~0.20**. Post-processing + PBR/IBL + particles + a
real sky + procedural normal maps + synth engine audio take the game from a
1980s look to a *good stylized web racer* — a 3–4× jump — but **not** to Gran
Turismo. The gap from there is authored art, which the loop cannot manufacture;
v1.9.0 makes the loop surface that as a human hand-off instead of grinding
fruitlessly. The f1 campaign (post-processing+IBL, sky, particles, normal maps,
PBR car + wheel animation, engine audio, camera grade) is the demonstration.
