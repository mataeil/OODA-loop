# Fixture: memo-intervention

## Purpose

Verify that evolve auto-writes persistent interventions into `memos.interventions[]`
for two patterns observed in production and formalized in v1.2.0:

1. **Starvation**: a domain with 0 executions in the last 10 cycles gets a
   `+1.0` intervention with `type: "starvation"`, `expires_after_cycles: 3`.
2. **Monopoly-breaker**: a domain selected 2+ consecutive cycles gets a
   `-10.0` intervention with `type: "monopoly_breaker"`, `expires_after_cycles: 1`.

Both patterns require the changes in Step 5-C (memo writing) and the Step 3-A
scoring path that now sums `score_adjustments[domain] + interventions[domain].delta`.

## Setup

`seed/agent/state/evolve/state.json` contains a 20-entry decision_log where:

- `service_health` appears in cycles 15, 16 (last two consecutive → monopoly candidate).
- `ux_evolution` appears in none of cycles 7–16 (last 10 → starvation candidate).
- `backlog`, `test_coverage` fill the rest.

`memos.json` starts empty (no prior interventions).

## Expected dry-run output

Two `[Reflect]` lines should print:

```
[Reflect] Starvation intervention: ux_evolution boosted +1.0 for 3 cycles.
[Reflect] Monopoly-breaker intervention: service_health penalized -10.0 for 1 cycle.
```

The next cycle's proposed `memos.json.interventions[]` contains two entries:

```json
[
  { "domain": "ux_evolution", "delta": 1.0, "type": "starvation", "expires_after_cycles": 3, "applied_count": 0 },
  { "domain": "service_health", "delta": -10.0, "type": "monopoly_breaker", "expires_after_cycles": 1, "applied_count": 0 }
]
```

On the FOLLOWING cycle's dry-run (simulate by manually bumping cycle_count +1),
Step 3-A applies both interventions to the score table — the top-1 winner
should flip away from service_health and toward ux_evolution (or whichever
domain is next-highest with the +1.0 boost).

## Config

Defaults. No tuning needed.
