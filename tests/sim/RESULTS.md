# Sandbox simulation — the empirical loop-improvement log

OODA-loop improved on itself: 3 simulated real projects (A/B/C, `scenarios.py`)
run through N OODA cycles by `runner.py`, measured, the top gap fixed, re-run —
iterated. The runner re-implements the 3-A scoring spec and records real
outcomes via the E2E engine driver, so the Loop Scorecard and these metrics are
computed from real state, not asserted.

Metrics: **loopVal** = mean quality_multiplier · **futile%** = cycles that ran
but changed nothing · **mission%** = on-mission-work hit rate · **goal%** =
final goal progress. Higher loopVal/mission/goal and lower futile are better.

Run: `python3 tests/sim/runner.py [--no-mission] [--cycles N]`

## Iteration 0 — baseline (v1.4.0), 12 cycles

| scenario | mode | loopVal | futile% | mission% | goal% |
|---|---|---|---|---|---|
| A_webapp | no-mission | 0.10 | 50.0 | 41.7 | 50.0 |
| A_webapp | mission | 0.083 | 58.3 | 41.7 | **66.7** |
| B_library | no-mission | 0.05 | 75.0 | 25.0 | 60.0 |
| B_library | mission | 0.083 | 58.3 | **41.7** | **80.0** |
| C_greenfield | no-mission | 0.283 | 33.3 | 33.3 | 42.9 |
| C_greenfield | mission | 0.333 | 33.3 | **41.7** | **57.1** |

**Findings (drive the iterations):**
1. A mission-alignment term in scoring lifts goal completion everywhere
   (+13–20pp) and the on-mission hit rate — validates capturing the project's
   mission at install and feeding it into Decide. → Iteration 1.
2. Futile rate stays high (33–58%) even mission-aware: scoring uses staleness ×
   weight × mission but is blind to **whether actionable work exists in a domain
   right now**, so stale-but-empty domains keep winning. → a top gap.
3. loopVal is low because few cycles end in a merged PR; observe/strategize
   cycles cap at 0.2. The loop needs to convert observation into accepted change
   faster (chain to implementation on the critical path). → a gap.

## Iteration 1 — Mission Capture (now the spec default)

ooda-setup now captures `config.mission` + per-domain `mission_alignment`; evolve
3-A/3-A2/3-J add a `mission_weight × alignment` term; ooda-status shows the
mission. The loop self-drives toward the installed purpose.

| scenario | before (no-mission) goal% | after (mission) goal% | Δ |
|---|---|---|---|
| A_webapp | 50.0 | **66.7** | +16.7 |
| B_library | 60.0 | **80.0** | +20.0 |
| C_greenfield | 42.9 | **57.1** | +14.2 |

Mission-hit rate also rose (B 25→42, C 33→42). **Open gap → Iteration 2:** futile
rate is still 33–58% — scoring rewards mission + staleness but a domain with
*no actionable work right now* still wins on staleness. Fix next.
