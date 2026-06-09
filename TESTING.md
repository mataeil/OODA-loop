# Testing & Verification

OODA-loop's engine (`skills/evolve/SKILL.md`) is a markdown specification executed
by Claude — there is no compiled binary. So "testing" here means: **is the spec
internally consistent, and does it produce the documented behavior from real
on-disk state?** This page documents how that's verified, honestly including what
is *not* yet covered.

## Run it

```bash
python3 tests/verify.py        # static fixture walkthrough — exits 0 iff all pass
```

Current status: **31 checks, 0 failures.**

## What's verified, and how

### 1. Static fixture walkthrough — `tests/verify.py`

Each fixture under `tests/<name>/` ships a `seed/` (real state JSON + sometimes a
config) and a `README.md` describing the expected behavior. `verify.py` asserts
the seed is internally consistent with the `evolve` logic the fixture exercises —
the trigger conditions, thresholds, and (where deterministic) the resulting
ordering. It does **not** invoke `/evolve`; it is a fast, semantic walkthrough.

### 2. Deterministic reference implementations — `scripts/`

Two side-effect-free Python references re-derive engine outputs from real state so
they can be checked objectively (not just by eye):

- **`scripts/render_cycle_card.py`** — implements the Step 7 Cycle Card data
  sourcing + LEARN-line priority + graceful degradation + config-driven level
  name. `verify.py` runs it on the `cycle-card` fixture and asserts the rendered
  card contains the reject→re-aim LEARN line, the PR number, and the level name.
- **`scripts/dryrun_score.py`** — implements the Step 3-A Decide scoring formula
  (logarithmic staleness + season `weight_overrides` + confidence term).
  `verify.py` runs it on `season-mode-toggle` to assert the overrides actually
  flip the winner (default → `service_health`, preparation → `backlog`).

These references are *checks*, not the engine. The canonical executor is Claude
running `SKILL.md`; the references exist to make the documented behavior falsifiable.

### 3. Fixture taxonomy (important)

- **Step-unit fixtures** (state-only seed, *no* `config.json`):
  `memo-intervention`, `principles-extraction`, `cost-ledger-autopatch`. These
  assert a single Step's logic given a seeded state (e.g. Step 5-C writes the
  intervention; Step 6-C8 backfills the ledger gap). They are **not** full-cycle
  runs — don't trace Observe/Decide scoring against them.
- **Config fixtures** (include a `config.json`): `lens-pre-init`,
  `season-mode-toggle`, `rotation-cursor`, `active-context-read`, `cycle-card`.
  These can be traced as (partial) full cycles; `--dry-run` shows the
  Observe/Decide portion (it exits at Step 3-H before Act/Reflect).

Each fixture README marks which output is `--dry-run`-visible vs full-cycle.

### 4. Sandbox + production (author-measured)

Beyond the unit fixtures, the engine has run across a 9-stack sandbox (60 cycles,
36 PRs, no compile/test failures observed) and two of the maintainer's own live
projects (fwd.page 152 cycles / 86% merge; Lynceus 119 observe-only). These are
*author-measured*, not third-party audited — see the README "On the numbers" note.

### 5. Controlled live engine run

Beyond static checks, the engine's core loop has been exercised **live on a real
project** — a throwaway Python package whose unittest suite was genuinely run each
cycle, with state read/written per `SKILL.md` (explicit paths; Level 1, no PRs):

| Cycle | Real test result | Engine reaction | Cycle Card |
|------|------------------|-----------------|------------|
| 1 | 2/2 pass | confidence 0.70 init; lens initialized | observe-only |
| 2 | **1/2 fail** (real regression) | status → degraded; confidence **+0.03 → 0.73**; lens learns a regression signal | alert + LEARN: lens re-aimed |
| 3 | fix → 2/2 pass | confidence **+0.02 → 0.75**; lens signal **decays 0.30→0.10**; cycle-2 lesson recalled + applied | recovery + LEARN: lens re-aimed 0.3→0.1 |

This verified, end-to-end, that Observe → Orient → Decide → Reflect → Cycle Card
react to **real, changing** outcomes: the confidence trajectory, the Adaptive Lens
learning-then-decaying a signal, the Reflexion loop closing (a prior lesson
recalled and marked `applied`), and the cost ledger accumulating ($0.02→$0.06).

**Method caveat (honest):** this run was *driven by Claude executing the spec
with explicit file paths* (the normal way `/evolve` runs, but pointed at a
sandbox instead of relying on the session CWD). It exercised Levels 0–1
(observe/test). It did **not** exercise the Level-3 Act path (autonomous PR
creation / auto-merge / rollback), which needs a GitHub remote.

## Coverage status (v1.2.0)

Levels 0–3 are verified end-to-end — the static suite + controlled runs +
**independent fresh-session live runs** (Tier A in a sandbox; Tier B / B+ in a
throwaway GitHub repo — each a separate Claude Code session running the `/evolve`
slash command against a real remote). The two earlier gaps are now closed:

1. **Fully-independent invocation — done.** Tier A/B/B+ were fresh sessions whose
   CWD was the target project, invoking `/evolve` itself over multiple cycles
   (not this framework repo, which would commit its own state).
2. **The Level-3 Act path — exercised live (Tier B / B+, throwaway repo, 2026-06).**
   A fresh Level-3 run against a real GitHub remote produced this result:
   - ✅ **Autonomous PR creation works.** `dev-cycle` selected the top-RICE
     action, branched, fixed `src/calc.py`, ran the suite (green), and opened a
     real PR — no human prompt.
   - ✅ **reject → re-aim works.** Closing the PR drove `implementation`
     confidence 0.70 → 0.50 (reject −0.2, the asymmetric 2× of a merge's +0.1)
     and re-aimed the lens; the Cycle Card LEARN line reported it.
   - ✅ **Kill-switch / cost cap / protected paths / checkpoints** all behaved.
   - ⚠️ **Auto-merge did NOT happen in that run** — at the time it was unreachable
     (dev-cycle hard-wired to Draft / Risk Tier 3; `gh pr view` →
     `isDraft:true, mergedAt:null`; `main` had zero auto-merged commits). That
     finding is what drove the **opt-in auto-merge implementation** below.

   Conclusion: Level 3 autonomous Draft-PR creation + reject→re-aim are **verified
   live**. Auto-merge was then **implemented as a low-risk opt-in** (see next).

### Auto-merge — live-verified (Tier B+, throwaway repo, 2026-06)

The opt-in low-risk auto-merge path was exercised end-to-end against a real
GitHub remote with `safety.enable_auto_merge: true` at Level 3:

| Test | Result |
|------|--------|
| **A** low-risk green change | ✅ PR auto-merged (`isDraft:false → MERGED`, fix landed on `main`, no human click) |
| **B1** oversize (6 files) | ✅ held — Draft, 4-C refused (changedFiles > 5) |
| **B2** protected path | ✅ blocked — no file, no PR, `main` unchanged |
| **C** failed post-merge health | ✅ (after fix) auto-reverts + HALTs |
| **D** `/ooda-config rollback {cycle}` | ✅ (after fix) reverts repo + state |

**A rollback bug was found and fixed during this run:** auto-merge originally used
`gh pr merge --merge` (a 2-parent merge commit), but 4-C2 / Step R reverted with
`git revert` *without* `-m` → it errored on the merge commit and left `main`
half-reverted. Fix: auto-merge now uses **`--squash`** (linear `main`), so
`git revert HEAD` is a clean one-liner. C was re-verified green after the fix.

So Levels 0–3 — including opt-in low-risk auto-merge with working auto-revert and
manual rollback — are now verified (static suite + controlled + live throwaway
runs). The default (auto-merge off) is unchanged and fully verified.

## Adding a fixture

1. Create `tests/<name>/seed/` with the minimal state (and a `config.json` if it's
   a full-cycle/config fixture).
2. Write `tests/<name>/README.md` with Setup + Expected output (mark dry-run vs
   full-cycle).
3. Add a `check_<name>(r)` function in `tests/verify.py` and register it in
   `main()`. Prefer asserting concrete seed facts and, where possible, drive a
   reference in `scripts/` for objective output checks.
