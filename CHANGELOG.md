# Changelog

All notable changes to OODA-loop are documented here. This project follows
[Semantic Versioning](https://semver.org/).

The `schema_version` field in `config.example.json` tracks the config schema
independently. Bump there signals migration work for downstream projects.

---

## [v1.2.0] — Unreleased

v1.2.0 distills lessons from two production deployments (fwd.page 152 cycles,
Lynceus 119 cycles) into the upstream framework. None of the downstream
projects are modified by this release; all changes land in the framework so
that the next project gets these improvements by default.

Design plan: `plans/enumerated-growing-teacup.md` (in this repo's parent
`.claude/plans/` directory).

### Added — M4: Observability + docs

- **Orient Health dashboard** (`skills/ooda-status/SKILL.md`). New block
  rendering Episodes count, Principles count (with high-confidence count),
  Lens coverage (M / N domains), chain executions in last 10 cycles, active
  intervention count, unresolved skill_gaps (with `learning_loop_break`
  broken out). `/ooda-status --orient` focuses the view on these fields
  alone.
- **Season + Context block** on `/ooda-status` — shows current season
  mode (if enabled) with the overrides count and the active_context path
  (with file age).
- **CONCEPTS.md additions**:
  - 7 new concept rows for v1.2.0 primitives: Memo Interventions, Active
    Context, Rotation Primitive, Orient Health Dashboard, RICE Dimension
    Palette, Season Mode Weights.
  - New "Patterns distilled from production" section documenting
    memos-as-interventions, data-sourcing pipelines (pattern-only, not a
    primitive), and multi-agent debate vs consensus (with `execution_mode:
    debate` roadmap note for v1.3.0).
- **agent/contracts/schema.md additions**:
  - Recommended RICE Dimension Palette: `timing | novelty | evidence |
    vulnerability | alignment | media | reach_precision`.
  - Action difficulty → risk tier mapping: `low/medium/high` maps to
    `risk_tier 0/1/2`; binding via `config.safety.risk_rules` (Phase 4).
  - execution_mode roadmap note: `debate` deferred to v1.3.0.
- **README.md / README.ko.md** v1.2.0 notes: updated scoring formula
  mention, updated Production Validation table (152 + 119 cycles),
  explicit note that fwd / Lynceus are not modified by v1.2.0.

### Added — M3: Primitive promotions

- **Season modes wire-up** (`config.example.json`, evolve Step 1-A / 3-B /
  6-C3). The v1.1.0 `season_modes` scaffold is now actually read. Each mode
  may declare `weight_overrides: { domain: multiplier }` (applied to
  `domain_config.weight` in-memory — no disk mutation), `disabled_domains:
  [name]` (filtered alongside `status: "disabled"`), and `signal_bonuses:
  { signal: value }` (merged on top of `config.signals.*` for this cycle).
  `/ooda-config season <name>` / `season list` / `season show` toggle and
  inspect. The "default" mode IS the static weight-multiplier case —
  fwd's hardcoded `service_health × 2.0` collapses into
  `season_modes.modes.default.weight_overrides.service_health: 2.0`.
  Formalizes the Lynceus `weight_presets` pattern.
- **Active context** (`config.active_context`, evolve Step 1 / 4-B). New
  optional top-level key `{ path, refresh_skill, refresh_interval_hours }`.
  evolve Step 1 loads the file as an opaque blob and exposes it to every
  invoked skill as the `active_context` context var. If `refresh_skill` is
  set and the file is older than `refresh_interval_hours`, a refresh is
  queued via memos. `/ooda-config context show` inspects. Formalizes the
  Lynceus `contexts/{persona}.json` pattern.
- **Rotation primitive** (`config.domains.{name}.rotation`, evolve Step
  4-B, `agent/state/{domain}/rotation_cursor.json`). Per-domain
  round-robin `focus_item` list. When the domain wins a cycle, evolve
  reads the cursor, passes `focus_item = list[cursor]` to the skill as a
  context var, and increments the cursor (wraps). `/ooda-config rotation
  show {d}` / `rotation reset {d}` inspect and reset. Formalizes the fwd
  `focus_rotation` pattern.
- **CHANGELOG template** gained `**Season**:` and `**Focus**:` lines
  (Step 6-C3 mandatory schema).
- **Sandbox fixtures** (`tests/`): `season-mode-toggle`,
  `rotation-cursor`, `active-context-read`.

### Added — M2: Learning-loop activation

- **Memo schema 1.0.0 → 1.1.0** (`skills/evolve/SKILL.md`, Step 2-D/5-C/6-C).
  New `interventions: []` field on memos.json. Unlike `score_adjustments`
  (one-shot, consumed), interventions persist across cycles with
  `{domain, delta, type, reason, created_at_cycle, expires_after_cycles,
  applied_count}`. Engine applies them in Step 3-A alongside score_adjustments,
  then decrements `expires_after_cycles` in Step 6-C, removing at 0.
- **Auto-starvation intervention** (Step 5-C). A domain with 0 executions
  in the last 10 cycles auto-gets a `+1.0` intervention with
  `type: "starvation", expires_after_cycles: 3`. Formalizes the Lynceus
  +1.0 manual pattern (cycles 61, 107).
- **Auto monopoly-breaker intervention** (Step 5-C). A domain selected 2+
  consecutive cycles auto-gets a `-10.0` intervention with
  `type: "monopoly_breaker", expires_after_cycles: 1`. Formalizes the
  Lynceus −10.0 manual pattern.
- **Principles extraction thresholds relaxed + config-tunable** (Tier 2b).
  Jaccard similarity default 0.8 → 0.5, occurrences default 3 → 2. New
  config keys `memory.principle_similarity_threshold` and
  `memory.principle_min_occurrences`.
- **Principles cluster fallback** (Tier 2b). When primary extraction yields
  no principle but total lessons across episodes ≥ 10, cluster by first-3
  significant tokens and emit top-3 cluster representatives as
  `confidence: 0.15, kind: "candidate"` for human review.
- **Manual principle seeding** documented (Tier 2b). Operators may add
  entries directly to `principles.json` with `kind: "manual"`.
- **Sandbox fixtures** (`tests/`): `principles-extraction`,
  `memo-intervention`, `cost-ledger-autopatch`, `lens-pre-init`. Each has
  a `seed/agent/state/evolve/` snapshot and a `README.md` describing
  expected `/evolve --dry-run` output.

### Added — M1: Foundation

- **Lens pre-init in Step 1-A** (`skills/evolve/SKILL.md`). Adaptive Lens
  files (`agent/state/{domain}/lens.json`) are now initialized at the start
  of Step 1-A Domain State Reading — before any read — so first cycles and
  domains with custom observe skills always have a valid lens on disk. Step
  5-E retains its own init as a safety net.
- **Cost Ledger Integrity Gate (6-C8)** (`skills/evolve/SKILL.md`). Before
  the cycle's git commit, evolve verifies that
  `cost_ledger.entries[-1].cycle_id == state.cycle_count`. If not, a
  synthetic entry is appended AND a `skill_gaps` record of type
  `learning_loop_break` is emitted — surfacing silent drift instead of
  accumulating it.
- **config schema version** bumped to `1.2.0`. Existing configs continue to
  load; all v1.2.0 fields are additive with safe defaults.
- **Root CHANGELOG.md** (this file) created for framework-level release
  notes, separate from the per-cycle `agent/state/evolve/CHANGELOG.md`.

### Status of earlier built-in behavior

- `/evolve --dry-run` already existed at v1.1.0 (Step 3-H). No change needed
  for M1.

### Coming in M2–M5

- M2: Memo schema distinction (intervention vs observation), auto-starvation
  and monopoly-breaker interventions, principles-extraction threshold
  relaxation with cluster fallback, sandbox fixtures.
- M3: Season modes full wire-up (Lynceus pattern), active_context primitive,
  rotation MVP (fwd pattern).
- M4: `/ooda-status --orient` Orient Health dashboard, CONCEPTS pattern
  docs, RICE palette + risk-tier mapping docs.
- M5: Run all fixtures, confirm Orient Health shows non-zero values,
  tag v1.2.0.

---

## [v1.1.0] — 2026-04-13

Earlier release. Phase 4 extensibility (RICE extensions, risk tiers,
cross-domain cascades, data classification) and Phase 5 rollback protocol +
multi-agent consensus execution mode. See commits c030a10, 33bd30c, 8405e14,
9da27cf, 3fec1af.
