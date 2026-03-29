---
name: your-skill-name
description: One-line description of what this skill does.
---

# your-skill-name: Brief Title

Short description of purpose. 2-3 sentences covering what it does, which OODA
phase it serves, and what output it produces.

## Contract

```yaml
name: your-skill-name
ooda_phase: observe|detect|strategize|execute|support
version: "1.0.0"
description: Same as frontmatter description.

input:
  files:
    - config.json
    - agent/state/your_domain.json
  apis: []
  config_keys: [test_command]

output:
  files:
    - agent/state/your_domain.json
  prs: none

safety:
  halt_check: true
  read_only: true
  branch_prefix: "auto/your-skill/"
  cost_limit_usd: 0.05

domains: [your_domain]

chain_triggers: []
```

## Safety Rules

1. **HALT check** -- verify `config.safety.halt_file` does not exist before any action.
2. **Read-only** -- this skill writes only to its state file. No PRs, no code changes.
   (Set `read_only: false` and add `branch_prefix` if your skill creates PRs.)
3. **Graceful degradation** -- if required data is missing, exit cleanly with a message.

## Workflow

### Step 0: Safety

```
if file exists at config.safety.halt_file:
  print "[HALT] Stopping. Reason: {file contents}"
  EXIT
```

Verify required config keys exist. If missing, print helpful message and exit.

### Step 1: Load State

Read your domain state file. If missing, create with initial structure:

```json
{
  "schema_version": "1.0.0",
  "last_run": null,
  "run_count": 0,
  "status": "unknown"
}
```

### Step 2: Core Logic

Describe the main work of your skill here. Be specific and unambiguous --
Claude will follow these instructions literally.

### Step 3: State Update

Write updated state to your domain state file. Include:
- `last_run`: current ISO 8601 timestamp
- `run_count`: incremented
- `status`: result of this run
- Any domain-specific fields (alerts, scores, metrics, etc.)

### Step 4: Report

Print a summary of what happened. Include:
- Key metrics or findings
- Any alerts generated
- Recommendation for next action (if applicable)

## Graceful Degradation

| Condition | Behavior |
|-----------|----------|
| HALT file exists | Exit immediately |
| Required config missing | Print message, exit 0 |
| State file missing | Create with defaults |
| External API unavailable | Record failure, continue |

## Registration

After creating your skill:

1. Place the file at `agent/skills/{phase}/{skill-name}/SKILL.md`
2. Add a domain entry in `config.json` with `primary_skill` pointing to your skill
3. Add your skill name to `config.safety.skill_allowlist`
4. Create a symlink: `ln -sf ../../agent/skills/{phase}/{skill-name} .claude/skills/{skill-name}`
