---
name: ooda-config
description: Configuration management for OODA-loop. View, modify, and validate config.json settings via slash commands.
version: "1.0.0"
input:
  files: [config.json]
output:
  files: [config.json]
safety:
  halt_check: true
  backup_before_write: true
  validate_json_after_write: true
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
2. If N == 3, print explicit warning (autonomous mode, auto-merge ON, no manual review)
   and require the user to type "yes" to confirm. Any other response: `Cancelled.`
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
7. At least one domain defined
8. Each domain has `weight`, `primary_skill`, `state_file`, `enabled`
9. Every enabled domain's `primary_skill` is in `safety.skill_allowlist`
10. `progressive_complexity.current_level` is 0–3
11. No sensitive field holds a raw token (must use `$ENV_VAR` form)

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
5. Overwrite lens.json with: `{ "schema_version": "1.0.0", "domain": "<name>", "reset_at": "<ISO timestamp>", "evidence": [] }`
6. Print: `Lens reset: <name>  (evidence cleared, next cycle starts fresh)`

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
```
