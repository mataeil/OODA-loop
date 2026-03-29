---
name: plan-backlog
description: Score GitHub Issues using the RICE framework and propose a priority ordering. Strategize phase skill — turns raw issues into a ranked action plan written to agent/state/backlog.json.
ooda_phase: strategize
version: "1.0.0"
input:
  files: [agent/state/backlog.json]
  config_keys: []
output:
  files: [agent/state/backlog.json]
safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.01
domains:
  - backlog
chain_triggers:
  - target: dev-cycle
    condition: "actionable_items >= 1 AND top_rice_score >= 50"
---

# plan-backlog: GitHub Issues RICE Scorer

Fetches open GitHub Issues, scores each with RICE (Reach × Impact × Confidence ÷ Effort),
and outputs a ranked priority table. READ-ONLY — writes only to `agent/state/backlog.json`.

---

## Step 0: Safety

**HALT check** — if `config.safety.halt_file` exists: print `[HALT] plan-backlog stopped. Reason: {content}` and exit.

**gh check** — run `gh --version`. If unavailable:
```
gh CLI not available. Skipping plan-backlog.
Install: https://cli.github.com  |  Auth: gh auth login
```
Exit cleanly (not an error).

---

## Step 1: Load Issues

```bash
gh issue list --state open --json number,title,labels,body,createdAt,assignees --limit 100
```

On command error → `Could not fetch issues. Is this a GitHub repository? Skipping.` — exit 0.
On empty array → write state with `status: "no_issues"`, print `No open issues to score.` — exit 0.

Also read `agent/state/backlog.json` (if it exists) to carry forward `run_count`.

---

## Step 2: RICE Scoring

For each issue estimate four components from title, labels, and body.

| Component | Range | Label signals (highest match wins) | Default |
|---|---|---|---|
| **Reach** | 0.0–1.0 | `user-facing/ux/frontend` → 0.8, `api/perf` → 0.6, `internal/chore` → 0.2 | **0.5** |
| **Impact** | 0.25–3.0 | `critical/P0` → 3.0, `bug/security` → 2.0, `enhancement/P1` → 1.0, `P2/low` → 0.5 | **1.0** |
| **Confidence** | 0.5–1.0 | ≥3 labels + body>200 → 1.0, ≥1 label or body>100 → 0.8, bare issue → 0.5 | **0.8** |
| **Effort** | 1–10 days | `easy/S` → 1, `L/needs-design` or body>500 → 5, `epic/XL` → 8 | **3** |

```
RICE = (Reach × Impact × Confidence) / Effort   [round to 2 decimal places]
```

---

## Step 3: Priority Table

Sort by RICE descending. Print:

```
plan-backlog — <ISO timestamp>   Scored: N issues
| # | Title                                         | RICE  |  R  |  I  |  C  |  E  | Labels      |
|---|-----------------------------------------------|-------|-----|-----|-----|-----|-------------|
| 42 | Fix login redirect loop                      | 53.33 | 0.8 | 2.0 | 1.0 |  3  | bug, P0     |
```

Truncate titles to 45 chars with `…`.

---

## Step 4: State Update

Write to `agent/state/backlog.json` (create `agent/state/` if missing):

```json
{ "schema_version": "1.0.0", "last_run": "<ISO 8601>", "run_count": 1,
  "scored_count": 12, "unscored_count": 0, "status": "scored",
  "scores": [{ "number": 42, "title": "Fix login redirect loop",
    "rice_score": 53.33, "reach": 0.8, "impact": 2.0, "confidence": 1.0,
    "effort": 3, "labels": ["bug", "P0"], "created_at": "<ISO 8601>" }] }
```

Every issue is scored (defaults applied when labels/body absent). `status`: `"scored"` or `"no_issues"`.

---

## Step 5: Report

```
Top 5 issues by RICE:
  1. #42 Fix login redirect loop (RICE 53.33) — bug, P0
  2. #7  Add dark mode toggle    (RICE 13.33) — enhancement
  ...

Recommendation: Start with #42. High-impact bug affecting most users.
Chain trigger will fire on next /evolve when top RICE > 50.
```

List all issues if fewer than 5. If none: `No open issues to score. Backlog is clear.`

---

## Graceful Degradation

| Scenario | Behavior |
|---|---|
| HALT file present | Print reason, exit immediately |
| `gh` not installed | Print install hint, exit 0 |
| Not a GitHub repo | Print message, exit 0 |
| No open issues | Write `status: "no_issues"`, exit 0 |
| Issue has no labels or body | Apply all defaults; still scored |
| `agent/state/` missing | Create directory, then write |
| `backlog.json` corrupt | Re-initialize as first run |
