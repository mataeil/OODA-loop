# Fixture: cost-ledger-autopatch

## Purpose

Verify that evolve Step 6-C8 Cost Ledger Integrity Gate auto-patches a missing
entry AND emits a `skill_gaps` record of type `learning_loop_break`. This
guards against the production pattern observed in fwd.page where
`cost-tracker.json` received no new entries for 13 consecutive days while
cycles continued to run.

## Setup

Seed state:

- `state.json` → `cycle_count: 42`.
- `cost_ledger.json` → last entry is `cycle_id: 39` (3 cycles behind).
- `skill_gaps.json` → empty.

## Expected dry-run output

```
[Reflect] ⚠ cost_ledger missing entry for cycle #42. Auto-patching.
[Reflect] Cost ledger gate: cycle #42 recorded (total $<previous + 0.02>).
```

Proposed `cost_ledger.entries` should have a new synthetic trailing entry:

```json
{
  "cycle_id": 42,
  "skill": "<selected_skill or 'unknown'>",
  "estimated_usd": 0.02,
  "synthetic": true,
  "reason": "6-C8 auto-patch: cycle completed without 6-C5b write"
}
```

Proposed `skill_gaps.gaps[]` should gain one entry:

```json
{
  "id": "gap-cost-ledger-autopatch-42",
  "type": "learning_loop_break",
  "description": "cost_ledger.json missing entry for cycle 42 — auto-patched with synthetic entry",
  "detected_in_cycle": 42,
  "resolved": false
}
```

## Config

Defaults.
