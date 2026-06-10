# OODA-loop
[한국어](README.ko.md) | English

**It watches your side project at 3am, opens a small PR for your morning review, and re-aims itself from which ones you merge.**

Here's what it prints at the end of every cycle — the one artifact no cron job, round-robin loop, or skills pack can produce, because of the **LEARN** line, where it re-orients from *your* merge/reject calls:

<p align="center">
  <img src="docs/demo.gif" alt="One OODA-loop cycle: it opens a PR, you reject it, and the Adaptive Lens re-aims a threshold — 'You rejected it. It re-aimed.'" width="820">
</p>

Re-render the latest card any time with `/ooda-status --share`.

<details>
<summary>Prefer plain text? The same Cycle Card.</summary>

```
┌─ fwd.page · OODA-loop cycle #152 ────────────── 2026-04-14 03:14 UTC ─┐
│                                                                        │
│  OBSERVE   4 domains · test_coverage dropped 91% → 84% overnight       │
│  ORIENT    flaky-retry pattern confirmed (3rd time); coverage now      │
│            the most stale + highest-signal domain                      │
│  DECIDE    test_coverage won (score 11.3) · confidence 0.74 · gate ✓   │
│  ACT       opened PR #29 — "wrap flaky network suite in retry"         │
│            └ Risk Tier 1 · 2 files · draft — you merge                 │
│  LEARN  🔭 you rejected PR #28 yesterday →                             │
│            service_health confidence 0.74 → 0.54 ↓                     │
│            (reject −0.2, 2× faster than a merge's +0.1)                │
│         🔭 lens re-aimed → flaky-alert threshold 0.30 → 0.25           │
│  COST      +$0.04 · $0.38 today · hard cap $10 (auto-HALTs on breach)  │
│                                                                        │
│  HALT: inactive · Level 2 (Full observation)                          │
└────────────────────────────────────────────────────────────────────────┘
```
</details>

An autonomous **operations** layer for your live side project — it watches, decides what matters, and proposes small PRs you approve. **You stay in command:** it proposes, you merge or reject, every change is an isolated one-click-revertible PR, and it re-aims from your calls. *(Auto-merge is **opt-in and off by default** — every change is a Draft PR you merge until you run `/ooda-config auto-merge on`, which lets it merge only low-risk PRs with a post-merge auto-revert. See "Auto-merge status".)*

**The receipts** *(author-measured — run your own pilot)*: two real projects have run it continuously — **[fwd.page](https://fwd.page)** (a live URL shortener) for **152 cycles → 28 PRs, 24 merged (86%)**, and **Lynceus** (parliamentary-audit automation) for **119 cycles at observe level (no PRs yet)**. It also ran clean across **9 language/framework stacks** in sandbox (60 cycles, 36 PRs, no compile or test failures observed).

**It can't give you a $6,000 surprise.** `touch agent/safety/HALT` stops everything instantly. Every change is a small PR (max 20 files / 500 lines) you can revert in one click. It can't touch its own safety rules. Typical cost is ~$1–2/day, and a **hard daily cap (default $10) auto-creates a HALT** the moment it's crossed. The first cycle, and Level 0, only watch.

> **Requires [Claude Code](https://claude.ai/code).** All commands (`/ooda-setup`, `/evolve`, etc.) are Claude Code slash commands.

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
/ooda-status --share  # the shareable Cycle Card
```

`/ooda-setup` creates `config.json` and `agent/state/` in your project. Your source code is never modified during observation. **Nothing changes until you say so.** Level 0 just watches. Level 3 opens PRs.

---

## How is this different?

You've seen a lot of "autonomous agent" projects. Here's the honest map.

| | What it does | The difference |
|---|---|---|
| **Code-gen agents** (Aider, Cline, OpenHands, Devin) | Write code on command, stop at the PR | OODA-loop decides *what* to work on and keeps your **live** project running — operations, not one-shot code-gen |
| **Round-robin loops** (continuous-claude / "Ralph" loops) | Re-run the same prompt forever | OODA-loop **re-orients**: per-domain confidence updated by your merge/reject calls, RICE-prioritized backlog, learned thresholds — it doesn't reinitialize every loop |
| **Self-rewriting agents** (ouroboros-class) | Rewrite their own source for spectacle | OODA-loop is the deliberate opposite: a **HALT file, protected paths, cost ledger, and observe-only first cycle** — plus 271 real production cycles those projects don't have |
| **Config / skills packs** | Configure the agent for coding | OODA-loop **operates** a deployed project with progressive Levels 0→3 and a learning loop |

The one thing none of them shows is the **LEARN** line above. That's the wedge.

---

## How the "learning" actually works

We're going to be straight with you, because you read code.

OODA-loop's learning is **heuristic outcome-driven re-orientation**, *not* machine learning. There is no gradient, no fitness function, no trained model. What actually happens:

- **Confidence** per domain moves with your decisions: **+0.1 when you merge** a PR, **−0.2 when you reject** one. Bad bets are punished twice as hard as good bets are rewarded.
- **The Adaptive Lens** (`agent/state/{domain}/lens.json`) accumulates learned thresholds, focus items, and discovered signals. New learning starts tentative (confidence 0.3) and only activates after repeated confirmation (0.6). **Disconfirming evidence decays it 2× faster than confirming evidence builds it** — so wrong lessons die fast. Each change is appended to a `lens_changelog.json` so the LEARN line is always auditable.
- **3-tier memory**: the last 20 decisions cascade into weekly episode summaries, which distill into permanent principles.
- **Verbal self-critique** ([Reflexion](https://arxiv.org/abs/2303.11366)-style): each decision cycle the agent writes a one-line lesson — what it did, and whether the outcome matched what it expected — stores it in `reflections.json`, and re-injects relevant past lessons into the next Orient. It's text the model re-reads, not training.

Think of it as **proto-evolution**: an explicit, inspectable control loop that adjusts from real outcomes via verbal self-correction — not RL, not gradient updates. We say "re-aimed," "adjusted," "deprioritized" — never "trained" or "learned weights." Every number is in plain JSON you can read and audit. That honesty *is* the point: a loop you can trust is a loop you can inspect.

---

## The OODA Loop (and why Orient matters)

A Korean-War F-86 pilot, John Boyd spent the next two decades working out why some pilots won dogfights. His answer — refined through the 1970s–90s, long after the cockpit — wasn't faster planes. It was a decision cycle, run continuously, each outcome updating the next: **Observe, Orient, Decide, Act**.

Boyd's real insight was **Orient** — and his actual diagram (in *The Essence of Winning and Losing*, 1995) is *not* four boxes in a circle. It's one large Orient block — genetic heritage, cultural traditions, previous experience, new information, analysis & synthesis — with **Implicit Guidance & Control arrows running *from* Orient *to* both Observe and Act**, so a well-oriented actor can observe and act almost simultaneously, bypassing explicit Decide. Orient is the loop's center of gravity: it shapes how you observe, decide, and act, and is reshaped by every outcome.

Most AI agents (ReAct / tool-calling loops) are structurally **Decide→Act with bolted-on memory** — they barely Orient and mostly don't learn between runs. OODA-loop puts the Orient phase first: each cycle it reviews PR outcomes, updates confidence, applies cross-cycle memos, detects patterns, and adjusts its world model.

> We implement the *spirit* of Boyd's Orient phase — outcome-driven re-orientation and an implicit fast-path (critical alerts bypass scoring). We do **not** claim to implement his full epistemology (Boyd's destruction-and-creation synthesis, the implicit cultural repertoire, a genetic-heritage analogue). For the real thing, read [Osinga, *Science, Strategy and War*](http://www.projectwhitehorse.com/pdfs/ScienceStrategyWar_Osinga.pdf) and [Richards' deconstruction](https://slightlyeastofnew.com/wp-content/uploads/2010/03/essence_of_winning_losing.pdf).

A cron job runs the same logic on day 100 as day 1. An OODA loop re-orients.

---

## What happens when you run it

**Day 1.** `/ooda-setup` detects your stack and writes your config. The first `/evolve` is observe-only — it looks, writes down what it found, prints a Cycle Card, and moves on.

**Day 3.** A few cycles in. Confidence scores climb as observations confirm each other. Bump to Level 1 — coverage tracking added, still no code changes.

**Day 7.** Level 2. Full backlog tracking, RICE scoring, reports — still no code changes (PRs unlock at Level 3). The Adaptive Lens has started learning — health checks that always pass get deprioritized, flaky patterns get flagged sooner.

**Day 30.** Level 3 (deliberate opt-in). It picks the highest-scoring backlog item, writes code, runs your tests, and leaves a PR + Cycle Card waiting for your morning — small by design (20 files / 500 lines max). By default every implementation change is a **Draft PR you review**; opt into low-risk auto-merge with `/ooda-config auto-merge on` and it merges small, green, non-protected changes itself — with a post-merge health check that auto-reverts on failure (see "Auto-merge status"). It watches at 3am, notices what you'd notice at 9am, and re-aims from what you merge or reject.

**Self-correction in the wild.** Across 60 sandbox cycles spanning 9 stacks, the agent opened 36 PRs with no compile or test failures observed. When one of its own changes caused a coverage regression, it *detected the drop, generated a corrective action ranked above every existing task, and fixed it the next cycle.* It observes the consequences of its own actions and adapts.

---

## How It Works

Every `/evolve` run executes one complete OODA cycle:

1. **Safety** — Check HALT file. Check cycle interval. Acquire lock (auto-expires).
2. **Observe** — Read all domain states, GitHub PR/issue status, external signals. Load the Adaptive Lens.
3. **Orient** — Detect patterns, update confidence from PR outcomes, sync the action queue, apply memos/interventions, build a world-model summary.
4. **Decide** — Score every domain. Apply urgent signals and goals. Gate on confidence. **Implicit Guidance**: critical alerts or stable high-confidence patterns bypass scoring (Boyd's Orient→Act shortcut).
5. **Act** — Execute the winning skill. Handle PR risk tiers (auto-merge / manual / human review). Re-check HALT before every destructive step.
6. **Reflect** — Update skill gaps, write memos, extract actions, update the Adaptive Lens, cascade memory.
7. **Cycle Card** — Render the shareable summary, including the one thing it learned. (Skipped in `--dry-run`.)

Domain scoring: `score = staleness + dampened_alert + (goals × 0.3) + (confidence × 0.2) + memo + balance_penalty`. Logarithmic staleness, an alert dampener, and an entropy balance penalty keep any one domain from monopolizing cycles. See [CONCEPTS.md](CONCEPTS.md) for the full glossary and formula details, and [CHANGELOG.md](CHANGELOG.md) for release notes.

---

## Built-in Skills

| Command | Phase | What it does |
|---------|-------|-------------|
| `/scan-health` | Observe | Check health endpoints, detect anomalies |
| `/check-tests` | Detect | Run tests, track coverage trends |
| `/plan-backlog` | Strategize | Score GitHub issues by RICE |
| `/run-deploy` | Execute | Trigger deployment workflow |
| `/dev-cycle` | Support | Full implementation pipeline |
| `/ooda-setup` | Wizard | 3-step project configuration |
| `/ooda-config` | Wizard | View and modify settings |
| `/ooda-status` | Wizard | Status dashboard (`--orient`, `--share`) |
| `/ooda-skill` | Wizard | Create, disable, enable domain skills |
| `/evolve` | Meta | Run one full OODA cycle (or `/loop 4h /evolve`) |

**Skill generation.** Run `/ooda-skill create scan-market`, answer 3–5 questions, and the wizard generates a complete, project-specific SKILL.md with Adaptive Lens integration. Templates for market research, UX auditing, and competitor monitoring ship in `templates/skill-generators/`.

---

## Progressive Complexity

Start at Level 0. Move up when you trust the observations.

| Level | Name | What happens |
|-------|------|-------------|
| 0 | Just watching | 1 domain. Observe only. No PRs. |
| 1 | Watching + testing | 2 domains. Coverage tracking added. |
| 2 | Full observation | All domains. Reports, scoring, lens learning. (PRs unlock at Level 3.) |
| 3 | Autonomous | Implementation enabled — autonomous **Draft PRs you review** by default; low-risk auto-merge is opt-in (`/ooda-config auto-merge on`). |

Skipping levels (e.g. 0 → 3) enforces a 3-cycle observe-only cooldown at the new level. `/ooda-config level 2`.

### Run it continuously (unattended operation)

One cycle is `/evolve`. Continuous operation is just `/evolve` on a schedule —
the safety rails are built for exactly this:

```bash
# inside a Claude Code session — recurring loop
/loop 4h /evolve

# or headless from cron / CI
0 */4 * * *  cd /path/to/project && claude -p "/evolve"
```

What makes unattended safe — and why the loop fails *stopped*, never runaway:

- **Overlap-proof** — a lock file skips concurrent runs; `min_cycle_interval_minutes` cleanly skips too-early ticks (and releases the lock).
- **Crash-proof** — a crashed cycle self-heals: the stale lock expires (`lock_timeout_minutes`, default 30), crash recovery resets the half-finished cycle, and the next tick proceeds. No manual cleanup.
- **Failure breaker** — `max_silent_failures` consecutive skill errors (default 3) auto-create a HALT.
- **Saturation breaker** — 15 fruitless observe-only cycles auto-create a HALT (warn at 5, boost at 10).
- **Cost breaker** — crossing the daily cap auto-creates a HALT; a corrupt cost ledger fails closed.
- **One switch** — every breaker converges on the same HALT file; nothing resumes until a human deletes it.

---

## Safety

Safe by default. Level 0 cannot create PRs. Level 3 requires deliberate opt-in.

- **HALT file** — `touch agent/safety/HALT` stops everything instantly. Re-checked before every destructive action (push, merge, deploy).
- **Protected paths** — `agent/safety/*`, `skills/evolve/*`, `agent/contracts/*` can never be modified or auto-merged. The agent cannot rewrite its own rules.
- **Confidence gate** — Actions below 0.6 confidence are skipped or downgraded.
- **PR limits** — Max 20 files, 500 lines per PR. Enforced in config.
- **Hard cost cap** — Daily API cost is tracked in `cost_ledger.json`. Crossing `cost.daily_limit_usd` ($10 default) **auto-creates a HALT**; warning at 80%. Resets 00:00 UTC. A missing ledger initializes at $0 (fresh install; gap-audited); a *corrupt* ledger fails closed (HALT).
- **Rollback** — Pre-action checkpoints (`enable_rollback`, also forced when auto-merge is on) snapshot HEAD + state before every action. When auto-merge is on, a failed post-merge health check **auto-reverts + HALTs**. For manual recovery, `/ooda-config rollback {cycle}` reverts the repo + state to any recorded checkpoint.
- **Adaptive Lens safety** — Bad learning decays 2× faster than good learning grows; lens corruption falls back to base behavior.

### Auto-merge status (honest)

Level 3 is **autonomous Draft-PR creation by default — you merge.** Auto-merge is a **separate opt-in** (`/ooda-config auto-merge on`; `safety.enable_auto_merge`, default `false`). When you turn it on, evolve merges **only low-risk PRs** on its own: non-protected paths, ≤ `auto_merge_max_files` (5) / `auto_merge_max_lines` (100), tests green — then runs a post-merge health check that **auto-reverts + HALTs** on failure. Anything larger or protected stays a Draft PR you merge. evolve re-checks every gate itself before merging (it doesn't trust dev-cycle's marker). Off by default because **you stay in command** unless you choose otherwise.

> **Verification note (honest):** the full Level-3 path is **verified live** in a throwaway repo — autonomous Draft-PR + reject→re-aim, and (with `enable_auto_merge: true`) a low-risk PR actually auto-merging while a large/protected one stays a Draft, plus a failed post-merge health check **auto-reverting + HALTing**. (The live run found and fixed a rollback bug: auto-merge uses `--squash` so the revert is a clean `git revert HEAD`.) See [TESTING.md](TESTING.md).

See [SECURITY.md](SECURITY.md) for the full threat model.

---

## Language & Framework Agnostic

OODA-loop is a thinking framework, not a code generator tied to a stack. The skills read your test output, check your endpoints, and score your issues — the language doesn't matter. **Verified across 9 environments:** Python + FastAPI, Python library, Go + net/http, Node + Express, Node CLI, TypeScript CLI, React + Vite, Rust, Bun + Hono.

---

## Production Validation

Two production deployments continuously feed real-world data back into the framework:

| Deployment | Domain | Cycles | PRs |
|------------|--------|--------|-----|
| [fwd.page](https://fwd.page) | URL shortener | 152+ | 28 (24 merged, 86%) |
| Lynceus | Parliamentary audit (국정감사) | 119+ | 0 (Level 2 — observe only) |

These projects are **reference data sources, not modified by the framework**. Every improvement they surface lands upstream so the next downstream project gets it for free. The v1.2.0 line distilled 271 production cycles: the Orient layer now actually learns (principles extraction, lens pre-init), cost-ledger integrity gating, and primitives promoted from production (season modes, active context, rotation). See [CHANGELOG.md](CHANGELOG.md).

> **On the numbers.** "86% merged" and the sandbox results are author-measured; the production cycle data is from the maintainer's own deployments. Run your own pilot at Level 1–2 for a week — that's the honest test, and we'd love your numbers. See **[TESTING.md](TESTING.md)** for exactly how the engine is verified (and what isn't yet).

---

## Configuration & Cost

`/ooda-setup` generates `config.json` automatically; edit via `/ooda-config` or directly. Key sections: `project`, `domains`, `safety`, `confidence`, `scoring`, `progressive_complexity`, `signals`, `memory`, `output` (Cycle Card on/off), `notifications` ($ENV_VAR only), `cost`.

**Cost.** Each observe cycle costs ~$0.02–0.05 in Claude API usage; implementation cycles ~$0.05–0.10. At 30-minute intervals that's roughly $1–2/day for continuous Level 2 — and the hard daily cap ($10 default) auto-HALTs if exceeded. See [config.example.json](config.example.json) for the annotated schema.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `[SKIP] Another evolve cycle is running` | Stale lock. Remove `agent/state/evolve/.lock` (auto-cleaned after 30 min). |
| `[SKIP] Too soon` | Wait for `min_cycle_interval_minutes` (default 30), or add a critical alert to bypass. |
| `All scores below 0.5` | No domain needs attention yet. Normal on early cycles. |
| Confidence stuck at 0.7 | At Level < 3, observation micro-adjustments apply automatically. At Level 3, merge or reject a PR. |
| `/evolve` skips a domain | Check its `status` in config — `available` means the skill isn't created yet (`/ooda-skill create <name>`). |
| Cost limit hit | Check `cost_ledger.json`. Resets 00:00 UTC, or raise `cost.daily_limit_usd`. |

---

## Contributing

Contributions welcome: new domain skills, scoring improvements, integrations, docs. See [CONTRIBUTING.md](CONTRIBUTING.md) for the skill authoring guide and 3-tier contribution model.

## Try it

```
/plugin marketplace add mataeil/OODA-loop
/plugin install ooda-loop
cd your-project && /ooda-setup
```

Give your side project an operator you stay in command of. Start at Level 0. It just watches.

## License

MIT — see [LICENSE](LICENSE)
