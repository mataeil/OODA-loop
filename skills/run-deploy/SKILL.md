---
name: run-deploy
description: Trigger deployment via GitHub Actions workflow_dispatch. Execute phase skill — validates pre-deploy conditions, fires the configured workflow, monitors completion, and verifies post-deploy health.
ooda_phase: execute
version: "1.0.0"
input:
  files:
    - agent/state/service_health.json
    - agent/state/test_coverage.json
  config_keys:
    - deploy_workflow
    - deploy_workflow_inputs
    - deploy_monitor_timeout_seconds
    - deploy_health_wait_seconds
    - health_endpoints
    - safety.halt_file
    - safety.branch_prefix
output:
  files: [agent/state/deploy.json]
safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.05
domains:
  - service_health
chain_triggers:
  - target: scan-health
    condition: "health_check == 'failed'"
    note: "Trigger health monitoring after a failed post-deploy health check"
---

# run-deploy: GitHub Actions Deployment Trigger

The "hand" of the harness. Validates deployment readiness, fires the configured
GitHub Actions workflow via `workflow_dispatch`, monitors completion, and
verifies the service is healthy afterward.

- NEVER auto-invoked without passing the full pre-deploy checklist
- Requires explicit conditions — does not deploy blindly
- Writes results to `agent/state/deploy.json`

---

## Safety Rules

1. **HALT file** — Mandatory first check. If present, print reason and stop.
2. **Pre-deploy checklist** — All six conditions must pass before triggering.
3. **gh required** — Cannot deploy without GitHub CLI. If unavailable, error and exit.
4. **No blind deploys** — `config.deploy_workflow` must be explicitly configured.

---

## Step 0: Safety

**0-A: HALT Check**
```
if file exists at config.safety.halt_file:
  Print "[HALT] run-deploy stopped. Reason: {file_content}"
  EXIT immediately.
```

**0-B: Config Validation**
```
if config.deploy_workflow is missing, null, or empty:
  Print "No deploy workflow configured. Skipping."
  EXIT cleanly (not an error).
```

---

## Step 1: Pre-Deploy Checklist

All six conditions must pass. On first failure, print the reason and skip deployment.

| # | Check | Source | Pass Condition |
|---|-------|--------|----------------|
| 1 | No critical health alerts | `agent/state/service_health.json` | `alerts` has no item with `severity == "critical"` |
| 2 | Tests passing | `agent/state/test_coverage.json` | `status == "passing"` |
| 3 | No HALT file | `config.safety.halt_file` | File does not exist (re-confirmed) |
| 4 | Complexity level | `config.json` | `progressive_complexity.current_level >= 3` OR invoked directly by user |
| 5 | Clean working tree | `git status --porcelain` | Output is empty (no uncommitted changes) |
| 6 | Workflow file exists | `.github/workflows/{deploy_workflow}` | File exists in the repository (prevents cryptic GitHub API errors) |

On any failure:
```
Pre-deploy checklist FAILED: {reason}
Deployment skipped.
```

State files missing (health, tests) count as unknown — treat as failure for that check.
Print which specific check failed so the user can act on it.

---

## Step 2: Trigger Deployment

Verify `gh` is available and authenticated:
```bash
gh --version
gh auth status
```
If not found: print `ERROR: gh (GitHub CLI) is required for deployment. Install from https://cli.github.com/` and exit non-zero.
If not authenticated: print `ERROR: gh is not authenticated. Run: gh auth login` and exit non-zero.

Determine the current branch:
```bash
git rev-parse --abbrev-ref HEAD
```

Trigger the workflow. If `config.deploy_workflow_inputs` is set (object of key-value
pairs), pass each entry as `-f key=value`:
```bash
# Without inputs:
gh workflow run {config.deploy_workflow} --ref {branch}

# With inputs (e.g. {"environment":"staging","tag":"v1.2.3"}):
gh workflow run {config.deploy_workflow} --ref {branch} -f environment=staging -f tag=v1.2.3
```

Wait up to 15 seconds for the run to register, then retrieve the run ID:
```bash
gh run list --workflow={config.deploy_workflow} --limit=1 --json databaseId,url --jq '.[0]'
```

Print:
```
Deployment triggered: {config.deploy_workflow} on {branch}
Workflow run: {run_url}
```

---

## Step 3: Monitor

Watch the run until completion. Timeout is read from
`config.deploy_monitor_timeout_seconds` (default 600 — 10 minutes):
```bash
gh run watch {run_id} --exit-status
```

- Exit 0 → `status: "success"`
- Non-zero exit → `status: "failed"`
- Timeout (> configured seconds): kill watch, record `status: "unknown"`, print:
  `Deployment monitor timed out after {timeout}s. Check {run_url} manually.`

Re-check the HALT file after the wait completes. If it appeared during the long
monitor window, record `status: "halted"` and skip post-deploy steps.

---

## Step 4: Post-Deploy Health Check

Skip this step if `config.health_endpoints` is missing or empty — note the skip.

If endpoints are configured:

1. Wait `config.deploy_health_wait_seconds` (default 30) for the service to stabilize.
2. Run health checks using the same logic as `scan-health` (Step 2 of that skill).
3. If any endpoint fails, retry once after another `deploy_health_wait_seconds` wait
   (services with rolling deploys may need extra time).
4. Evaluate final results:
   - All endpoints 200 → `health_check: "passed"` — print `Deployment verified healthy.`
   - Any endpoint non-200 or critical alert after retry → `health_check: "failed"` — print:
     `ALERT: Post-deploy health check failed after retry. Consider rollback.`

---

## Step 5: State Update + Report

Write to `agent/state/deploy.json`:
```json
{
  "schema_version": "1.1.0",
  "last_deploy": "<ISO 8601>",
  "deploy_count": N,
  "status": "success|failed|unknown|halted",
  "workflow": "{config.deploy_workflow}",
  "branch": "{branch}",
  "commit_sha": "{HEAD short SHA at trigger time}",
  "run_id": "{run_id}",
  "run_url": "{run_url}",
  "health_check": "passed|failed|skipped",
  "health_retry_count": 0,
  "duration_seconds": N,
  "error_message": null
}
```

`deploy_count`: increment from previous value in the file (default 0 if file absent).
`commit_sha`: captured via `git rev-parse --short HEAD` before triggering.
`duration_seconds`: wall-clock time from trigger to final state write.
`error_message`: null on success; short description on failure/unknown.

Print deployment summary:
```
run-deploy — <ISO timestamp>
Workflow : {config.deploy_workflow}
Branch   : {branch}
Commit   : {commit_sha}
Run ID   : {run_id}
Status   : success | failed | unknown | halted
Health   : passed | failed | skipped
Duration : {duration_seconds}s
Run URL  : {run_url}
```

If `status == "failed"`: print `Workflow failed. Investigate at {run_url} before retrying.`
If `status == "halted"`: print `HALT file appeared during deployment. Monitoring stopped.`
If `health_check == "failed"`: print `Post-deploy health check failed after retry. Manual rollback may be needed.`

---

## Graceful Degradation

| Scenario | Behavior |
|---|---|
| HALT file present | Print reason, exit immediately — no deployment |
| HALT file appears during monitor | Record `status: "halted"`, skip health check, print warning |
| `deploy_workflow` not configured | Print skip message, exit 0 |
| Workflow file not found in `.github/workflows/` | Print `Workflow file {name} not found. Check config.deploy_workflow.`, exit non-zero |
| `deploy_workflow_inputs` invalid (non-object) | Print `deploy_workflow_inputs must be a key-value object.`, exit non-zero |
| `gh` not installed | Print install instructions, exit non-zero |
| Pre-deploy checklist fails | Print failing check, exit 0 (not an error — a safety gate) |
| Run ID not found after trigger | Record `run_id: null`, status `"unknown"`, print warning |
| Monitor timeout | Record `status: "unknown"`, print manual check URL with configured timeout value |
| Workflow fails (non-zero exit) | Record `status: "failed"`, capture `error_message` from run logs, skip health check |
| Health check fails first attempt | Retry once after `deploy_health_wait_seconds`, then record final result |
| `health_endpoints` missing | Record `health_check: "skipped"`, note in report |
| `service_health.json` or `test_coverage.json` missing | Treat as checklist failure for that check |
| `deploy.json` missing | Create fresh with `deploy_count: 1` |
