---
name: ooda-status
description: Display OODA-loop status dashboard. Shows cycle count, domain states, confidence scores, action queue, and alerts in a single view.
ooda_phase: support
version: "1.3.0"
input:
  files:
    - config.json
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/cost_ledger.json
    - agent/state/evolve/memos.json
    - agent/state/evolve/episodes.json
    - agent/state/evolve/principles.json
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/CHANGELOG.md
    - agent/state/evolve/reflections.json
    - agent/state/evolve/outcomes.json
    - agent/state/evolve/cycle_log.jsonl
    - "agent/state/*/lens.json"
    - "agent/state/*/lens_changelog.json"
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

Also read `config.mission` (the project's purpose the loop drives toward) and each domain's `mission_alignment`.

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

**agent/state/evolve/metrics.json** — execution counters/streaks (under `counters`)
```bash
cat agent/state/evolve/metrics.json 2>/dev/null || echo "MISSING"
```

**Cost source**: today's spend comes from `agent/state/evolve/cost_ledger.json`
(`total_estimated_usd`, after confirming `date` == today UTC; stale date ⇒ $0.00
pending reset) and the limit from `config.cost.daily_limit_usd`. metrics.json has
NO cost fields — never read cost from it.

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

**Cost** — `cost_ledger.json.total_estimated_usd` (if `date` == today UTC, else $0.00) / `config.cost.daily_limit_usd`. Show `—/—` if unavailable.

**Orient Health (v1.2.0)** — parsed from the Orient layer state files:

- `episodes_count` and `last_episode_week` — from `episodes.json.episodes[]`.
  Show `0` and `—` if empty or missing.
- `principles_count` and `principles_high_conf` — from `principles.json.principles[]`,
  where `high_conf` is `count(confidence >= 0.5)`.
- `lens_domains` — number of `agent/state/*/lens.json` files that exist; denominator
  is the count of active domains in config.domains.
- `chain_count_last_10` — in `state.json.decision_log[-10:]`, count entries
  where `chain_executed` exists and is non-empty.
- `active_interventions` — length of `memos.json.interventions[]`.
- `skill_gaps_unaddressed` — `count(gap.resolved != true)` in `skill_gaps.json.gaps[]`.
  Break out `learning_loop_break` count separately since those flag internal
  evolve invariants (e.g., cost_ledger auto-patches).
- `reflections_count` and `last_lesson` — from `reflections.json.reflections[]`:
  total count and the most recent entry's `lesson` (truncate to ~32 chars).
  Show `0` / `—` if the file is empty or missing. This shows whether the
  Reflexion self-critique loop (evolve Step 5-F / 2-F) is actually running.

**Season + Focus (v1.2.0)** — from `config.json`:

- `season_mode` — `config.season_modes.current_mode` if enabled, else `"disabled"`.
- `season_overrides_count` — length of
  `config.season_modes.modes[current_mode].weight_overrides`.

**Active context (v1.2.0)** — from `config.json.active_context.path`:
- if set and file readable: `<path> (age: <mtime>m)`; else `none`.

## Step 3: Render Dashboard

Print the dashboard using box-drawing characters exactly as shown below.
Replace `{placeholders}` with the computed values from Step 2.

```
╔══════════════════════════════════════════════════════╗
║  OODA-loop status                                    ║
║ Mission: {mission_oneline_or_—}                       ║
╠══════════════════════════════════════════════════════╣
║ Cycle: #{N}  Last: {ago}  Level: {N}  Vel: {N}/day   ║
╠══════════════════════════════════════════════════════╣
║ Domain           Score  Conf  Trend  Last  Status    ║
║ {domain_name}    {score} {conf} {↑↓→}  {ago} {sym}   ║
╠══════════════════════════════════════════════════════╣
║ Actions: {N} pending, {N} proposed  Oldest: {age}d   ║
║ Next: {top_action_title} (RICE {score})              ║
╠══════════════════════════════════════════════════════╣
║ Saturation: {N} observe-only cycles {bar}            ║
║ Alerts: {count_or_none}                              ║
║ HALT: {ACTIVE / inactive}                            ║
║ Cost: ${spent}/${limit} today (${rate}/h)             ║
╠══ Orient Health (v1.2.0) ═══════════════════════════╣
║ Episodes: {episodes_count} (last: {week})            ║
║ Principles: {principles_count} ({high_conf} conf≥0.5)║
║ Lens: {lens_domains}/{active_domain_count} domains   ║
║ Chain exec: {chain_count_last_10}/10 cycles          ║
║ Interventions: {active_interventions} active         ║
║ Gaps: {skill_gaps_unaddressed} ({loop_break} break)  ║
║ Reflections: {reflections_count} (last: {last_lesson})║
╠══ Season + Context (v1.2.0) ════════════════════════╣
║ Season: {season_mode} ({overrides_count} overrides)  ║
║ Context: {context_path_or_none}                      ║
╚══════════════════════════════════════════════════════╝
```

The `--orient` flag opens a detailed view of Orient Health only (useful when
debugging whether the learning loop is actually running):

```
/ooda-status --orient
```

Output focuses on Episodes / Principles / Lens / Chain / Interventions /
Skill gaps and omits the domain/cost/saturation rows.

### `--scorecard` — is the loop actually WORKING?

```
/ooda-status --scorecard          (all recorded cycles)
/ooda-status --scorecard --window 20   (last 20 cycles)
```

Renders the **Loop Scorecard** — the loop-engineering measurement view that
answers "is the loop *improving the project*, or just running?". This is the
deterministic reference `scripts/loop_scorecard.py` rendered verbatim; it reads
`outcomes.json` (Step 6-C9), `metrics.json` counters, `cost_ledger.json`, and
`action_queue.json` — no recomputation, no model call. KPIs (the measurement
canon):

- **Loop Value Score** — mean `quality_multiplier` across scored cycles (0–1).
  The single headline number: 1.0 = every cycle merged & held; 0.0 = all futile.
- **Task Completion Rate** — % of cycles that merged and were accepted.
- **Futile Cycle Rate** — % of cycles that ran but changed nothing.
- **PR Merge Rate** + **hold rate** (merged that weren't reverted).
- **Action Queue Resolution** — resolved ÷ added (a value < 100% means the
  backlog is growing faster than the loop clears it).
- **Cost per Successful Cycle** — total cost ÷ accepted-value cycles.
- **Goal Progress** — mean progress of active `goals.json` done-conditions
  (the loop-engineering "run until a verifiable goal is met" signal).
- **Gap Resolution** / **Lesson Application** — learning-loop health: are
  self-diagnosed skill gaps closed, and are reflexion lessons re-applied?
- **Verdict** — working / partial / stalled, from the Loop Value Score.

Graceful degradation: with no `outcomes.json` yet (pre-v1.4.0 state or a fresh
project), every KPI shows `—` and the verdict reads "no outcomes recorded yet."

### `--share` — render the latest Cycle Card

`/ooda-status --share` re-renders the most recent cycle's **Cycle Card** — the
same shareable artifact evolve prints at the end of its Step 7 — so it can be
screenshotted or pasted into X / Reddit / Slack without re-running a cycle. It is
read-only.

```
/ooda-status --share
```
#### `--share --plain` — emit only the text line

If the `--plain` flag is appended (`/ooda-status --share --plain`), this mode acts as a strict subset of 
`--share` that omits the Cycle Card rendering output. It reuses identical state
 reconstruction logic, LEARN-line selection priority, and all graceful degradation rules defined in `--share`.
 It emits only the single-sentence plain-text share line (as defined in evolve Step 7).

```
/ooda-status --share --plain
```

Reconstruct the card (or plain text) from existing state — no recomputation:

- **header / DECIDE / ACT** — `state.json.decision_log[-1]` (cycle, timestamp,
  domain, skill, score, confidence, result, pr_number, risk_tier, orient_summary).
- **OBSERVE / ORIENT** — `decision_log[-1].orient_summary` and, if present, the
  `**Orient**` line of the latest entry in `agent/state/evolve/CHANGELOG.md`.
- **LEARN** — pick the highest-signal change using the SAME priority order as
  evolve Step 7 (human-decision confidence change > lens change > new
  intervention > micro-adjustment). Source it, in order, from the latest
  `agent/state/*/lens_changelog.json` entry, `memos.json.interventions[]` created
  this cycle, and the `**Confidence**` (trend / micro-adj) line of the latest
  CHANGELOG.md entry. If none is recoverable, render
  `no new orientation recorded for cycle #{N}`.
- **COST** — latest `cost_ledger.json` entry + `config.cost.daily_limit_usd`.

Render byte-for-byte the same box and the plain-text share line as evolve
Step 7, including the honesty rule on verbs (re-aimed / adjusted /
deprioritized — never "trained" or "learned weights") and the same
missing-field graceful degradation (render `—` for any absent field; on legacy
pre-v1.2.0 state expect more `—`). If no cycle has run yet (`decision_log`
empty), print: `No cycle to share yet. Run /evolve first.`

**New columns and rows explained:**

- **Vel (Velocity)**: cycles per day = `total_cycles / days_since_first_cycle`. Helps detect runaway loops or idle periods.
- **Trend**: per-domain confidence direction. decision_log only snapshots the WINNER's confidence each cycle, so compare the domain's two most recent decision_log appearances (`↑`/`↓`/`→` by delta); a domain with fewer than two appearances in the retained log renders `→`. Do not pretend a "5 cycles ago" per-domain snapshot exists — it doesn't.
- **Oldest**: age of the oldest pending action in action_queue, in days. Shows `—` if queue is empty. Highlights aging items that may need human review.
- **Saturation**: `consecutive_observe_only_cycles` from state.json. Render as a progress bar toward `saturation.halt_threshold` (e.g., `████░░░░░░ 40%`). Shows `0` if no saturation.
- **$/h (Cost rate)**: `cost_ledger.total_estimated_usd / hours_since_midnight_utc`. Helps predict whether daily limit will be hit.

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
| cost_ledger.json missing | Show `Cost: —/— today`. |
| HALT active | Show full dashboard. Mark `HALT: ACTIVE`. Do not suppress any data. |
