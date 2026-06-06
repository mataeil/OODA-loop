# Fixture: cycle-card

Verifies that **evolve Step 7 (Cycle Card)** and **`/ooda-status --share`** render
the intended artifact from a complete v1.2.0 cycle — including the differentiating
**LEARN** line that re-orients from a human merge/reject decision.

## Scenario

A live URL shortener (`fwd.page`) at **Level 2 (Full observation)**, cycle **#152**:

- During Orient (Step 2-B), the engine detected the human **rejected PR #28**
  (a `service_health` proposal) → `service_health` confidence **0.74 → 0.54** (−0.2).
- During Reflect (Step 5-E), the `service_health` **flaky-alert threshold decayed
  0.30 → 0.25** after a 3rd false-positive confirmation (logged to
  `lens_changelog.json`).
- Decide picked **`test_coverage`** (score 11.3, confidence 0.74, gate ✓), which
  **opened PR #29** ("wrap flaky network suite in retry", Risk Tier 1, 2 files, draft).
- A Reflexion self-critique (Step 5-F) was recorded with `verdict: hit`.
- Cost this cycle: **+$0.04**, **$0.38** today (hard cap $10).

## Seed (`seed/`)

```
config.json                                  # fwd.page, Level 2, 4 active domains, output.cycle_card true
agent/state/evolve/state.json                # cycle 152, decision_log w/ #151 (PR#28) and #152 (PR#29 + reject outcome)
agent/state/evolve/confidence.json           # service_health 0.54, test_coverage 0.74
agent/state/evolve/cost_ledger.json          # cycle 152 entry, $0.38 today
agent/state/evolve/reflections.json          # one hit reflection (Step 5-F)
agent/state/evolve/CHANGELOG.md              # cycle #152 + #151 entries (source for --share)
agent/state/service_health/lens.json         # flaky-alert threshold now 0.25
agent/state/service_health/lens_changelog.json # the 0.30 -> 0.25 change (LEARN priority 2 source)
```

## Expected `/evolve` Step 7 Cycle Card output

```
┌─ fwd.page · OODA-loop cycle #152 ────────────── 2026-04-14 03:14 UTC ─┐
│                                                                        │
│  OBSERVE   4 domains · test_coverage dropped 91% → 84% overnight       │
│  ORIENT    flaky-retry pattern confirmed (3rd time); coverage now      │
│            the most stale + highest-signal domain                      │
│  DECIDE    test_coverage won (score 11.3) · confidence 0.74 · gate ✓   │
│  ACT       opened PR #29 — "wrap flaky network suite in retry"         │
│            └ Risk Tier 1 · 2 files · draft — you merge                 │
│  LEARN  🔭 you rejected PR #28 yesterday →                             │
│            service_health confidence 0.74 → 0.54 ↓                     │
│            (reject −0.2, 2× faster than a merge's +0.1)                │
│         🔭 lens re-aimed → flaky-alert threshold 0.30 → 0.25           │
│  COST      +$0.04 · $0.38 today · hard cap $10 (auto-HALTs on breach)  │
│                                                                        │
│  HALT: inactive · Level 2 (Full observation)                          │
└────────────────────────────────────────────────────────────────────────┘
```

Plain-text share line:

```
fwd.page ran OODA-loop cycle #152: test_coverage → opened PR #29. Learned: you rejected PR #28 → service_health confidence 0.74→0.54. Cost +$0.04/cycle ($0.38 today). — github.com/mataeil/OODA-loop
```

`/ooda-status --share` reconstructs the **same card** from `state.json`,
`CHANGELOG.md` (Orient + Confidence lines), `lens_changelog.json`, and
`cost_ledger.json`.

## What `verify.py` checks (static)

- `confidence.service_health == 0.54` (= 0.74 − 0.2 reject), proving the LEARN
  priority-1 (human-decision) delta is real and recorded.
- `lens_changelog` last entry: `before 0.30 → after 0.25` (LEARN priority-2 source).
- `cost_ledger` has an entry for `cycle_id 152` with `0.04`, total `0.38`.
- `reflections` is non-empty with `verdict: hit` (Step 5-F ran).
- `config.progressive_complexity.levels["2"].name == "Full observation"` — the
  Cycle Card footer label is read from config, not hardcoded.
- 4 active domains → the OBSERVE "4 domains" count.
