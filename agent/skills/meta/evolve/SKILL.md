---
name: evolve
description: OODA Meta-Orchestrator. Observes all domain states, orients by learning from past outcomes, decides the highest-priority action, and executes it. Run with /evolve or /loop 4h /evolve.
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
  episodes.json       -- weekly summaries (tier 2 memory)
  principles.json     -- permanent learnings (tier 3 memory)
  CHANGELOG.md        -- cycle activity log (most recent 50)
```

Domain skills write their own state files. evolve reads but never writes them.

---

## Step 0: Safety Checks

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

The lock file is deleted at the end of Step 6. If evolve crashes, the lock
persists — the next invocation detects it and exits. To recover from a stale
lock, the operator deletes the file manually.

### 0-C: Crash Recovery

```
if state.json.cycle_in_progress == true:
  Print "[WARN] Previous cycle did not complete. Resetting."
  Set cycle_in_progress = false, write state.json.
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

  if not domain_config.enabled: skip
  file = domain_config.state_file
  if file missing:
    mark as "never_run", hours_since_last = config.scoring.hours_if_never_run
  else:
    read JSON. Calculate hours_since_last from data.last_run to now.
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
goals.json, action_queue.json, skill_gaps.json.

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

Store patterns for Steps 2-E and 5-C.

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
  set to config.confidence.initial (default 0.5)
```

If config.implementation.enabled: apply same logic to implementation PRs.

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

Read memos.json.score_adjustments -- one-shot bonuses/penalties keyed by domain.
They will be applied in Step 3-A. After application, DELETE them (set to {}).
They apply exactly once.

### 2-E: Orient Summary

Write 2-3 sentence world model: what changed, what's urgent, what to focus on.
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

### 3-A: Standard Scoring Formula

For each enabled domain (after filtering):

```
score = (hours_since_last * domain.weight)
      + urgent_signal                              -- from 3-B (0 if none)
      + (goal_contribution * config.scoring.goal_weight)   -- from 3-C
      + (confidence * config.scoring.confidence_weight)
      + memo_adjustment                            -- from memos.json, consumed in 2-D
```

Tie-break: prefer domain with fewer total executions (metrics.json.domain_executions).

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
  Try next-highest domain. Repeat until:
    a) domain with confidence >= threshold found -> use it
    b) all below -> use any fallback=true domain
    c) no fallback -> skip Act entirely
  When confidence-gated: primary skill ONLY, skip chain[].
  Print "[Decide] Confidence-gated: primary skill only, no chain."
```

### 3-H: Dry-Run Exit

```
if invoked with --dry-run:
  Print score table + "Would execute: {skill}". Chain if any.
  Skip Steps 4-5. Jump to Step 6 (minimal state update).
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

6 rules govern execution:

1. **confidence >= threshold**: execute primary skill, then chain[] sequentially (max 3). Re-check HALT before each chain skill.
2. **confidence < threshold**: primary skill only, skip chain.
3. **HALT during execution**: stop immediately, log partial execution.
4. **Error during execution**: log to skill_gaps.json, continue to Reflect.
5. **Chain failure tracking**: if chain skill failed 3+ times (skill_gaps.json), mark action as "blocked".
6. **Chain depth cap**: max 3 skills. Truncate with warning if more.

Execute by calling the slash command:

```
Print "[Act] /{skill} starting..."
Execute: /{skill}
Print "[Act] /{skill} completed. (elapsed: {time})"

if chain AND confidence >= threshold:
  for each chain_skill (max 3):
    Check HALT. If exists: stop.
    Print "[Act] Chain: /{chain_skill} starting..."
    Execute: /{chain_skill}
    Print "[Act] Chain: /{chain_skill} completed."
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
  `RICE = (Reach * Impact * Confidence) / Effort`
- Dedup: skip if title keyword overlap > 80% with existing queue items.
- Add to action_queue.json pending. Cap at 20 (remove lowest RICE as "superseded").

If implementation skill was executed: skip (it manages its own queue).

Print: `[Reflect] Extracted {N} actions. Queue: {pending_count} pending.`

### 5-E: Adaptive Lens Update

```
for each observe-phase skill that ran this cycle:
  Read the skill's observation output (domain state file)
  Read current lens: agent/state/{domain}/lens.json
  Read last 3-5 observations from decision_log

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

  Write updated lens to agent/state/{domain}/lens.json
  Append changes to agent/state/{domain}/lens_changelog.json

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
last_cycle = now (ISO 8601)
cycle_in_progress = false
Append to decision_log: {
  cycle, timestamp, domain, skill, score, confidence,
  result, pr_number, orient_summary, elapsed_seconds
}
Cap decision_log at config.memory.working_memory_size (default 20).
```

### 6-B: confidence.json

Persist updated confidence scores from Step 2-B.

### 6-C: memos.json

Persist score_adjustments (2-D cleared consumed ones) and history (cap 10).

### 6-C2: action_queue.json

Persist queue: pending sorted by RICE desc (cap 20), in_progress, completed (keep last 20).

### 6-C3: CHANGELOG.md

Prepend entry:

```
## Cycle #{N} -- {date} -- {domain}
- **Skill**: {skill} {chain}
- **Result**: {success/error/skip}
- **Score**: {score} (confidence: {conf})
- **Orient**: {summary}
- **PR**: #{n} ({level}) or "none"
```

Cap at 50 entries (remove oldest from bottom).

### 6-C4: Memory Cascade

**Tier 2 -- Episodes**: If ISO week changed since last episode, generate weekly
summary (cycles, domains, PRs, goal deltas, learnings). Append to episodes.json.
Cap at config.memory.episode_retention_weeks.

**Tier 3 -- Contrarian Check**: If cycle_count % config.memory.contrarian_check_interval === 0,
identify dominant strategy, generate counter-argument, store in memos with type "contrarian".

### 6-C5: Metrics Update

```
counters.total_cycles += 1
counters.total_skill_executions += (1 + chain_count)
Update total_prs_created/merged/rejected as applicable.
domain_executions[winner] += 1
Update streaks (current_domain, current_streak, longest_streak).
Set first_cycle_at if null. Set last_updated = now.
```

### 6-C6: Action Queue Decay

```
for each pending item older than config.memory.action_queue_decay_days:
  periods_overdue = floor((age_days - decay_days) / decay_days) + 1
  cumulative_decay = periods_overdue * config.memory.action_queue_decay_amount
  item.effective_rice = item.rice_score - (cumulative_decay * item.rice_score)
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
git add agent/state/evolve/skill_gaps.json
git add agent/state/evolve/goals.json
git add agent/state/evolve/CHANGELOG.md
git add agent/state/evolve/episodes.json    # if updated
git add agent/state/evolve/principles.json  # if updated
git add agent/state/*/lens.json             # if updated
git add agent/state/*/lens_changelog.json   # if updated
# NEVER use git add -A or git add .

git commit -m "evolve: cycle #{N} -- {domain} ({result})"
git push origin HEAD
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
