---
name: check-tests
description: Run test suite, track coverage trends, and detect regressions. Detect phase skill — uses config.test_command to execute tests and records results.
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

Execute with a 5-minute (300-second) timeout:
```bash
{config.test_command} 2>&1
```

Capture exit code, stdout, stderr. Parse:
- **Counts**: look for `X passed`, `X failed`, `X skipped`, `X tests` (Jest, pytest, Go, Mocha, RSpec)
- **Coverage**: look for `coverage: X%`, `X% coverage`, `Statements: X%`; if absent record `null`
- **Status**: exit 0 → `"passing"`, non-zero → `"failing"`, crash/not-found → `"error"`, timeout → `"error"` with note

---

## Step 3: Detect Regressions

Skip on first run (no previous state) — record baseline only. Otherwise compare:

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

History: keep last 20 entries (append current, drop oldest).

---

## Step 5: Report

```
Tests: {passed}/{total} passed ({coverage}% coverage)
Status: {passing|failing|error}
vs Previous: +{N} passed, -{N} failed, coverage {+/-N%}
Alerts: {alert list or "none"}
```

Example: `Tests: 142/145 passed (87.3% coverage) | Status: failing | vs Previous: +3 failed, coverage -1.2% | Alerts: [warning] regression — 3 new failures`

---

## Graceful Degradation

- No `test_command` → skip with message
- Test command fails to start → record `"error"` status, write state
- Coverage parsing fails → record `coverage_pct: null`, continue
- Timeout (> 300s) → kill process, record `"error"` with timeout note
- State file corrupt → treat as first run, re-initialize
