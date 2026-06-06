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

## What is NOT yet covered (the honest gap)

The remaining gate before tagging a **stable `1.2.0`** (it is currently
`v1.2.0-beta`) is a clean, **independent, live multi-cycle `/evolve` run** on the
corrected fixtures — i.e. actually invoking `/evolve` in a real Claude Code
session (`cd` into a sandbox project), over several cycles, and diffing the
console output + written state against the fixture expectations. This exercises
the full Observe→Orient→Decide→Act→Reflect→Cycle-Card path end-to-end, including
the Reflect/Act steps that `--dry-run` and the static walkthrough do not run.

That run is deliberately deferred to a dedicated session: invoking `/evolve` from
the framework repo itself would mutate OODA-loop's *own* `agent/state/`, so it
must be done with the working directory set to a throwaway sandbox project.

## Adding a fixture

1. Create `tests/<name>/seed/` with the minimal state (and a `config.json` if it's
   a full-cycle/config fixture).
2. Write `tests/<name>/README.md` with Setup + Expected output (mark dry-run vs
   full-cycle).
3. Add a `check_<name>(r)` function in `tests/verify.py` and register it in
   `main()`. Prefer asserting concrete seed facts and, where possible, drive a
   reference in `scripts/` for objective output checks.
