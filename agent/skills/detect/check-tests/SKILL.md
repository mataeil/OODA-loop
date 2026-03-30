---
name: check-tests
description: Run test suite, track coverage trends, and detect regressions. Detect phase skill — uses config.test_command to execute tests and records results.
ooda_phase: detect
version: "1.0.0"
input:
  files: [agent/state/test_coverage.json]
  config_keys: [test_command, test_timeout_seconds]
output:
  files: [agent/state/test_coverage.json]
safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.05
domains: [test_coverage]
chain_triggers:
  - target: dev-cycle
    condition: "new_failures >= 1 OR coverage_drop > 5"
---

# check-tests: Test Suite Runner & Coverage Tracker

Runs the configured test command, tracks pass/fail counts and coverage percentage
over time, and alerts when regressions appear or coverage drops. READ-ONLY in
terms of PRs — writes only to `agent/state/test_coverage.json`.

---

## Safety Rules

1. **HALT File** — Check `config.safety.halt_file` first. If it exists, print reason and stop.
2. **Read-only** — Writes only to `agent/state/test_coverage.json`. Never touches test files or source.
3. **No test_command** — If `config.test_command` is empty or unset, skip gracefully.

---

## Step 0: Safety

**0-A: HALT Check**
```
if file exists at config.safety.halt_file:
  Print "[HALT] check-tests stopped. Reason: {file_content}"
  EXIT immediately.
```

**0-B: Config Validation**
```
if config.test_command is missing or empty:
  Print "No test command configured. Skipping check-tests."
  Print "Set config.test_command (e.g. \"npm test\", \"pytest\", \"go test ./...\") to enable."
  EXIT cleanly (not an error).
```

---

## Step 1: Load Previous State

Read `agent/state/test_coverage.json`. If missing, initialize with:
`{ "schema_version": "1.0.0", "last_run": null, "run_count": 0, "status": "unknown",`
`  "results": { "total": 0, "passed": 0, "failed": 0, "skipped": 0, "coverage_pct": null },`
`  "previous_results": null, "alerts": [], "history": [] }`

Note previous `passed`, `failed`, and `coverage_pct` values for Step 3.

---

## Step 2: Run Tests

Execute with a configurable timeout (read `config.test_timeout_seconds`; default 300):
```bash
{config.test_command} 2>&1
```

Capture exit code, stdout, stderr. Parse:
- **Counts**: try framework-specific patterns in order:
    - **Jest**: `Tests:\s+(\d+) failed.*?(\d+) passed.*?(\d+) total` (also `(\d+) skipped`)
    - **pytest**: `(\d+) passed`, `(\d+) failed`, `(\d+) skipped`, `(\d+) error`
    - **Go**: count `ok` lines as passed packages, `FAIL` lines as failed packages
    - **Mocha**: `(\d+) passing`, `(\d+) failing`, `(\d+) pending`
    - **RSpec**: `(\d+) examples?,\s*(\d+) failures?(?:,\s*(\d+) pending)?`
    - **Fallback**: generic `(\d+)\s+(?:tests?\s+)?passed`, `(\d+)\s+(?:tests?\s+)?failed`
    - Compute `total = passed + failed + skipped` when the framework does not emit a total
- **Coverage**: try patterns in order — `All files.*?\|\s*([\d.]+)%` (Istanbul/nyc), `TOTAL\s+.*?([\d.]+)%` (pytest-cov), `coverage:\s*([\d.]+)%` (Go), `Statements\s*:\s*([\d.]+)%` (Jest), `([\d.]+)%\s*coverage`; use first match; if none match record `null`
- **Status**: exit 0 → `"passing"`, exit 127 (command not found) or 126 (permission denied) → `"error"` with detail `"test command not found or not executable"`, timeout → `"error"` with detail `"timeout after Ns"`, other non-zero → `"failing"`

---

## Step 3: Detect Regressions

Skip regression detection when: (a) first run (no previous state), (b) current run status is `"error"`, or (c) previous run status was `"error"`. In these cases record results only, no alerts. Otherwise compare against the last *successful* (`"passing"` or `"failing"`) run:

| Condition | Type | Severity |
|-----------|------|----------|
| failed increased by > 5 | `regression` | `critical` |
| failed increased by 1–5 | `regression` | `warning` |
| coverage dropped by > 5% | `coverage_drop` | `warning` |
| failed → 0 (was > 0) | `recovery` | `info` |

Alert format: `{"severity": "warning", "type": "regression", "detail": "3 new failures (was 2, now 5)"}`

---

## Step 4: State Update

Write to `agent/state/test_coverage.json`:
```json
{
  "schema_version": "1.0.0",
  "last_run": "ISO 8601",
  "run_count": N,
  "status": "passing|failing|error",
  "results": { "total": N, "passed": N, "failed": N, "skipped": N, "coverage_pct": N.N },
  "previous_results": { "...previous results object..." },
  "alerts": [{"severity": "warning", "type": "regression", "detail": "..."}],
  "history": [{"timestamp": "...", "passed": N, "failed": N, "coverage_pct": N.N}]
}
```

History: append the current run, then truncate to the most recent 50 entries (drop oldest first). If the array already exceeds 50 (e.g., manual edits), truncate to 50 in this write.

---

## Step 5: Report

```
Tests: {passed}/{total} passed, {skipped} skipped {coverage_section}
Status: {passing|failing|error}
vs Previous: {delta_section or "first run / no comparison available"}
Alerts: {alert list or "none"}
```

Where:
- `{coverage_section}` = `(X.X% coverage)` when available, or `(coverage: n/a)` when `coverage_pct` is `null`.
- If `total` is 0 and status is not `"error"`, display `Tests: 0 found (check test_command output)`.
- `{delta_section}` omits coverage delta when either the current or previous `coverage_pct` is `null`.

Example: `Tests: 142/145 passed, 0 skipped (87.3% coverage) | Status: failing | vs Previous: +3 failed, coverage -1.2% | Alerts: [warning] regression — 3 new failures`

---

## Graceful Degradation

- No `test_command` → skip with message
- Test command fails to start → record `"error"` status, write state
- Coverage parsing fails → record `coverage_pct: null`, continue
- Timeout (exceeds `config.test_timeout_seconds`, default 300) → kill process, record `"error"` with timeout note
- State file corrupt → treat as first run, re-initialize
