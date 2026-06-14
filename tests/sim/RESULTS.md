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

## Iteration 2 — Work-availability (dry-domain dampener)

A *work* domain (strategize/execute) that ran dry last time gets its staleness
dampened ×0.3 until it produces output again; monitors (observe) keep cadence;
an active alert exempts. `config.scoring.dry_domain_dampen`.

| scenario | before futile% → after | before goal% → after |
|---|---|---|
| A_webapp | 58.3 → 58.3 | 66.7 → 66.7 (futile is quiet-monitor polling — Iteration 3) |
| B_library | 58.3 → 58.3 | 80.0 → **100.0** |
| C_greenfield | 33.3 → **25.0** | 57.1 → 57.1 (loopVal 0.333 → 0.35) |

**Open gap → Iteration 3:** A's futile is a *quiet monitor* (service_health)
being re-polled on staleness when nothing's wrong. Monitors need a cadence, not
every-cycle polling. Add a mild dry-dampener / cadence for observe domains.

## Iteration 3 — Monitor cadence (mild dry-dampen for observe domains)

A quiet monitor (e.g. service_health with nothing wrong) was re-picked every
cycle on staleness → futile. Now observe domains that ran dry get a *mild*
staleness ×`config.scoring.monitor_dry_dampen` (0.6) — still polled periodically,
no longer dominating. Alert exempts.

| scenario | futile% | goal% | mission% |
|---|---|---|---|
| A_webapp | 58.3 → **50.0** | 66.7 → **83.3** | 41.7 → **50.0** |
| B_library | 58.3 (unchanged) | 100.0 | 41.7 |
| C_greenfield | 25.0 (unchanged) | 57.1 | 41.7 |

## Iteration 4 — Off-mission deprioritization

When a mission is set, domains with mission_alignment < 0.2 get staleness ×0.2
(`config.scoring.off_mission_dampen`) — distractions stop stealing cycles. Alert
exempts.

| scenario | futile% | mission% | goal% | loopVal |
|---|---|---|---|---|
| A_webapp | 50.0 | 50.0 | 83.3 | 0.10 |
| B_library | 58→**25** | 42→**75** | 100 | 0.083→**0.15** |
| C_greenfield | 25→42 | 42→**50** | 57→**71** | 0.35→**0.367** |

## Iteration 5 — Goal-completion idle gate (verifiable stopping)

Canon #1: a loop runs *until* a verifiable goal is met — so once met, stop
spinning. New Decide gate 3-E2: when all active goals are at 100% and there's no
alert and nothing actionable, the cycle idles (a skip, not a futile cycle).
`config.goal_completion_idle`.

| scenario (20cy) | futile% | idle cycles | loopVal |
|---|---|---|---|
| A_webapp | 50→**46** | 0→**7** (idled after goal) | 0.10→0.108 |
| B_library | 15 (real maintenance work) | 0 | 0.17 |
| C_greenfield | 45→**35** | 0→**3** | 0.38→**0.45** |

## Iteration 6 — Install: auto-derive goals from the mission

ooda-setup now *proposes* verifiable done-conditions (with `metric_command`s)
from the mission text + detected stack, instead of making the operator hand-write
them — the "state your purpose, the loop figures out how to measure it" install
flow. (Structural; validated by the loop reaching goal 100% in the sims once
goals exist.)

## Iteration 7 — Loop-engineering letter grade on the scorecard

`scripts/loop_scorecard.py grade()` distills goal progress + futile rate + loop
value into a single A–F grade with a composite score, so an operator gets an
at-a-glance verdict. Fixture → **B (0.798)**; empty state → `—` (no false grade).
