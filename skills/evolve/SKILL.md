---
name: evolve
description: OODA Meta-Orchestrator. Observes all domain states, orients by learning from past outcomes, decides the highest-priority action, and executes it. Run with /evolve or /loop 4h /evolve.
ooda_phase: meta
version: "1.2.0"
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
    - agent/state/evolve/reflections.json
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
    - agent/state/evolve/reflections.json
    - "agent/state/*/lens.json"
    - "agent/state/*/lens_changelog.json"
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
  age_minutes = now - lock_file.started_at
  if age_minutes < config.safety.lock_timeout_minutes:   -- default 30: live lock
    Print "[SKIP] Another evolve cycle is running (lock age {age_minutes}m)."
    EXIT.  -- do NOT delete a live lock
  -- Stale lock: the previous cycle crashed or was killed mid-run.
  Print "[WARN] Stale lock detected (age {age_minutes}m >= {lock_timeout_minutes}m). Removing and recovering."
  Delete lock_file.
  -- Fall through to 0-C, which performs the crash recovery for the cycle
  -- that left this lock behind.
Create lock_file with content: {"pid": current, "started_at": "ISO 8601"}
```

The lock file is deleted at the end of Step 6. **Every early-exit path
(min-cycle-interval skip in 0-D, HALT re-check in 4-A, HALT during execution,
dry-run, min-score skip, confidence gate with no fallback) MUST also delete the
lock file before exiting.** If evolve crashes mid-run, the lock persists and
blocks live invocations only until `lock_timeout_minutes` elapses — then the
next invocation removes it, runs 0-C crash recovery, and proceeds. Unattended
operation therefore self-heals from crashes; manual `rm` is never required
(though always allowed).

### 0-C: Crash Recovery

```
if state.json.cycle_in_progress == true:
  -- The crashed cycle never reached Step 6, so it has NO decision_log entry:
  -- decision_log[-1] is the last COMPLETED cycle, and the crashed one is
  -- cycle_count + 1. Name them correctly in the diagnostics (surfaced by the
  -- v1.3.0 live soak run — the old message blamed the wrong cycle number).
  crashed_cycle = state.cycle_count + 1
  last = state.json.decision_log[-1] (if exists — the last completed cycle)
  Print "[WARN] Cycle #{crashed_cycle} did not complete (crash/kill detected)."
  Print "  Last completed: #{last.cycle} — domain {last.selected_domain}, skill {last.selected_skill}, at {last.timestamp}"
  Print "  Resetting cycle_in_progress. Starting fresh cycle."
  Set cycle_in_progress = false, write state.json.
  Add memo: { type: "crash_recovery", cycle: crashed_cycle, last_completed: last.cycle }
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
    Delete lock_file.   -- 0-B created it; leaking it would block the next
                        -- on-time invocation until the stale timeout
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
    selected_domain: winner_domain, selected_skill: winner_skill,
    score: winner_score, orient_summary, result: "observe_only",
    score_verified: true }
  cycle_count MUST increment to 1 so the next cycle proceeds normally.
```

Set `cycle_in_progress = true` in state.json before proceeding.
Record `cycle_start_time = now`.

---

## Step 1: Observe

### 1-A: Domain State Reading

**Season mode pre-apply (v1.2.0)**: Before iterating domains, check if
`config.season_modes.enabled == true`. If so, resolve the active mode:

```
if config.season_modes.enabled:
  mode_name = config.season_modes.current_mode or "default"
  mode = config.season_modes.modes[mode_name]
  weight_overrides = mode.weight_overrides or {}
  disabled_by_season = set(mode.disabled_domains or [])
  Print "[Observe] Season mode: {mode_name} ({len(weight_overrides)} weight overrides, {len(disabled_by_season)} disabled domains)"
else:
  weight_overrides = {}
  disabled_by_season = set()
```

Apply overrides in-memory only (do NOT mutate config.json on disk). Each
domain's effective weight becomes `weight_overrides.get(domain_name, domain_config.weight)`.

**Active context pre-load (v1.2.0)**: Load stakeholder context blob if
configured, so skills receive it via a standard context var.

```
if config.active_context and config.active_context.path:
  try:
    active_context_blob = read JSON from config.active_context.path
    active_context.path_resolved = config.active_context.path
    -- Check staleness for refresh_skill policy
    if config.active_context.refresh_skill:
      file_age_hours = hours since file mtime
      if file_age_hours >= config.active_context.refresh_interval_hours:
        Schedule a chain-trigger refresh via config.active_context.refresh_skill
        (recorded as a memo, consumed by Step 4-B's chain logic)
  except (file missing or malformed):
    Print "[Observe] active_context not loadable: {error}. Proceeding without context."
    active_context_blob = null
else:
  active_context_blob = null
```

The resolved `active_context_blob` is passed to every invoked skill in Step 4-B
as a context variable (opaque blob; skills interpret domain-specifically).

```
for each domain_name, domain_config in config.domains:
  if domain_name in disabled_by_season:
    log "[{domain}] Disabled by season mode '{mode_name}'. Skipping."
    skip, do not score
  if domain_config.status == "disabled": skip entirely, do not score
  if domain_config.status == "available":
    log "[{domain}] Not yet configured. Skipping."
    skip, do not score
  if domain_config.status == "active": proceed normally
  # Legacy: if no status field, treat as "active" (backward compat)

  # Season mode weight override (v1.2.0): replace the static weight in-memory
  if domain_name in weight_overrides:
    domain_config.weight = weight_overrides[domain_name]

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

  # Lens pre-init (v1.2.0): initialize the lens file here, before reading, so
  # first cycles and domains with custom observe skills (which may not call the
  # Step 5-E init helper) always have a valid lens file on disk. Production
  # deployments observed 152 cycles with zero lens.json files created because
  # the only init path was inside Step 5-E's observe-skill loop.
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
    Print "[Observe] Initialized lens for {domain_name}."

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

If `cost_ledger.json` is MISSING (fresh install / first run), create with initial structure:
`{"schema_version": "1.0.0", "date": "<today YYYY-MM-DD>", "entries": [], "total_estimated_usd": 0.0}`

If it EXISTS but is CORRUPT (unparseable JSON): **fail closed** — back it up to
`cost_ledger.json.corrupt`, create the HALT file ("cost ledger corrupt — today's
spend unknown; refusing to run without cost accounting"), and EXIT (delete the
lock first). Recreating a corrupt ledger as $0.00 would silently erase today's
spend and defeat the daily cap.

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
- **Futile loop**: derive the consecutive-futile count by scanning `decision_log` backwards from the newest entry (no separately persisted counter — the log IS the source of truth, so the count survives restarts): consecutive entries with the same `selected_domain`, result "success", and no actionable output recorded (no actions extracted, no alerts generated, no PR — e.g., plan-backlog returning "no_remote" repeatedly). If >= 3 consecutive futile cycles for the same domain, add a memo penalty of -10.0 to that domain and log `[Orient] Futile loop detected: {domain} produced no output for {N} consecutive cycles. Penalizing.` This prevents the staleness score from endlessly selecting an unproductive domain.
  - **Scope**: penalty applies only to the specific futile domain, not globally.
  - **Lifetime**: written as `score_adjustments[domain] = -10.0` in memos.json. Consumed (deleted) after one application in Step 3-A scoring. Does not persist across multiple cycles.
  - **Recovery**: domain recovers automatically by producing a non-empty observation in any subsequent cycle (the consecutive futile counter resets to 0).

Store patterns for Steps 2-E and 5-C.

### 2-A2: Saturation Circuit Breaker

Track `consecutive_observe_only_cycles` in state.json. A cycle is "observe-only"
if it produced result "success" but: no PRs created, no actions extracted, no
new alerts generated, and no confidence changes occurred.

This check runs in Orient, BEFORE the current cycle has acted — so it evaluates
the **previous completed cycle** (the newest `decision_log` entry and what Step 6
recorded for it), never the in-flight one. If the counter field is missing from
state.json (fresh install, pre-v1.3 state), initialize it to 0 — a missing field
must not silently disable the circuit breaker.

```
-- Evaluate the PREVIOUS completed cycle's actionable output (from its
-- decision_log entry / recorded outcome — current cycle hasn't acted yet)
if state.consecutive_observe_only_cycles is undefined:
  state.consecutive_observe_only_cycles = 0
prev = decision_log[-1]  (if none: skip 2-A2 entirely — nothing to evaluate)
has_output = (prev created a PR OR extracted actions OR generated new alerts
              OR changed confidence)

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

`confidence.json` exists in two shapes in the wild and BOTH must be read
correctly (surfaced by the 2026-06 framework-repo dogfood run, where live state
was nested while fixtures were flat):
- flat (fixtures, early projects): `{ "domain_name": 0.7, ... }`
- nested (live deployments): `{ "domains": { "domain_name": { "score": 0.7,
  "last_updated": ..., "recent_outcomes": [...] } } }`

Read rule: if a top-level `domains` key holds objects, the per-domain value is
`domains[name].score`; otherwise the top-level value itself. Write rule:
preserve the file's existing shape (update `score` in place for nested; the
bare float for flat) — never silently convert a project's state file.

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

### 2-B3: Cross-Domain Cascade Detection

If `config.domain_dependencies` is defined, check for cascade events that
affect multiple domains simultaneously.

```
if config.domain_dependencies exists:
  -- Read cascades.json (create if missing)
  cascades_path = agent/state/evolve/cascades.json
  if cascades_path does not exist:
    write { "schema_version": "1.0.0", "cascades": [] }

  -- Check for new cascade events from executed skill output
  for each domain_dep in config.domain_dependencies:
    source = domain_dep key
    depends_on = domain_dep.depends_on (array of domain names)
    cascade_events = domain_dep.cascade_events (array of event types)

    -- Detect cascade: if source domain's state changed significantly
    if source was executed this cycle AND state changed:
      for each event_type in cascade_events:
        -- Pattern match against domain state changes
        if event_type matches observed change (e.g., entity_rename, schema_change):
          cascade = {
            id: "C-{date}-{seq}",
            event_type: event_type,
            source_domain: source,
            affected_domains: depends_on,
            details: description of what changed,
            status: "pending",
            created_at: now
          }
          cascades.append(cascade)
          Print "[Orient] Cascade detected: {event_type} from {source} → affects {depends_on}"

  -- Apply cascade scoring bonus to affected domains.
  -- One-shot per (cascade, domain): score_adjustments are consumed by 2-D/3-A
  -- the next time that domain is scored, so re-adding the bonus every cycle
  -- while the cascade stays pending would compound +3.0 indefinitely. Track
  -- which domains already received this cascade's bonus.
  for each pending cascade:
    for each affected_domain in cascade.affected_domains:
      if affected_domain in (cascade.bonus_applied_to or []):
        continue  -- already boosted once for this cascade
      memos.score_adjustments[affected_domain] = (memos.score_adjustments[affected_domain] or 0) + 3.0
      cascade.bonus_applied_to = (cascade.bonus_applied_to or []) + [affected_domain]
      Print "[Orient] Cascade bonus: {affected_domain} +3.0 (from {cascade.source_domain} {cascade.event_type})"

    -- Check if all affected domains have run since cascade was created
    all_updated = all(
      domain.last_run > cascade.created_at
      for domain in cascade.affected_domains
    )
    if all_updated:
      cascade.status = "resolved"
      cascade.resolved_at = now
      Print "[Orient] Cascade resolved: {cascade.id}"

  -- Persist: write cascades.json (new cascades, bonus_applied_to, resolutions)
  -- and memos.json (the score_adjustments added above) back to disk. Without
  -- this write, every cascade detected above is silently lost at cycle end.
  Write cascades.json
  Write memos.json
```

### 2-B4: Outcome Back-Annotation (merge & hold, v1.4.0)

The Step 6-C9 Outcome Record scores a cycle from what was knowable AT cycle end
(a freshly-opened PR scores `pr_created` = 0.5). The true value of that PR is
only knowable later — when a human merges it, and when it survives. This step
back-annotates the earlier outcome entry as that information arrives, so the
scorecard reflects *accepted, durable* value rather than mere PR creation.

```
for each PR in merged_prs (from 1-B):
  find the outcomes.json entry where entry.pr_number == PR.number
  if found and entry.result_type in ("pr_created",):
    entry.result_type = "pr_merged"; entry.quality_multiplier = 0.8
    Print "[Orient] Outcome back-annotated: cycle #{entry.cycle_id} PR #{n} merged (0.5 → 0.8)."

for each merged outcome entry older than 48h whose hold has not been resolved:
  -- merge-and-hold check: was the merge commit reverted since?
  reverted = `gh api repos/{owner}/{repo}/commits?since=...` shows a revert of PR.number
             (or git log --grep "Revert" referencing the PR/merge SHA)
  if reverted:
    entry.result_type = "pr_rejected"; entry.quality_multiplier = 0.0
    Print "[Orient] PR #{n} was REVERTED within 48h → outcome downgraded to 0.0."
  else:
    entry.result_type = "pr_merged_held"; entry.quality_multiplier = 1.0
    Print "[Orient] PR #{n} merged and held 48h → confirmed value (1.0)."

for each PR in closed_prs (not merged):
  find the outcomes.json entry where entry.pr_number == PR.number
  if found: entry.result_type = "pr_rejected"; entry.quality_multiplier = 0.0

Write outcomes.json if any entry changed.
```

This is what makes `pr_merged_held` (1.0) and the merge-and-hold rate on the
scorecard real signals rather than aspirational ones. The `score_outcome.py`
reference already maps these result_types; this step is what SETS them over time.

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

Read memos.json. The canonical format (v1.1.0, bumped in v1.2.0) is:
`{"schema_version":"1.1.0", "score_adjustments":{}, "interventions":[], "history":[], "last_memo":null}`

If the file has `schema_version: "1.1.0"` and no `interventions` key, treat
`interventions` as an empty list and leave the file's schema_version at 1.0.0
until the next write (6-C) promotes it to 1.1.0 automatically.
If the file has a `memos` array but no `score_adjustments` key (pre-v1.1.0 legacy),
treat `score_adjustments` as empty `{}` and `history` as the `memos` array.

**Two memo kinds:**

1. **Score adjustments** (one-shot, consumed) — `score_adjustments: { domain: delta }`.
   Applied once in Step 3-A. After application, DELETE them (set to {}). They do
   not persist across cycles. If a key does not match any domain in
   config.domains, log `[WARN] Memo adjustment for unknown domain '{key}' --
   ignored and cleared.` and discard it.

2. **Interventions** (multi-cycle, decremented) — `interventions: [{domain, delta, type, reason, created_at_cycle, expires_after_cycles, applied_count}]`.
   For each entry, apply `delta` to the named domain's score in Step 3-A (same
   place as score_adjustments — their effects sum). After application:
   - `applied_count += 1`
   - `expires_after_cycles -= 1`
   - if `expires_after_cycles <= 0`: remove the intervention.
   Interventions are written by Step 5-C (auto-starvation, monopoly-breaker,
   contrarian) and by external operators. They formalize the "memo-as-active-
   intervention" pattern observed in production (Lynceus cycles 61, 107 used
   manual +1.0/−10.0 score deltas that spanned multiple cycles).

Compute the combined `memo_adjustment[domain]` for Step 3-A as:
```
memo_adjustment[domain] = score_adjustments.get(domain, 0)
                        + sum(iv.delta for iv in interventions if iv.domain == domain)
```
This value flows into the Step 3-A formula as the `memo_adjustment` term.

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

### 2-F: Reflection Recall (Reflexion loop, closes 5-F)

Re-inject recent verbal self-critiques so the loop acts on its own past lessons
instead of relearning them. This is the read side of the Reflexion loop written
in Step 5-F.

```
-- Read agent/state/evolve/reflections.json (skip silently if missing/empty).
-- Select up to config.memory.reflection_recall_count (default 3) reflections,
-- most recent first, preferring those whose `domain` matches a current
-- candidate domain or the dominant recent pattern.
relevant = recent reflections matching candidate domains (cap N)

if relevant is non-empty:
  -- Fold their `lesson` lines into the world model as prior guidance. They
  -- inform the orient_summary (2-E) and break ties in Decide (Step 3): when two
  -- domains score within ~0.5, a matching lesson nudges the choice.
  Print "[Orient] Recalling {len(relevant)} past lesson(s): {lesson_1}; ..."
  for each reflection applied this way:
    set its status = "applied"   -- persisted in Step 6 alongside reflections.json
```

A reflection whose `verdict` was `miss` and whose lesson was applied and then
held (no repeat miss) is the clearest signal the verbal loop is working — surface
it in the Cycle Card LEARN line (Step 7) when no higher-priority delta exists.

---

## Step 3: Decide

### 3-G: Progressive Complexity Filter (apply FIRST)

```
level = config.progressive_complexity.current_level
level_config = config.progressive_complexity.levels[level]

First, exclude non-active domains:
  Remove any domain where status == "disabled" or status == "available"
  Also remove any domain listed in the active season mode's `disabled_domains`
  (Step 1-A removes them from scoring in-memory; re-filter here so a
  season-disabled domain can never re-enter via this filter's own list)
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
  domain_share = metrics.counters.domain_executions[domain] / max(metrics.counters.total_skill_executions, 1)
  -- (metrics.json nests these under `counters` — see Step 6-C7; reading the
  --  flat path silently yields 0/1 and zeroes the balance penalty)
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

**Season mode signal bonuses (v1.2.0)**: If the active season mode defines
`signal_bonuses: { signal_key: value }`, merge those values on top of
`config.signals.*` for this cycle only (in-memory). Example: a "launch" mode
may set `signal_bonuses: { health_alert_bonus: 10.0, queue_pressure_bonus: 1.0 }`
to temporarily amplify health alerts and dampen queue pressure. When the
season flips back to default, the bonuses no longer apply — no disk writes
are needed to revert.

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

Invocation: `/evolve --dry-run` or `/evolve dry-run`

```
if invoked with --dry-run:
  Print score table + "Would execute: {skill}". Chain if any.
  Print chain_triggers conditions and whether they would fire.
  Print confidence snapshot for all domains.
  Print saturation counter: "Observe-only streak: {N} cycles"
  Print "[Dry-run] No changes applied. No state files modified."

  -- TRUE dry-run: do NOT modify ANY state files.
  -- Previous behavior updated metrics.json and CHANGELOG.md which
  -- was not truly "dry". Now: zero writes, zero side effects.
  -- Delete lock file only.
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

After selecting the winner, re-derive its score by re-running the **exact 3-A
pipeline** for that domain — same staleness curve (`config.scoring.staleness_curve`,
logarithmic by default, NOT a hardcoded linear product), and the same terms:

```
verify = staleness(per 3-A curve) + signal_bonuses + (goal * goal_weight)
       + (confidence * confidence_weight) + memo_adjustment + balance_penalty
```

Do not re-derive with a simplified formula: a verify formula that differs from
3-A (e.g. linear staleness when the config says logarithmic, or omitting
balance_penalty) fires a false mismatch every cycle and then *replaces the
correct score with the wrong one*, silently changing the winner.

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

Re-check HALT file. If appeared: delete the lock file, then EXIT immediately.
(A HALT created mid-cycle — e.g. the 2-A2 saturation halt or an operator's
manual `touch` — is caught here; without the lock deletion the next post-HALT
invocation would stay blocked until the stale-lock timeout.)
```

### 4-B: Execution Rules

7 rules govern execution:

1. **confidence >= threshold**: execute primary skill, then chain[] sequentially (max 3). Re-check HALT before each chain skill.
2. **confidence < threshold**: primary skill only, skip chain.
3. **HALT during execution**: stop immediately, log partial execution.
4. **Error during execution**: log to skill_gaps.json, increment
   `state.consecutive_silent_failures` (initialize to 0 if missing), continue to
   Reflect. A successful execution resets the counter to 0. If the counter
   reaches `config.safety.max_silent_failures` (default 3), create the HALT
   file: "{N} consecutive skill executions failed. Unattended operation paused
   for human review. Delete this file to resume." — the current cycle still
   completes Reflect/Step 6 normally (so the failure is recorded and the lock
   is released); the HALT stops the *next* invocation.
5. **Chain failure tracking**: if chain skill failed 3+ times (skill_gaps.json), mark action as "blocked".
6. **Chain depth cap**: max 3 skills. Truncate with warning if more.
7. **Skill timeout**: if a skill runs longer than `config.safety.lock_timeout_minutes` (default 30 min), treat as error. Print `[Act] TIMEOUT: /{skill} exceeded {timeout}m. Treating as error.` Log to skill_gaps.json and continue to Reflect.

Execute by calling the slash command:

```
-- Rotation primitive (v1.2.0): if the winning domain has a rotation list,
-- read the cursor, pass the focus_item as a context var, and schedule the
-- cursor increment for after execution.
rotation_focus_item = null
rotation_cursor_path = null
if config.domains[winner].rotation is a non-empty list:
  rotation_list = config.domains[winner].rotation
  rotation_cursor_path = "agent/state/{winner}/rotation_cursor.json"
  if rotation_cursor_path exists and is valid JSON:
    cursor = (cursor_json.cursor or 0) % len(rotation_list)
  else:
    cursor = 0
  rotation_focus_item = rotation_list[cursor]
  next_cursor = (cursor + 1) % len(rotation_list)
  -- Schedule write (only if not dry-run). For dry-run, print what would happen.
  rotation_cursor_next = next_cursor
  Print "[Act] Rotation: {winner} focus='{rotation_focus_item}' (cursor {cursor} -> {next_cursor})"

-- Active context pass-through (v1.2.0): if active_context_blob is loaded,
-- expose it to the invoked skill via a documented context var. The blob is
-- opaque to evolve; each skill interprets it (e.g., a lawmaker persona for
-- draft-inquiry, a launch config for deploy, etc.).

Print "[Act] /{skill} starting..."
Execute: /{skill}
  context_vars:
    - focus_item: rotation_focus_item        (may be null)
    - active_context: active_context_blob    (may be null)
Print "[Act] /{skill} completed. (elapsed: {time})"

-- After primary skill execution, persist rotation cursor if it was consumed.
if rotation_cursor_path and NOT dry_run:
  Write {"cursor": rotation_cursor_next, "last_updated": now, "focus_item": rotation_focus_item}
  to rotation_cursor_path

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
      -- Evaluate condition against the INVOKED SKILL's own output: the
      -- top-level fields of the state file its contract lists under
      -- output.files (e.g. check-tests → test_coverage.json, run-deploy →
      -- deploy.json) — NOT the winner domain's file. If the condition variable
      -- is not a top-level field there (e.g. dev-cycle's pr_created), read it
      -- from the skill's printed Report variables. A variable found in neither
      -- place ⇒ condition is FALSE (log "[Act] Chain condition undecidable:
      -- {var} not found — treating as false", never guess).
      -- Condition format: "field_name >= value AND other_field == 'string'"
      condition_met = evaluate trigger.condition as above
      if condition_met:
        Check HALT. If exists: stop.
        -- SAFETY GATE — chains get the SAME gates as the 4-A primary skill;
        -- a chain must never be a side door around them:
        if trigger.target not in config.safety.skill_allowlist:
          Print "[Act] SAFETY: chain /{trigger.target} not in allowlist. Skipping."
          continue
        if trigger.target is an implementation/PR-creating skill (e.g. /dev-cycle):
          if progressive_complexity.current_level < 3 OR implementation.enabled == false:
            Print "[Act] SAFETY: chain /{trigger.target} requires Level 3 + implementation.enabled. Skipping."
            continue
          if prs_created_this_cycle >= config.safety.max_prs_per_cycle:
            Print "[Act] SAFETY: max_prs_per_cycle ({max}) reached. Skipping /{trigger.target}."
            continue
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
      Apply the same SAFETY GATE as Source 1 (allowlist; level/implementation
      gate and max_prs_per_cycle for PR-creating skills). Skip on any failure.
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

Track `prs_created_this_cycle` (starts at 0 each cycle; increment per new PR
detected here). This is what enforces `config.safety.max_prs_per_cycle`
(default 1): the 4-B chain gate consults it before invoking another PR-creating
skill, and if a skill somehow opens a PR beyond the limit anyway, classify that
PR as Risk Tier 3 (Draft, human review) regardless of other gates and add a
memo `{type: "safety_violation", message: "max_prs_per_cycle exceeded"}`.

If PR created, determine risk tier (distinct from progressive complexity levels):

> **Auto-merge is opt-in and OFF by default.** It fires ONLY when
> `config.safety.enable_auto_merge == true`. With the default (`false`), EVERY PR
> — including dev-cycle's — is **Risk Tier 3 (human merge)**. That is the "you
> stay in command" default. When enabled, evolve re-checks every gate below
> ITSELF before merging — fetch the facts with
> `gh pr view {n} --json isDraft,additions,deletions,changedFiles,files` and do
> NOT trust dev-cycle's `auto_merge_eligible` marker. Re-check the HALT file
> immediately before any `gh pr merge`.

**Risk Tier 1 — Auto-merge** (auto-merges ONLY if ALL are true):
- `config.safety.enable_auto_merge == true`                  (opt-in; default false)
- `progressive_complexity.current_level >= 3`
- PR is NOT a draft (`isDraft == false`)
- no changed file matches `config.safety.protected_paths`
- the action did NOT skip a protected path — the PR meta has no
  `protected_blocked=true` (a partial change with protected files removed is NOT
  eligible; it may be incomplete/incoherent — #35)
- `changedFiles <= config.safety.auto_merge_max_files`        (default 5)
- `additions + deletions <= config.safety.auto_merge_max_lines` (default 100)
- the PR's tests are green — canonical marker: dev-cycle Step 4 reported
  `test_status == "passed"` this cycle ("skipped"/"failed" are NOT eligible)

Action: re-check HALT → take a pre-action checkpoint (4-C2) → `gh pr merge {n}
--squash` → **post-merge health check** (`config.health_endpoints` if set, else
re-run `config.test_command`). If the health check FAILS → 4-C2 auto-rollback
(`git revert --no-edit HEAD && git push origin HEAD`, create HALT, notify).
Print "[Act] Auto-merged PR #{n} (low-risk, opt-in). Health: {ok|reverted}."

`--squash` is deliberate: it keeps `main` linear so the 4-C2 revert is a simple
`git revert HEAD` (no `-m`). It requires squash-merge to be enabled on the repo
(GitHub's default). If `gh pr merge --squash` errors because squash is disabled,
do NOT fall back to `--merge` (that breaks rollback) — leave the PR ready for a
human merge and log `[Act] Auto-merge skipped: enable squash-merge on the repo.`

**Risk Tier 3 — Human review** (the DEFAULT — everything that is not Tier 1; ANY
of: `enable_auto_merge` is false, protected paths touched OR a protected path was
skipped during the action (`protected_blocked=true`), complexity level < 3, PR is
a draft, tests not green, or the change EXCEEDS the auto_merge size limits — too
large for the low-risk bar): keep as draft. Print: "PR #{n} requires human review."

> There is no separate "auto-merge but oversize" tier — anything past the
> low-risk bar is simply Tier 3 (human review). The old Tier 2 was unreachable
> via dev-cycle and is removed (#34): a PR is either auto-merged (Tier 1) or left
> a Draft you merge (Tier 3).

### 4-C2: Rollback Protocol

When `config.safety.enable_rollback` is true (default false), the engine
maintains checkpoints for post-merge recovery.

**Pre-action checkpoint** (before Step 4-B execution):
```
if config.safety.enable_rollback OR config.safety.enable_auto_merge:
  -- enable_auto_merge FORCES checkpointing: a merge the agent performs by
  -- itself must always have a recorded recovery point, even when the operator
  -- left enable_rollback off. (4-C Tier 1 additionally re-checkpoints
  -- immediately before the merge itself, so the revert target is merge-adjacent.)
  checkpoint = {
    cycle: cycle_count,
    branch: current git branch,
    commit_sha: HEAD commit SHA,
    timestamp: now,
    state_snapshot: {
      confidence: copy of confidence.json,
      action_queue: copy of action_queue.json pending items
    }
  }

  -- Read or create checkpoints.json
  checkpoints_path = agent/state/evolve/checkpoints.json
  if checkpoints_path does not exist:
    write { "schema_version": "1.0.0", "checkpoints": [] }

  checkpoints.append(checkpoint)
  -- Retain last 5 only
  if len(checkpoints) > 5: remove oldest
  Write checkpoints.json
```

**Automatic rollback trigger** (after a Risk Tier 1 auto-merge). Reachable only
when `config.safety.enable_auto_merge` is on (otherwise nothing auto-merges and
this never runs). The pre-action checkpoint above is taken on every action when
`enable_rollback` is on; when `enable_auto_merge` is on, evolve forces a
checkpoint before a Tier-1 merge regardless, so this revert always has a target.
```
if PR was auto-merged AND health check fails:
  Print "[Rollback] Health check failed after auto-merge of PR #{n}."
  -- Revert the squash-merge commit. Auto-merge uses `gh pr merge --squash`, so
  -- HEAD is a normal 1-parent commit and `git revert HEAD` needs no `-m`.
  -- CRITICAL: if auto-merge is ever switched back to `--merge` (a 2-parent
  -- merge commit), this line MUST become `git revert --no-edit -m 1 HEAD`,
  -- otherwise git errors "is a merge but no -m option was given" and the bad
  -- merge stays on the branch (verified: Tier-B+ live run, 2026-06).
  git revert --no-edit HEAD
  git push origin HEAD
  -- If the push FAILS (network, protection rule), the bad merge is still live
  -- on the remote while local has the revert. Do NOT swallow this: create the
  -- HALT regardless (below) and make the failure loud:
  if push failed:
    Print "[Rollback] ⚠ Revert committed locally but push FAILED: {error}"
    Print "[Rollback] Remote still has the bad merge. Push manually: git push origin HEAD"
  -- Restore state from checkpoint
  restore confidence.json from checkpoint.state_snapshot.confidence
  restore action_queue.json pending from checkpoint
  -- Create HALT file — ALWAYS, even if the push failed (especially then)
  Create HALT: "Auto-rollback: PR #{n} merged but health check failed. Reverted to {checkpoint.commit_sha}.{' PUSH FAILED — remote still has the bad merge.' if push failed}"
  Print "[Rollback] Reverted PR #{n}. HALT created. Human review required."
```

**Manual rollback** via `/ooda-config rollback {cycle}` — `ooda-config/SKILL.md`
Step R is the CANONICAL definition (typed confirmation phrase `rollback {cycle}`,
non-destructive `git revert {sha}..HEAD` default on linear history, `--hard`
fallback, HALT on completion). Summary only — do not re-derive behavior from here:
```
1. Find checkpoint by cycle number in checkpoints.json
2. If not found: "No checkpoint for cycle {cycle}" — exit
3. Typed confirm (exact phrase "rollback {cycle}", anything else cancels)
4. git revert --no-edit {checkpoint.commit_sha}..HEAD  (default, non-destructive;
   `git reset --hard` only with the operator's explicit --hard flag)
5. Restore state files from checkpoint snapshot
6. Create HALT; print "Rolled back to cycle {cycle}."
```

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

**This step MUST execute on every cycle.** Production deployments showed 209
cycles with zero skill_gaps detected. The gap detection must be more proactive.

Check for gaps across multiple signal sources:

```
-- Initialize skill_gaps.json if missing
if skill_gaps.json does not exist or is malformed:
  Write: {"schema_version": "1.0.0", "gaps": []}

gaps_detected = []

-- Source 1: execution errors (missing capability, chain failure, timeout)
if Step 4 produced an error:
  gaps_detected.append({
    name: "execution_error_{skill}",
    type: "execution_failure",
    detail: error message
  })

-- Source 2: domain without recent execution (starvation)
for each active domain:
  if domain not executed in last 10 cycles (from decision_log):
    gaps_detected.append({
      name: "domain_starvation_{domain}",
      type: "coverage_gap",
      detail: "Domain not executed in {N} cycles"
    })

-- Source 3: action queue items aging beyond 2x decay_days without progress
for each pending item older than 2 * config.memory.action_queue_decay_days:
  gaps_detected.append({
    name: "stale_action_{item.id}",
    type: "action_aging",
    detail: "Action '{item.title}' pending for {age} days"
  })

-- Source 4: chain trigger conditions met but chain not executed (blocked)
if chain_triggers evaluated but not executed (due to confidence gate or disabled impl):
  gaps_detected.append({
    name: "chain_blocked_{trigger.target}",
    type: "chain_gap",
    detail: "Chain to {trigger.target} blocked: {reason}"
  })

for each detected gap:
  if gap_name exists in skill_gaps.json: increment frequency, update last_seen
  else: add with frequency=1, first_seen=now

Print "[Reflect] Gaps: {len(gaps_detected)}. Top: {highest_freq_gap}" or "No new gaps."
```

### 5-B: Auto Skill Proposal

```
for each gap in skill_gaps.json where frequency >= 3:
  if agent/state/evolve/proposed-skills/{gap_name}.md does not exist:
    Generate proposal: background, gap, proposed OODA phase, estimated I/O.
    Print "[Reflect] Skill proposal: {gap_name} (freq: {n})"
```

### 5-C: Memo Writing

Consecutive domain detection (from 2-A patterns) writes one-shot
`score_adjustments` (consumed next cycle):
- Same domain 2 consecutive: all other domains +0.5 adjustment.
- Same domain 3 consecutive: all other domains +1.0 adjustment.

PR outcome memos (one-shot `score_adjustments`):
- PR merged this cycle: that domain gets -0.3 (focus elsewhere).
- PR rejected this cycle: that domain gets +0.5 (retry needed).

Store in memos.json.history (cap at 10). Each entry:
`{ timestamp, cycle, domain, type, message }`.

**Auto-starvation intervention (v1.2.0)**:
Formalizes the Lynceus +1.0 starvation pattern so it no longer requires
manual memo editing.

```
for each active domain D in config.domains where D.status == "active":
  executions_in_last_10 = count of decision_log entries where
                          entry.selected_domain == D
                          AND cycle > (cycle_count - 10)   -- strictly: the last
                          -- 10 completed cycles [cycle_count-9 .. cycle_count];
                          -- ">=" would make it an 11-cycle window
  if executions_in_last_10 == 0:
    -- Skip if an active starvation intervention for this domain already exists
    if interventions contains iv where iv.domain == D AND iv.type == "starvation":
      continue
    interventions.append({
      domain: D,
      delta: +1.0,
      type: "starvation",
      reason: "No executions in last 10 cycles",
      created_at_cycle: cycle_count,
      expires_after_cycles: 3,
      applied_count: 0
    })
    Print "[Reflect] Starvation intervention: {D} boosted +1.0 for 3 cycles."
```

**Auto monopoly-breaker intervention (v1.2.0)**:
Formalizes the Lynceus −10.0 monopoly-breaker pattern and complements the
existing 5-C "consecutive domain" one-shot adjustments above. Where the
one-shots nudge *other* domains up, the monopoly-breaker pushes the
dominant domain *down* directly so the next cycle has no pull toward it.

```
consecutive = same-domain run length from 2-A pattern analysis
active_domain_count = count of config.domains where status in ("active","degraded")
-- Single-domain guard: with only one scoreable domain there is nothing to
-- rotate TO, so penalizing the sole domain -10.0 would just starve the cycle
-- (no winner -> wasted cycle). Skip the monopoly-breaker entirely. (The 2-A
-- futile-loop penalty still guards an *unproductive* single domain, since it
-- only fires when the domain produces no output.)
if consecutive >= 2 AND active_domain_count >= 2:
  dominant = decision_log[-1].selected_domain
  -- Skip if an active monopoly_breaker for this domain already exists
  if interventions contains iv where iv.domain == dominant AND iv.type == "monopoly_breaker":
    continue
  interventions.append({
    domain: dominant,
    delta: -10.0,
    type: "monopoly_breaker",
    reason: "Selected {consecutive} consecutive cycles",
    created_at_cycle: cycle_count,
    expires_after_cycles: 1,
    applied_count: 0
  })
  Print "[Reflect] Monopoly-breaker intervention: {dominant} penalized -10.0 for 1 cycle."
```

**Contrarian interventions (v1.2.0)**: When Tier 3 contrarian check (below)
writes a score adjustment, it can optionally emit an intervention with
`type: "contrarian"` instead of a one-shot `score_adjustments` entry, if the
operator wants the adjustment to persist beyond one cycle. The default
contrarian path continues to use one-shot adjustments for backward compatibility.

### 5-C2: Action Extraction

If executed skill was NOT implementation's primary_skill:
- Parse output for actionable items. Assign RICE scores:

  **Base RICE formula:**
  `base_RICE = (Reach * Impact * Confidence) / max(Effort, 0.5) * 100`
  (Effort is floored at 0.5 to prevent division-by-zero or inflated scores. The ×100 normalizes scores to the same scale used by plan-backlog and chain triggers.)

  **Extended RICE dimensions** (optional, project-specific):
  If `config.scoring.rice_extensions` is defined, apply extension multiplier:
  ```
  extension_bonus = sum(extension.score * extension.weight for each rice_extension)
  RICE = base_RICE * (1 + extension_bonus)
  ```
  Extensions are defined in config.json:
  ```json
  "rice_extensions": {
    "timing": { "weight": 0.3 },
    "novelty": { "weight": 0.2 }
  }
  ```
  Each skill provides extension scores in its output (e.g., `timing: 0.8, novelty: 0.5`).
  If no extensions defined or no extension scores in output, `RICE = base_RICE`.

- Dedup: tokenize titles to lowercase keyword sets (strip stop words: "the", "a", "an", "is", "for", "in", "to", "of"). Compute Jaccard similarity against each existing queue item: `|A ∩ B| / |A ∪ B|`. If >= 0.8, treat as duplicate — keep existing item (lower ID wins), skip new extraction.
- Each extracted action MUST include these fields:
  `{ id, title, source_domain, rice_score, effective_rice: rice_score,
     related_files, status: "pending", extracted_at: ISO_8601,
     pr_number: null, decay_applied: 0.0, risk_tier: null }`
  Note: `effective_rice` is initialized to equal `rice_score` at extraction time.
  Step 6-C6 (decay) will later adjust it based on age.
  `risk_tier` is set by matching related_files against `config.safety.risk_rules` patterns
  (if defined). Null means no risk classification assigned.
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

  -- Append a human-readable changelog entry for EACH concrete change this
  -- cycle, so the Cycle Card (Step 7) and `/ooda-status --share` have a real,
  -- auditable source for the LEARN line. This file MUST exist whenever a lens
  -- item is added, promoted, decayed, or deprecated — never leave it phantom.
  -- Path: agent/state/{domain_name}/lens_changelog.json
  --   { "schema_version": "1.0.0", "domain": "{domain_name}", "entries": [] }
  -- For each change, append (cap entries at 50, drop oldest):
  for each lens item added / promoted / decayed / deprecated this cycle:
    lens_changelog.entries.append({
      cycle: cycle_count,
      timestamp: now (ISO 8601),
      domain: domain_name,
      item: the focus_item / threshold / signal label,
      change_type: "added" | "promoted" | "decayed" | "deprecated",
      before: prior confidence or threshold value (null if newly added),
      after: new confidence or threshold value,
      delta: after - before (e.g. +0.1 confirm, -0.2 disconfirm),
      reason: one short phrase (e.g. "3 confirmations", "false positive")
    })
  if no lens item changed this cycle: do not write (leave file as-is).
  Write updated lens_changelog to its path.

if cycle_count % config.memory.contrarian_check_interval == 0:
  Compare current observation quality against baseline (first 3 cycles)
  If quality degraded: flag lens for human review in memos
```

Print: `[Reflect] Lens updated for {N} domains.` or "Lens unchanged."

### 5-D: Goal Update

Update goal.last_activity for relevant goals. Update progress if measurable.
If patterns suggest recurring unaddressed area, propose new goal with status
"proposed" (requires human approval).

### 5-F: Verbal Self-Critique (Reflexion loop)

A short, honest natural-language critique of THIS cycle's decision — the
[Reflexion](https://arxiv.org/abs/2303.11366) / Self-Refine mechanism. This is
verbal self-correction stored in language and re-injected next cycle (Step 2-F),
NOT weight updates or training. It is the honest mechanism behind the claim that
the loop "learns from its own cycles."

Skip this step on `--dry-run` and on observe-only cycles that made no decision.

```
-- Compare the outcome to what Orient expected this cycle.
expectation = decision_log[-1].orient_summary   -- what we predicted/intended
outcome     = decision_log[-1].result + any PR merge/reject + lens/conf deltas

Generate (≤ 3 short sentences total):
  - decided: what was chosen and the one-line why.
  - verdict: did the outcome match expectation? one of {hit, miss, too_early, unclear}.
  - lesson: a single concrete guidance for next time, ≤ 20 words, imperative
            (e.g. "When backlog returns no_remote 2× running, skip it for 3 cycles.").

-- Persist to agent/state/evolve/reflections.json (create if missing):
--   { "schema_version": "1.0.0", "reflections": [] }
reflections.reflections.append({
  cycle: cycle_count,
  timestamp: now (ISO 8601),
  domain: selected_domain,
  skill: selected_skill,
  result: decision_log[-1].result,
  verdict: <hit|miss|too_early|unclear>,
  critique: <decided + verdict sentences>,
  lesson: <the lesson>,
  status: "open"           -- becomes "applied" when 2-F re-injects it
})
-- Cap at config.memory.reflections_buffer_size (default 20); drop oldest.
Write reflections.json.
Print "[Reflect] Self-critique recorded ({verdict}): {lesson}"
```

Honesty rule: this is verbal self-reflection (text the model re-reads), not
learned parameters. Frame it that way in any user-facing surface.

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
  cycle, timestamp, selected_domain, selected_skill, score, confidence,
  result, pr_number, orient_summary, elapsed_seconds,
  score_verified, risk_tier
}
-- CANONICAL field names are `selected_domain` / `selected_skill` (every reader
-- — 2-A patterns, 5-C starvation/monopoly, fixtures, live state — queries
-- those). Never write bare `domain`/`skill` keys here.
Cap decision_log at config.memory.working_memory_size (default 20).
When cap is reached, remove the oldest entry (index 0) before appending.
```

### 6-B: confidence.json

Persist updated confidence scores from Step 2-B.

### 6-C: memos.json

Persist:
- `score_adjustments` (2-D cleared consumed ones, so this is `{}` unless 5-C
  wrote new one-shots this cycle).
- `interventions` — after Step 3-A applied each entry's delta, decrement its
  `expires_after_cycles` and remove entries where it reached 0. New entries
  from Step 5-C are appended.
- `history` (cap 10).
- `schema_version: "1.1.0"` — if the file previously had 1.0.0 and did not
  carry `interventions`, write it as 1.1.0 with `interventions: []` on this
  first v1.2.0 commit.

### 6-C2: action_queue.json

Persist queue: pending sorted by `effective_rice` desc — falling back to
`rice_score` for legacy items that predate the field, initializing the missing
field BEFORE sorting (the 6-C6 guard runs later in the step order, so sorting
must not assume it already ran; a legacy item otherwise crashes the sort —
surfaced by the 2026-06 dogfood run). Cap 20; in_progress; completed (keep last 30).

### 6-C3: CHANGELOG.md

Prepend entry using this **mandatory schema** (do not abbreviate or compress
over time — consistent format enables automated parsing and trend detection):

```
## Cycle #{N} -- {YYYY-MM-DD HH:MM UTC} -- {domain}
- **Skill**: {skill}
- **Chain**: {chain_executed or "none"}
- **Result**: {success/error/skip/observe_only/dry-run}
- **Score**: {score} (staleness: {staleness_term}, alert: {dampened_alert}, balance: {balance_penalty})
- **Confidence**: {conf} (trend: {↑↓→}, micro-adj: {delta or "none"})
- **Orient**: {summary — 1-2 sentences explaining WHY this domain was selected}
- **PR**: #{n} (Risk Tier {tier}) or "none"
- **Elapsed**: {seconds}s
- **Saturation**: {consecutive_observe_only_cycles} observe-only cycles
- **Cost**: +${cycle_cost} (total today: ${daily_total})
- **Season**: {current_mode or "default" if season_modes.enabled, else "disabled"}
- **Focus**: {rotation_focus_item or "none"}  (v1.2.0: present when domain has a rotation list)
```

Cap at 50 entries (remove oldest from bottom).

Every field is REQUIRED. This prevents the format drift observed in production
where later cycles had progressively less detail. The Orient field must contain
the reasoning, not just the domain name.

### 6-C4: Memory Cascade

**This step is MANDATORY on every cycle.** The episode and contrarian logic below
must execute — do not skip even if the cycle was observe-only or no actions were
taken. Production deployments showed 209 cycles with only 1 episode generated
due to this step being skipped; the learning loop depends on it.

**Tier 2 -- Episodes**: Compare the current ISO week+year vs the week of the most
recent episode (treat missing file or empty array as "no episodes yet").

```
current_week = ISO week+year (e.g., "2026-W15")
-- The episode id encodes its week: "EP-2026-W15". Parse the week from
-- episodes[-1].id; accept a legacy `week_year` field for pre-v1.3 entries.
-- NEVER compare against a field the entries don't have — that reads null,
-- "current != null" is always true, and a new episode gets generated EVERY
-- cycle after the first week boundary.
last_episode_week = week parsed from episodes[-1].id  OR  episodes[-1].week_year
                    OR null if empty

summarized_week = the most recently COMPLETED ISO week (current_week - 1)
already_summarized = (last_episode_week == summarized_week)
                     OR an episode with id "EP-{summarized_week}" exists

if already_summarized OR decision_log has no entries in summarized_week:
  Print "[Reflect] Episode for {summarized_week} already exists or no data — deferred."
else:
  relevant_entries = decision_log entries whose timestamp falls in summarized_week

  episode = {                       -- CANONICAL schema (= tests/ fixtures)
    id: "EP-{summarized_week}",     -- e.g. "EP-2026-W15"
    week_start: ISO date, week_end: ISO date,
    cycle_range: [first_cycle_number, last_cycle_number],
    total_cycles: count,
    summary: one-line week summary,
    domains_selected: { backlog: 3, test_coverage: 2, ... },
    prs_created: count, prs_merged: count, prs_rejected: count,
    key_decisions: [top 3 decisions by score, with domain and rationale],
    lessons: [
      -- Extract lessons from:
      -- 1. Domains selected 3+ consecutive times (monopoly pattern)
      -- 2. Domains never selected (starvation pattern)
      -- 3. Confidence changes (what caused boost/penalty)
      -- 4. Alert patterns (what triggered, how resolved)
      -- 5. Any memos written during the week
    ],
    confidence_snapshot: { domain: score for each active domain },
    skill_gaps_found: count, contrarian_checks: count,
    patterns_detected: [strings], created_at: now
  }

  -- Initialize episodes.json if file missing or malformed
  if episodes.json does not exist or is not valid JSON:
    write { "schema_version": "1.0.0", "episodes": [] }

  Append episode to episodes.json.
  Cap at config.memory.episode_retention_weeks (default 52).
  If cap exceeded: evict oldest episode and trigger Tier 2b (principle extraction).

  Print "[Reflect] Episode {episode.id} generated: {total_cycles} cycles, {prs_merged} PRs, {lessons count} lessons."
```

**Tier 2b -- Principle Extraction**: Triggered when any of:
- Episode cap is exceeded (oldest episode evicted), OR
- 2+ episodes exist and fuzzy pattern match fires (see below — was 5+ in v1.1.0), OR
- Contrarian check found a dominant strategy (validation needed), OR
- Cluster fallback (v1.2.0): total lesson count across all episodes >= 10

v1.2.0 note: The pre-v1.2.0 thresholds (80% Jaccard, occurrences >= 3) were
too strict for short lesson strings — in production, Lynceus ran 119 cycles
with 2 valid episodes and extracted 0 principles because lessons rarely
share 80% of their tokens. Defaults are now 0.5 Jaccard and 2 occurrences,
with both knobs exposed as config.

Initialize principles.json if missing:
```
if principles.json does not exist or malformed:
  write { "schema_version": "1.0.0", "principles": [] }
```

```
-- Tunable thresholds (v1.2.0)
similarity_threshold = config.memory.principle_similarity_threshold  -- default 0.5
min_occurrences      = config.memory.principle_min_occurrences       -- default 2

-- Primary extraction: Jaccard-similarity clustering
for each unique lesson text across episodes:
  occurrences = count of episodes containing this lesson
                (fuzzy match: Jaccard similarity >= similarity_threshold
                 on lowercase token sets, stop-word stripped)
  if occurrences >= min_occurrences:
    if lesson not already in principles.json (Jaccard >= similarity_threshold
                                              against any existing principle.text):
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

-- Cluster fallback (v1.2.0): for projects whose lessons are too lexically
-- diverse for Jaccard matching (short strings, multilingual, renamed concepts).
-- Fires when the lesson corpus is big enough but primary extraction produced
-- no new principle this cycle.
total_lessons = sum(len(ep.lessons) for ep in episodes)
if total_lessons >= 10 AND no new principles were extracted above:
  -- Cluster by the first 3 significant tokens (lowercase, stop-word stripped)
  -- Take the top-3 clusters by size, emit one representative each
  -- Mark them as low-confidence "candidate" principles for human review
  clusters = group_lessons_by_first_3_tokens(all_lessons)
  for cluster in top_3(clusters by cluster.size):
    representative = cluster.most_frequent_lesson
    if representative not already a principle:
      Add to principles.json: {
        text: representative,
        confidence: 0.15,
        source_episodes: cluster.source_week_years,
        created_at: now,
        last_confirmed: now,
        kind: "candidate",
        cluster_size: cluster.size
      }
      Print "[Reflect] Candidate principle (cluster fallback): '{representative}' (confidence 0.15, {cluster.size} lessons)"

-- Deprecate weak principles
for each principle in principles.json:
  if not confirmed in last 10 episodes: principle.confidence -= 0.05
  if principle.confidence < 0.1: remove (deprecated)

Cap at 50 principles. Remove lowest-confidence first.
```

**Manual principle seeding**: Operators may add principles directly by
editing `agent/state/evolve/principles.json` with entries of the form
`{text, confidence: 0.5, kind: "manual", created_at, last_confirmed}`.
The engine treats manual principles identically to extracted ones
(subject to the same deprecation rule). Useful for seeding hard-won
domain knowledge that has not yet accumulated enough episodes to trigger
automatic extraction.

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
    -- Store as a STANDARD intervention (the shape 2-D/3-A actually consume —
    -- an ad-hoc object with no delta would never affect scoring):
    interventions.append({
      domain: neglected,
      delta: +1.0,
      type: "contrarian",
      reason: argument,
      dominant_domain: dominant,
      created_at_cycle: cycle_count,
      expires_after_cycles: 3,
      applied_count: 0
    })
    Write memos.json
    Print "[Reflect] Contrarian: {dominant} dominated (5/{last_7_count}). {neglected} boosted +1.0 for 3 cycles."
  else:
    Print "[Reflect] Contrarian: no dominant strategy detected. No memo written."
```

### 6-C5: Metrics Update

```
counters.total_cycles += 1
counters.total_skill_executions += (1 + chain_count)
Update counters.total_prs_created/merged/rejected as applicable.
counters.domain_executions[winner] += 1
-- everything lives under metrics.json `counters` — the 3-A balance penalty
-- reads metrics.counters.domain_executions / metrics.counters.total_skill_executions
-- Loop-effectiveness counters (v1.4.0) — feed the scorecard (scripts/loop_scorecard.py):
counters.total_futile_cycles += (1 if this cycle had_output == false else 0)
counters.actions_added += (count of NEW action_queue items extracted this cycle, Step 5-C2)
counters.actions_resolved += (count of items that moved to completed with a merged PR this cycle)
Update streaks (current_domain, current_streak, longest_streak).
Set first_cycle_at if null. Set last_updated = now.
```

### 6-C5b: Cost Ledger Entry

**This step MUST execute every cycle.** Production deployments showed 209 cycles
with $0.0 total cost — the entry recording logic was never firing.

```
-- Ensure cost_ledger.json is initialized (Step 0-Pre already handles this,
-- but re-check here in case Step 0 was bypassed or file was deleted)
if cost_ledger.json is missing:
  Write: {"schema_version": "1.0.0", "date": "<today>", "entries": [], "total_estimated_usd": 0.0}
if cost_ledger.json is corrupt (unparseable):
  fail closed — same as Step 0-Pre: back up to .corrupt, create HALT, delete lock, EXIT
  (never recreate a corrupt ledger as $0.00 mid-day; that erases today's spend)

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

-- Action lifecycle hygiene (sweep, every cycle) — prevents items orphaned by
-- a crash or a blocked dev-cycle from silently jamming the queue forever:
for each item with status == "in_progress":
  if item was already in_progress when THIS cycle started
     AND no open PR references item.id:
    item.status = "pending"            -- the run that claimed it died mid-way
    Add memo { type: "action_requeued", id: item.id, reason: "orphaned in_progress" }
    Print "[Reflect] Re-queued orphaned action '{item.title}'."
for each item with status == "blocked":
  move it to completed[] keeping status "blocked"   -- pending[] is for workable
                                                    -- items only; blocked needs a human
  Print "[Reflect] Blocked action '{item.title}' moved to completed (human review)."
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

### 6-C8: Cost Ledger Integrity Gate (v1.2.0)

**This gate MUST run before 6-D Git Commit.** Production deployments showed a
13-day stretch where cost_ledger.json received no new entries while cycles
continued to complete — the optional Step 6-C5b write was being silently skipped.
The integrity gate ensures the ledger is always in sync with state.cycle_count.

```
-- Load cost_ledger.json. Detect SEQUENCE gaps, not just a missing last entry:
-- Step 6-C5b appends the current cycle's entry, which would mask an earlier
-- hole if we only compared last_entry.cycle_id to cycle_count. So scan the whole
-- recorded range and backfill every missing cycle_id up to state.cycle_count.
recorded = sorted(set(e.cycle_id for e in cost_ledger.entries if e.cycle_id is an int))
expected = state.cycle_count
MAX_BACKFILL = config.cost.max_backfill_cycles (default 100)

if recorded is empty:
  missing = [expected]                                   -- nothing recorded yet
else:
  lo = recorded[0]
  missing = [c for c in range(lo, expected + 1) if c not in recorded]

if missing is non-empty:
  truncated = len(missing) > MAX_BACKFILL
  if truncated:
    missing = missing[-MAX_BACKFILL:]                    -- keep the most recent; never write thousands

  Print "[Reflect] ⚠ cost_ledger gap: missing entr(ies) for cycle(s) {missing[0]}..{missing[-1]} ({len(missing)}). Backfilling."

  for c in missing:
    is_current = (c == expected)
    cost_ledger.entries.append({
      cycle_id: c,
      timestamp: now (ISO 8601),
      skill: (selected_skill or "unknown") if is_current else "unknown",
      chain: (chain_executed or []) if is_current else [],
      estimated_usd: 0.02,                                -- safe minimum
      synthetic: true,
      reason: "6-C8 gap backfill: cycle had no 6-C5b write"
    })
    cost_ledger.total_estimated_usd += 0.02
  Re-sort cost_ledger.entries by cycle_id ascending.

  -- Emit ONE skill_gaps signal summarizing the whole gap span (not one per cycle)
  skill_gaps.gaps.append({
    id: "gap-cost-ledger-autopatch-{expected}",
    description: "cost_ledger missing {len(missing)} entr(y/ies) in range {missing[0]}..{missing[-1]} — backfilled with synthetic entries" + (truncated ? "; older cycles beyond max_backfill_cycles were not backfilled" : ""),
    detected_at: now,
    detected_in_cycle: expected,
    ooda_phase: "meta",
    frequency: len(missing),
    last_seen_cycle: expected,
    related_domain: null,
    proposed_skill: null,
    resolved: false,
    resolution: null,
    type: "learning_loop_break"
  })

  Print "[Reflect] Cost ledger gate: backfilled {len(missing)} cycle(s) {missing[0]}..{missing[-1]} (total ${cost_ledger.total_estimated_usd})."
else:
  -- Ledger in sync with state.cycle_count. No action.

-- Cap skill_gaps.gaps at 50 entries whenever the file is written (here or from
-- 4-B error logging): evict resolved==true entries oldest-first, then unresolved
-- oldest-first. Unbounded growth over hundreds of unattended cycles bloats every
-- read of the file.
```

Rationale: fails loud, not silent, and now *self-heals multi-cycle drift*. If
Step 6-C5b silently skips for several cycles (the 13-day production drop), 6-C8
detects every hole in the recorded sequence and backfills it, emitting one
`learning_loop_break` skill_gap (visible in `/ooda-status`) so the root cause is
still investigated. The `max_backfill_cycles` cap prevents a corrupt counter
from writing an unbounded number of synthetic entries.

> **Interaction with the Step 1-A daily reset.** The reset clears the ledger when
> `cost_ledger.date` differs from today (UTC). 6-C8 backfills only *within the
> current day's* recorded range — it does not (and should not) resurrect entries
> the daily reset intentionally cleared. Its job is to stop the bleed going
> forward, not to reconstruct prior days.

### 6-C9: Outcome Record (v1.4.0 — "did this cycle help?")

**This step MUST run every cycle.** It is the atomic ground-truth signal that
lets the loop distinguish *"we ran 100 cycles"* from *"we improved the project
100 times"* — the missing primitive that loop-engineering measurement depends on.
It is fully **deterministic** (no model call): it scores the cycle from facts
already recorded this cycle. The richer separate-model verdict is layered on top
in Step 7-B (opt-in), never replacing this.

Compute `quality_multiplier` (0.0–1.0) from the cycle's actual `result_type`:

| result_type | quality_multiplier | meaning |
|---|---|---|
| `pr_merged_held` | 1.0 | a prior cycle's PR merged and survived (no revert) — confirmed value |
| `pr_merged` | 0.8 | PR merged this cycle (hold not yet confirmed) |
| `pr_created` | 0.5 | PR opened, awaiting human merge |
| `action_extracted` | 0.2 | no PR, but the cycle produced actionable output (queue grew with real work) |
| `observe` | 0.1 | first-cycle / confidence-gated observe-only that still recorded state |
| `futile` | 0.0 | `had_output == false` — ran, changed nothing |
| `error` | 0.0 | skill errored |
| `pr_rejected` | 0.0 | a prior cycle's PR was closed unmerged — negative outcome |

```
-- Append to agent/state/evolve/outcomes.json (create if missing:
--   { "schema_version": "1.0.0", "entries": [] }):
outcomes.entries.append({
  cycle_id: cycle_count,
  timestamp: now (ISO 8601),
  domain: selected_domain,
  skill: selected_skill,
  declared_goal: (active goals.json goal id this cycle advanced)
                 OR (action_queue item id acted on) OR null,
  result_type: <one of the table above>,
  quality_multiplier: <from the table>,
  pr_number: pr_number or null,
  verifier_verdict: null   -- filled by Step 7-B if eval.enabled
})
-- Cap entries at config.memory.outcomes_buffer_size (default 200); drop oldest.
Write outcomes.json.
Print "[Reflect] Outcome: {result_type} (quality {quality_multiplier})."
```

Also append ONE machine-readable line to `agent/state/evolve/cycle_log.jsonl`
(append-only; never rewritten — this is the queryable substrate for every trend
metric, complementing the human-readable CHANGELOG.md):
```
{cycle_id, timestamp, domain, skill, score, confidence, result, result_type,
 quality_multiplier, pr_number, had_output, cost_usd, saturation}
```
The JSONL file has no cap (one short line per cycle; at 1 cycle/30min that is
~17k lines/year). If it must be bounded, an operator rotates it; the engine
never truncates it (truncating would corrupt trend history).

### 6-D: Git Commit

Guard first — verify the state path is actually trackable:
```bash
if git check-ignore -q agent/state/evolve/state.json; then
  echo "[WARN] agent/state/ is gitignored — state commits are NO-OPs."
  echo "[WARN] The decision history is NOT being versioned. Remove 'agent/state/'"
  echo "[WARN] from .gitignore (keep only *.lock + HALT ignored) to fix. See ooda-setup."
  # skip the adds/commit below — do not stage into the void silently
fi
```

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
git add agent/state/evolve/reflections.json # if updated
git add agent/state/evolve/outcomes.json    # v1.4.0 outcome record (every cycle)
git add agent/state/evolve/cycle_log.jsonl  # v1.4.0 machine-readable cycle log
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

## Step 7: Cycle Card (shareable summary)

After the cycle completes, render a single screenshottable **Cycle Card** — the
one artifact a user can paste into X / Reddit / Slack to show what the agent did
and, crucially, what it **learned** this cycle. No competitor that lacks an
Orient phase (cron loops, round-robin bash agents, config packs) can produce the
LEARN line. This renders at the end of every full `/evolve` cycle — but **not** in
`--dry-run`, which exits at Step 3-H before Act/Reflect — unless
`config.output.cycle_card` is `false`. It is re-rendered on demand by
`/ooda-status --share`.

Every field comes from data already produced this cycle — no new computation:

| Line | Source |
|------|--------|
| header | `state.cycle_count`, `config.project.name`, `decision_log[-1].timestamp` |
| OBSERVE | observation (Step 1-D): domains scanned + the single most notable change |
| ORIENT | `decision_log[-1].orient_summary` (Step 2-E), truncated to ~70 chars |
| DECIDE | winner domain, score (Step 3-D), confidence + gate result (Step 3-F) |
| ACT | result + `pr_number` + `risk_tier` (Step 4-D); `observe-only` / `skip` if no action |
| LEARN | the single highest-signal Orient delta this cycle (see priority below) |
| COST | `cycle_cost`, daily total, `config.cost.daily_limit_usd` (Step 6-C5b) |
| footer | HALT state, `progressive_complexity.current_level` + its human label |

**The LEARN line is the differentiator.** Pick the highest-signal change in this
priority order and render exactly one (or two — see below):

1. **A confidence change driven by a HUMAN decision** (PR merged/rejected this
   cycle, Step 2-B) — the most shareable moment:
   `You rejected PR #28 → service_health confidence 0.74→0.54 ↓ (reject −0.2, 2× faster than a merge's +0.1)`
2. **A lens change** from Step 5-E (a `learned_threshold` / `focus_item` /
   `discovered_signal` added, promoted, or decayed):
   `lens re-aimed → flaky-alert threshold 0.30→0.25 after 3 confirmations (+0.1)`
3. **A new intervention** written in Step 5-C (`starvation` / `monopoly_breaker`
   / `contrarian`): `monopoly_breaker → service_health −10.0 for 1 cycle`
4. **An observation micro-adjustment** (Step 2-B1):
   `test_coverage produced findings → confidence +0.02`
5. **A re-applied lesson** (Step 2-F) — a past verbal self-critique whose lesson
   informed this cycle: `recalled lesson: skip backlog after 2× no_remote (held)`
6. **Nothing changed:** `no new orientation this cycle (observing)`

If BOTH a human-decision confidence change (1) and a lens change (2) occurred,
render both as two LEARN lines — together they are the clearest proof the loop
re-orients from real outcomes.

Render with box-drawing characters (fall back to the plain layout below on narrow
terminals, same rule as `/ooda-status`):

```
┌─ {project.name} · OODA-loop cycle #{N} ────────── {YYYY-MM-DD HH:MM UTC} ─┐
│                                                                           │
│  OBSERVE   {domains_scanned} domains · {most_notable_change}              │
│  ORIENT    {orient_summary}                                               │
│  DECIDE    {winner} won (score {score}) · confidence {conf} {gate ✓/✗}    │
│  ACT       {act_summary}                                                  │
│            └ {pr_detail_or_blank}                                         │
│  LEARN  🔭 {learn_line_1}                                                 │
│            {learn_line_2_if_any}                                          │
│  COST      +${cycle_cost} · ${daily_total} today · hard cap ${limit}      │
│            (agent auto-HALTs if the daily cap is breached)                │
│                                                                           │
│  HALT: {inactive/ACTIVE} · Level {N} ({level_label})                      │
└───────────────────────────────────────────────────────────────────────────┘
```

`{level_label}` is read **verbatim** from
`config.progressive_complexity.levels[{N}].name` (e.g. 0 = `Just watching`,
2 = `Full observation`, 3 = `Autonomous`) — never a hardcoded label, so the card
always agrees with `/ooda-config` and the README level table.

**Missing-field handling (graceful degradation).** The card must NEVER error on
incomplete or legacy state. For any field whose source is absent — e.g. a
pre-v1.2.0 `decision_log` entry without `orient_summary` / `confidence` /
`risk_tier`, an empty `cost_ledger.json`, or no lens files yet — render `—` for
that field and continue. The LEARN line falls through its priority order to
`no new orientation recorded for cycle #{N}` when no delta is recoverable. If
`decision_log` is empty, skip the card and print
`No cycle to card yet. Run /evolve first.` The richest LEARN lines require
v1.2.0+ state (a populated `lens_changelog.json` and recorded confidence
deltas); older projects still get a valid card, just with more `—`.

Then print one plain-text line below the box for frictionless copy-paste sharing:

```
{project.name} ran OODA-loop cycle #{N}: {winner} → {act_summary}. Learned: {learn_line_1}. Cost +${cycle_cost}/cycle (${daily_total} today). — github.com/mataeil/OODA-loop
```

Strip any trailing `.` from `{learn_line_1}` before substituting it so the
sentence doesn't end in `..`.

**Honesty rule (non-negotiable).** The LEARN line describes *outcome-driven
re-orientation* — heuristic confidence/lens updates with asymmetric decay — NOT
machine learning. Never render "trained", "model updated", or "learned weights".
The correct verbs are "re-aimed", "adjusted", "deprioritized", "confidence
+/−". This honest framing is itself a credibility signal; see the README
section **How the "learning" actually works**.

---

## Step 7-B: Outcome Verdict (separate-model eval, opt-in)

Loop-engineering canon: **the writer must not grade its own work.** OODA-loop's
deterministic Outcome Record (6-C9) is always on and unbiased because it scores
from facts, not opinion. This step adds the *maker/checker* layer — a SEPARATE
model reads what the cycle actually did and judges whether it achieved the
declared goal. It runs ONLY when `config.eval.enabled == true` (default
**false** — the deterministic signal stands alone at zero extra cost).

```
if not config.eval.enabled: skip Step 7-B.
-- Only grade cycles worth grading (don't spend a call on observe/futile):
if this cycle's result_type not in config.eval.grade_on
   (default ["pr_created","pr_merged","action_extracted"]): skip.

-- Invoke a SEPARATE model (config.eval.model, default a small fast model such
-- as claude-haiku-4-5) — NOT the cycle's own context. Give it ONLY:
--   the declared_goal (goals.json goal or action title),
--   the orient_summary, the skill's output summary, and the PR diff if any.
verdict = evaluator(
  system: "You are an independent reviewer. You did NOT do this work. Decide
           ONLY whether it achieved the declared goal. Be skeptical; default to
           achieved=false if the evidence is weak. Output {achieved, reason, confidence}.",
  input:  { declared_goal, orient_summary, skill_output, pr_diff }
) -> { achieved: bool, reason: string (<=30 words), confidence: 0.0-1.0 }

-- Write into THIS cycle's outcomes.json entry (do not change quality_multiplier;
-- the deterministic score is the ground truth — the verdict is a second opinion):
outcomes.entries[-1].verifier_verdict = verdict
Write outcomes.json.
Print "[Eval] Independent verdict: {achieved} ({confidence}) — {reason}"

-- If the independent verdict DISAGREES with the deterministic score
-- (achieved=false but quality_multiplier>=0.5, i.e. a merged/created PR the
-- reviewer thinks missed the goal), record a skill_gap of type "eval_disagreement"
-- so persistent maker/checker divergence is visible on the scorecard.
if verdict.achieved == false AND quality_multiplier >= 0.5:
  skill_gaps.gaps.append({ name: "eval_disagreement_{domain}", type: "eval_gap",
    detail: "Deterministic score {q} but independent reviewer says goal not met: {reason}",
    frequency: 1, first_seen: now, resolved: false })
```

Honesty rule: the deterministic `quality_multiplier` remains the scorecard's
ground truth (it cannot be gamed). The verdict is an *independent second signal*
— never let the maker's own model overwrite the deterministic score. The
scorecard surfaces verifier agreement as a separate line when eval is enabled.

---

## I/O Contract

```yaml
name: evolve
ooda_phase: meta
version: "1.1.0"

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
    - agent/state/evolve/reflections.json
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
    - eval

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
    - agent/state/evolve/reflections.json (Step 5-F, per decision cycle)
    - agent/state/evolve/outcomes.json (Step 6-C9, per cycle)
    - agent/state/evolve/cycle_log.jsonl (Step 6-C9, append-only)
    - "agent/state/*/lens.json (Step 5-E)"
    - "agent/state/*/lens_changelog.json (Step 5-E, when a lens item changes)"
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
