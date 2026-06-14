# OODA-loop × Claude Code — how the pieces compose

OODA-loop is **Claude-Code-exclusive**. That is a feature: instead of shipping a
scheduler, a daemon, or a goal-tracker, it *composes with the ones Claude Code
already has* (`/loop`, `/schedule`, `/goal`, hooks, subagents) and adds the one
thing they don't: a **stateful, measured, mission-driven OODA cycle** (`evolve`).

This page is the canonical design for that composition. Rule of thumb:

> **Claude Code provides the *cadence and the rails*. OODA-loop provides the
> *cycle, the memory, and the scorecard*.** Don't make OODA-loop re-implement a
> primitive Claude Code owns; wire `evolve` into it.

---

## The division of labor

| Concern | Owned by | OODA-loop's part |
|---|---|---|
| **When to run** (cadence) | `/loop` (in-session) · `/schedule`/routines (cloud) · Desktop scheduled tasks (local, unattended) | Nothing — you point one of these at `evolve` |
| **One cycle of work** | — | **`evolve`**: Observe→Orient→Decide→Act→Reflect, one cycle |
| **Drive a session to "done"** | `/goal` (Stop-hook convergence gate, per session) | `config.mission` is the *standing* objective `/goal` conditions can reference |
| **Cross-run memory** | git (commit per cycle) · subagent `memory:project` | **`agent/state/`** — the loop's decision log, confidence, episodes, outcomes |
| **Did it work?** | — | **Loop Scorecard** (`--scorecard`), Outcome Record, Cycle Card |
| **Stop everything now** | a `Stop`/`PreToolUse` hook | the **HALT file** the hook enforces (see `hooks/hooks.json`) |
| **Bounded blast radius** | permission modes, protected paths | size caps, opt-in auto-merge, cost ceiling |

`/loop`, `/goal`, and `/schedule` are *generic* — they re-run a prompt, gate a
session, or cron a clone. None of them accumulate per-domain confidence, score
outcomes, or re-orient from your merge/reject calls. That gap **is** OODA-loop.

---

## `/loop` vs `/schedule` vs `/goal` — which to reach for

### `/loop N /evolve` — interactive, in-session
The simplest driver. `/loop 4h /evolve` runs a cycle every 4h **while the session
is open**; it dies when you close the terminal and auto-expires after 7 days.
Best for: supervised runs, demos, "watch it for an afternoon." Minimum interval
1 minute. (Dynamic `/loop` — no interval — lets Claude self-pace; useful for
event-gated checks, less so for a fixed OODA cadence.)

### `/schedule` → routines — durable, cloud, unattended
For "run while I sleep, no machine open." Creates a cloud routine on Anthropic's
infra. **Minimum interval 1 hour.** Subscription-billed (no extra charge) with a
daily run cap; see [the billing notes](https://code.claude.com/docs/en/routines.md).
**Critical constraint: each run is a *fresh git clone of the default branch* with
no local state carried between runs.** OODA-loop already solves this — see
"State across cloud runs" below.

### `/goal` — the per-cycle convergence gate (composes with both)
`/goal` keeps Claude working until a separate evaluator model confirms a typed
condition, then clears itself. It is **single-session** (the condition is
restored on `--resume`, but it is not a cross-session mission). Use it to make
*one* evolve cycle truly finish:

```
/goal the evolve cycle completed: a decision was logged, outcome recorded, and state committed
```

`config.mission` is the **strategic, persistent** objective (it shapes every
Decide and the scorecard's goal/mission KPIs across all sessions). `/goal` is the
**tactical, per-session** gate. They stack: the mission says *where*, `/goal`
says *don't stop until this cycle lands there*.

### Recommended setups

```bash
# A) Supervised, interactive (start here)
/ooda-setup                      # capture mission + domains + a verifiable goal
/evolve                          # first cycle (observe-only)
/loop 4h /evolve                 # then let it run while you watch

# B) Unattended on your machine (Desktop scheduled task, 1m+ cadence)
#    point a local scheduled task at:  claude -p "/evolve"

# C) Durable cloud (no machine open) — /schedule → routine, 1h+ cadence
#    routine prompt:  /evolve   (state persists via git; see below)
```

> **Plugin vs symlink install changes the command name.** Installed as a plugin
> (`/plugin install ooda-loop`), skills are **namespaced**: use
> `/ooda-loop:evolve`, `/ooda-loop:ooda-status`, and `/loop 4h /ooda-loop:evolve`.
> Installed via `git clone … && install.sh` (symlinks into `~/.claude/skills/`),
> the **bare** names work: `/evolve`, `/ooda-status`. This page uses the bare
> form; prefix with `ooda-loop:` if you installed the plugin.

---

## State across cloud runs (the fresh-clone problem)

A cloud routine clones the default branch fresh every run — anything written to
local disk and not committed is gone next run. OODA-loop's design already fits:
**Step 6-D commits `agent/state/` every cycle** (state is *deliberately
versioned*, not gitignored — see issue #31). For cloud routines:

1. Let `evolve` commit `agent/state/**` each cycle (it does).
2. Point the routine at a branch the next run reads — either allow the routine to
   push to `main`/your default branch, or dedicate a `ooda/state` branch and have
   the routine clone/commit there. The decision log, confidence, episodes,
   outcomes, and scorecard inputs then survive across fresh-clone runs.
3. Cloud runs set `CLAUDE_CODE_REMOTE=true`; `evolve` and the HALT hook use it to
   recognize unattended context (no human to answer a prompt).

On a local machine (`/loop` or a Desktop scheduled task) the working directory is
reused, so state persists on disk *and* in git — no extra steps.

---

## The HALT kill-switch, enforced by a hook

Historically `touch agent/safety/HALT` worked only because every skill *politely*
checks for it at Step 0. OODA-loop now ships a **`PreToolUse` hook**
(`hooks/hooks.json`) that makes it deterministic: while the HALT file exists, the
hook blocks file-writing / shell / merge tools — so a runaway cycle is stopped at
the Claude Code level, not by skill cooperation. The hook allows commands that
*remove* the HALT file, so you (or the agent) can always resume. This works in
cloud routines too (plugin hooks run there; user-level `~/.claude` hooks do not).

See `hooks/hooks.json` and [SECURITY.md](../SECURITY.md).

---

## Subagents (optional, advanced)

`evolve` runs cycles in the main thread today. For heavy isolation you can run a
cycle as a subagent with `isolation: worktree` (parallel-safe file edits) and
`memory: project` (a persistent `.claude/agent-memory/` that complements
`agent/state/`). This is optional; the default in-thread cycle is simpler and is
what the test tiers cover.

---

## Anti-patterns (don't do these)

- ❌ Building a scheduler into `evolve`. Use `/loop` or `/schedule`.
- ❌ Using `/goal` as the project mission. It's per-session; the mission lives in
  `config.mission`.
- ❌ Relying on `~/.claude/settings.json` hooks for cloud routines — they don't
  run there. Ship enforcement in the plugin's `hooks/hooks.json`.
- ❌ Gitignoring `agent/state/` — cloud runs (and your own history) lose the
  loop's memory. State is versioned on purpose.
