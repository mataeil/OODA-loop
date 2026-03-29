# Skill Contract Schema

Every skill in OODA-loop declares a contract. The engine reads these
contracts to route OODA cycles, validate safety rules, and wire up chain
triggers between skills. If a skill has no contract, evolve will refuse to
call it.

---

## OODA Phases

Each skill belongs to exactly one phase. The phases map to Boyd's OODA loop
plus two operational roles:

| Phase | OODA Step | Purpose | When evolve picks it |
|------------|-----------|----------------------------------------------|----------------------------------------------|
| meta | (all) | Orchestrates the loop itself | Never picked by scoring; runs the cycle |
| observe | Observe | Gather raw signals about the world | Domain staleness is high |
| detect | Orient | Analyze signals, find patterns and problems | Observation data exists but is unanalyzed |
| strategize | Decide | Prioritize work, plan next actions | Problems detected, no plan yet |
| execute | Act | Change code, deploy, ship | Plan exists with approved actions |
| support | (any) | Cross-cutting helpers (full cycles, tooling) | Called by chain triggers or direct invocation |

**Phase-to-OODA Mapping**: The 6 contract phases are a finer-grained
decomposition of Boyd's 4-step OODA loop (see CONCEPTS.md). `observe` maps
to the Observe step, `detect` to Orient (signal analysis), `strategize` to
Decide (action planning), and `execute` to Act. The `meta` phase is the
orchestrator (evolve itself) and `support` skills are cross-cutting utilities.

The scoring engine in evolve uses `ooda_phase` to break ties: observe skills
run before detect, detect before strategize, and so on. Support skills are
never auto-selected by scoring; they run only via chain triggers or manual
invocation.

---

## Contract Format

Every skill MUST have a YAML front-matter block (fenced with `---`) at the top
of its `SKILL.md`, OR a standalone `contract.yaml` in the same directory.

```yaml
# --- REQUIRED FIELDS ---

name: skill-name              # Unique identifier. Must match directory name.
ooda_phase: observe            # One of: meta, observe, detect, strategize, execute, support
version: "1.0.0"              # Semver. Bump on breaking input/output changes.
description: >
  One-paragraph summary of what this skill does and why it exists.

input:
  files: []                   # State files this skill READS (relative to repo root)
output:
  files: []                   # State files this skill WRITES (relative to repo root)

safety:
  halt_check: true            # Must check HALT file before any action. Always true.
  read_only: true             # true = no PRs, no code changes (state file writes always OK).
                              # false = may create PRs and modify code files.

# --- OPTIONAL FIELDS ---

input:
  apis: []                    # External API endpoints called (for documentation)
  web_search: false           # true if skill uses web search
  config_keys: []             # config.json keys this skill reads (e.g., "health_endpoints")

output:
  prs: none                   # none | "Draft PR" | "Ready PR"

chain_triggers: []            # List of trigger rules (see Chain Triggers section)

safety:
  branch_prefix: "auto/name/" # Required only when read_only is false
  cost_limit_usd: 0.05        # Per-invocation cost cap. Optional but recommended.
  max_files: 20               # PR size guard. Inherits from config if omitted.
  max_lines: 500              # PR size guard. Inherits from config if omitted.

domains: []                   # Which config domains this skill serves (for routing)
```

### Required vs Optional Summary

| Field | Required | Default | Notes |
|------------------------|----------|-----------------|-----------------------------------------------|
| name | YES | -- | Must match directory name |
| ooda_phase | YES | -- | One of the 6 phases |
| version | YES | -- | Semver string |
| description | YES | -- | Human-readable, one paragraph |
| input.files | YES | `[]` | Empty list is valid (skill reads nothing) |
| output.files | YES | `[]` | Empty list is valid (skill writes nothing) |
| safety.halt_check | YES | `true` | Must always be true. Engine rejects false. |
| safety.read_only | YES | -- | true = no PRs (state writes OK). false = PRs allowed |
| input.apis | no | `[]` | |
| input.web_search | no | `false` | |
| input.config_keys | no | `[]` | |
| output.prs | no | `none` | |
| chain_triggers | no | `[]` | |
| safety.branch_prefix | COND | -- | Required when read_only is false |
| safety.cost_limit_usd | no | from config | Overrides config.cost.daily_limit_usd per call |
| safety.max_files | no | from config | |
| safety.max_lines | no | from config | |
| domains | no | `[]` | Used by evolve for routing |

---

## Chain Triggers

A skill can trigger another skill after it finishes. The engine evaluates
conditions against the calling skill's output state.

```yaml
chain_triggers:
  - target: dev-cycle
    condition: "actionable_items >= 1 AND confidence >= 0.7"
  - target: scan-health
    condition: "deploy_completed == true"
```

**Rules:**
- `target` must be a skill name in the `skill_allowlist` (config.json).
- `condition` is a simple expression evaluated against the skill's output JSON.
- Supported operators: `>=`, `<=`, `==`, `!=`, `>`, `<`, `AND`, `OR`.
- Chain depth is capped at 3 to prevent runaway loops.
- Each chained skill still checks HALT before running.

---

## Default Skill Chain Map

```
                          +-----------+
                          |  evolve   |  (meta: picks next skill each cycle)
                          +-----+-----+
                                |
              +-----------------+-----------------+
              |                 |                 |
        +-----v-----+   +------v------+   +------v------+
        | scan-health|   | check-tests |   | plan-backlog|
        |  (observe) |   |  (detect)   |   | (strategize)|
        +-----+------+   +------+------+   +------+------+
              |                  |                 |
              |  failures >= 3   |  coverage_drop   |  actionable >= 1
              +--------+         +--------+         +--------+
                       |                  |                  |
                       v                  v                  v
                 +-----+------+    +------+------+    +-----+------+
                 | dev-cycle  |    | dev-cycle   |    | dev-cycle  |
                 | (support)  |    | (support)   |    | (support)  |
                 +-----+------+    +-------------+    +-----+------+
                       |                                    |
                       | deploy_completed                   |
                       v                                    |
                 +-----+------+                             |
                 | run-deploy |<----------------------------+
                 | (execute)  |  when: approved AND safe
                 +-----+------+
                       |
                       | deploy_completed
                       v
                 +-----+------+
                 | scan-health|  (post-deploy verification)
                 +------------+
```

This is the default wiring. You can rewire everything via `chain_triggers` in
each skill's contract and `chain` arrays in config.json domains.

---

## Default Skill Contracts

### scan-health (observe)

```yaml
name: scan-health
ooda_phase: observe
version: "1.0.0"
description: >
  Checks service health by hitting configured endpoints and reading CI status.
  Writes a health snapshot to state. This is the system's eyes -- it runs most
  frequently and provides the ground truth for every other skill.

input:
  files:
    - agent/state/service_health.json
  apis:
    - "config: health_endpoints[]"
    - "GitHub Actions API (latest runs)"
  config_keys:
    - health_endpoints
    - test_command

output:
  files:
    - agent/state/service_health.json
  prs: none

chain_triggers:
  - target: dev-cycle
    condition: "consecutive_failures >= 3"

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.02

domains:
  - service_health
```

### check-tests (detect)

```yaml
name: check-tests
ooda_phase: detect
version: "1.0.0"
description: >
  Runs the project test suite, parses results, and tracks coverage trends.
  Detects regressions, flaky tests, and coverage drops. Provides the data
  that strategize and execute skills use to decide what to fix.

input:
  files:
    - agent/state/test_coverage.json
  config_keys:
    - test_command

output:
  files:
    - agent/state/test_coverage.json
  prs: none

chain_triggers:
  - target: dev-cycle
    condition: "new_failures >= 1 OR coverage_drop > 5"

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.05

domains:
  - test_coverage
```

### plan-backlog (strategize)

```yaml
name: plan-backlog
ooda_phase: strategize
version: "1.0.0"
description: >
  Scans GitHub Issues, scores them with RICE, and maintains a prioritized
  action queue. Bridges the gap between "we know what's wrong" (detect) and
  "let's fix it" (execute). Does not create PRs -- only plans.

input:
  files:
    - agent/state/backlog.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/goals.json
  apis:
    - "GitHub Issues API"
  config_keys: []

output:
  files:
    - agent/state/backlog.json
    - agent/state/evolve/action_queue.json
  prs: none

chain_triggers:
  - target: dev-cycle
    condition: "actionable_items >= 1 AND top_rice_score >= 50"

safety:
  halt_check: true
  read_only: true
  cost_limit_usd: 0.01

domains:
  - backlog
```

### run-deploy (execute)

```yaml
name: run-deploy
ooda_phase: execute
version: "1.0.0"
description: >
  Triggers a deployment via GitHub Actions workflow_dispatch. Only runs when
  there is an approved, merged PR and all health checks pass. After deploy,
  chain-triggers scan-health for post-deploy verification.

input:
  files:
    - agent/state/service_health.json
  apis:
    - "GitHub Actions API (workflow_dispatch)"
  config_keys:
    - deploy_workflow

output:
  files:
    - agent/state/deploy.json
  prs: none

chain_triggers:
  - target: scan-health
    condition: "deploy_completed == true"

safety:
  halt_check: true
  read_only: false
  branch_prefix: "auto/deploy/"
  cost_limit_usd: 0.02

domains:
  - service_health
```

### dev-cycle (support)

```yaml
name: dev-cycle
ooda_phase: support
version: "1.0.0"
description: >
  Full development cycle: reads the action queue, picks the highest-priority
  item, implements it on a branch, runs tests, and opens a Draft PR. This is
  the only default skill that writes code. Gated behind progressive complexity
  Level 3 or explicit invocation.

input:
  files:
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/confidence.json
    - agent/state/test_coverage.json
  config_keys:
    - test_command

output:
  files:
    - agent/state/evolve/action_queue.json
  prs: "Draft PR"

chain_triggers:
  - target: run-deploy
    condition: "pr_merged == true AND health_status == 'green'"

safety:
  halt_check: true
  read_only: false
  branch_prefix: "auto/dev-cycle/"
  cost_limit_usd: 0.50
  max_files: 20
  max_lines: 500

domains:
  - implementation
```

### evolve (meta)

```yaml
name: evolve
ooda_phase: meta
version: "1.0.0"
description: >
  The OODA orchestrator. Runs one full loop: observe the world, orient by
  scoring domains, decide which skill to invoke, then act. Manages cycle
  state, confidence tracking, memory tiers, and the action queue. Never
  called by other skills -- it IS the loop.

input:
  files:
    - config.json
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/goals.json
    - agent/state/evolve/action_queue.json
    - agent/state/evolve/memos.json

output:
  files:
    - agent/state/evolve/state.json
    - agent/state/evolve/confidence.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/CHANGELOG.md

safety:
  halt_check: true
  read_only: true

domains: []
```

---

## Registering a Custom Skill

Three steps:

**1. Create the skill directory and SKILL.md**

```
agent/skills/<phase>/<your-skill>/SKILL.md
```

Include the contract YAML block at the top of SKILL.md (fenced with `---`).

**2. Add it to config.json**

Add the skill to `safety.skill_allowlist` and wire it to a domain:

```json
{
  "domains": {
    "your_domain": {
      "primary_skill": "/your-skill",
      "weight": 1.0,
      "state_file": "agent/state/your_domain.json",
      "chain": [],
      "enabled": true
    }
  },
  "safety": {
    "skill_allowlist": ["...", "/your-skill"]
  }
}
```

**3. Create the Claude Code symlink**

```bash
ln -s ../../agent/skills/<phase>/<your-skill> .claude/skills/<your-skill>
```

The engine discovers skills by reading `skill_allowlist` from config, then
loading each skill's contract from its SKILL.md. No other registration is
needed.

---

## Contract Validation

The engine validates every contract at cycle start. A skill is skipped (with a
warning in the cycle log) if any of these checks fail:

| Check | Rule |
|-------------------------------|------------------------------------------------------|
| Required fields present | All YES fields from the table above must exist |
| Phase is valid | Must be one of the 6 defined phases |
| Name matches directory | `name` field must equal the skill's directory name |
| HALT check is true | `safety.halt_check` must be `true` |
| Branch prefix when writable | `safety.branch_prefix` required if `read_only: false` |
| Allowlist membership | Skill must appear in `safety.skill_allowlist` |
| Chain targets exist | Every `chain_triggers[].target` must be a known skill |
| Version is semver | Must match `MAJOR.MINOR.PATCH` format |

Validation errors are logged to `agent/state/evolve/CHANGELOG.md` and the
skill is excluded from that cycle. The cycle continues with remaining valid
skills.
