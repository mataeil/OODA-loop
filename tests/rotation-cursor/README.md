# Fixture: rotation-cursor

## Purpose

Verify that evolve Step 4-B reads `agent/state/{domain}/rotation_cursor.json`,
passes the current `focus_item` to the winning skill as a context var, and
increments the cursor post-execution. Formalizes the fwd.page `focus_rotation`
pattern (fwd `agent/state/ux/state.json:6-46`).

## Setup

`config.json` enables a `ux_evolution` domain with a 3-item rotation:

```json
"rotation": ["thumbnail-editor", "dashboard", "stats"]
```

`seed/agent/state/ux_evolution/rotation_cursor.json` initially points to
cursor 0.

## Expected output — full cycle (4 consecutive cycles where ux_evolution wins)

> The `[Act] Rotation` lines are Step 4-B (Act), which `--dry-run` does **not**
> execute (it exits at Step 3-H). In `--dry-run` the engine may print what it
> *would* rotate to, but the cursor is never written. The behavior below is for
> full `/evolve` cycles.


```
Cycle N   [Act] Rotation: ux_evolution focus='thumbnail-editor' (cursor 0 -> 1)
Cycle N+1 [Act] Rotation: ux_evolution focus='dashboard'        (cursor 1 -> 2)
Cycle N+2 [Act] Rotation: ux_evolution focus='stats'            (cursor 2 -> 0)
Cycle N+3 [Act] Rotation: ux_evolution focus='thumbnail-editor' (cursor 0 -> 1)
```

Cursor wraps at 3 → 0. `focus_item` appears in the Step 6-C3 CHANGELOG
entry's `**Focus**:` field. In a real (non-dry-run) execution, the cursor
file is persisted after each cycle; across `/evolve --dry-run` invocations
the cursor is NOT written, so the same focus_item will appear repeatedly
unless the cursor file is manually bumped between runs.

## Config

Single-domain config with rotation. Only `ux_evolution` is active, to
guarantee it wins every cycle for the purposes of this fixture.
