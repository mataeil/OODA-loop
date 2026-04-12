---
name: ooda-config
description: View, modify, and validate config.json settings via slash commands.
ooda_phase: support
version: "1.0.0"
input:
  files: [config.json]
  config_keys: []
output:
  files: [config.json]
  prs: none
safety:
  halt_check: true
  read_only: true
domains: []
chain_triggers: []
---

# ooda-config: Configuration Management CLI

View, modify, and validate `config.json` without editing JSON by hand.
All writes: back up to `config.json.bak`, then re-parse to confirm valid JSON.

---

## Step 0: HALT + Preflight

Read `config.safety.halt_file` (default `agent/safety/HALT`).
If that path exists: `HALT: <reason>. ooda-config aborted.` — stop.

If `config.json` is missing and subcommand is not `validate`:
`config.json not found. Run /ooda-setup to create one.` — stop.

Parse the user's invocation to one of: `show | level | domain add | domain remove | domain list | safety | validate`.
Unknown subcommand → print the Usage block and exit.

---

## Step A — show

Print a compact summary: schema_version, project fields, domain list with
weight/skill/enabled status, current progressive_complexity level and name,
and key safety values (halt_file presence, confidence_threshold, max_prs_per_cycle).

---

## Step B — level {N}

1. Validate N is 0–3; fail fast otherwise.
2. If N == 3, print explicit warning and require a typed confirmation phrase:
   ```
   [DANGER] Level 3 enables AUTONOMOUS mode:
     - The agent will create PRs AND auto-merge them without human review
     - Implementation changes will be deployed automatically
     - Only HALT file or cost limit can stop a running cycle
   Type "enable autonomous" to confirm (anything else cancels):
   ```
   Only accept the exact phrase `enable autonomous`. Any other response: `Cancelled.`
3. Back up config.json.
4. Set `progressive_complexity.current_level = N` and `implementation.enabled = (N == 3)`.
5. Write + validate JSON. Print: `Level changed: <old> → <N> ("<name>")`.

---

## Step C — domain add {name}

Ask the user in sequence for: weight (float, default 1.0), primary_skill (must start with "/"),
state_file path (default `agent/state/<name>.json`).

Back up config.json. Insert into `config.domains`:
```json
{ "weight": <w>, "state_file": "<path>", "primary_skill": "<skill>",
  "chain": [], "branch_prefix": "auto/<name>/", "fallback": true, "enabled": true }
```
Create empty state file if absent (`{ "schema_version": "1.0.0", "domain": "<name>", "last_run": null }`).
Append primary_skill to `safety.skill_allowlist` if not already present.
Write + validate. Print confirmation showing state file status and allowlist change.

---

## Step D — domain remove {name}

Look up `config.domains.<name>`. Not found or already disabled → print message and exit.
Back up. Set `enabled: false` (soft-delete — data retained). Write + validate.
Print: `Domain disabled: <name>  (re-enable by setting enabled: true)`

---

## Step E — domain list

Print a table: name, status (enabled/disabled), weight, primary_skill, state_file.
Footer: `Total: <N> domains, <enabled_count> enabled`.
If `config.domains` is empty: `No domains configured.`

---

## Step F — safety

Print the full safety section as a labeled key-value block:
halt_file (with presence indicator), confidence_threshold, min_cycle_interval_minutes,
max_prs_per_cycle, max_files_per_pr, max_lines_per_pr, first_cycle_observe_only,
protected_paths list, and skill_allowlist.

---

## Step G — validate

Run checks in order; print `[PASS]` or `[FAIL] <reason>` for each:

1. config.json exists and is readable
2. Parses as valid JSON
3. `schema_version` field present
4. `project.name`, `project.locale`, `project.timezone` all present
5. `safety.halt_file`, `safety.confidence_threshold`, `safety.max_prs_per_cycle` present
6. Value ranges: `confidence_threshold` in [0.0, 1.0]; `max_prs_per_cycle` >= 1; `min_cycle_interval_minutes` >= 1
7. If present, `health_check_timeout_seconds` is a number in [2, 30]
8. If present, `test_timeout_seconds` is a number >= 10
9. If present, `deploy_monitor_timeout_seconds` is a number >= 60
10. If present, `deploy_health_wait_seconds` is a number >= 5
11. If present, `deploy_workflow_inputs` is a plain object (not array, not null)
12. If present, `safety.lock_timeout_minutes` is a number >= 1
13. At least one domain defined
14. Each domain has `weight`, `primary_skill`, `state_file`, `enabled`
15. Every enabled domain's `primary_skill` is in `safety.skill_allowlist`
16. `progressive_complexity.current_level` is 0–3
17. No sensitive field holds a raw token (must use `$ENV_VAR` form)

Final: `Validation: <N> passed, <M> failed`
On any failure append: `Run /ooda-config show to review your settings.`

---

## Lens Management

### Step H — lens review {domain}

Show the lens snapshot for the named domain.

1. Look up the domain in `config.domains`. Not found → `Domain not found: <name>` and exit.
2. Derive the lens path: `agent/state/<name>/lens.json` (or `lens_file` field if present in config).
3. If lens.json does not exist → `No lens data for <name>. Run a cycle first.` and exit.
4. Print the full contents of lens.json as a labeled key-value block, including all evidence trail entries (timestamps, sources, confidence deltas).

---

### Step I — lens reset {domain}

Wipe the lens snapshot for the named domain, forcing a fresh start on the next cycle.

1. Look up the domain in `config.domains`. Not found → `Domain not found: <name>` and exit.
2. Derive the lens path the same way as Step H.
3. If lens.json does not exist → `No lens file found for <name>. Nothing to reset.` and exit.
4. Ask for confirmation: `Reset lens for <name>? This clears all accumulated evidence. (yes/no)`
   Any answer other than "yes" → `Cancelled.` and exit.
5. Back up the existing lens file to `lens.json.bak` in the same directory before overwriting.
   Print: `  Backed up: <lens_path>.bak`
6. Overwrite lens.json with: `{ "schema_version": "1.0.0", "domain": "<name>", "reset_at": "<ISO timestamp>", "evidence": [] }`
7. Print: `Lens reset: <name>  (evidence cleared, backup saved, next cycle starts fresh)`

---

## Action Queue Management

### Step J — action list

Print pending actions from `agent/state/evolve/action_queue.json`:

```
[Action Queue] {pending_count} pending, {completed_count} completed

| # | ID     | Title                        | RICE  | Age  | Status  |
|---|--------|------------------------------|-------|------|---------|
| 1 | a15-1  | Update context.json names    | 50400 | 3.2d | pending |
| 2 | a17-1  | Pipeline FTS index           | 25200 | 3.0d | approved |
```

Show `effective_rice` (with decay applied) and age since `extracted_at`.

---

### Step K — action approve {id}

Set action status to `"approved"`. Approved items are prioritized over pending
items in dev-cycle selection regardless of RICE score.

```
1. Find action by id in action_queue.pending
2. If not found: "Action not found: {id}" — exit
3. Set status = "approved", approved_at = now
4. Boost effective_rice by 20% (item.effective_rice *= 1.2)
5. Print "Approved: {title} (effective RICE: {new_rice})"
```

---

### Step L — action defer {id} [days]

Defer an action for N days (default 7). Deferred items are excluded from
dev-cycle selection until their defer period expires.

```
1. Find action by id
2. Set status = "deferred", deferred_until = now + N days
3. Print "Deferred: {title} until {date} ({N} days)"
```

---

### Step M — action reject {id} [reason]

Move action to completed with status `"rejected_by_human"`.

```
1. Find action by id
2. Move to completed array with status = "rejected_by_human", reason = reason
3. Print "Rejected: {title} — {reason or 'no reason given'}"
```

---

### Step N — action prioritize {id}

Move action to top of queue by setting effective_rice above current highest.

```
1. Find action by id
2. Set effective_rice = max(all pending effective_rice) + 1.0
3. Re-sort pending by effective_rice descending
4. Print "Prioritized: {title} → top of queue (RICE: {new_rice})"
```

---

### Step O — mode {name}

Switch season/phase mode. Mode overrides domain weights and settings.

```
1. Read config.season_modes.modes
2. If modes not configured: "No season modes defined. Add season_modes to config.json." — exit
3. If {name} not in modes: "Unknown mode: {name}. Available: {list}" — exit
4. Back up config.json
5. Set config.season_modes.current_mode = {name}
6. Print applied overrides (weight changes, disabled domains)
7. Write + validate JSON
8. Print "Mode changed: {old} → {name}"
```

---

## Step G — validate (extended)

Run checks in order; print `[PASS]` or `[FAIL] <reason>` for each:

1. config.json exists and is readable
2. Parses as valid JSON
3. `schema_version` field present
4. `project.name`, `project.locale`, `project.timezone` all present
5. `safety.halt_file`, `safety.confidence_threshold`, `safety.max_prs_per_cycle` present
6. Value ranges: `confidence_threshold` in [0.0, 1.0]; `max_prs_per_cycle` >= 1; `min_cycle_interval_minutes` >= 1
7. If present, `health_check_timeout_seconds` is a number in [2, 30]
8. If present, `test_timeout_seconds` is a number >= 10
9. If present, `deploy_monitor_timeout_seconds` is a number >= 60
10. If present, `deploy_health_wait_seconds` is a number >= 5
11. If present, `deploy_workflow_inputs` is a plain object (not array, not null)
12. If present, `safety.lock_timeout_minutes` is a number >= 1
13. At least one domain defined
14. Each domain has `weight`, `primary_skill`, `state_file`, `enabled`
15. Every enabled domain's `primary_skill` is in `safety.skill_allowlist`
16. `progressive_complexity.current_level` is 0–3
17. No sensitive field holds a raw token (must use `$ENV_VAR` form)
18. At least one domain has `fallback: true` (confidence gate escape)
19. No duplicate `branch_prefix` values across domains
20. `signals.health_alert_bonus` should be <= 2× max domain weight (monopoly risk)
21. `memory.contrarian_check_interval` is in range [1, 100]
22. `memory.action_queue_decay_days` > 0 and `action_queue_decay_amount` in (0, 1]
23. If `implementation.enabled`, `progressive_complexity.current_level` must be 3
24. `memory.working_memory_size` >= 5 (minimum for pattern detection)
25. If `saturation` block present, `warn_threshold < boost_threshold < halt_threshold`

Final: `Validation: <N> passed, <M> failed`
On any failure append: `Run /ooda-config show to review your settings.`

---

## Usage

```
/ooda-config show                  Print current config summary
/ooda-config level {0-3}           Change progressive complexity level
/ooda-config domain add {name}     Add a new domain (interactive)
/ooda-config domain remove {name}  Disable a domain (soft-delete)
/ooda-config domain list           List all domains with status
/ooda-config safety                Show full safety settings
/ooda-config validate              Validate config.json structure and values
/ooda-config lens review {domain}  Show lens.json for a domain with evidence trails
/ooda-config lens reset {domain}   Wipe lens.json for a domain (start fresh)
/ooda-config action list           List pending actions with RICE and age
/ooda-config action approve {id}   Approve action for priority execution
/ooda-config action defer {id} [N] Defer action for N days (default 7)
/ooda-config action reject {id}    Reject action with optional reason
/ooda-config action prioritize {id} Move action to top of queue
/ooda-config mode {name}           Switch season/phase mode
```
