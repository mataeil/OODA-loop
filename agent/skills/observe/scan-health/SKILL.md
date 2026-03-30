---
name: scan-health
description: Monitor service health endpoints and detect anomalies. Observe phase skill — reads config.health_endpoints, checks availability, records baseline metrics.
ooda_phase: observe
version: "1.0.0"
input:
  files: [agent/state/service_health.json]
  config_keys: [health_endpoints, test_command]
output:
  files: [agent/state/service_health.json]
safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.02
domains:
  - service_health
chain_triggers:
  - target: dev-cycle
    condition: "consecutive_failures >= 3"
---

# scan-health: Service Health Monitor

The "eyes" of the harness. Checks configured HTTP endpoints for availability
and response time, compares against baseline metrics, and generates alerts
when thresholds are breached.

- Checks configured HTTP endpoints for availability and response time
- Compares against baseline metrics stored in service_health.json
- Generates alerts when thresholds are breached
- READ-ONLY: no code changes, no PRs — writes only to agent/state/service_health.json

---

## Safety Rules

1. **HALT file** — Check `config.safety.halt_file` before any work. If present, print reason and stop.
2. **Read-only** — Only writes to `agent/state/service_health.json`. No external API modifications.
3. **Graceful degradation** — Record failures without crashing. Missing config → skip with a message.

---

## Step 0: Safety

Check the HALT file at `config.safety.halt_file`. If it exists, print:
`HALT: <reason>. scan-health aborted.` and exit.

Check `config.health_endpoints`. If missing or empty:
`No health endpoints configured. Skipping.` — exit 0.

---

## Step 0.5: Lens Load (Adaptive Context)

Read `agent/state/service_health/lens.json`. If missing or unparseable, proceed
with base behavior only — this step is purely additive.

If lens exists:
- **focus_items** (confidence >= 0.6): Prioritize these endpoints/metrics first.
  Allocate extra time and retries to high-priority items.
- **learned_thresholds** (confidence >= 0.6): Override default thresholds. For
  example, if the lens says endpoint X has a learned threshold of 800ms instead
  of the default 3000ms, use 800ms for anomaly detection on that endpoint.
- **discovered_signals** (actionable=true): Include these as additional diagnostic
  checks beyond the base behavior. For example, if the lens says "deploy failures
  correlate with health degradation", check recent deploy status first.

If lens is corrupt (invalid JSON, missing schema_version):
  Log: "[WARN] Lens file corrupt, using base behavior."
  Continue normally. Do NOT crash.

---

## Step 1: Baseline Load

Read `agent/state/service_health.json`. If missing, create with initial structure:

```json
{
  "schema_version": "1.0.0",
  "last_check": null,
  "run_count": 0,
  "status": "unknown",
  "alerts": [],
  "baseline": { "endpoints": [] }
}
```

Extract previous per-endpoint `avg_response_ms`, `last_status`, `consecutive_failures`
for use in anomaly detection.

---

## Step 2: Endpoint Checks

For each URL in `config.health_endpoints`:

```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 10 <url>
```

Record: `url`, `status_code`, `response_time_ms`, `timestamp`.
Timeout: 10s. Retry once on network failure.

If `curl` unavailable, fall back to `wget --server-response --timeout=10`.
If both unavailable, record `status_code: 0`, `error: "no_http_client"`.

---

## Step 3: Anomaly Detection

| Condition | Alert type | Severity |
|---|---|---|
| status_code != 200 (single endpoint) | `endpoint_down` | warning |
| status_code != 200 (2+ endpoints) | `multiple_endpoints_down` | critical |
| response_time_ms > 3000 | `slow_response` | warning |
| response_time_ms > 2x baseline avg | `response_degradation` | warning |

**Baseline comparison on failure** — when an endpoint is DOWN (HTTP 000, connection refused, or timeout with no response), include baseline context in the alert detail so the user understands what changed:

```
Previous baseline: {avg_response_ms}ms / 200 OK (from {samples} samples)
Current: CONNECTION REFUSED
Change: endpoint_down (was healthy)
```

If no baseline exists for the endpoint (first run), omit the "Previous baseline" line and note `Change: endpoint_down (no prior baseline)`.

Alert shape: `{ "severity": "warning", "type": "...", "endpoint": "...", "detail": "..." }`

Increment `consecutive_failures` per endpoint on non-200; reset to 0 on success.

---

## Step 4: State Update

Write to `agent/state/service_health.json`:

```json
{
  "schema_version": "1.0.0",
  "last_check": "<ISO 8601>",
  "run_count": "<N>",
  "status": "healthy | degraded | critical",
  "alerts": [{ "severity": "warning", "type": "slow_response", "endpoint": "...", "detail": "..." }],
  "baseline": {
    "endpoints": [{ "url": "...", "avg_response_ms": 130, "last_status": 200, "consecutive_failures": 0 }]
  }
}
```

Status: `healthy` = all 200 + no alerts. `degraded` = warning alerts only. `critical` = any critical alert.
Update `avg_response_ms` as a rolling average (weight new reading at 0.2).

**Note:** This skill does NOT write to `agent/state/service_health/lens.json`.
Lens updates (learning thresholds, promoting signals, adjusting focus) happen
exclusively in evolve's Reflect phase (Step 5-E).

---

## Step 5: Report

```
scan-health — <ISO timestamp>
Overall status: healthy | degraded | critical

| Endpoint                 | Status | Response (ms) | Baseline (ms) | Alert          |
|--------------------------|--------|---------------|---------------|----------------|
| https://example.com/     |  200   |     142       |     130       | —              |
| https://example.com/api  |  503   |     —         |     120       | endpoint_down  |
```

If alerts exist: `Alerts: N warning, N critical. Consider running /dev-cycle for investigation.`
If `consecutive_failures >= 3`, note that the `dev-cycle` chain trigger condition is met.

---

## Graceful Degradation

| Scenario | Behavior |
|---|---|
| `health_endpoints` empty or missing | Print skip message, exit 0 |
| `curl` not available | Fall back to `wget`; if both missing, record `status_code: 0` |
| All endpoints unreachable | Record `status: "critical"`, write state, report — do NOT crash |
| `service_health.json` missing | Create with initial structure and continue |
| HALT file present | Print reason, exit immediately before any checks |
