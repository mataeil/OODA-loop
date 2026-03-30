---
name: scan-health
description: Monitor service health endpoints and detect anomalies. Observe phase skill — reads config.health_endpoints, checks availability, records baseline metrics.
ooda_phase: observe
version: "1.0.0"
input:
  files: [agent/state/service_health.json]
  config_keys: [health_endpoints, health_check_timeout_seconds]
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

Validate the list before proceeding:
- **Deduplicate** — remove duplicate URLs (keep first occurrence).
- **Reject malformed URLs** — entries that do not start with `http://` or `https://` are skipped with a warning: `[WARN] Skipping malformed URL: <url>`.
- **Cap at 20 endpoints** — if more than 20 remain after dedup, check only the first 20 and warn: `[WARN] Endpoint list truncated to 20 (had <N>).`

---

## Step 0.5: Lens Load (Adaptive Context)

Read `agent/state/service_health/lens.json`. If missing or unparseable, proceed
with base behavior only — this step is purely additive.

If lens exists:
- **focus_items** (confidence >= 0.6): Prioritize these endpoints/metrics first.
  Allocate extra time and retries to high-priority items.
- **learned_thresholds** (confidence >= 0.6): Override default thresholds. For
  example, if the lens says endpoint X has a learned threshold of 800ms instead
  of the default 1500ms, use 800ms for anomaly detection on that endpoint.
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
curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time <timeout_seconds> <url>
```

Record: `url`, `status_code`, `response_time_ms`, `timestamp`.
Timeout: `config.health_check_timeout_seconds` (default 10, valid range 2-30).
Retry once on network failure (status 0 / connection refused).

If `curl` unavailable, fall back to `wget --server-response --timeout=<timeout_seconds>`.
If both unavailable, record `status_code: 0`, `error: "no_http_client"`.

---

## Step 3: Anomaly Detection

| Condition | Alert type | Severity |
|---|---|---|
| status_code 5xx or 0 (single endpoint) | `endpoint_down` | warning |
| status_code 5xx or 0 (2+ endpoints) | `multiple_endpoints_down` | critical |
| status_code 3xx | `endpoint_redirect` | info |
| status_code 403 | `endpoint_forbidden` | warning |
| response_time_ms > 1500 | `slow_response` | warning |
| response_time_ms > 2x baseline avg | `response_degradation` | warning |

**Baseline comparison on failure** — when an endpoint is DOWN (HTTP 000, connection refused, or timeout with no response), include baseline context in the alert detail so the user understands what changed:

```
Previous baseline: {avg_response_ms}ms / 200 OK (from {samples} samples)
Current: CONNECTION REFUSED
Change: endpoint_down (was healthy)
```

If no baseline exists for the endpoint (first run), omit the "Previous baseline" line and note `Change: endpoint_down (no prior baseline)`.

Alert shape: `{ "severity": "warning", "type": "...", "endpoint": "...", "detail": "..." }`

Increment `consecutive_failures` per endpoint on 5xx or status 0 (timeout/connection refused).
Reset to 0 on any 2xx response. Do NOT increment on 3xx or 403 (endpoint is reachable).

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

Status: `healthy` = all 2xx, no warning/critical alerts (info alerts are OK). `degraded` = any warning alert. `critical` = any critical alert.
Update `avg_response_ms` using an exponential moving average:
`new_avg = old_avg * 0.8 + current_response_ms * 0.2`.
On the first run for an endpoint (no prior baseline), set `avg_response_ms = current_response_ms` directly.

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
| First run (no baseline for endpoint) | Record current values as baseline; skip `response_degradation` alert (no prior avg to compare) |
| HALT file present | Print reason, exit immediately before any checks |
