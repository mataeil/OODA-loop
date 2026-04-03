---
name: ooda-status
description: Display OODA-loop status dashboard. Shows cycle count, domain states, confidence scores, action queue, and alerts in a single view.
ooda_phase: support
version: "1.0.0"
input:
  files:
    - config.json
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/cost_ledger.json
  config_keys: []
output:
  files: []
  prs: none
safety:
  halt_check: true
  read_only: true
domains: []
chain_triggers: []
---

# /ooda-status — Status Dashboard

Display the current state of the OODA-loop at a glance.

## Step 0: Safety Check

Check for the HALT file before anything else.

```bash
ls agent/safety/HALT 2>/dev/null && echo "HALT_ACTIVE" || echo "HALT_INACTIVE"
```

If HALT exists, continue rendering the dashboard but mark HALT status as "ACTIVE".
Do not abort — status must always be readable regardless of HALT state.

## Step 1: Gather Data

Read each file below. If a file is missing, note it and use a safe default value.
If a file exists but contains invalid JSON (parse error), treat it the same as missing
and append an alert: `[WARN] Corrupt state file: <path> — skipped (parse error)`.
Do not let a single corrupt file abort the entire dashboard.

**config.json** — project name, current level, cost limit, domain list, domain status fields
```bash
cat config.json 2>/dev/null || echo "MISSING"
```

Read each domain's `status` field from config.json to identify which domains are `"available"` (not yet configured) vs `"active"` vs `"disabled"`.

**agent/state/evolve/state.json** — cycle_count, last_cycle timestamp
```bash
cat agent/state/evolve/state.json 2>/dev/null || echo "MISSING"
```

**agent/state/evolve/confidence.json** — per-domain confidence scores (0.0–1.0)
```bash
cat agent/state/evolve/confidence.json 2>/dev/null || echo "MISSING"
```

**agent/state/evolve/action_queue.json** — pending and proposed action counts, top action
```bash
cat agent/state/evolve/action_queue.json 2>/dev/null || echo "MISSING"
```

**agent/state/evolve/metrics.json** — cost_today, cost_limit
```bash
cat agent/state/evolve/metrics.json 2>/dev/null || echo "MISSING"
```

**Domain state files** — for each domain in config.domains, read its state_file path:
- last_run timestamp
- status field (healthy / degraded / critical / error)
- score value
- alerts array
```bash
# Example: cat agent/state/health/state.json 2>/dev/null
```

## Step 2: Calculate Display Values

**Time formatting** — compute elapsed time from last_run or last_cycle to now:
- < 60 minutes → `Xm`
- < 24 hours   → `Xh`
- >= 24 hours  → `Xd`
- Never run    → `—`

**Domain status symbol:**
- `✓` if status is healthy
- `⚠` if status is degraded
- `✗` if status is critical or error
- `?` if domain has never run or state file is missing

**Score** — numeric value from domain state, formatted to 2 decimal places. Show `—` if unavailable.

**Confidence** — value from confidence.json for this domain (e.g. `0.9`). Show `—` if unavailable.

**Actions** — count items in action_queue.json by status field: pending vs proposed.
Top action: first item sorted by RICE score descending.

**Alerts** — collect all alerts arrays from domain state files. Count total.
Show `none` if count is 0, otherwise show the count.

**Cost** — from metrics.json: `cost_today` / `cost_limit`. Show `—/—` if unavailable.

## Step 3: Render Dashboard

Print the dashboard using box-drawing characters exactly as shown below.
Replace `{placeholders}` with the computed values from Step 2.

```
╔══════════════════════════════════════════╗
║  OODA-loop status                     ║
╠══════════════════════════════════════════╣
║ Cycle: #{N}  Last: {ago}  Level: {N}     ║
╠══════════════════════════════════════════╣
║ Domain           Score  Conf  Last  Status║
║ {domain_name}    {score} {conf} {ago} {sym}║
╠══════════════════════════════════════════╣
║ Actions: {N} pending, {N} proposed       ║
║ Next: {top_action_title} (RICE {score})  ║
╠══════════════════════════════════════════╣
║ Alerts: {count_or_none}                  ║
║ HALT: {ACTIVE / inactive}                ║
║ Cost: ${spent}/${limit} today            ║
╚══════════════════════════════════════════╝
```

One row per enabled domain. Pad domain names and numbers so columns align.
If HALT is active, write `HALT: ACTIVE` (all caps, no color codes needed -- emphasis via caps).

**Narrow terminal fallback** — The box-drawing layout above assumes >= 50 columns.
If the output environment is narrow (e.g. split pane, mobile terminal), fall back to
a compact plain-text list without box-drawing characters:
```
OODA-loop status
Cycle #0 | Last — | Level 0
---
service_health  — — — ?
test_coverage   — — — ?
---
Actions: — pending, — proposed
Alerts: none | HALT: inactive | Cost: —/—
```

## Step 4: Suggestions

After rendering the dashboard, check whether a suggestion should be shown:

1. Read `cycle_count` from state.json. If `cycle_count >= 3`, proceed.
2. Collect all domains from config.json where `status: "available"`.
3. If any `"available"` domains exist, show **exactly one** suggestion per status check:

```
  Suggestion: You've run {N} cycles. Consider adding
  /scan-market for strategic insights.
  Run: /ooda-skill create scan-market
```

   Replace the domain name and description with the actual available domain being suggested.

4. Rotate through available domains across successive status checks (use cycle_count mod available-domain-count to pick which one to show).
5. Once all domains are either `"active"` or `"disabled"` (none remain `"available"`), omit the Suggestions block entirely.
6. Never show more than 1 suggestion per status check.

---

## Graceful Degradation

| Condition | Behavior |
|-----------|----------|
| config.json missing | Print: `Not configured. Run /ooda-setup first.` — stop. |
| state files missing (all) | Show dashboard with `Cycle: #0  Last: —  Level: 0` and domain rows as `?`. Add note: `No cycles run yet. Run /evolve to start.` |
| Individual domain state file missing | Show `?` for score, conf, last, status for that domain only. |
| Any state file contains invalid JSON | Treat as missing (use defaults), add `[WARN] Corrupt state file: <path>` to alerts section. |
| action_queue.json missing | Show `Actions: — pending, — proposed` and `Next: —`. |
| metrics.json missing | Show `Cost: —/— today`. |
| HALT active | Show full dashboard. Mark `HALT: ACTIVE`. Do not suppress any data. |
