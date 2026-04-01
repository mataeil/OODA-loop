# OODA-loop

**Your side project just got an operations team.**

It watches your project and gets smarter over time. Start at Level 0. Move up when you trust it.

> **Requires [Claude Code](https://claude.ai/code).** All commands (`/ooda-setup`, `/evolve`, etc.) are Claude Code slash commands.

[한국어](README.ko.md) | English

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue)](https://claude.ai/code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Quick Start

**Install** (choose one):

```bash
# Option A: Claude Code plugin (recommended)
/plugin marketplace add mataeil/OODA-loop
/plugin install ooda-loop

# Option B: Global install via git
git clone https://github.com/mataeil/OODA-loop.git ~/.ooda-loop
~/.ooda-loop/install.sh
```

**Set up your project:**

```bash
cd your-project/
/ooda-setup           # auto-detects your stack, writes config
/evolve               # first cycle (observe-only — just watches)
/ooda-status          # check what it found
```

`/ooda-setup` creates `config.json` and `agent/state/` in your project. Your source code is never modified during observation.

**Nothing changes until you say so.** Level 0 just watches. Level 3 opens PRs.

---

## The OODA Loop

In the 1950s, fighter pilot John Boyd studied why some pilots won dogfights and
others did not. His answer was not faster planes or better weapons. It was a
decision cycle: **Observe, Orient, Decide, Act.**

The pilot who cycled through OODA faster gained the advantage. But Boyd's deeper
insight was not about speed alone -- it was about the **Orient** phase. Orient is
where you build your mental model of the world. Every past engagement, every
lesson learned, every pattern recognized -- all of it converges in Orient. The
pilot with the better world model makes the better call, even under pressure.

OODA is not a flowchart you walk through once. It is a continuous feedback loop:

```
            +----------+        +-----------+
    +------>| OBSERVE  |------->|  ORIENT   |------+
    |       +----------+        +-----------+      |
    |            ^               |        |        |
    |            |       implicit|        |        v
    |            |       guidance|        |   +-----------+
    |            |               |        +-->|  DECIDE   |
    |       +----------+        |            +-----------+
    +-------+   ACT    |<------+-------------|
            +----------+
```

Orient does not just feed Decide. It reshapes how you Observe next time. It builds
implicit guidance that can bypass deliberate decision-making entirely -- the way an
experienced pilot reacts before consciously thinking. Each cycle sharpens the model.
Each outcome updates your beliefs.

This is what separates OODA from a state machine or a scheduled script.
A cron job runs the same logic forever. An OODA loop evolves.

---

## Why OODA for AI Agents?

Most automation is lobotomized. It runs the same script on day 100 as on day 1.
It does not know what worked last week. It does not adjust when the environment
changes. It has no memory, no judgment, no model of the world it operates in.

OODA-loop is different because of **Orient** -- the phase where the agent builds
and updates its world model. After each cycle, the agent knows which domains need
attention (confidence scores), what patterns are emerging across observations
(cross-domain correlation), and what its past decisions led to (outcome tracking).

**The Adaptive Lens.** Observe skills are not static. Each cycle, the engine
analyzes observation results and proposes refinements to a per-domain `lens.json`
-- learned thresholds, focus items, discovered signals. New learning starts
tentative (confidence 0.3) and only activates after repeated validation (0.6).
Disconfirming evidence kills bad learning twice as fast as confirming evidence
builds it (+0.1 vs -0.2). By cycle 50, the agent catches patterns that cycle 1
had no idea to look for. Anti-fragile by design.

**3-tier memory.** Working memory (last 20 decisions) flows into weekly episode
summaries (52 weeks), which distill into permanent principles. The agent does not
just remember what happened -- it learns what matters.

Cron gives you a heartbeat. OODA-loop gives you a brain.

---

## Language & Framework Agnostic

OODA-loop is not a code generator tied to a specific stack. It is a **thinking
framework for AI** -- a structured way for the agent to observe, learn, and act.
The skills read your test output, check your endpoints, and score your issues.
The language you write in does not matter.

Any project with a test command, a git repo, or an HTTP endpoint can use it.
Web servers, CLI tools, libraries, monorepos -- the loop adapts to what you have.

**Verified across:**

| Stack | Project Type | Test Framework |
|-------|-------------|---------------|
| Python + FastAPI | REST API | pytest + pytest-cov |
| Go + net/http | URL shortener | go test |
| Node.js | CLI tool (no server) | Jest |

---

## Who is this for?

You are running a side project. Maybe it is a SaaS with a handful of paying
users, maybe it is an API you launched last month and forgot to check on. You
have a day job, or three other projects, or both. The health endpoint has been
returning 503 for six hours and you have no idea because you were asleep.

You do not have a DevOps team. You do not have on-call rotations or a PagerDuty
subscription. You have a git repo, a CI pipeline you set up once, and a vague
sense that things are probably fine.

OODA-loop is for you.

It is for the indie hacker shipping a product in a competitive market who needs
to move faster than their monitoring setup allows. It is for the two-person
startup where one founder writes code and the other writes copy, and neither has
time to review the backlog every morning. It is for the developer who wants their
project to grow and improve even when they are not looking at it.

This is not an enterprise platform. There is no dashboard SaaS, no seat-based
pricing, no sales call. It is not a CI/CD pipeline, not a monitoring service,
and not an auto-coding agent that writes your app for you. It is a framework
that lives in your repo, runs inside Claude Code, and earns trust one cycle
at a time.

---

## What happens when you run it

**Day 1.** You clone the repo and run the setup wizard. It detects your stack,
suggests domains to monitor, and writes your config. The first `/evolve` is
observe-only -- it looks, writes down what it found, and moves on.

```
/ooda-status

Cycle: #1  |  Level: 0 (Just watching)
Domains scanned: 3
  service_health    —        score 336.29  confidence 0.70
  test_coverage     —        score 168.29  confidence 0.70
  backlog           12 open  confidence 0.70
  backlog           —        score 134.69  confidence 0.70
Actions: 0 pending  |  PRs: 0
HALT: inactive
```

That is all. It looked. It learned nothing yet. You read it and move on.

**Day 3.** Three cycles in. Confidence scores are climbing as observations confirm
each other. You bump the level to 1. The loop now watches two domains and tells
you when coverage drops. Still no code changes -- just sharper observations.

**Day 7.** Level 2. Full backlog tracking, issue scoring, reports. The Adaptive
Lens has started learning -- health checks that always pass get deprioritized,
flaky test patterns get flagged sooner. OODA-loop suggests you set up market
analysis: `/ooda-skill create scan-market`.

**Day 30.** Level 3. The loop is designed to pick the highest-scoring backlog
item, write code, run your tests, and open a draft PR. PRs are small -- 20
files max, 500 lines max, enforced by config. You review it over coffee. The
loop runs at 3am, notices what you would notice at 9am, and acts on it before
you wake up.

---

## How It Works

Every `/evolve` run executes one complete OODA cycle:

1. **Safety** -- Check HALT file. Check cycle interval. Acquire lock (auto-expires after `lock_timeout_minutes`).
2. **Observe** -- Read all domain states, GitHub PR/issue status, external signals. Load the Adaptive Lens.
3. **Orient** -- Detect patterns, update confidence scores, sync action queue with PR outcomes, build a world model summary.
4. **Decide** -- Score every domain. Apply urgent signals and goal contributions. Pick the winner. Gate on confidence threshold. **Implicit Guidance**: critical alerts or stable high-confidence patterns bypass scoring and feed Orient directly into Act (Boyd's Orient-to-Act shortcut).
5. **Act** -- Execute the winning skill. Run chain if confidence is high enough. Re-check HALT before each chain step. Handle PR risk tiers (auto-merge / manual deploy / human review).
6. **Reflect** -- Update skill gaps, write memos, extract actions, update the Adaptive Lens, cascade memory.

Domain scoring: `score = (hours_since_last x weight) + urgent + (goals x 0.3) + (confidence x 0.2) + memo_adjustment`

See [CONCEPTS.md](CONCEPTS.md) for the full glossary, architecture diagram, and formula details.

---

## Built-in Skills

Five domain skills, four wizards, and the orchestrator:

| Command | Phase | What it does |
|---------|-------|-------------|
| `/scan-health` | Observe | Check health endpoints, detect anomalies |
| `/check-tests` | Detect | Run tests, track coverage trends |
| `/plan-backlog` | Strategize | Score GitHub issues by RICE |
| `/run-deploy` | Execute | Trigger deployment workflow |
| `/dev-cycle` | Support | Full implementation pipeline |
| `/ooda-setup` | Wizard | 3-step project configuration |
| `/ooda-config` | Wizard | View and modify settings |
| `/ooda-status` | Wizard | Status dashboard |
| `/ooda-skill` | Wizard | Create, disable, enable domain skills |
| `/evolve` | Meta | Run one full OODA cycle (or `/loop 4h /evolve`) |

**Domain status.** Each domain in config is `active` (runs every cycle), `available`
(configured but skill not yet created), or `disabled` (opted out). Available skills
are skipped silently -- no errors, no interruptions.

**Skill generation.** Run `/ooda-skill create scan-market` and answer 3-5 questions
about your project. The wizard generates a complete, project-specific SKILL.md with
Adaptive Lens integration. Templates for market research, UX auditing, and competitor
monitoring are included in `templates/skill-generators/`.

---

## Progressive Complexity

Start at Level 0. Move up when you trust the observations.

| Level | Name | What happens |
|-------|------|-------------|
| 0 | Just watching | 1 domain. Observe only. No PRs. |
| 1 | Watching + testing | 2 domains. Coverage tracking added. |
| 2 | Full observation | All domains. Draft PRs (human merges). Reports, scoring, lens learning. |
| 3 | Autonomous | Implementation enabled. Full PRs. Auto-merge for low-risk changes. |

Skipping levels (e.g. 0 to 3) enforces a 3-cycle observe-only cooldown at the new level before any action.

```
/ooda-config level 2
```

---

## Safety

OODA-loop is safe by default. Level 0 cannot create PRs. Level 3 requires deliberate opt-in.

- **HALT file** -- `touch agent/safety/HALT` stops everything instantly. Delete to resume. Re-checked before every destructive action (push, merge, deploy) during a cycle.
- **Protected paths** -- `agent/safety/*`, `skills/evolve/*`, `agent/contracts/*` cannot be modified by the agent. It cannot rewrite its own rules.
- **Confidence gate** -- Actions below 0.6 confidence are skipped or downgraded.
- **PR limits** -- Max 20 files, 500 lines per PR. Enforced in config.
- **First cycle observe-only** -- No action on the first run. Just observation.
- **Skill allowlist** -- Only registered skills can be invoked.
- **Lock timeout** -- Concurrent execution lock auto-expires after 30 minutes (configurable via `lock_timeout_minutes`). Stale locks from crashes are cleaned up automatically.
- **Cost ledger** -- Daily API cost tracked in `cost_ledger.json`. Hard stop at `cost.daily_limit_usd` ($10 default), warning at 80%. Resets daily at 00:00 UTC. Missing ledger = fail-closed.
- **Adaptive Lens safety** -- Bad learning decays 2x faster than good learning grows. Lens corruption falls back to base behavior.

See [SECURITY.md](SECURITY.md) for the full threat model and safety architecture.

---

## Configuration

Copy `config.example.json` to `config.json`. Key sections: `project` (name, locale,
timezone), `domains` (what to monitor, weights, skills, status), `safety` (HALT path,
PR limits, allowlist, `lock_timeout_minutes`), `confidence` (initial value, merge boost,
reject penalty), `scoring` (formula parameters), `progressive_complexity` (current level),
`signals` (urgent signal thresholds), `memory` (retention, decay, action queue decay),
`notifications` (Telegram via `$ENV_VAR`), `cost` (daily limit, warning threshold).

**Cost estimate.** Each observe cycle costs ~$0.02-0.05 in Claude API usage.
Implementation cycles (Level 3) cost ~$0.05-0.10. At 30-minute intervals, that
is roughly $1-2/day for continuous Level 2 operation. The default daily cap is
$10 (`cost.daily_limit_usd`).

See [config.example.json](config.example.json) for the complete annotated schema.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `[SKIP] Another evolve cycle is running` | Stale lock. Remove `agent/state/evolve/.lock` (auto-cleaned after 30 min). |
| `[SKIP] Too soon` | Wait for `min_cycle_interval_minutes` (default 30) to elapse, or add a critical alert to bypass. |
| `All scores below 0.5` | No domain needs attention yet. Normal on early cycles. |
| Confidence stuck at 0.7 | Initial value. Merge or reject a PR to move it. |
| `/evolve` skips a domain | Check its `status` in config -- `available` means the skill has not been created yet. Run `/ooda-skill create <name>`. |
| Cost limit hit | Check `agent/state/evolve/cost_ledger.json`. Resets at 00:00 UTC, or raise `cost.daily_limit_usd`. |

---

## Contributing

Contributions welcome: new domain skills, scoring improvements, integrations, and
documentation. See [CONTRIBUTING.md](CONTRIBUTING.md) for the skill authoring guide,
3-tier contribution model (Skills / Docs / Core), and code style rules.

---

## License

MIT -- see [LICENSE](LICENSE)
