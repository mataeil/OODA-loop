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

## Expected output (Step 6-C8 unit fixture)

> **Fixture type: Step 6-C8 unit (state-only seed, no config.json).** It asserts
> the integrity gate *in isolation*: given a ledger whose last entry (cycle 39)
> is behind `state.cycle_count` (42), 6-C8 detects the mismatch and patches.
>
> **Important full-cycle caveats** (so a live run isn't surprising):
> 1. 6-C8 is a **same-cycle backstop**. In a normal full cycle, Step 6-C5b writes
>    the current cycle's entry *before* 6-C8, so the gate is a no-op unless 6-C5b
>    was skipped (the production failure mode it guards). It patches the *current*
>    `cycle_count`; it does **not** backfill a multi-cycle historical gap (see
>    issue: 6-C8 gap-backfill enhancement).
> 2. After Step 6-A increments `cycle_count`, the gate references the incremented
>    number — so on a live run from this seed the message is cycle #43, not #42.
> 3. `cost_ledger.date` here is `2026-04-19`; Step 1-A's daily reset wipes the
>    ledger if run on a different UTC date. For a faithful live trace, set the
>    date to the run date. (The static `verify.py` check is date-independent.)

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
