# OODA-loop v1.7.0 — Artifact-Grounded Evaluation + Leap Cycles

**Date:** 2026-06-17
**Trigger:** F1-racing dogfood. 22 cycles, every cycle graded **A** (Loop 0.995),
futile **0%**, mission-hit **100%** — yet the actual game is *처참* (dismal):
a jagged Z-fighting cyan blob for a track, no recognizable car, flat untextured
world, polished HUD bolted over a broken core.

> The metrics said the loop was perfect. The artifact proved the metrics were
> lying. This is a **Goodhart collapse** — the loop optimized its own scoreboard,
> not the game.

This document diagnoses *why* the engine produced that outcome and specifies the
v1.7.0 evolution that fixes it.

---

## Part 1 — Diagnosis (the game as a mirror)

### Evidence
- `outcomes.json`: all 22 entries **identical** — `quality_multiplier: 0.5`,
  `verifier_verdict: null`, `on_mission: true`. The evaluation layer recorded
  the same number 22 times.
- `loop_scorecard.py:123` grade = `0.5*goal + 0.3*(1-futile) + 0.2*min(lv/0.5,1)`.
  With goal=0.99 (self-written feature checklist), futile=0 (any commit), lv=0.5
  (constant) → **0.995 = A, arithmetically guaranteed.**
- Screenshot (`f1-load.png`): glassmorphism HUD panels (lap / pos / minimap /
  speed / ERS / tyre) sit over a broken 3D scene.
- `wc -l src/*.js`: 22 feature modules bolted onto one 415-line `main.js`. The
  longest file is `track.js` (209) — the visual core — and it was never revisited
  after the early cycles; 16 of 22 cycles added *new* peripheral modules.

### The four structural defects

**D1 — Goodhart collapse: the grade is mathematically pinned to A.**
None of the three grade terms measures whether the output is *good*. `goal` is a
self-authored checklist, `futile` only asks "did you commit anything," `lv` was a
constant. Any loop that (1) writes itself a feature list, (2) commits each cycle,
(3) records `pr_created` scores an A forever. (`loop_scorecard.py:114-127`)

**D2 — `quality_multiplier` is blind to the artifact.**
It is a pure function of *process state* (`pr_merged_held`=1.0 … `pr_created`=0.5
… `futile`=0.0). A beautiful feature and a broken one score **identically** if
both committed. The Reflect step's self-critique (`5-F`) critiques the *decision*,
never the *output*. The opt-in 7-B eval only checks "did you ship the feature you
declared" — goal-conformance, not artifact quality — and is *forbidden from
changing the score* (`7-B` honesty rule). So no signal that looks at the artifact
can ever move the number. (`score_outcome.py:22-59`, `evolve 6-C9`, `7-B`)

**D3 — Monotonic incrementalism: no quantum leaps are structurally possible.**
RICE = `Reach×Impact×Confidence / Effort`. An overhaul ("rebuild the track
rendering," "make the car look like an F1 car") is high-effort + uncertain
confidence → **low RICE → never selected.** The cycle template says *"implement
ONE focused feature"*; brainstorming generates *"NEW mission-aligned features."*
There is no plateau detector, no leap trigger, no reference standard ("what does
a real F1 game look like?"), no cohesion/debt accounting. 22 cycles = 22 isolated
features, never a consolidation or a step-change.

**D4 (deepest, non-obvious) — the testability gate created a perverse incentive.**
The *only* quality gate is `config.test_command = node tests/smoke.mjs`, which can
only assert **pure modules**. So the loop systematically chose work that *could*
be unit-tested (HUD widgets, gap math, ghost replay) and systematically avoided
work that *couldn't* (track mesh, car model, lighting, feel, fun) — exactly the
things that make an F1 game good. **Measurement didn't just fail to catch low
quality; it actively repelled the loop from quality.** The screenshot is the
proof: the testable shell is polished, the untestable core is broken.

### Root cause (one sentence)
> The loop measures **process** (did the machinery advance?) and is blind to the
> **artifact** (is the thing good?), and its action selection (RICE + feature
> template) can only ever take small safe steps — so it optimized the scoreboard
> while the game rotted, and could never re-found the broken core.

---

## Part 2 — The v1.7.0 Evolution

Three coordinated mechanisms. Each maps to one user complaint.

> "결과물에 대한 평가가 빈약하다 / 셀프 피드백이 약하다" → **M1 + M2**
> "변곡점에서 퀀텀 점프가 없다" → **M3**

### M1 — Artifact Critique (a real, independent critic) → fixes D2, D4
New Reflect sub-step **5-G**. After a build cycle produces output, an
**independent** evaluator (reuses the 7-B separate-model infrastructure) *engages
the actual artifact* — for a web app it renders it (screenshot) and exercises it;
for a library it calls the API — and scores it against a **mission rubric**
(`config.quality_rubric`), producing:
- `artifact_score ∈ [0,1]` — grounded, adversarial, **allowed to be low**.
- `dimension_scores` per rubric axis, and the single `weakest_dimension`.
- a one-line critique.

The critic is *not the maker* (independent context) and *must cite evidence*
(what it saw), satisfying the "don't grade your own work" principle while finally
measuring quality. Rubric for the game: `visual_fidelity, driving_feel,
fun_challenge, cohesion, performance, robustness`, each weighted, with a target
`bar` (e.g. 0.7).

### M2 — Honest scoring (kill Goodhart) → fixes D1
- `score_outcome.py`: `quality_multiplier = process_factor × artifact_factor`.
  A `pr_created` (0.5 process) with `artifact_score 0.2` now scores **~0.1**, not
  0.5. The artifact axis finally modulates the number. (Reframes the 7-B honesty
  rule: artifact quality is *independent + grounded*, so it is allowed to move the
  score; the maker's *self*-opinion still cannot.)
- `loop_scorecard.py grade()`: replace the gameable self-`goal` weight with
  **artifact_quality**. New composite:
  `0.45*artifact_quality + 0.25*goal_progress + 0.20*(1-futile) + 0.10*min(lv/0.5,1)`.
- **Goodhart Guard:** if process metrics are green (futile≈0, goal high) but
  `artifact_quality < bar`, **cap the grade at C** and print
  `⚠ MEASUREMENT WARNING: process green, artifact below bar — the scoreboard is lying.`
  Surface `artifact_quality` as the headline KPI, above Loop Value.
- Goal progress requires **evidence** (an artifact_score crossing a bar), not
  self-assertion.

### M3 — Leap Cycles (quantum jumps at inflection points) → fixes D3, D4
- **Plateau detection** (Orient, new **2-G**): track `artifact_score` across recent
  build cycles. If it hasn't improved by ≥ `ε` over the last `N` build cycles
  *despite shipping*, OR the same `weakest_dimension` has stayed weakest for `N`
  cycles → declare a **plateau**.
- **Leap trigger** (Decide, new **3-K**): on plateau — or every `K` cycles, or
  while `artifact_quality < bar` after warmup — the next cycle is forced into
  **LEAP mode** instead of FEATURE mode. A leap cycle:
  - does **not** add a feature; it makes a step-change on the `weakest_dimension`
    (overhaul / rebuild / refactor-for-cohesion / raise the bar);
  - is selected by **biggest gap-to-bar**, *bypassing pure RICE* (the mechanism
    that structurally forbade overhauls);
  - is allowed a larger diff (own size budget `config.leap.max_lines`);
  - is verified by the **artifact critique** (must raise the targeted dimension),
    not only the narrow unit-test gate — so untestable-but-vital work is first
    class at last (directly undoing D4).
- Brainstorming must now also propose **quality/overhaul** items scored by
  gap-to-bar, not only features.

### Safety (autonomous operation)
Leap mode loosens size limits and can bypass the unit-test gate — that is risky
under unattended Level-3 autonomy. Guards:
- Leap cycles still honor HALT, cost cap, protected_paths, and **must** pass the
  artifact critique with a *measured improvement* on the targeted dimension or the
  change is reverted (rollback protocol 4-C2).
- `config.leap.max_per_day` caps leaps; a leap that fails to improve twice running
  on the same dimension escalates to a `skill_gap`/HALT instead of looping.
- The artifact critic is independent + evidence-citing → it cannot rubber-stamp.

---

## Part 3 — Implementation surface
- `scripts/rubric_score.py` (new) — deterministic rubric aggregation + bar/Goodhart logic + plateau detector.
- `scripts/score_outcome.py` — fold `artifact_score` into `quality_multiplier`.
- `scripts/loop_scorecard.py` — artifact_quality KPI, honest grade, Goodhart Guard.
- `skills/evolve/SKILL.md` — new 5-G, 2-G, 3-K; reframe 6-C9 + 7-B; evidence-based 2-C.
- `skills/dev-cycle/SKILL.md` — artifact gate + LEAP mode (size + RICE bypass).
- `config.example.json` — `quality_rubric`, `leap` blocks.
- `agent/state/evolve/CHANGELOG.md` + version → **v1.7.0**.

## Part 4 — Proof obligations (the fix must have teeth)
1. Re-grade the F1 game with the new scorecard → A must drop to a realistic
   low grade (D/F) once `artifact_quality` (≈0.2 from the screenshot) is folded in.
2. Run ONE real **leap cycle** on the game that overhauls the broken visual core,
   re-score the artifact, and show the dimension actually improved — a demonstrated
   quantum jump, the thing the loop could never do before.
