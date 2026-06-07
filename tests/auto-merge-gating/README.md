# Fixture: auto-merge-gating

Verifies the **auto-merge eligibility gate** (evolve 4-C / dev-cycle) — the
safety-critical decision of whether evolve may merge a PR on its own. Auto-merge
is **opt-in** (`safety.enable_auto_merge`, default `false`) and **low-risk only**.

## Setup

`seed/config.json` is opted in (the riskiest config): Level 3,
`enable_auto_merge: true`, `auto_merge_max_files: 5`, `auto_merge_max_lines: 100`,
standard `protected_paths`. The gate must STILL refuse anything that isn't small,
non-protected, ready, and green.

## Expected gate decisions (Step 4-C unit)

> **Fixture type: gate unit.** `verify.py` runs `scripts/auto_merge_gate.eligible()`
> — a deterministic reference for the evolve 4-C gate — against synthetic PRs.

| PR | Decision |
|----|----------|
| 1 file, +3/−1, non-protected, ready, green | ✅ **auto-merge** |
| touches `skills/evolve/SKILL.md` (protected) | ❌ hold (protected path) |
| 6 changed files (> 5) | ❌ hold (too many files) |
| +200 lines (> 100) | ❌ hold (too many lines) |
| draft | ❌ hold (draft) |
| tests red | ❌ hold (not green) |

And with `enable_auto_merge: false` (the default), **every** PR holds — auto-merge
never fires unless explicitly opted in.

Run the reference directly: `python3 scripts/auto_merge_gate.py tests/auto-merge-gating/seed/config.json`
