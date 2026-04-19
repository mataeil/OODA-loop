# Fixture: season-mode-toggle

## Purpose

Verify that `config.season_modes.current_mode` rewrites domain weights
in-memory at evolve Step 1-A and merges signal_bonuses at Step 3-B, without
mutating config.json on disk. Formalizes the Lynceus `weight_presets` pattern
(Lynceus config.json:279-315) as a first-class upstream primitive.

## Setup

Two seed configs in this directory — `config.default.json` and
`config.preparation.json`. They are identical except for `season_modes.current_mode`.

The `preparation` mode defines:

```json
"preparation": {
  "weight_overrides": { "service_health": 1.0, "backlog": 2.0 },
  "disabled_domains": [],
  "signal_bonuses": { "queue_pressure_bonus": 5.0 }
}
```

Both configs inherit identical base weights (`service_health: 2.0`,
`backlog: 0.3`). Under the default mode, `service_health` dominates scoring
due to its 2.0 base weight. Under preparation mode, the override drops it
to 1.0 and boosts `backlog` to 2.0 — flipping the ordering.

## Expected dry-run output

**Default mode** (`config.default.json`):

```
[Observe] Season mode: default (0 weight overrides, 0 disabled domains)
[Decide] Domain scores: service_health > backlog > ...
```

**Preparation mode** (`config.preparation.json`):

```
[Observe] Season mode: preparation (2 weight overrides, 0 disabled domains)
[Decide] Domain scores: backlog > service_health > ...
```

The reordering confirms Step 1-A applied the weight_overrides. The
`queue_pressure_bonus: +5.0` should also reach the implementation virtual
domain when pending_count >= queue_pressure_threshold.

**No config.json should be written to disk.** Both runs are dry-runs.

## Config

Two full configs in this fixture (not a single one with overrides) so the
diff is obvious. Copy whichever into `config.json` before running.
