# Changelog

All notable changes to OODA-loop are documented here. This project follows
[Semantic Versioning](https://semver.org/).

The `schema_version` field in `config.example.json` tracks the config schema
independently. Bump there signals migration work for downstream projects.

---

## [Unreleased]

Post-beta quality work toward a stable `1.2.0` (surfaced by the stable-gate
verification — see TESTING.md).

### Added — auto-merge, implemented as a low-risk opt-in (supersedes the relabel below)

The Tier B finding (auto-merge was unreachable dead code) is now resolved by
*implementing* it conservatively rather than only relabeling:
- **`config.safety.enable_auto_merge`** (default `false`) — the single opt-in
  switch, plus `auto_merge_max_files` (5) / `auto_merge_max_lines` (100).
- **`dev-cycle`** opens a **ready** (non-draft) PR only when a change is
  auto-merge-eligible (opt-in + Level 3 + non-protected + within the low-risk
  size bar + tests green); otherwise it stays a **Draft** (the default).
- **`evolve` 4-C** Risk Tier 1 now fires *only* under those gates, which evolve
  **re-checks itself** via `gh pr view` (defense in depth) — then merges, runs a
  post-merge health check, and (4-C2) **auto-reverts + HALTs** on failure. Large
  changes → Tier 2 (ready, human merges); everything else → Tier 3 (Draft).
- **`/ooda-config auto-merge {on|off}`** toggle (typed-phrase confirm, Level-3
  gated) and **`/ooda-config rollback {cycle}`** (now implemented — reverts repo
  + state to a checkpoint). Level-3 DANGER prompt corrected to the opt-in reality.
- Default behavior is unchanged: **you stay in command; nothing auto-merges
  unless you flip the switch.** The new auto-merge path is implemented but awaits
  a live throwaway re-verification (see TESTING.md "remaining gate").

### Honesty relabel — auto-merge is experimental (Tier B finding)

> Superseded by the implementation above; kept for history.

A live Tier B run (throwaway repo, Level 3) confirmed a doc-vs-implementation
mismatch: the advertised **auto-merge** does not happen. The only PR-producing
skill, `dev-cycle`, is hard-wired to open **Draft** PRs at **Risk Tier 3**, so
`evolve`'s Risk Tier 1 `gh pr merge` path is never reached with the bundled
skills (and the auto-revert + `/ooda-config rollback` that depend on it are
likewise unreachable / unimplemented). The behavior is actually *safer* than
advertised; the claims were ahead of the code. Relabeled accordingly:
- `ooda-config` Level-3 DANGER prompt no longer claims "create PRs AND
  auto-merge … without human review"; it states Draft-only + experimental
  auto-merge.
- `evolve` 4-C / 4-C2 marked EXPERIMENTAL with an explicit "not reachable with
  bundled skills" note; manual rollback flagged NOT-YET-IMPLEMENTED.
- `config.example.json` level 3 `auto_merge` set to `false` with a doc note
  (evolve never read this flag anyway).
- README: new **"Auto-merge status (honest)"** section; Day-30 / level-table /
  rollback claims corrected.
- **No engine behavior changed** — this is documentation/positioning only.
  Level 3 = autonomous *Draft-PR* creation; merging stays human.

### Added
- **TESTING.md** — documents the verification stack (static walkthrough,
  deterministic reference renderers, fixture taxonomy) and the honest remaining
  gate for stable (a live multi-cycle `/evolve` run).
- **`scripts/dryrun_score.py`** — deterministic Step 3-A scoring reference;
  `verify.py` uses it to assert season-mode `weight_overrides` flip the winner.
- **State-file schemas** in CONCEPTS.md (`reflections.json`, `lens_changelog.json`).
- **`templates/minimal-domain-skill/`** — a ~30-line custom-domain starting point.

### Changed
- **Step 6-C8** now backfills multi-cycle ledger gaps (sequence-gap detection,
  capped by `config.cost.max_backfill_cycles`) instead of only the current cycle
  (#17). `cost.max_backfill_cycles` added (default 100).
- Reframed the three state-only fixtures (`memo-intervention`,
  `principles-extraction`, `cost-ledger-autopatch`) as **step-unit** fixtures and
  documented the 6-C8 daily-reset interaction.

### Tests
- `tests/verify.py`: 31 PASS / 0 FAIL (added gap-detection, season-mode winner,
  and Cycle Card runtime-render checks).

---

## [v1.2.0-beta] — 2026-06-06

### Added — Visible engine (Week-1)

The goal of this milestone is to make the (already production-validated) engine
**visible and shareable**, and to reposition honestly around control + safety.

- **Cycle Card** (`skills/evolve/SKILL.md` Step 7) — a screenshottable
  end-of-cycle summary (Observe → Orient → Decide → Act → **Learn** → Cost)
  rendered at the end of every full cycle (not in `--dry-run`), gated by the new
  `config.output.cycle_card` key (default `true`). The LEARN line surfaces the
  single highest-signal re-orientation: a confidence change from a human
  merge/reject > a lens re-aim > a new intervention > a micro-adjustment.
- **`/ooda-status --share`** re-renders the latest Cycle Card read-only from
  state (`skills/ooda-status/SKILL.md`).
- **`lens_changelog.json`** is now written by evolve Step 5-E whenever a lens
  item is added/promoted/decayed/deprecated, giving the Cycle Card and
  `--share` LEARN line an auditable source (previously referenced but never
  written).
- **`config.output.cycle_card`** top-level config key (`config.example.json`).
- **Reflexion verbal self-critique loop** — evolve Step 5-F writes a one-line
  self-critique + lesson per decision cycle to `reflections.json`; Step 2-F
  re-injects the most relevant recent lessons into the next Orient (config:
  `memory.reflection_recall_count`, `memory.reflections_buffer_size`). This is
  the honest, SOTA-adjacent mechanism behind "it learns from its own cycles" —
  verbal self-correction (text re-read), not weight updates. Surfaced in
  `/ooda-status` Orient Health as a `Reflections` count + latest lesson, and as
  a Cycle Card LEARN fallback when no higher-signal delta exists.
- **README hero demo** — `docs/demo.gif`, a dark-terminal animation of one cycle
  ending on the LEARN line (reject PR #28 → confidence 0.74→0.54, lens re-aims
  0.30→0.25; caption "You rejected it. It re-aimed."), embedded above the fold
  in both READMEs (static ASCII card kept in `<details>`). Reproducible via
  `scripts/gen_demo_gif.py`.
- **`tests/cycle-card/` fixture + reference renderer** — a full v1.2.0 seed
  (fwd.page #152) with the expected Cycle Card / `--share` output, plus
  `scripts/render_cycle_card.py`, a deterministic Step-7 renderer used to
  runtime-verify the card end-to-end from real on-disk state. `tests/verify.py`
  is now **28 PASS / 0 FAIL** (incl. runtime render checks).

### Changed

- **Repositioning** — plugin/marketplace descriptions and both READMEs reframed
  from "operations team while you sleep" to "an autonomous operations layer you
  stay in command of." Added an honest **"How the learning actually works"**
  section (heuristic proto-evolution, not ML) and corrected the Boyd/Orient
  framing (real five-component Orient diagram; Implicit Guidance arrows run
  *from* Orient; theory formulated in the 1970s–90s, not the 1950s).
- **Versions** — plugin/marketplace `version` → `1.2.0-beta` (was `1.0.0`);
  `evolve` and `ooda-status` skill `version` → `1.1.0` (gained Cycle Card /
  `--share`). Promoted alpha → **beta** (pre-release): the new Cycle Card render
  is runtime-verified, but full-engine `/evolve` runtime verification across all
  fixtures remains the gate for a stable `1.2.0` — so this stays a pre-release.

---

## [v1.2.0-alpha] — 2026-04-19

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
