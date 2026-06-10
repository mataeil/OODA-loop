# E2E suite — isolated Docker verification of the autonomy rails

OODA-loop has no shipped binary: the canonical executor is **Claude interpreting
`skills/evolve/SKILL.md`**. So this suite does the strongest thing that is still
deterministic — it runs a **verbatim transcription of the spec's mechanical
rails** (`driver/engine.py`, every block cites its SKILL.md section) against a
**real filesystem, real git repos, real processes (including SIGKILL), and an
injected clock**, inside a fully isolated Docker container.

```bash
tests/e2e/run.sh           # build + run the isolated Docker suite
tests/e2e/run.sh --local   # identical suite directly on the host
```

CI runs both Tier 0 and this suite on every push/PR (`.github/workflows/e2e.yml`).

## The official test process (tier map)

| Tier | What | Where | When |
|------|------|-------|------|
| **0** | `tests/verify.py` — static fixture walkthrough + 4 deterministic references (38 checks) | host / container | every push/PR (CI) |
| **1** | **this suite** — 19 rail scenarios on real FS/git/processes/clock, isolated in Docker | Docker container | every push/PR (CI) |
| **2** | live Claude runs — the real `/evolve` slash command in a fresh session (Tier A core, Tier B/B+ Level-3 + auto-merge, soak) | throwaway project + real GitHub remote | human-triggered, per release gate (procedures in TESTING.md) |

## What Tier 1 covers (and Tier 0 can't)

- **Lock lifecycle** — created/released per cycle; a live lock blocks without
  being deleted; a **stale lock self-heals** into 0-C crash recovery.
- **Real crash** — a child process acquires the lock, gets SIGKILL'd, and the
  debris (lock + `cycle_in_progress`) is recovered with correct diagnostics
  (the crashed cycle is `cycle_count + 1`).
- **Breakers, end to end** — min-interval skip releases the lock; critical
  alerts bypass the interval; saturation warn@5 / boost@10 / HALT@15 with the
  4-A mid-cycle exit; `max_silent_failures` → HALT; every breaker converges on
  the HALT file and the next run **fails stopped**.
- **Cost ledger** — UTC daily reset, 6-C8 sequence-gap backfill, and
  **corrupt ⇒ fail-closed** (backup + HALT, never recreated at $0.00).
- **Real git (6-D)** — explicit staging (untracked junk never swept in), state
  committed per cycle, and the **#31 guard**: gitignored state warns loudly and
  skips instead of staging into the void.
- **State flow over weeks** — canonical `selected_*` decision-log keys,
  working-memory cap, weekly episodes generated **exactly once** per completed
  week (id-existence guard), action-queue hygiene (orphaned `in_progress`
  re-queued, `blocked` moved out of `pending[]`).

## Honest caveat

`driver/engine.py` is a *reference transcription*, not the engine — exactly like
`scripts/*.py` in Tier 0, just covering the stateful rails instead of pure
functions. It verifies that the **spec's logic is correct on the real
substrate** `/evolve` manipulates (files, locks, git, processes). Whether Claude
*follows* the spec is what Tier 2 live runs verify. When you change a rail in
`SKILL.md`, update the matching block here in the same PR — reviewers diff them
side by side.
