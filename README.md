# OODA-loop

**Your side project just got an operations team.**

[한국어](README.ko.md) | English

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude-Code-blue)](https://claude.ai/code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

OODA-loop is an autonomous AI agent framework for Claude Code that watches your
codebase, learns what matters, and acts on it -- while you sleep. Built on Boyd's
OODA cycle (Observe, Orient, Decide, Act), it gives a solo developer the operational
awareness of a team ten times their size. Extracted from a production system that ran
14 autonomous cycles without human intervention. Ships with progressive autonomy levels,
confidence thresholds, a single-file kill switch, and protected paths the agent can
never rewrite.

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
pricing, no sales call. It is a framework that lives in your repo, runs inside
Claude Code, and earns your trust one cycle at a time.

---

## What happens when you run it

**Day 1.** You clone the repo, copy the example config, and run the setup wizard.

```bash
git clone https://github.com/mataeil/OODA-loop.git
cd OODA-loop
```

```
/ooda-setup
```

It detects your stack, suggests domains to monitor, and writes your config.
You run your first cycle:

```
/evolve
```

Nothing changes. The first cycle is observe-only by default. OODA-loop scans
your configured domains and writes what it found. You check the output:

```
/ooda-status
```

```
Cycle: #1  |  Level: 0 (Just watching)
Domains scanned: 3
  service_health    OK       confidence 0.50
  test_coverage     87.2%    confidence 0.50
  backlog           12 open  confidence 0.50
Actions: 0 pending  |  PRs: 0
HALT: inactive
```

That is all. It looked. It wrote down what it saw. You read it and move on.

**Day 3.** Three cycles in. Confidence scores are climbing as observations confirm
each other. You bump the level to 1. The loop now watches two domains and tells
you when coverage drops. Still no code changes -- just sharper observations.

**Day 7.** Level 2. Full backlog tracking, issue scoring, reports. The Adaptive
Lens has started learning -- health checks that always pass get deprioritized,
flaky test patterns get flagged sooner. OODA-loop suggests you set up market
analysis: `/ooda-skill create scan-market`.

**Day 30.** Level 3. The next cycle, OODA-loop picks the highest-scoring backlog
item, writes code, runs your tests, and opens a draft PR. The PR is small -- 20
files max, 500 lines max, enforced by config. You review it over coffee. The loop
ran at 3am, noticed what you would have noticed at 9am, and acted on it four
hours before you woke up.

You still have the HALT file. You have not needed it.

---

## How It Works

Every `/evolve` run executes one complete OODA cycle:

1. **Safety** -- Check HALT file. Check cycle interval. Acquire lock.
2. **Observe** -- Read all domain states, GitHub PR/issue status, external signals. Load the Adaptive Lens.
3. **Orient** -- Detect patterns, update confidence scores, sync action queue with PR outcomes, build a world model summary.
4. **Decide** -- Score every domain. Apply urgent signals and goal contributions. Pick the winner. Gate on confidence threshold.
5. **Act** -- Execute the winning skill. Run chain if confidence is high enough. Handle PR risk tiers (auto-merge / manual deploy / human review).
6. **Reflect** -- Update skill gaps, write memos, extract actions, update the Adaptive Lens, cascade memory.

Domain scoring: `score = (hours_since_last x weight) + urgent + (goals x 0.3) + (confidence x 0.2) + memo_adjustment`

See [CONCEPTS.md](CONCEPTS.md) for the full glossary, architecture diagram, and formula details.

---

## Built-in Skills

Five operational skills, three wizards, and a skill creation command:

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
| 2 | Full observation | All domains. Reports, scoring, lens learning. |
| 3 | Autonomous | Implementation enabled. Draft PRs. Auto-merge for low-risk changes. |

```
/ooda-config level 2
```

---

## Safety

OODA-loop is safe by default. Level 0 cannot create PRs. Level 3 requires deliberate opt-in.

- **HALT file** -- `touch agent/safety/HALT` stops everything instantly. Delete to resume.
- **Protected paths** -- `agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*` cannot be modified by the agent. It cannot rewrite its own rules.
- **Confidence gate** -- Actions below 0.6 confidence are skipped or downgraded.
- **PR limits** -- Max 20 files, 500 lines per PR. Enforced in config.
- **First cycle observe-only** -- No action on the first run. Just observation.
- **Skill allowlist** -- Only registered skills can be invoked.
- **Adaptive Lens safety** -- Bad learning decays 2x faster than good learning grows. Lens corruption falls back to base behavior.

See [SECURITY.md](SECURITY.md) for the full threat model and safety architecture.

---

## Configuration

Copy `config.example.json` to `config.json`. Key sections: `project` (name, locale),
`domains` (what to monitor, weights, skills, status), `safety` (HALT path, PR limits,
allowlist), `scoring` (formula parameters), `progressive_complexity` (current level),
`signals` (urgent signal thresholds), `memory` (retention, decay), `notifications`
(Telegram via `$ENV_VAR`), `cost` (daily limit).

See [config.example.json](config.example.json) for the complete annotated schema.

---

## Contributing

Contributions welcome: new domain skills, scoring improvements, integrations, and
documentation. See [CONTRIBUTING.md](CONTRIBUTING.md) for the skill authoring guide,
3-tier contribution model (Skills / Docs / Core), and code style rules.

---

## License

MIT -- see [LICENSE](LICENSE)
