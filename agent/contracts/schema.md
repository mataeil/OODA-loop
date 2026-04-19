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

contract_version: "1.0"       # Schema version of the contract format itself.
                              # Bump when adding new required fields or changing semantics.
name: skill-name              # Unique identifier. Must match directory name.
ooda_phase: observe            # One of: meta, observe, detect, strategize, execute, support
version: "1.0.0"              # Semver (MAJOR.MINOR.PATCH). Bump MAJOR on breaking
                              # input/output changes, MINOR on additive changes,
                              # PATCH on bug fixes that don't alter I/O.
description: >
  One-paragraph summary of what this skill does and why it exists.

input:
  files: []                   # State files this skill READS (relative to repo root)
  apis: []                    # External API endpoints called (for documentation)
  web_search: false           # true if skill uses web search
  config_keys: []             # config.json keys this skill reads (e.g., "health_endpoints")
output:
  files: []                   # State files this skill WRITES (relative to repo root)
  prs: none                   # none | "Draft PR" | "Ready PR"

safety:
  halt_check: true            # Must check HALT file before any action. Always true.
  read_only: true             # true = no PRs, no code changes (state file writes always OK).
                              # false = may create PRs and modify code files.

# --- OPTIONAL FIELDS ---

status: active                # active | deprecated. Deprecated skills are loaded
                              # but never auto-selected by scoring. They remain
                              # callable via direct invocation or chain triggers
                              # until fully removed.

chain_triggers: []            # List of trigger rules (see Chain Triggers section)

safety:                       # (merged with required safety block above)
  branch_prefix: "auto/name/" # Required only when read_only is false
  cost_limit_usd: 0.05        # Per-invocation cost cap. Optional but recommended.
  max_files: 20               # PR size guard. Inherits from config if omitted.
  max_lines: 500              # PR size guard. Inherits from config if omitted.

domains: []                   # Which config domains this skill serves (for routing)

data_classification:          # Security classification for skill's data access
  level: internal             # internal | api | external
                              #   internal: reads only local files/SQLite (safest)
                              #   api: calls first-party or trusted APIs
                              #   external: calls third-party APIs or web search (requires Level >= 2)
  pii_handling: false         # true if skill processes personally identifiable information
  external_apis: []           # List of external APIs called (for audit trail)
                              # At Level < 3, skills with level: external require human approval.
                              # At Level 3, external skills run autonomously but are logged to cost_ledger.

execution_mode: standard     # standard | consensus
                              #   standard: skill runs once, output is final (default)
                              #   consensus: skill runs N times with different perspectives,
                              #              output is the intersection of agreed-upon items
consensus:                    # Only used when execution_mode is "consensus"
  agents: 3                   # Number of parallel runs (2-5 recommended)
  rounds: 2                   # Deliberation rounds (1-3)
  agreement_threshold: 0.67   # Fraction of agents that must agree for item to be included
  perspectives: []            # Named perspectives for each agent run
                              # e.g., ["conservative", "progressive", "user-advocate"]
                              # If empty, agents run with the same prompt (diversity from temperature)
                              # The evolve orchestrator runs the skill N times, passing each
                              # perspective as context. Items present in >= agreement_threshold
                              # fraction of outputs are included in the final result.
                              # Consensus mode multiplies cost by N (tracked in cost_ledger).
```

### Required vs Optional Summary

| Field | Required | Default | Notes |
|------------------------|----------|-----------------|-----------------------------------------------|
| contract_version | no | `"1.0"` | Schema version (currently `"1.0"`) |
| name | YES | -- | Must match directory name |
| ooda_phase | YES | -- | One of the 6 phases |
| version | YES | -- | Semver `MAJOR.MINOR.PATCH` string |
| description | YES | -- | Human-readable, one paragraph |
| input.files | YES | `[]` | Empty list is valid (skill reads nothing) |
| output.files | YES | `[]` | Empty list is valid (skill writes nothing) |
| safety.halt_check | YES | `true` | Must always be true. Engine rejects false. |
| safety.read_only | YES | -- | true = no PRs (state writes OK). false = PRs allowed |
| status | no | `active` | `active` or `deprecated` |
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
- String literals must use single quotes: `status == 'green'`. Unquoted tokens
  are treated as field references into the output JSON.
- `AND` binds tighter than `OR` (standard precedence). Parentheses are NOT
  supported; split complex conditions into separate trigger entries instead.
- Chain depth is capped at **3** (configurable via `config.safety.max_chain_depth`,
  hard ceiling of 5). If a chain would exceed this depth, the remaining triggers
  are skipped and a warning is logged: `[WARN] Chain depth {N} exceeded max {max}. Remaining triggers skipped.`
- Each chained skill still checks HALT before running.
- Circular chains (A triggers B triggers A) are detected at validation time and
  rejected. The engine builds a directed graph of all `chain_triggers` and
  rejects any skill whose triggers form a cycle.

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
              | consecutive      | new_failures    | actionable >= 1
              | _failures >= 3   | OR coverage     | AND top_rice
              |                  | _drop > 5       | >= 50
              +--------+         +--------+         +--------+
                       |                  |                  |
                       v                  v                  v
                 +-----+------+    +------+------+    +-----+------+
                 | dev-cycle  |    | dev-cycle   |    | dev-cycle  |
                 | (support)  |    | (support)   |    | (support)  |
                 +-----+------+    +-------------+    +-----+------+
                       |                                    |
                       | pr_created == true                 |
                       v                                    |
                 +-----+------+                             |
                 | scan-health|  (post-impl verification)   |
                 +------------+                             |
                                                            |
                 +------------+                             |
                 | run-deploy |<----------------------------+
                 | (execute)  |  when: approved AND safe
                 +-----+------+
                       |
                       | health_check == 'failed'
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
  config_keys:
    - health_endpoints
    - health_check_timeout_seconds

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
    - test_timeout_seconds

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
    - agent/state/test_coverage.json
  apis:
    - "GitHub Actions API (workflow_dispatch)"
  config_keys:
    - deploy_workflow
    - deploy_workflow_inputs
    - deploy_monitor_timeout_seconds
    - deploy_health_wait_seconds
    - health_endpoints
    - safety.halt_file
    - safety.branch_prefix

output:
  files:
    - agent/state/deploy.json
  prs: none

chain_triggers:
  - target: scan-health
    condition: "health_check == 'failed'"

safety:
  halt_check: true
  read_only: false
  branch_prefix: "auto/deploy/"
  cost_limit_usd: 0.05

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
    - agent/state/evolve/state.json
    - config.json
    - CLAUDE.md
  config_keys:
    - safety.halt_file
    - safety.max_files_per_pr
    - safety.max_lines_per_pr
    - safety.protected_paths
    - test_command

output:
  files:
    - agent/state/evolve/action_queue.json
  prs: "Draft PR"

chain_triggers:
  - target: scan-health
    condition: "pr_created == true"

safety:
  halt_check: true
  read_only: false
  branch_prefix: "auto/dev-cycle/"
  cost_limit_usd: 0.10
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
    - agent/state/evolve/skill_gaps.json
    - agent/state/evolve/metrics.json
    - agent/state/evolve/episodes.json
    - agent/state/evolve/principles.json
    - agent/state/evolve/cost_ledger.json
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
    - agent/state/evolve/cost_ledger.json
  prs: "Determined by executed skill (evolve itself creates no PRs)"

safety:
  halt_check: true
  read_only: true

domains: []
```

### ooda-setup (support)

```yaml
name: ooda-setup
ooda_phase: support
version: "1.0.0"
description: >
  3-step project setup wizard. Auto-detects language, test framework, CI,
  and endpoints. Creates config.json from config.example.json.

input:
  files: [config.example.json]
  config_keys: []

output:
  files: [config.json]
  prs: none

safety:
  halt_check: true
  read_only: true

domains: []
```

### ooda-config (support)

```yaml
name: ooda-config
ooda_phase: support
version: "1.0.0"
description: >
  View, modify, and validate config.json settings via slash commands.

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
```

### ooda-status (support)

```yaml
name: ooda-status
ooda_phase: support
version: "1.0.0"
description: >
  Display OODA-loop status dashboard. Shows cycle count, domain states,
  confidence scores, action queue, and alerts in a single view.

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
```

### ooda-skill (support)

```yaml
name: ooda-skill
ooda_phase: support
version: "1.0.0"
description: >
  Create, disable, and enable domain skills. Generates project-specific
  SKILL.md files via a short interview.

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
```

---

## Registering a Custom Skill

Three steps:

**1. Create the skill directory and SKILL.md**

```
skills/<your-skill>/SKILL.md
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

**3. Skill discovery**

The plugin system auto-discovers skills from `skills/*/SKILL.md`. The engine
reads `skill_allowlist` from config and loads each skill's contract from its
SKILL.md. No symlinks or manual registration needed.

---

## Contract Validation

The engine validates every contract at cycle start. A skill is skipped (with a
warning in the cycle log) if any of these checks fail:

| Check | Rule | Error message |
|-------------------------------|------------------------------------------------------|-------------------------------------------------------|
| Required fields present | All YES fields from the table above must exist | `[contract] {skill}: missing required field '{field}'` |
| Contract version supported | `contract_version` must be a version the engine knows | `[contract] {skill}: unsupported contract_version '{v}' (engine supports up to '{max}')` |
| Phase is valid | Must be one of the 6 defined phases | `[contract] {skill}: invalid ooda_phase '{phase}'` |
| Name matches directory | `name` field must equal the skill's directory name | `[contract] {skill}: name '{name}' does not match directory '{dir}'` |
| HALT check is true | `safety.halt_check` must be `true` | `[contract] {skill}: safety.halt_check must be true` |
| Branch prefix when writable | `safety.branch_prefix` required if `read_only: false` | `[contract] {skill}: read_only is false but no branch_prefix set` |
| Allowlist membership | Skill must appear in `safety.skill_allowlist` | `[contract] {skill}: not in skill_allowlist` |
| Chain targets exist | Every `chain_triggers[].target` must be a known skill | `[contract] {skill}: chain target '{target}' is not a known skill` |
| No circular chains | Chain trigger graph must be acyclic (DAG) | `[contract] {skill}: circular chain detected: {cycle_path}` |
| Version is semver | Must match `MAJOR.MINOR.PATCH` (digits only, no `v` prefix) | `[contract] {skill}: version '{v}' is not valid semver` |
| Deprecated skill not auto-selected | `status: deprecated` skills pass validation but are excluded from scoring | `[contract] {skill}: status is deprecated, skipping auto-selection` (info, not error) |

Validation errors are logged to `agent/state/evolve/CHANGELOG.md` and the
skill is excluded from that cycle. The cycle continues with remaining valid
skills. Multiple errors per skill are collected and reported together (the
engine does not stop at the first error).

---

## Recommended RICE Dimension Palette (v1.2.0)

Phase-4 introduced `config.scoring.rice_extensions` to attach arbitrary
extra dimensions to the base RICE formula. Skills that emit extended RICE
scores (e.g., plan-questions, plan-backlog) should pick dimension names
from this shared palette when possible, so different projects converge on
the same vocabulary instead of each inventing its own:

| Dimension | Meaning | Typical range |
|-----------|---------|---------------|
| `timing` | Window-of-opportunity urgency (e.g., D-day approaching, release train) | 0–10 |
| `novelty` | Newness / unexpectedness of the angle | 0–10 |
| `evidence` | Strength of supporting data (citations, logs, repro steps) | 0–10 |
| `vulnerability` | Severity of the exposure the action addresses | 0–10 |
| `alignment` | Fit with stakeholder priorities (pair with `active_context`) | 0–10 |
| `media` | Publicity / visibility potential | 0–10 |
| `reach_precision` | Accuracy of the Reach estimate (replaces raw reach when data is weak) | 0–1.0 |

These are recommendations, not a closed set. Projects may define additional
dimensions; the engine accepts any key declared in `config.scoring.rice_extensions`.
Lynceus's 6D RICE (evidence, media, vulnerability, timing, alignment, novelty)
is a specialization of this palette — the same upstream machinery handles it.

## Action Difficulty ↔ Risk Tier (v1.2.0 docs)

Action-queue items MAY carry a `difficulty` field as a UX convention:

| `difficulty` | Label examples | Maps to `risk_tier` | Auto-merge policy |
|--------------|----------------|---------------------|-------------------|
| `low`        | 하, easy, small | 0 | Eligible for auto-merge at Level 3 if protected-paths clean |
| `medium`     | 중, medium     | 1 | Requires human review regardless of level |
| `high`       | 상, large, risky | 2 | Always protected; never auto-merged |

The binding to an actual `risk_tier` is made via
`config.safety.risk_rules` (Phase-4), which matches PR file paths against
patterns and assigns a numeric tier. `difficulty` is a display/UX hint for
the action queue; `risk_tier` is the load-bearing safety gate. fwd's 하 /
중 / 상 convention maps directly to `low` / `medium` / `high` here.

## execution_mode roadmap

`execution_mode: consensus` ships in v1.1.0 (Phase 5). `execution_mode: debate`
is reserved for v1.3.0: named role-agents (Evaluator / Planner / Designer /
…), multi-round deliberation with an anti-agreement rule, and an archived
markdown transcript. v1.2.0 documents the distinction in CONCEPTS.md under
"Multi-agent debate vs consensus" but does not implement the new mode —
use `consensus` for now.
