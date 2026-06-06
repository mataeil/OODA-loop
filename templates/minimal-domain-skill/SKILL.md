---
name: scan-disk
description: Minimal example Observe-phase domain skill. Checks disk usage and records it. Copy this as a starting point for your own domain.
ooda_phase: observe
version: "1.0.0"
input:
  files:
    - config.json
    - "agent/state/disk_usage/lens.json"
  config_keys:
    - "domains.disk_usage"
output:
  files:
    - agent/state/disk_usage/state.json
  prs: none
safety:
  halt_check: true
  read_only: true
domains:
  - disk_usage
chain_triggers: []
---

# /scan-disk — Minimal Domain Skill Example

The smallest useful Observe skill: it reads disk usage, records a baseline, and
emits an alert when usage crosses a learned threshold. Use it as a 30-line
template for your own domain. **Every skill starts with a HALT check.**

## Step 0: Safety

```bash
ls agent/safety/HALT 2>/dev/null && echo "HALT_ACTIVE" || echo "HALT_INACTIVE"
```

If HALT is active, print the reason and stop immediately.

## Step 1: Observe

```bash
df -P / | tail -1 | awk '{print $5}' | tr -d '%'   # → integer percent used
```

Load the lens (`agent/state/disk_usage/lens.json`) if present. Use its
`learned_thresholds` for `warn_pct` if it has one; otherwise default `warn_pct = 85`.

## Step 2: Record + alert

Write `agent/state/disk_usage/state.json`:

```json
{
  "schema_version": "1.0.0",
  "last_run": "<now ISO-8601>",
  "status": "healthy",            // healthy | degraded | critical
  "metrics": { "used_pct": 73 },
  "alerts": []                    // e.g. ["disk 91% > warn_pct 85"] when crossed
}
```

Set `status: "degraded"` and add an alert when `used_pct >= warn_pct`;
`"critical"` at `>= 95`. The evolve engine reads `status`/`alerts` during Observe
and factors them into scoring.

## Adaptive Lens (optional but recommended)

evolve's Step 5-E initializes and updates `agent/state/disk_usage/lens.json`
automatically. To participate, just emit consistent `metrics`/`alerts`; the engine
learns a per-host `warn_pct` over time (raising it on repeated false positives,
lowering it after real incidents). You don't write the lens yourself.
