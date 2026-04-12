---
name: evolve
description: OODA Meta-Orchestrator. Observes all domain states, orients by learning from past outcomes, decides the highest-priority action, and executes it. Run with /evolve or /loop 4h /evolve.
ooda_phase: meta
version: "1.0.0"
input:
  files:
    - config.json
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/goals.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/memos.json
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/episodes.json
    - agent/state/evolve/principles.json
    - agent/state/evolve/cost_ledger.json
  apis:
    - "GitHub CLI (gh pr list, gh issue list, gh pr merge, gh pr view)"
    - "Health endpoints (config.health_endpoints)"
    - "Notification APIs (config.notifications)"
  config_keys:
    - domains
    - implementation
    - scoring
    - confidence
    - safety
    - progressive_complexity
    - signals
    - memory
    - test_command
    - health_endpoints
    - deploy_workflow
    - notifications
    - cost
output:
  files:
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/memos.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/goals.json
    - agent/state/evolve/episodes.json
    - agent/state/evolve/principles.json
    - agent/state/evolve/cost_ledger.json
    - agent/state/evolve/CHANGELOG.md
  prs: none
safety:
  halt_check: true
  read_only: true
domains: []
chain_triggers: []
---

# evolve: OODA Meta-Orchestrator -- Autonomous Decision Engine

evolve is the brain of OODA-loop. It sits above every domain skill and runs
one full OODA loop per cycle: Observe the world, Orient by analyzing patterns
and updating beliefs, Decide which domain needs attention most, then Act by
invoking the winning skill.

This is NOT a round-robin scheduler. The Orient step differentiates evolve from
a cron job -- each cycle it reviews PR outcomes, updates confidence, applies
memos, detects urgent signals, and adjusts its world model. Over time it learns
which domains produce value and which waste cycles.

Based on John Boyd's OODA loop with an added Reflect step that extracts skill
gaps, writes memos, and feeds the next Orient -- creating a double-loop learning
system. All behavior is driven by `config.json`. No domain names, skills, or
routing tables are hardcoded.

---

## Safety Rules

These rules are absolute. Violating any is a bug.

1. **HALT File** -- Before ANY work, check `config.safety.halt_file`. If it exists, print reason and stop immediately.
2. **Protected Paths** -- PRs touching `config.safety.protected_paths` MUST be Risk Tier 3 (human review). No auto-merge ever.
3. **PR Limit** -- Max `config.safety.max_prs_per_cycle` PRs per cycle (default 1).
4. **State-Only Direct Write** -- evolve writes only to `agent/state/evolve/*`. All other changes require branch + PR.
5. **Skill Allowlist** -- Only invoke skills in `config.safety.skill_allowlist`. Unlisted skill = safety violation, skip to Reflect.
6. **PR Size Limits** -- Respect `config.safety.max_files_per_pr` (20) and `config.safety.max_lines_per_pr` (500). Exceeding = Level 3.

---

## File Structure

```
agent/state/evolve/
  state.json          -- cycle_count, last_cycle, decision_log (max 20)
  confidence.json     -- per-domain confidence scores (0.1-1.0)
  goals.json          -- user-defined goals with progress tracking
  skill_gaps.json     -- detected missing capabilities with frequency
  memos.json          -- cross-cycle notes and score_adjustments
  action_queue.json   -- RICE-scored pending/in_progress/completed actions
  metrics.json        -- permanent counters (cycles, PRs, costs)
  cost_ledger.json    -- daily API cost tracking (resets at 00:00 UTC)
  episodes.json       -- weekly summaries (tier 2 memory)
  principles.json     -- permanent learnings (tier 3 memory)
  CHANGELOG.md        -- cycle activity log (most recent 50)
```

Domain skills write their own state files. evolve reads but never writes them.

---

## Step 0: Safety Checks

### 0-Pre: Config Validation

```
if config.json does not exist:
  Print "[FATAL] config.json not found. Run /ooda-setup to create it."
  EXIT immediately.
if config.json is not valid JSON:
  Print "[FATAL] config.json parse error: {error_message}. Fix syntax and retry."
  EXIT immediately.
```

### 0-A: HALT Check

```
if file exists at config.safety.halt_file:
  Print "[HALT] Agent stopped. Reason: {file_content}"
  Print "Remove to resume: rm {config.safety.halt_file}"
  EXIT immediately.
```

### 0-B: Concurrent Execution Lock

```
lock_file = agent/state/evolve/.lock
if lock_file exists:
  Print "[SKIP] Another evolve cycle is running (lock file exists)."
  Print "If stale, remove manually: rm {lock_file}"
  EXIT.
Create lock_file with content: {"pid": current, "started_at": "ISO 8601"}
```

The lock file is deleted at the end of Step 6. **Every early-exit path (HALT
during execution, dry-run, min-score skip, confidence gate with no fallback)
MUST also delete the lock file before exiting.** If evolve crashes unexpectedly,
the lock persists — the next invocation detects it and exits. To recover from a
stale lock, the operator deletes the file manually.

Stale lock detection: if `started_at` in the lock file is older than
`config.safety.lock_timeout_minutes` (default 30), treat the lock as stale,
log `[WARN] Stale lock detected (age: {minutes}m). Removing.`, delete it,
and proceed.

### 0-C: Crash Recovery

```
if state.json.cycle_in_progress == true:
  last = state.json.decision_log[-1] (if exists)
  Print "[WARN] Previous cycle #{last.cycle} did not complete."
  Print "  Last domain: {last.domain}, skill: {last.skill}, started: {last.timestamp}"
  Print "  Resetting cycle_in_progress. Starting fresh cycle."
  Set cycle_in_progress = false, write state.json.
  Add memo: { type: "crash_recovery", cycle: last.cycle, domain: last.domain }
  Continue with fresh cycle (do NOT resume old one).
```

### 0-D: Min Cycle Interval

```
elapsed = (now - state.json.last_cycle) in minutes.
if elapsed < config.safety.min_cycle_interval_minutes:
  EXCEPTION: if ANY domain state file has alerts with severity "critical":
    Print "[URGENT] Critical alert detected, bypassing interval."
    Continue.
  Otherwise:
    Print "[SKIP] Too soon. {remaining} min until next cycle."
    EXIT.
if last_cycle is null: first cycle, proceed.
```

### 0-E: First Cycle Observe-Only

```
if state.json.cycle_count === 0 AND config.safety.first_cycle_observe_only:
  Print "[INFO] First cycle -- observe-only mode."
  Run Steps 1-3 only. Skip Steps 4-5.
  Print "First cycle complete. Here's what I found:" + score table.
  Print "Run /evolve again to take action."
  Jump to Step 6.

  In Step 6, record decision_log entry as:
  { cycle: 1, timestamp, action: "observe_only", reason: "first_cycle",
    domain: winner_domain, skill: winner_skill, score: winner_score,
    orient_summary, result: "observe_only", score_verified: true }
  cycle_count MUST increment to 1 so the next cycle proceeds normally.
```

Set `cycle_in_progress = true` in state.json before proceeding.
Record `cycle_start_time = now`.

---

## Step 1: Observe

### 1-A: Domain State Reading

```
for each domain_name, domain_config in config.domains:
  if domain_config.status == "disabled": skip entirely, do not score
  if domain_config.status == "available":
    log "[{domain}] Not yet configured. Skipping."
    skip, do not score
  if domain_config.status == "active": proceed normally
  # Legacy: if no status field, treat as "active" (backward compat)

  # Legacy: "enabled" field is superseded by "status" but still honored as fallback
  if not domain_config.enabled: skip
  file = domain_config.state_file
  if file missing:
    mark as "never_run", hours_since_last = config.scoring.hours_if_never_run
  else:
    read JSON. Calculate hours_since_last from data.last_run to now.
    (Legacy: if `last_run` is missing, also check `last_check` — older scan-health
    versions used this key. Treat either as the last-run timestamp.)
    Extract: status, run_count, alerts.

  Also read lens file: agent/state/{domain_name}/lens.json
  If lens exists and is valid JSON:
    Extract focus_items where confidence >= 0.6
    Extract learned_thresholds where confidence >= 0.6
    Extract discovered_signals
    Store as domain_config.lens for use in Step 4 skill invocation
  If lens missing or corrupt: proceed without lens (base behavior)
```

Also read evolve self-state: state.json, confidence.json, memos.json,
goals.json, action_queue.json, skill_gaps.json, cost_ledger.json.

If `cost_ledger.json` is missing or corrupt (invalid JSON), create with initial structure:
`{"schema_version": "1.0.0", "date": "<today YYYY-MM-DD>", "entries": [], "total_estimated_usd": 0.0}`

**Daily reset**: Compare `cost_ledger.json.date` to current UTC date (`YYYY-MM-DD`).
If different: reset `total_estimated_usd` to 0.0, clear `entries`, update `date` to today.
Cost accounting always uses UTC regardless of `config.project.timezone`.

If `config.implementation.enabled`: read action_queue.json for pending_count,
oldest_pending_hours, highest_rice.

### 1-B: GitHub Status

Run these commands. If `gh` fails, log warning and continue with empty data.

```bash
gh pr list --state open --json number,title,labels,createdAt,headRefName
gh pr list --state merged --limit 5 --json number,title,mergedAt,headRefName
gh pr list --state closed --limit 5 --json number,title,closedAt,headRefName
gh issue list --state open --json number,title,labels
```

Store as: open_prs, merged_prs, closed_prs, open_issues.

### 1-C: External Signals

Read `agent/state/external/*.json` if any files exist. Include contents in
observations under "external_signals". Missing directory = skip silently.

### 1-D: Observation Structuring

Assemble in-memory observation object (NOT written to file):

```
observation = {
  timestamp, domains (1-A), github (1-B),
  implementation { pending_count, oldest_pending_hours, highest_rice },
  external_signals (1-C),
  evolve_state { cycle_count, decision_log_length, active_goals, pending_actions }
}
```

Print: `[Observe] Scanned {N} domains. {M} open PRs, {K} merged since last cycle.`

---

## Step 2: Orient

### 2-A: Pattern Analysis

Read last 5 entries from state.json.decision_log. Detect:
- **Consecutive same domain**: count recent consecutive selections of same domain.
- **Execution-result correlation**: match decision_log PR numbers to merged/closed PRs.
- **Repeated failures**: count entries with result "error"/"failed" for same domain. If >= 2, flag as infrastructure_issue.
- **Futile loop**: count consecutive cycles where the selected domain produced result "success" but no actionable output (no actions extracted, no alerts generated, no PRs created — e.g., plan-backlog returning "no_remote" repeatedly). If >= 3 consecutive futile cycles for the same domain, add a memo penalty of -10.0 to that domain and log `[Orient] Futile loop detected: {domain} produced no output for {N} consecutive cycles. Penalizing.` This prevents the staleness score from endlessly selecting an unproductive domain.
  - **Scope**: penalty applies only to the specific futile domain, not globally.
  - **Lifetime**: written as `score_adjustments[domain] = -10.0` in memos.json. Consumed (deleted) after one application in Step 3-A scoring. Does not persist across multiple cycles.
  - **Recovery**: domain recovers automatically by producing a non-empty observation in any subsequent cycle (the consecutive futile counter resets to 0).

Store patterns for Steps 2-E and 5-C.

### 2-A2: Saturation Circuit Breaker

Track `consecutive_observe_only_cycles` in state.json. A cycle is "observe-only"
if it produced result "success" but: no PRs created, no actions extracted, no
new alerts generated, and no confidence changes occurred. Increment the counter
each time; reset to 0 when any of those events occurs.

```
-- Check if this cycle produced actionable output
has_output = (prs_created > 0 OR actions_extracted > 0 OR new_alerts > 0 OR confidence_changed)

if has_output:
  state.consecutive_observe_only_cycles = 0
else:
  state.consecutive_observe_only_cycles += 1
  N = state.consecutive_observe_only_cycles

  warn_threshold = config.saturation.warn_threshold      -- default 5
  boost_threshold = config.saturation.boost_threshold    -- default 10
  halt_threshold = config.saturation.halt_threshold      -- default 15

  if N == warn_threshold:
    Add memo: { type: "saturation_warning", message: "Observation saturation: {N} cycles without actionable output. Consider enabling implementation or reviewing domain configuration." }
    Print "[Orient] ⚠ Saturation warning: {N} consecutive observe-only cycles."

  if N == boost_threshold:
    -- Boost pending actions and implementation domain to break out of observation loop
    for each item in action_queue.pending:
      item.effective_rice += config.saturation.implementation_boost  -- default 5.0
    Print "[Orient] ⚠ Saturation boost applied: action queue +{boost}, implementation domain boosted."

  if N >= halt_threshold AND config.saturation.auto_halt (default true):
    Create HALT file: "Observation saturation: {N} cycles without actionable output. Human review needed. Delete this file to resume."
    Print "[Orient] 🛑 Saturation halt: {N} cycles. HALT file created. Review required."
```

### 2-B: Confidence Update

```
for each PR in merged_prs:
  match PR.headRefName to domain via config.domains.*.branch_prefix
  if PR.number already in decision_log: skip (prevent double-counting)
  confidence[domain] += config.confidence.merge_boost  (cap at config.confidence.max)
  Print "[Orient] PR #{n} merged -> {domain} confidence +{boost}"

for each PR in closed_prs (not merged):
  match branch to domain via branch_prefix
  if already logged: skip
  confidence[domain] -= config.confidence.reject_penalty  (floor at config.confidence.min)
  Print "[Orient] PR #{n} rejected -> {domain} confidence -{penalty}"

for domains not yet in confidence.json:
  set to config.confidence.initial (default 0.7)
```

If config.implementation.enabled: apply same logic to implementation PRs.

### 2-B1: Observation-Based Micro-Adjustments

When `config.confidence.observation_micro_adjustments` is true (default) AND
`progressive_complexity.current_level < 3`, apply observation-based confidence
updates. This prevents confidence stagnation in observation-only deployments
where no PRs are created and PR-based updates never fire.

```
for each domain that was executed this cycle:
  if skill produced actionable findings (actions extracted > 0 or alerts found):
    confidence[domain] += 0.02   (cap at config.confidence.max)
    Print "[Orient] {domain} produced findings -> confidence +0.02"
  else if skill produced alerts (domain state has severity warning or critical):
    confidence[domain] += 0.03   (cap at config.confidence.max)
    Print "[Orient] {domain} alert detected -> confidence +0.03"
  else if skill produced no new data (status unchanged from previous cycle):
    confidence[domain] -= 0.01   (floor at config.confidence.min)
    Print "[Orient] {domain} no new data -> confidence -0.01"
```

At Level 3 (autonomous mode), these micro-adjustments are suppressed to avoid
double-counting with PR-based confidence updates. The PR merge/reject deltas
(+0.1/-0.2) are the primary signal at Level 3.

### 2-B2: Action-Queue Sync

For each action in action-queue with status "proposed" (has pr_number):
- PR merged -> status = "merged", move to completed.
- PR closed (not merged) -> status = "rejected", move to completed. Add memo.
- PR has review comments -> summarize feedback in memos.
- PR still open -> no change.

### 2-C: Goal Progress

```
for each goal in goals.json where status == "active":
  if goal.metric_command exists:
    run command, parse numeric output as current_value
    if command fails: log warning, keep previous progress
  goal.progress = clamp(current_value / goal.target, 0.0, 1.0)
  if progress >= 1.0: mark status "completed"
```

### 2-D: Memo Adjustments

Read memos.json. The canonical format is:
`{"schema_version":"1.0.0", "score_adjustments":{}, "history":[], "last_memo":null}`

If the file has a `memos` array but no `score_adjustments` key (legacy format),
treat `score_adjustments` as empty `{}` and `history` as the `memos` array.

Read `score_adjustments` -- one-shot bonuses/penalties keyed by domain.
They will be applied in Step 3-A. After application, DELETE them (set to {}).
They apply exactly once. If a key does not match any domain in config.domains,
log `[WARN] Memo adjustment for unknown domain '{key}' -- ignored and cleared.`
and discard it.

### 2-E: Orient Summary

Read the previous cycle's orient_summary from `state.json.decision_log[-1].orient_summary`
(if decision_log is non-empty). Use it as prior context: what changed since that assessment?
What predictions held? What was surprising? This creates a cumulative world model that
evolves across cycles rather than being rebuilt from scratch each time.

Write 2-3 sentence world model: what changed, what's urgent, what to focus on.
Truncate orient_summary to 500 characters max. If the previous cycle's summary
exceeds 500 chars when read, truncate it before using as prior context.
Store as orient_summary in the decision_log entry being built.
Print: `[Orient] {orient_summary}`

---

## Step 3: Decide

### 3-G: Progressive Complexity Filter (apply FIRST)

```
level = config.progressive_complexity.current_level
level_config = config.progressive_complexity.levels[level]

First, exclude non-active domains:
  Remove any domain where status == "disabled" or status == "available"
  Only status == "active" domains count toward the level-based domain limit

Sort remaining (active) domains by weight descending.

Level 0: keep first level_config.domains active domains only.
Level 1: keep first level_config.domains active domains only.
Level 2: all active domains. No implementation.
Level 3: all active domains + implementation (if config.implementation.enabled).
```

Filter domains BEFORE scoring.

If zero domains remain after filtering (all disabled/available/over limit):
  Print "[Decide] No scoreable domains. All are disabled or not yet configured."
  Print "[Decide] Configure a domain with /ooda-skill or set status to 'active'."
  Log decision_log: { action: "skip", reason: "no_scoreable_domains" }
  Jump to Step 6.

### 3-A0: Implicit Guidance Check (Boyd Shortcut)

Before formal scoring, check if Orient produced a clear, high-confidence directive:

1. **Critical alert override.** If any domain state file contains `alerts` with
   `severity: "critical"`, skip scoring entirely. Select that domain as the winner.
   If multiple domains have critical alerts, pick the one with the highest weight.
   Print: `[Decide] Implicit guidance: critical alert in {domain}. Bypassing scoring.`
   Jump directly to Step 3-I.

2. **Stable pattern shortcut.** If the same domain won scoring for 3+ consecutive
   cycles (check decision_log last 3 entries) AND its confidence >= 0.8 AND no
   urgent signals exist for other domains: skip full scoring, continue with that
   domain. Print: `[Decide] Implicit guidance: stable pattern, continuing {domain}.`
   Jump to Step 3-I.

3. Otherwise, proceed to normal scoring (3-A).

This implements Boyd's key insight: Orient can bypass Decide and feed directly
into Act. An experienced operator does not score every option when the building
is on fire.

### 3-A: Standard Scoring Formula

For each enabled domain (after filtering):

```
staleness_term:
  if config.scoring.staleness_curve == "linear":
    staleness = hours_since_last * domain.weight           -- legacy behavior
  else:  -- "logarithmic" (default)
    K = 10.0                                               -- scaling constant
    T = 4.0                                                -- time constant (hours)
    staleness = domain.weight * K * ln(1 + hours_since_last / T)

  Reference values (logarithmic, weight=1.0):
    1h → 2.23,  4h → 6.93,  12h → 13.86,  24h → 19.46,  168h → 37.62
  The curve rises quickly for recently-stale domains but plateaus for very stale
  ones, preventing extreme scores that caused domain monopoly in production
  (e.g., 168h × 2.0 = 336 under linear).

-- Per-domain cooldown (skip if within min_interval_hours)
if domain.min_interval_hours is set AND hours_since_last < domain.min_interval_hours:
  score = 0   -- hard cooldown, domain cannot be selected this cycle
  Print "[Decide] {domain} cooldown: {hours_since_last}h < {min_interval_hours}h minimum"
  continue to next domain

-- Alert recency dampener (prevents alert-driven domain monopoly)
cooldown_hours = config.signals.alert_cooldown_hours  -- default 4
if urgent_signal > 0 AND alert severity is NOT "critical":
  recency_factor = max(0, 1.0 - hours_since_last / cooldown_hours)
  dampened_alert = urgent_signal * (1.0 - recency_factor)
  -- Example: domain ran 0h ago → dampened to 0. Ran 2h ago → 50%. Ran 4h+ → full bonus.
else:
  dampened_alert = urgent_signal  -- critical alerts bypass dampener (Step 3-A0 still fires)

-- Consecutive alert cap: after N consecutive alert-driven selections, auto-acknowledge
max_alert_cycles = config.signals.max_consecutive_alert_cycles  -- default 3
if domain was selected by alert in last max_alert_cycles consecutive cycles:
  dampened_alert = 0
  Print "[Decide] {domain} alert auto-acknowledged after {max_alert_cycles} consecutive cycles"

-- Entropy-based domain balance penalty (prevents systematic monopoly)
if config.scoring.balance_enabled (default true):
  B = config.scoring.balance_weight                   -- default 5.0
  N = count of active domains
  domain_share = metrics.domain_executions[domain] / max(metrics.total_skill_executions, 1)
  expected_share = 1.0 / N
  balance_penalty = max(-B * (domain_share - expected_share), -10.0)
  -- Example: 5 domains, domain ran 50% of the time (expected 20%): penalty = -5.0 * 0.3 = -1.5
  -- A domain that ran LESS than expected gets a bonus (penalty is positive).
else:
  balance_penalty = 0

score = staleness
      + dampened_alert                             -- from 3-B, with recency dampener
      + (goal_contribution * config.scoring.goal_weight)   -- from 3-C
      + (confidence * config.scoring.confidence_weight)
      + memo_adjustment                            -- from memos.json, consumed in 2-D
      + balance_penalty                            -- entropy-based domain balance
```

Floor: if computed score < 0, clamp to 0. Negative scores indicate a domain
that should be avoided this cycle, but displaying them as 0 prevents confusion
in the score table. The decision_log still records the raw (pre-clamp) score
for diagnostics.

Tie-break: prefer domain with fewer total executions (metrics.json.domain_executions).
If still tied, prefer domain with higher weight. If still tied, prefer the domain
that appears first in `config.domains` (deterministic by insertion order).

### 3-A2: Implementation Scoring

ONLY if config.implementation.enabled AND progressive_complexity >= 3:

```
impl_score = (pending_count * config.scoring.implementation_formula.pending_multiplier)
           + (oldest_pending_hours * config.scoring.implementation_formula.age_multiplier)
           + (highest_rice * config.scoring.implementation_formula.rice_multiplier)
           + (open_draft_pr_count > 0 ? config.scoring.implementation_formula.open_pr_penalty : 0)
           + (goal_contribution * config.scoring.goal_weight)
           + (confidence * config.scoring.confidence_weight)
           + memo_adjustment

if pending_count === 0: impl_score = 0
```

Add implementation as virtual domain in score table.

### 3-B: Urgent Signals

5 signal types. Multiple can stack on one domain.

| Signal | Condition | Bonus | Target |
|--------|-----------|-------|--------|
| health_alert | Domain state has alerts with severity critical/warning | config.signals.health_alert_bonus | Domain with fallback=true that has alerts |
| stale_after_change | PR merged in domain X, but X not run for > config.signals.stale_after_change_hours | config.signals.stale_after_change_bonus | The stale domain |
| queue_pressure | pending_count >= config.signals.queue_pressure_threshold | config.signals.queue_pressure_bonus | implementation |
| queue_age | oldest pending > config.signals.queue_age_hours | config.signals.queue_age_bonus | implementation |
| observe_loop_escape | 3 consecutive non-implementation cycles AND pending > 0 | config.implementation.observe_loop_escape_bonus | implementation |

health_alert only applies to domains with fallback=true.
queue_pressure/queue_age/observe_loop_escape only when config.implementation.enabled.

### 3-C: Goal Contribution

```
default goal_contribution = 0.5
for each domain:
  find active goals related to this domain (via goal.related_domains or keyword)
  if found: goal_contribution = 0.5 * (1.0 - min(matching_goal.progress))
  (optional) if user adds goal_contributions to a domain in config.json, use those values directly
```

### 3-D: Score Table Output

Print sorted by score descending:

```
[Decide] Domain scores:
| # | Domain         | Hours | Weight | Urgent | Goal | Conf | Memo  | SCORE |
|---|----------------|-------|--------|--------|------|------|-------|-------|
| 1 | domain_a       | 24.5  | 2.0    | +5.0   | 0.15 | 0.18 | +0.0  | 54.33 |
| 2 | implementation | P:5   | 1.5    | +3.0   | 0.15 | 0.16 | +0.0  |  9.31 |
```

Implementation shows pending_count as "P:{N}" in Hours column.

### 3-E: Min Score Skip

```
if highest score < 0.5:
  Print "[Decide] All scores below 0.5. Skipping cycle."
  Log decision_log: { action: "skip", reason: "all_scores_below_minimum" }
  Jump to Step 6.
```

### 3-F: Confidence Gate

```
winner = highest scoring domain
if winner confidence < config.safety.confidence_threshold:
  Print "[Decide] {winner} confidence below threshold."
  # Iterate candidates in descending score order (from Step 3-D sort).
  for candidate in scored_domains_descending:
    if candidate.confidence >= threshold:
      winner = candidate
      break
  else:
    # No domain meets threshold. Try fallback.
    fallback = first domain where config.domains[name].fallback == true
    if fallback:
      winner = fallback
    else:
      Print "[Decide] All domains below confidence threshold and no fallback domain."
      Print "[Decide] Observe-only cycle. Skipping Act, proceeding to Reflect."
      Log decision_log: { action: "skip", reason: "all_below_confidence_no_fallback" }
      Skip to Step 5.
  When confidence-gated: primary skill ONLY, skip chain[].
  Print "[Decide] Confidence-gated: primary skill only, no chain."
```

### 3-H: Dry-Run Exit

```
if invoked with --dry-run:
  Print score table + "Would execute: {skill}". Chain if any.
  Print "[Dry-run] No changes applied. State files not modified."
  Skip Steps 4-5. In Step 6: update ONLY metrics.json (increment
  total_cycles) and CHANGELOG.md (mark result as "dry-run"). Do NOT
  update confidence.json, memos.json, action_queue.json, or
  decision_log. Do NOT git commit or push. Delete lock file.
  EXIT.
```

### 3-I: Decision Output

```
[Decide] Selected: {winner} (score: {score})
[Decide] Rationale: {orient_summary}
[Decide] Skill: {config.domains[winner].primary_skill}
[Decide] Chain: {config.domains[winner].chain or "none"}
[Decide] Confidence: {confidence} (threshold: {threshold})
```

### 3-J: Score Verification

After selecting the winner, re-derive its score from raw components as a sanity check:

```
verify = (hours_since_last * weight) + urgent + (goal * goal_weight) + (conf * conf_weight) + memo
```

For implementation domain, use the implementation formula instead (3-A2 components).

If `abs(verify - reported_score) > 0.01`:
  Print: `[WARN] Score mismatch for {winner}: computed {verify}, reported {score}. Using recomputed.`
  Replace the score with the verified value.
  Re-sort all domains and re-select winner if rank changed.

Cross-check: verify winner confidence >= config.safety.confidence_threshold (redundant
check against 3-F to catch any gate bypass).

Record `"score_verified": true` (or `false` if mismatch was found) in the decision_log entry.

---

## Step 4: Act

### 4-A: Skill Validation

```
if config.safety.skill_allowlist is non-empty
   AND selected_skill NOT in allowlist:
  Print "[Act] SAFETY: {skill} not in allowlist. Skipping."
  Log { action: "blocked", reason: "skill_not_in_allowlist" }
  Skip to Step 5.

Re-check HALT file. If appeared: EXIT immediately.
```

### 4-B: Execution Rules

7 rules govern execution:

1. **confidence >= threshold**: execute primary skill, then chain[] sequentially (max 3). Re-check HALT before each chain skill.
2. **confidence < threshold**: primary skill only, skip chain.
3. **HALT during execution**: stop immediately, log partial execution.
4. **Error during execution**: log to skill_gaps.json, continue to Reflect.
5. **Chain failure tracking**: if chain skill failed 3+ times (skill_gaps.json), mark action as "blocked".
6. **Chain depth cap**: max 3 skills. Truncate with warning if more.
7. **Skill timeout**: if a skill runs longer than `config.safety.lock_timeout_minutes` (default 30 min), treat as error. Print `[Act] TIMEOUT: /{skill} exceeded {timeout}m. Treating as error.` Log to skill_gaps.json and continue to Reflect.

Execute by calling the slash command:

```
Print "[Act] /{skill} starting..."
Execute: /{skill}
Print "[Act] /{skill} completed. (elapsed: {time})"

-- Chain execution: evaluate chain_triggers from the skill's contract
-- Production deployments (209 cycles) showed zero chain records in decision_log.
-- Root cause: chains were read from config.domains[winner].chain (legacy, often empty)
-- instead of from the skill contract's chain_triggers with condition evaluation.

chain_executed = []
if confidence >= threshold:
  -- Source 1: skill contract chain_triggers (preferred, condition-based)
  contract = read YAML frontmatter from skills/{skill}/SKILL.md
  if contract.chain_triggers exists and is non-empty:
    for each trigger in contract.chain_triggers (max config.safety.max_chain_depth, default 3):
      -- Evaluate condition against skill output (domain state file just written)
      -- Condition format: "field_name >= value AND other_field == 'string'"
      condition_met = evaluate trigger.condition against domain state JSON
      if condition_met:
        Check HALT. If exists: stop.
        Print "[Act] Chain trigger: {trigger.condition} → /{trigger.target} starting..."
        Execute: /{trigger.target}
        chain_executed.append(trigger.target)
        Print "[Act] Chain: /{trigger.target} completed."
      else:
        Print "[Act] Chain condition not met: {trigger.condition} — skipping /{trigger.target}"

  -- Source 2: legacy config.domains[winner].chain (fallback for old configs)
  else if config.domains[winner].chain exists and is non-empty:
    for each chain_skill in config.domains[winner].chain (max 3):
      Check HALT. If exists: stop.
      Print "[Act] Chain (legacy): /{chain_skill} starting..."
      Execute: /{chain_skill}
      chain_executed.append(chain_skill)
      Print "[Act] Chain: /{chain_skill} completed."

-- Record chain execution in decision_log (MUST be present even if empty)
decision_log_entry.chain_executed = chain_executed
decision_log_entry.chain_count = len(chain_executed)
Print "[Act] Chain summary: {len(chain_executed)} skills executed: {chain_executed or 'none'}"
```

### 4-C: PR Post-Processing

After execution, check if a new PR was created (new open PR matching domain
branch_prefix or skill output indicating PR creation).

If PR created, determine risk tier (distinct from progressive complexity levels):

**Risk Tier 1 -- Auto-merge** (ALL must be true):
- progressive_complexity >= 3
- no protected paths touched
- files <= config.safety.max_files_per_pr
- lines <= config.safety.max_lines_per_pr

Action: `gh pr merge {n} --merge`. If config.deploy_workflow configured, wait
for deploy. If config.health_endpoints configured, run health check. If health
fails: `git revert --no-edit HEAD && git push origin HEAD`, create HALT file,
notify.

**Risk Tier 2 -- Merge, manual deploy** (progressive_complexity >= 3, no
protected paths, but exceeds size limits):
Action: `gh pr merge {n} --merge`. Print: "Deploy manually with /run-deploy."

**Risk Tier 3 -- Human review** (ANY: protected paths touched, complexity
level < 3, implementation PR):
Keep as draft. Print: "PR #{n} requires human review."

### 4-D: Execution Output

```
[Act] /check-tests starting...
  ... (skill output) ...
[Act] /check-tests completed. (elapsed: 1m 42s)
[Act] PR #42 created on branch auto/check-tests/2025-01-15-fix
[Act] Risk Tier 1 (auto-merge eligible)
[Act] PR #42 auto-merged.
```

---

## Step 5: Reflect

### 5-A: Skill Gap Analysis

Check: execution errors (missing capability), chain stopped early (broken
connection), data insufficient (missing collection), no skill matched domain.

```
for each detected gap:
  if gap_name exists in skill_gaps.json: increment frequency, update last_seen
  else: add with frequency=1, first_seen=now
Print "[Reflect] Gaps: {count}. Top: {highest_freq_gap}" or "No new gaps."
```

### 5-B: Auto Skill Proposal

```
for each gap in skill_gaps.json where frequency >= 3:
  if agent/state/evolve/proposed-skills/{gap_name}.md does not exist:
    Generate proposal: background, gap, proposed OODA phase, estimated I/O.
    Print "[Reflect] Skill proposal: {gap_name} (freq: {n})"
```

### 5-C: Memo Writing

Consecutive domain detection (from 2-A patterns):
- Same domain 2 consecutive: all other domains +0.5 adjustment.
- Same domain 3 consecutive: all other domains +1.0 adjustment.

PR outcome memos:
- PR merged this cycle: that domain gets -0.3 (focus elsewhere).
- PR rejected this cycle: that domain gets +0.5 (retry needed).

Store in memos.json.history (cap at 10). Each entry:
`{ timestamp, cycle, domain, type, message }`.

### 5-C2: Action Extraction

If executed skill was NOT implementation's primary_skill:
- Parse output for actionable items. Assign RICE scores:
  `RICE = (Reach * Impact * Confidence) / max(Effort, 0.5) * 100`
  (Effort is floored at 0.5 to prevent division-by-zero or inflated scores. The ×100 normalizes scores to the same scale used by plan-backlog and chain triggers.)
- Dedup: tokenize titles to lowercase keyword sets (strip stop words: "the", "a", "an", "is", "for", "in", "to", "of"). Compute Jaccard similarity against each existing queue item: `|A ∩ B| / |A ∪ B|`. If >= 0.8, treat as duplicate — keep existing item (lower ID wins), skip new extraction.
- Each extracted action MUST include these fields:
  `{ id, title, source_domain, rice_score, effective_rice: rice_score,
     related_files, status: "pending", extracted_at: ISO_8601,
     pr_number: null, decay_applied: 0.0 }`
  Note: `effective_rice` is initialized to equal `rice_score` at extraction time.
  Step 6-C6 (decay) will later adjust it based on age.
- Add to action_queue.json `pending` array. Cap at 20 (remove lowest effective_rice as "superseded").

If implementation skill was executed: skip (it manages its own queue).

Print: `[Reflect] Extracted {N} actions. Queue: {pending_count} pending.`

### 5-E: Adaptive Lens Update

**This step MUST execute on every cycle.** Production deployments showed 209 cycles
with zero lens.json files created. The issue was that lens initialization was
not explicit — the code assumed lens files already existed.

```
for each observe-phase skill that ran this cycle:
  Read the skill's observation output (domain state file)
  domain_name = the domain that was executed

  -- Initialize lens file if it does not exist
  lens_path = agent/state/{domain_name}/lens.json
  if lens_path does not exist:
    mkdir -p agent/state/{domain_name}/
    Write initial lens:
    {
      "schema_version": "1.0.0",
      "domain": "{domain_name}",
      "last_updated": now (ISO 8601),
      "focus_items": [],
      "learned_thresholds": [],
      "discovered_signals": [],
      "evidence": [],
      "deprecated_items": []
    }
    Print "[Reflect] Initialized lens for {domain_name}."

  Read current lens from lens_path
  Read last 3-5 observations from decision_log for this domain

  Analyze for patterns:
  - Endpoints/metrics with high variance -> propose focus_item (confidence 0.3)
  - Thresholds that missed real problems -> propose learned_threshold (confidence 0.3)
  - Thresholds that fired on false positives -> decrease existing threshold confidence by 0.2
  - Cross-domain correlations -> propose discovered_signal (confidence 0.3)

  Confidence updates for EXISTING lens items:
  - Confirming observation:    confidence += 0.1  (cap at 1.0)
  - Disconfirming observation: confidence -= 0.2  (asymmetric: bad learning dies 2x faster)
  - Item drops below 0.1: move to deprecated_items
  - Cap: max 50 items per lens; prune lowest-confidence items if exceeded

  lens.last_updated = now (ISO 8601)
  Write updated lens to lens_path

  -- Record evidence trail (append, cap at 20 entries)
  lens.evidence.append({
    timestamp: now,
    cycle: cycle_count,
    source: "evolve Step 5-E",
    observation: brief summary of what was observed,
    items_added: count of new focus/threshold/signal items,
    confidence_changes: count of items with confidence updates
  })

if cycle_count % config.memory.contrarian_check_interval == 0:
  Compare current observation quality against baseline (first 3 cycles)
  If quality degraded: flag lens for human review in memos
```

Print: `[Reflect] Lens updated for {N} domains.` or "Lens unchanged."

### 5-D: Goal Update

Update goal.last_activity for relevant goals. Update progress if measurable.
If patterns suggest recurring unaddressed area, propose new goal with status
"proposed" (requires human approval).

---

## Step 6: State Update + Commit

### 6-A: state.json

```
cycle_count += 1
# cycle_count is a plain integer with no upper cap. At one cycle per 30 min,
# reaching Number.MAX_SAFE_INTEGER (9e15) takes ~500 billion years.
# No overflow guard needed; if encountered, it is a bug elsewhere.
last_cycle = now (ISO 8601)
cycle_in_progress = false
Append to decision_log: {
  cycle, timestamp, domain, skill, score, confidence,
  result, pr_number, orient_summary, elapsed_seconds,
  score_verified, risk_tier
}
Cap decision_log at config.memory.working_memory_size (default 20).
When cap is reached, remove the oldest entry (index 0) before appending.
```

### 6-B: confidence.json

Persist updated confidence scores from Step 2-B.

### 6-C: memos.json

Persist score_adjustments (2-D cleared consumed ones) and history (cap 10).

### 6-C2: action_queue.json

Persist queue: pending sorted by RICE desc (cap 20), in_progress, completed (keep last 30).

### 6-C3: CHANGELOG.md

Prepend entry:

```
## Cycle #{N} -- {date} -- {domain}
- **Skill**: {skill} {chain}
- **Result**: {success/error/skip}
- **Score**: {score} (confidence: {conf})
- **Orient**: {summary}
- **PR**: #{n} (Risk Tier {tier}) or "none"
```

Cap at 50 entries (remove oldest from bottom).

### 6-C4: Memory Cascade

**This step is MANDATORY on every cycle.** The episode and contrarian logic below
must execute — do not skip even if the cycle was observe-only or no actions were
taken. Production deployments showed 209 cycles with only 1 episode generated
due to this step being skipped; the learning loop depends on it.

**Tier 2 -- Episodes**: Compare current ISO week+year vs the most recent episode's
`week_year` (read from `episodes.json`; treat missing file or empty array as "no
episodes yet").

```
current_week = ISO week+year (e.g., "2026-W15")
last_episode_week = episodes[-1].week_year  OR  null if empty

if current_week != last_episode_week:
  -- Generate weekly summary from decision_log entries since last episode
  -- (or from the oldest decision_log entry if no prior episode exists)

  relevant_entries = decision_log entries where timestamp falls within last_episode_week
                     (if last_episode_week is null, use ALL decision_log entries)

  episode = {
    week_year: last_episode_week OR current_week (the week being summarized),
    cycle_range: [first_cycle_number, last_cycle_number],
    domain_distribution: { backlog: 3, test_coverage: 2, ... },
    outcomes: {
      prs_merged: count,
      prs_rejected: count,
      actions_completed: count,
      actions_extracted: count
    },
    key_decisions: [top 3 decisions by score, with domain and rationale],
    lessons: [
      -- Extract lessons from:
      -- 1. Domains selected 3+ consecutive times (monopoly pattern)
      -- 2. Domains never selected (starvation pattern)
      -- 3. Confidence changes (what caused boost/penalty)
      -- 4. Alert patterns (what triggered, how resolved)
      -- 5. Any memos written during the week
    ],
    confidence_snapshot: { domain: score for each active domain }
  }

  -- Initialize episodes.json if file missing or malformed
  if episodes.json does not exist or is not valid JSON:
    write { "schema_version": "1.0.0", "episodes": [] }

  Append episode to episodes.json.
  Cap at config.memory.episode_retention_weeks (default 52).
  If cap exceeded: evict oldest episode and trigger Tier 2b (principle extraction).

  Print "[Reflect] Episode {week_year} generated: {cycle_count} cycles, {prs_merged} PRs, {lessons_count} lessons."
else:
  Print "[Reflect] Same week ({current_week}) — episode generation deferred."
```

**Tier 2b -- Principle Extraction**: Triggered when:
- Episode cap is exceeded (oldest episode evicted), OR
- 5+ episodes exist (sufficient data for pattern detection), OR
- Contrarian check found a dominant strategy (validation needed)

```
-- Scan ALL episodes for recurring patterns
for each unique lesson text across episodes:
  occurrences = count of episodes containing this lesson (fuzzy match: 80% Jaccard similarity)
  if occurrences >= 3:
    if lesson not already in principles.json:
      Add to principles.json: {
        text: lesson,
        confidence: 0.3,
        source_episodes: [week_year list],
        created_at: now,
        last_confirmed: now
      }
      Print "[Reflect] New principle extracted: '{lesson}' (confidence 0.3, from {occurrences} episodes)"
    else:
      -- Confirming existing principle
      principle.confidence += 0.1 (cap at 1.0)
      principle.last_confirmed = now
      Print "[Reflect] Principle confirmed: '{lesson}' -> confidence {new_confidence}"

-- Initialize principles.json if missing
if principles.json does not exist or malformed:
  write { "schema_version": "1.0.0", "principles": [] }

-- Deprecate weak principles
for each principle in principles.json:
  if not confirmed in last 10 episodes: principle.confidence -= 0.05
  if principle.confidence < 0.1: remove (deprecated)

Cap at 50 principles. Remove lowest-confidence first.
```

**Tier 3 -- Contrarian Check**: This check is MANDATORY when the modulo condition
is met. Do not silently skip it.

```
if cycle_count % config.memory.contrarian_check_interval === 0:
  Print "[Reflect] Contrarian check triggered (cycle {cycle_count})."

  -- Dominant strategy = same domain won >= 5 of last 7 decisions
  last_7 = decision_log[-7:]
  domain_counts = count occurrences of each domain in last_7
  dominant = domain with count >= 5 (if any)

  if dominant found:
    neglected = domain with lowest count in last_7 (excluding disabled domains)
    -- Generate counter-argument: what would happen if neglected were chosen?
    argument = "If {neglected} were chosen instead of {dominant}, it would
                address: {neglected domain's staleness}, {pending actions for neglected},
                {confidence trend for neglected}."
    Store in memos.json: {
      type: "contrarian",
      domain: neglected,
      dominant_domain: dominant,
      argument: argument,
      created_at: now,
      expires_after_cycles: 3,
      applied: false
    }
    Print "[Reflect] Contrarian: {dominant} dominated (5/{last_7_count}). Counter-argument for {neglected} stored."
  else:
    Print "[Reflect] Contrarian: no dominant strategy detected. No memo written."
```

### 6-C5: Metrics Update

```
counters.total_cycles += 1
counters.total_skill_executions += (1 + chain_count)
Update total_prs_created/merged/rejected as applicable.
domain_executions[winner] += 1
Update streaks (current_domain, current_streak, longest_streak).
Set first_cycle_at if null. Set last_updated = now.
```

### 6-C5b: Cost Ledger Entry

**This step MUST execute every cycle.** Production deployments showed 209 cycles
with $0.0 total cost — the entry recording logic was never firing.

```
-- Ensure cost_ledger.json is initialized (Step 0-Pre already handles this,
-- but re-check here in case Step 0 was bypassed or file was deleted)
if cost_ledger.json is missing or corrupt:
  Write: {"schema_version": "1.0.0", "date": "<today>", "entries": [], "total_estimated_usd": 0.0}

-- Estimate cost for this cycle based on skill contract cost_limit_usd
-- Each skill contract declares a cost_limit_usd (e.g., scan-health: $0.02, check-tests: $0.05)
skill_cost = read executed skill contract's cost_limit_usd (default 0.02 if not declared)
chain_cost = sum of chain skill contracts' cost_limit_usd (0 if no chain)
cycle_cost = skill_cost + chain_cost

-- Record entry
cost_ledger.entries.append({
  cycle_id: cycle_count,
  timestamp: now (ISO 8601),
  skill: selected_skill,
  chain: chain_executed,
  estimated_usd: cycle_cost
})
cost_ledger.total_estimated_usd += cycle_cost

-- Check daily limit
if cost_ledger.total_estimated_usd >= config.cost.daily_limit_usd:
  Create HALT file: "Daily cost limit reached: ${total} >= ${limit}. Resets at 00:00 UTC."
  Print "[Reflect] 🛑 Cost limit reached: ${total}. HALT created."
else if cost_ledger.total_estimated_usd >= config.cost.daily_limit_usd * config.cost.warning_threshold_pct / 100:
  Print "[Reflect] ⚠ Cost warning: ${total} (${pct}% of daily limit)."

Print "[Reflect] Cost: +${cycle_cost} this cycle, ${total} today."
```

### 6-C6: Action Queue Decay

Unconditionally run decay on every cycle (not conditionally on item age).
The age check is inside the loop to prevent items from being missed when
they are exactly at the threshold boundary.

```
decay_days = config.memory.action_queue_decay_days       -- default 14
decay_amount = config.memory.action_queue_decay_amount   -- default 0.05

for each pending item in action_queue.pending:
  -- ensure effective_rice is initialized (bug fix: missing in some legacy items)
  if item.effective_rice is undefined or null:
    item.effective_rice = item.rice_score

  age_days = (now - item.extracted_at).total_days()
  if age_days >= decay_days:                              -- ">=" not ">" (threshold fix)
    periods_overdue = floor((age_days - decay_days) / decay_days) + 1
    decay_factor = min(periods_overdue * decay_amount, 1.0)
    new_effective = item.rice_score * (1.0 - decay_factor)

    -- prevent double-decay within same period
    if item.last_decay_at is not null:
      days_since_decay = (now - item.last_decay_at).total_days()
      if days_since_decay < decay_days: continue          -- skip, already decayed this period

    item.effective_rice = new_effective
    item.decay_applied = decay_factor
    item.last_decay_at = now (ISO 8601)
    Print "[Reflect] Decay: '{item.title}' effective_rice {old} -> {new_effective} (factor {decay_factor})"

  if item.effective_rice <= 0: move to completed as "superseded"

Re-sort pending by effective_rice descending.
```

### 6-C7: Notifications

```
for each provider in config.notifications where enabled:
  Build message: "OODA-loop cycle #{N}: {domain} -> {result}"
  Send via provider API (resolve $ENV_VAR references from environment).
  On failure: increment failure counter.
    3 consecutive failures -> auto-disable provider at runtime
    (do NOT modify config.json on disk).
  Notification failure is non-fatal.
```

### 6-D: Git Commit

```bash
git add agent/state/evolve/state.json
git add agent/state/evolve/confidence.json
git add agent/state/evolve/memos.json
git add agent/state/evolve/action_queue.json
git add agent/state/evolve/metrics.json
git add agent/state/evolve/cost_ledger.json
git add agent/state/evolve/skill_gaps.json
git add agent/state/evolve/goals.json
git add agent/state/evolve/CHANGELOG.md
git add agent/state/evolve/episodes.json    # if updated
git add agent/state/evolve/principles.json  # if updated
git add agent/state/deploy.json             # if updated by run-deploy
git add agent/state/*/lens.json             # if updated
git add agent/state/*/lens_changelog.json   # if updated
# NEVER use git add -A or git add .

git commit -m "evolve: cycle #{N} -- {domain} ({result})"
git push origin HEAD
# If git push fails (network error, auth, etc.):
#   Print "[WARN] git push failed: {error}. State committed locally."
#   Print "  Local commit preserved. Will push on next successful cycle."
#   Do NOT revert the local commit. Continue to lock cleanup.
#   Push failure is non-fatal -- state integrity is maintained locally.
```

Delete the lock file: `rm agent/state/evolve/.lock`

Print cycle completion:

```
--- Cycle #{N} Complete ---
Domain: {winner} | Skill: {skill} | Result: {result}
Confidence: {conf} | Elapsed: {total_time}
Next cycle available in {min_interval} minutes.
```

---

## I/O Contract

```yaml
name: evolve
ooda_phase: meta
version: "1.0.0"

input:
  files:
    - config.json
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/goals.json
    - agent/state/evolve/memos.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/cost_ledger.json
    - agent/state/evolve/episodes.json
    - agent/state/evolve/principles.json
    - "config.domains.*.state_file (all domain state files)"
    - "agent/state/external/*.json (if present)"
  apis:
    - "GitHub CLI (gh pr list, gh issue list, gh pr merge, gh pr view)"
    - "Health endpoints (config.health_endpoints)"
    - "Notification APIs (config.notifications)"
  config_keys:
    - domains
    - implementation
    - scoring
    - confidence
    - safety
    - progressive_complexity
    - signals
    - memory
    - test_command
    - health_endpoints
    - deploy_workflow
    - notifications
    - cost

output:
  files:
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/memos.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/cost_ledger.json
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/goals.json
    - agent/state/evolve/CHANGELOG.md
    - agent/state/evolve/episodes.json (weekly)
    - agent/state/evolve/principles.json (rare)
  prs: "Determined by executed skill (evolve itself creates no PRs)"

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: "Inherited from config.cost.daily_limit_usd"
```

---

## Cycle Output Format

```
[HALT check] Clear.
[Observe] Scanned 3 domains. 2 open PRs, 1 merged since last cycle.
[Orient] PR #38 merged -> service_health confidence +0.1
[Orient] Action 'fix-timeout' merged via PR #38.
[Orient] World model: service_health just merged a fix. test_coverage
  hasn't run in 26h. backlog has 3 new issues. Focus: test_coverage.

[Decide] Domain scores:
| # | Domain         | Hours | Weight | Urgent | Goal | Conf | Memo  | SCORE |
|---|----------------|-------|--------|--------|------|------|-------|-------|
| 1 | test_coverage  | 26.3  | 1.0    | +0.0   | 0.15 | 0.14 | +0.0  | 26.59 |
| 2 | backlog        | 12.1  | 0.5    | +0.0   | 0.15 | 0.10 | +0.0  |  6.30 |
| 3 | service_health |  0.5  | 2.0    | +0.0   | 0.09 | 0.18 | -0.3  |  0.97 |

[Decide] Selected: test_coverage (score: 26.59)
[Decide] Skill: /check-tests | Chain: none | Confidence: 0.7

[Act] /check-tests starting...
[Act] /check-tests completed. (elapsed: 1m 42s)

[Reflect] No new gaps. Extracted 2 actions. Queue: 5 pending.
[State] Weekly episode generated for week 12.

--- Cycle #15 Complete ---
Domain: test_coverage | Skill: /check-tests | Result: success
Confidence: 0.7 | Elapsed: 2m 08s
Next cycle available in 30 minutes.
```

---

## Operations Guide

**First run**: Ensure config.json exists (run /ooda-setup if not). Run /evolve.
First cycle is observe-only. Review score table, verify domains. Run /evolve
again for first real execution.

**Loop operation**: `/loop 4h /evolve` runs evolve every 4 hours. The min cycle
interval prevents premature re-runs.

**Emergency stop**: `echo "reason" > agent/safety/HALT`. Remove to resume:
`rm agent/safety/HALT`.

**Decision history**: state.json.decision_log (last 20), CHANGELOG.md (last 50),
episodes.json (weekly summaries).

**Manual adjustments**: Edit memos.json.score_adjustments to influence next
cycle. Example: `{ "test_coverage": 5.0, "service_health": -2.0 }`. Applied
once then auto-cleared.
