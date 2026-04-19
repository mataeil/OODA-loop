# OODA-loop Scenario Fixtures

Each subdirectory here is a self-contained scenario fixture for testing a
specific evolve behavior. Use these alongside `/evolve --dry-run` to verify
v1.2.0+ Orient layer changes without modifying any live state.

These fixtures sit under `tests/` (not `sandbox/`) because `sandbox/` is
gitignored for the full validation projects (markd, taskapi, jsonlint…);
scenario fixtures need to be tracked so downstream contributors can reproduce
the expected behavior.

## How to use

```bash
# From the fixture's seed/ directory, run /evolve --dry-run and compare
# the printed score table, memo operations, and proposed state diff against
# the fixture's README.md "Expected dry-run output" section.
```

Fixtures are seed-state snapshots, not full projects. They exist purely to
exercise evolve logic paths that require specific preconditions (empty
principles, starved domains, stale cost ledgers, missing lens files, etc.).

## M2 (Learning-loop activation)

- `principles-extraction/` — verifies the relaxed Jaccard trigger and
  cluster fallback actually produce principles.
- `memo-intervention/` — verifies auto-starvation and monopoly-breaker
  interventions are written and influence next-cycle selection.
- `cost-ledger-autopatch/` — verifies 6-C8 integrity gate patches missing
  entries and emits a `learning_loop_break` skill_gap.
- `lens-pre-init/` — verifies Step 1-A lens pre-init creates files for all
  active domains before any observe skill runs.

## M3 (Primitive promotions, added later)

- `season-mode-toggle/`
- `rotation-cursor/`
- `active-context-read/`
