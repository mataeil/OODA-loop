# tests/sim — sandbox simulation harness

An empirical instrument for improving OODA-loop *as a loop-engineering
framework*. It runs three simulated real projects (`scenarios.py`: A webapp,
B library, C greenfield) through N OODA cycles using the real 3-A scoring spec
(re-implemented in `runner.py`, kept in sync with `skills/evolve/SKILL.md`) and
the E2E engine driver, then reports the Loop Scorecard + loop-engineering quality
metrics (mission-hit rate, goal completion, futile rate, loop value).

```bash
python3 tests/sim/runner.py                 # all scenarios, mission-aware
python3 tests/sim/runner.py --no-mission    # ablation: scoring without mission term
python3 tests/sim/runner.py A_webapp --cycles 20
```

This is an analysis tool, not a CI gate (it is intentionally stochastic-free but
exploratory). The measured improvement history lives in `RESULTS.md`.
