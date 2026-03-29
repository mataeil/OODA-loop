# OODA-loop

**An autonomous brain for your codebase — powered by Boyd's OODA loop and Claude Code**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue)](https://claude.ai/code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## What is this?

OODA-loop is an open-source autonomous agent framework that gives your codebase a self-managing loop. It uses Boyd's OODA cycle — Observe, Orient, Decide, Act — to continuously monitor your project, learn from past outcomes, choose the highest-priority action, and execute it by running skills and creating pull requests. Unlike scheduled scripts or simple automation, OODA-loop builds and maintains a world model: it knows what changed, what worked, what failed, and why.

The framework has been battle-tested on a production service (a URL shortening platform) running 14 autonomous cycles successfully. It is designed specifically for Claude Code and runs entirely within your repository.

---

## Why OODA-loop?

- **vs. cron scripts**: Cron runs on schedule. OODA runs on need.
- **vs. simple automation**: Automation follows rules. OODA builds a world model and learns.
- **vs. manual ops**: You set the domains and safety levels. The harness does the rest.
- **vs. AI copilots**: Copilots answer questions. OODA-loop acts autonomously and tracks consequences.
- **vs. one-shot agents**: One-shot agents forget. OODA-loop accumulates memory across cycles.

---

## Quick Start

```bash
git clone https://github.com/mataeil/OODA-loop.git
cd OODA-loop
cp config.example.json config.json
# Edit config.json with your project details
```

Then open Claude Code in your project directory and run:

```
/ooda-setup    # Auto-detect your project
/evolve        # First cycle (observe-only by default)
/ooda-status   # Check what happened
```

Your first `/evolve` run will observe all configured domains and write initial state files. No code changes, no PRs — just observation. When you are ready to go further, increase your complexity level in `config.json`.

---

## Progressive Complexity

OODA-loop is designed to earn your trust. Start at Level 0 and move up only when the observations look right.

| Level | Name | What happens |
|-------|------|-------------|
| 0 | Just Watching | 1 domain (`service_health`). Observe only, no PRs |
| 1 | Watching + Testing | 2 domains. Observe + test coverage tracking |
| 2 | Full Observation | All domains. Reports but no code changes |
| 3 | Autonomous | Implementation enabled. Draft PRs, auto-merge for Level 1 changes |

Start at Level 0. When you trust the observations, bump to Level 1. Work your way up.

To change levels, edit `config.json`:

```json
"progressive_complexity": {
  "current_level": 1
}
```

---

## How It Works

Every `/evolve` run executes one complete OODA cycle:

1. **Check HALT file** — If `agent/safety/HALT` exists, stop immediately. Safety first.
2. **Observe** — Read all domain state files, query GitHub for PR status, collect urgent signals.
3. **Orient** — Detect patterns across signals, update per-domain confidence scores, build a world model snapshot, apply memo adjustments. This is the key differentiator: orientation is not score math alone — it is pattern recognition, confidence calibration, and contextual reasoning.
4. **Decide** — Score every domain using the scoring formula. The domain with the highest score wins and its primary skill is selected.
5. **Act** — Execute the winning skill, create PRs, update state files, trigger skill chains.
6. **Reflect** — Write a decision log entry, update domain state, cascade memory (working → episodes → principles).

Scoring formula:
```
score = (hours_since_last × weight) + urgent_signal + (goal_contribution × 0.3) + (confidence × 0.2) + memo_adjustment
```

See [CONCEPTS.md](CONCEPTS.md) for full terminology, architecture diagram, and scoring details.

---

## Configuration

Copy `config.example.json` to `config.json` and fill in your project details. The top-level sections are:

| Section | Purpose |
|---------|---------|
| `project` | Name, locale, timezone |
| `domains` | What the harness monitors — each domain has a weight, state file, and primary skill |
| `safety` | HALT file path, cycle intervals, PR size limits, skill allowlist |
| `scoring` | Formula parameters: goal weight, confidence weight, staleness window |
| `progressive_complexity` | Current autonomy level (0–3) |
| `confidence` | How confidence scores update on PR merge and rejection |
| `memory` | Working memory size, episode retention, action queue decay |
| `notifications` | Optional Telegram alerts (uses `$ENV_VAR` references — no secrets in config) |

See [config.example.json](config.example.json) for the full annotated schema.

---

## Safety

OODA-loop is designed to be safe by default. Level 0 cannot create PRs. Level 3 requires deliberate opt-in.

- **HALT file** — `agent/safety/HALT` stops everything instantly. Create the file to pause the harness. Delete it to resume. No code needed.
- **Protected paths** — `agent/safety/*`, `agent/skills/meta/*`, and `agent/contracts/*` cannot be modified by the harness. The agent cannot rewrite its own safety rules.
- **Progressive complexity** — The harness starts in observation-only mode. Code changes are only possible at Level 3.
- **PR size limits** — Maximum 20 files and 500 lines per PR, enforced in config.
- **First cycle observe-only** — When `first_cycle_observe_only: true`, the very first `/evolve` run observes all domains without taking any action.
- **Skill allowlist** — `safety.skill_allowlist` restricts which skills the engine is permitted to call.
- **Confidence threshold** — Risky actions are gated behind a minimum confidence score (default: `0.6`). New domains start at `0.5` — below the threshold until they prove themselves.

See [SECURITY.md](SECURITY.md) for the full threat model, protected path policy, and HALT file procedures.

---

## Built-in Skills

OODA-loop ships with five operational skills organized by OODA phase, plus three wizard commands:

| Skill | Phase | Description |
|-------|-------|-------------|
| `/scan-health` | Observe | Monitor service health endpoints |
| `/check-tests` | Detect | Run tests, track coverage trends |
| `/plan-backlog` | Strategize | Score GitHub issues by RICE (Reach × Impact × Confidence / Effort) |
| `/run-deploy` | Execute | Trigger deployment workflow |
| `/dev-cycle` | Support | Full implementation cycle — observe, plan, and code |
| `/ooda-setup` | Wizard | 3-step project setup and auto-detection |
| `/ooda-config` | Wizard | Configuration management and validation |
| `/ooda-status` | Wizard | Status dashboard — last cycle, scores, memory summary |

Skills are organized under `agent/skills/` by phase. Each skill reads the HALT file first, writes structured output to its domain state file, and returns a contract-compliant result.

---

## Creating Custom Skills

Any Claude Code slash command can become a domain skill. To add a skill:

1. Create your skill file using the template at `templates/SKILL_TEMPLATE.md`
2. Register it in `config.json` under the relevant domain's `primary_skill` field
3. Create a symlink in `.claude/skills/` so Claude Code can invoke it

The skill interface specification is defined in `agent/contracts/schema.md`. All skills must conform to the contract: read the HALT file, accept domain context as input, and return a structured state update as output.

---

## Contributing

OODA-loop is open source and welcomes contributions: new domain skills, scoring formula improvements, integrations (GitHub Actions, Slack, PagerDuty), and documentation. Before submitting a PR, please read [CONTRIBUTING.md](CONTRIBUTING.md) for the skill authoring guide, domain registration steps, and the code style rules. All skill PRs must include a contract-compliant example output.

---

## License

MIT — see [LICENSE](LICENSE)
