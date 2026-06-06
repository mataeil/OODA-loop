# Fixture: cost-ledger-autopatch

## Purpose

Verify that evolve **Step 6-C8 Cost Ledger Integrity Gate** detects and backfills
**multi-cycle gaps** in `cost_ledger.json` AND emits one `skill_gaps` record of
type `learning_loop_break`. Guards against the production pattern (fwd.page) where
the ledger received no new entries for ~13 days while cycles kept running.

## Setup

Seed state (state-only — no `config.json`):

- `state.json` → `cycle_count: 42`.
- `cost_ledger.json` → entries for cycles `[37, 38, 39]` (total `$0.08`); cycles
  **40, 41, 42 are missing** (a 3-cycle gap).
- `skill_gaps.json` → empty.

## Expected output (Step 6-C8 unit fixture)

> **Fixture type: Step 6-C8 unit (state-only seed, no config.json).** It asserts
> the integrity gate *in isolation*: given a ledger whose recorded cycles end at
> 39 while `state.cycle_count` is 42, 6-C8 scans the recorded sequence, finds the
> holes `[40, 41, 42]`, and backfills each.
>
> **Full-cycle caveats** (so a live run isn't surprising):
> 1. In a normal full cycle, Step 6-C5b appends the *current* cycle's entry before
>    6-C8 runs. 6-C8 detects gaps by scanning the whole recorded sequence (not just
>    last-vs-current), so it still catches earlier holes that 6-C5b's append would
>    otherwise mask.
> 2. `cost_ledger.date` here is `2026-04-19`; Step 1-A's daily reset clears the
>    ledger when run on a different UTC date — 6-C8 backfills only within the
>    current day's range and does not resurrect reset-cleared prior days. For a
>    faithful live trace, set the date to the run date. (The static `verify.py`
>    check is date-independent.)
> 3. Backfill is capped by `config.cost.max_backfill_cycles` (default 100) so a
>    corrupt counter can't write thousands of synthetic entries.

Console:

```
[Reflect] ⚠ cost_ledger gap: missing entr(ies) for cycle(s) 40..42 (3). Backfilling.
[Reflect] Cost ledger gate: backfilled 3 cycle(s) 40..42 (total $0.14).
```

Proposed `cost_ledger.entries` gains three synthetic entries (then re-sorted ascending):

```json
{ "cycle_id": 40, "estimated_usd": 0.02, "synthetic": true, "reason": "6-C8 gap backfill: cycle had no 6-C5b write" }
{ "cycle_id": 41, "estimated_usd": 0.02, "synthetic": true, "reason": "6-C8 gap backfill: cycle had no 6-C5b write" }
{ "cycle_id": 42, "estimated_usd": 0.02, "synthetic": true, "reason": "6-C8 gap backfill: cycle had no 6-C5b write" }
```

`total_estimated_usd`: `0.08 → 0.14`. Cycle 42 (== `cycle_count`) carries the real
`selected_skill`; 40 and 41 use `"unknown"`.

Proposed `skill_gaps.gaps[]` gains **one** summary entry (not one per cycle):

```json
{
  "id": "gap-cost-ledger-autopatch-42",
  "type": "learning_loop_break",
  "description": "cost_ledger missing 3 entr(y/ies) in range 40..42 — backfilled with synthetic entries",
  "detected_in_cycle": 42,
  "frequency": 3,
  "resolved": false
}
```

## Config

Defaults. `config.cost.max_backfill_cycles` (default 100) bounds the backfill.
