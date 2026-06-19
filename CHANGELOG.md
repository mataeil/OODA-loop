# Changelog

All notable changes to OODA-loop are documented here. This project follows
[Semantic Versioning](https://semver.org/).

The `schema_version` field in `config.example.json` tracks the config schema
independently. Bump there signals migration work for downstream projects.

---

## [v1.8.1] — 2026-06-19

### Validated + guidance — the gameplay_metrics path works end-to-end

The f1 probe exercised v1.8.0's per-dimension capture: it authored a
`gameplay_metrics` harness (drives the real pure physics headlessly) for the two
**frozen** experiential axes (`driving_feel`, `fun_challenge` = 45% of the rubric
a screenshot can't judge).

- **Honest measurement first dropped artifact_quality 0.533 → 0.490** — the
  screenshot had been *over*-scoring feel/fun (0.51/0.38 → measured 0.41/0.29).
  Confirms the v1.8.0 thesis: measurement was the bottleneck *and* inflating.
- Two leaps the unlock enabled: `fun_challenge` 0.29 → **0.81** (distinct AI
  racing lines + tamed DRS slingshot) and `driving_feel` 0.41 → **0.78** (steering
  inertia + power oversteer + weight transfer). **artifact_quality crossed the bar
  for the first time (0.687 ≥ 0.65) → an HONEST grade A** (the loop's original A
  was a lie; this one is earned).
- **Guidance (config doc):** a `gameplay_metrics` harness must MEASURE BEHAVIOUR
  (drive the artifact, read the numbers), never assert an implementation fact — the
  probe's first harness hardcoded a feature flag and couldn't credit the fix,
  which would trigger a spurious thrashing-HALT. Rewritten to measure behaviour.

---

## [v1.8.0] — 2026-06-19

### Changed — drive quality to "good", not "passable" (config schema 1.4.0)

The F1 probe stayed crap after **three** v1.7.0 leaps (artifact 0.394 → 0.447 →
0.472 → 0.522, never reaching the 0.65 bar). A 13-agent adversarially-verified
diagnosis (`.claude/ooda-evolution-v1.8.0.md`) found the loop **detects** a
quality gap but isn't built to **close** it. Four fixes, ranked by leverage:

- **Thrashing-guard bug fix (prerequisite).** evolve 2-G counted a nonexistent
  `leap_delta` field on `weakest_dimension`, so the guard's `fails` count was
  ALWAYS 0 and the HALT safety valve **never fired** — the loop could thrash a
  dimension forever. Now counts `leap_attempts[].delta_score` on the actual
  `leap_target` (`rubric_score.failed_leaps()`).
- **Per-dimension `capture_method` (5-G).** The critic scored every axis from one
  screenshot, so `driving_feel` + `fun_challenge` (**45% of the rubric's weight**)
  were frozen across all 25 cycles. Each axis now declares its capture;
  experiential axes use `gameplay_metrics` — a human-authored, hash-verified,
  protected harness (same independence invariant as the rubric hash). Missing/
  unverified → score `null` + skill_gap, never a faked or silent-screenshot score.
- **Dimension lock until bar (2-G).** A successful leap that left its target below
  `bar − eps` now keeps the plateau active on the SAME target (drive-to-bar, not
  detect-and-nudge + rotate). `rubric_score.lock_target()`; toggle with
  `config.leap.lock_until_bar`. Tolerance band + the now-working max-attempts HALT
  prevent infinite lock.
- **Auto-queue remainder (5-G).** A leap that passes its delta gate but leaves the
  dimension below bar queues a high-RICE remainder, triggered by the *independent
  critic's* score (not the maker's self-report), so dropped/partial scope can't be
  silently orphaned (as leap 3's materials/lighting was).

**Rejected** (kept the loop honest): raising the bar to 0.80 before feel/fun are
measurable; an inner multi-pass refine loop; an LLM-component-coverage gate
(gameable); `multi_probe` still-sequences. `tests/verify.py` 59 → **61**.

---

## [v1.7.0] — 2026-06-17

### Added — artifact-grounded evaluation + quantum-leap cycles (config schema 1.3.0)

The F1-racing dogfood (22 cycles, every cycle graded **A** / futile 0% /
mission-hit 100%) produced a *처참* (dismal) game: a Z-fighting cyan blob for a
track, no recognizable car, polished HUD bolted over a broken core. The metrics
were perfect; the artifact proved them a lie — a **Goodhart collapse**. Root
cause: the loop measured **process** (did a PR/commit advance?) and was blind to
the **artifact** (is the thing good?), and its action selection (RICE + "one
focused feature") could only ever take small steps. Diagnosis + design:
`.claude/ooda-evolution-v1.7.0.md`.

- **Artifact axis in scoring (fixes D2).** `quality_multiplier = process_factor ×
  artifact_factor` (`scripts/score_outcome.py`). A `pr_created` (0.5) whose
  artifact scores 0.4 now records **0.2**, not 0.5. `artifact_score` is a
  first-class field in `outcomes.json` (Step 6-C9). No rubric → factor 1.0
  (process-only loops unchanged).
- **Step 5-G: Artifact Critique.** An *independent*, evidence-grounded critic
  (separate model context) captures the real artifact (screenshot / API call /
  benchmark per `quality_rubric.capture_method`) and scores it against a
  HUMAN-AUTHORED, integrity-checked rubric — the loop may never author its own
  grading standard.
- **Honest scorecard (fixes D1).** `scripts/loop_scorecard.py`: `★ Artifact
  Quality` is the new headline KPI; the self-declared goal term is **evidence-
  weighted** by artifact reality; an **artifact-only Goodhart Guard** caps the
  grade (graduated C/D/F) and prints a measurement warning when artifact < bar.
  The F1 run re-grades **A (0.995) → D (0.567)**.
- **Quantum-leap cycles (fixes D3).** Step 2-G plateau detector + Step 3-K
  Leap-Mode Gate: when artifact quality plateaus *below bar*, the next cycle is
  forced to **overhaul the weakest dimension** (step-change, RICE bypassed via a
  gap-to-bar bonus, larger size budget) instead of adding another feature.
- **Leap safety.** Pre-PR artifact gate with a checkpoint baseline; revert on
  `min_dimension_delta` miss (→ `leap_regressed`, quality 0.0); thrashing
  escalates to HALT after `max_attempts_per_dimension`; per-leap cost cap +
  `max_per_day`; protected-path diff-time check. Hardened by a 5-agent adversarial
  red-team (gaming-resistance / autonomous-safety / implementability).
- **`on_mission` is now a real signal** for build cycles (`artifact_score >= bar`)
  instead of a static config echo.
- **Config:** new `quality_rubric` (per-domain, canonical) + `leap` blocks in
  `config.example.json`. **Tests:** new `scripts/rubric_score.py` (pure) + 8 new
  `tests/verify.py` checks (now 58 passing; the previously-unregistered
  `scorecard` suite is wired back in).

---

## [v1.6.1] — 2026-06-14

### Added / clarified — plugin namespacing + cloud routine recipe
- **Command-naming callout** at the top of README / README.ko: the docs use the
  bare `/evolve` form (git/symlink install); plugin installs prefix with
  `ooda-loop:` (`/ooda-loop:evolve`). Stated once at first command exposure
  rather than noising every line.
- **Cloud routine recipe** in docs/claude-code-integration.md — the exact
  `/schedule` setup + routine prompt + the git state-branch flow.
- **Cloud state persistence is now verified** (not just documented):
  tests/e2e/scenarios/test_cloud_state.py proves with real git that state
  committed in one clone is read by a separate FRESH clone (cycle_count
  continuity, Outcome Record accumulation) — the fresh-clone path a cloud
  routine takes. Docker E2E 22 → 23.

## [v1.6.0] — 2026-06-14

**The Claude-Code-native release.** OODA-loop is Claude-Code-exclusive, so it now
*composes with* Claude Code's orchestration primitives instead of reinventing
them — and ships the missing deterministic safety control.

### Added
- **[docs/claude-code-integration.md](docs/claude-code-integration.md)** — the
  canonical composition design: the division of labor between Claude Code
  (cadence + rails: `/loop`, `/schedule`/routines, `/goal`, hooks, subagents) and
  OODA-loop (the cycle, memory, scorecard); when to use `/loop` vs `/schedule`
  vs `/goal`; **state persistence across fresh-clone cloud runs**; and the
  `config.mission` (strategic, persistent) vs `/goal` (tactical, per-session)
  distinction.
- **HALT enforced by a hook** — `hooks/hooks.json` ships a `PreToolUse` guard
  (`hooks/halt-guard.sh`, dependency-free) that BLOCKS file/shell/merge tools
  while `agent/safety/HALT` exists, so the kill-switch is deterministic at the
  Claude Code level (and works in cloud routines, where only repo/plugin hooks
  run) — not merely by each skill's Step-0 check. Always allows the HALT-clearing
  action; no-ops in non-OODA repos. Plus a SessionStart notice when HALT is
  present. verify.py +5 halt-hook checks (42 → 47).

### Fixed / clarified
- **Skill namespacing**: documented that a plugin install exposes
  `/ooda-loop:evolve` while the git/symlink install exposes the bare `/evolve` —
  the docs' bare commands assumed the symlink install.
- Cloud-routine guidance: `evolve` already commits `agent/state/` each cycle
  (state is versioned, not gitignored — #31), which is exactly what survives a
  fresh-clone routine run; `CLAUDE_CODE_REMOTE` distinguishes unattended context.

## [v1.5.0] — 2026-06-14

**The self-driving release.** OODA-loop becomes a loop-engineering framework you
*install with a purpose*: state the mission at setup and the loop drives toward
it. Every change here was tuned empirically — 8 measured iterations against three
simulated real projects (`tests/sim/`), each kept only if the scorecard improved
(`tests/sim/RESULTS.md`).

### Added — self-driving (mission-aware scoring)
- **Mission capture** at `/ooda-setup` → `config.mission` + per-domain
  `mission_alignment`; evolve 3-A/3-A2/3-J add a `mission_weight × alignment`
  term. Sandbox: goal completion +14–40pp across all three projects (Iter 1).
- **Work-availability**: a work domain that ran dry gets staleness ×0.3
  (`dry_domain_dampen`); a quiet monitor ×0.6 (`monitor_dry_dampen`) — polled,
  not spammed. Cut futile cycles; lifted a library project to 100% goal
  (Iters 2–3).
- **Off-mission deprioritization**: domains with alignment <0.2 get staleness
  ×0.2 (`off_mission_dampen`) — distractions stop stealing cycles; alert exempts.
  B mission-hit 42→75%, futile 58→25% (Iter 4).
- **Goal-completion idle gate** (Decide 3-E2): when all active goals hit 100% and
  nothing is actionable/alerting, the cycle idles instead of spinning — the loop
  runs *until* the goal is met (Iter 5).
- **Install auto-derives goals** from the mission text + stack (Iter 6).

### Added — measurement surfacing
- **Loop grade** (A–F) and **Mission-hit Rate** on `/ooda-status --scorecard`
  (Iters 7–8) — at-a-glance "is the loop working, and staying on purpose?".

### Added — the instrument
- **`tests/sim/`** — sandbox simulation harness (3 scenarios × N cycles via the
  real scoring spec + engine driver → scorecard + loop-engineering quality
  metrics) and `RESULTS.md`, the empirical log of all 8 iterations. Analysis
  tool, not a CI gate.

Cumulative sandbox result (baseline → now): B_library goal 60→100% / futile
75→25% / mission-hit 25→75%; A_webapp goal 50→83%; C_greenfield goal 43→71%.
verify.py 42/0 · Docker E2E 22/22, green on every iteration's CI.

## [v1.4.0] — 2026-06-14

**The measurement release.** Deep research into 2026 "loop engineering" (Anthropic
+ practitioner canon) found OODA-loop's one structural gap: it measured
*activity* (cycles, PRs, cost) but never whether the loop *improved the project*.
This release adds the outcome-measurement stack the canon demands — so the loop
can tell "we ran 100 cycles" from "we improved the project 100 times."

### Added — outcome measurement
- **Outcome Record** (evolve Step 6-C9, every cycle, deterministic): scores each
  cycle a `quality_multiplier` (0.0–1.0) from its real `result_type` into a new
  `agent/state/evolve/outcomes.json`; appends a machine-readable line to
  `cycle_log.jsonl`. The atomic "did this help?" signal. New loop-effectiveness
  counters (futile cycles, actions added/resolved). `scripts/score_outcome.py`
  is the single source of truth.
- **Loop Scorecard** — `/ooda-status --scorecard` (`scripts/loop_scorecard.py`):
  Loop Value Score, Task Completion Rate, Futile Cycle Rate, PR Merge & hold
  rate, Action Queue Resolution, Cost per Successful Cycle, plus Goal Progress
  and learning-loop health (gap resolution, lesson application) and a
  working/partial/stalled verdict. Graceful `—` on fresh state.
- **Merge-and-hold back-annotation** (Step 2-B4): outcomes upgrade
  pr_created→pr_merged→pr_merged_held as PRs merge and survive, or downgrade to
  pr_rejected on a revert-within-48h — so merge-and-hold is a real signal.
- **Maker/checker eval** (Step 7-B, opt-in `config.eval`, off by default): a
  *separate* model independently grades whether a cycle met its declared goal
  (→ `outcomes.json.verifier_verdict`); the deterministic score stays ground
  truth. Disagreement logs an `eval_disagreement` skill_gap.
- **Verifiable goals** (loop-engineering canon #1): ooda-setup now seeds/
  documents a `goals.json` done-condition with a `metric_command`; the scorecard
  shows Goal Progress. Confidence-calibration metric tracked as #56.
- Verification: `verify.py` 38 → **42** (outcome-scoring, eval-config,
  scorecard checks + the deterministic references); Docker E2E 19 → **22**
  (the driver now transcribes Step 6-C9; measurement scenarios). Config:
  `memory.outcomes_buffer_size`, `eval` block; ooda-config validate #28.

### Added — official Docker E2E tier (Tier 1)
- **`tests/e2e/`** — 19 rail scenarios driven by a spec-transcribed deterministic
  driver (`driver/engine.py`, every block cites its SKILL.md section) against a
  real filesystem, real git repos, real processes (incl. SIGKILL crash), and an
  injected clock, fully isolated in Docker (`tests/e2e/run.sh`, `--local`
  fallback). Covers: lock lifecycle + stale self-heal + crash recovery, all
  breakers end-to-end (interval/saturation/silent-failure/HALT convergence),
  cost-ledger reset/backfill/corrupt-fail-closed, 6-D explicit staging + the
  #31 gitignore guard, weekly-episode exactly-once, action-queue hygiene.
- **`.github/workflows/e2e.yml`** — CI now runs Tier 0 (static verify) +
  Tier 1 (Docker E2E) on every push and pull request; TESTING.md documents the
  official three-tier process (0 static / 1 Docker E2E / 2 live Claude runs).

- **Live soak run recorded** (TESTING.md): the v1.3.0 unattended-operation rails
  — lock lifecycle, crash self-heal, min-interval skip, silent-failure breaker →
  HALT — all verified live over 14 cycles in a throwaway project ("fails
  stopped" closed by measurement).
- evolve 0-C: crash-recovery diagnostics now name the **crashed** cycle
  (`cycle_count + 1`) instead of the last completed one (soak-run finding;
  behavior was already correct, the message blamed the wrong number).

---

## [v1.3.0] — 2026-06-10

**The unattended-operation release.** A 37-agent adversarially-verified review
of every SKILL.md (126 raw findings → 22 confirmed + the verified tail) focused
on one question: *can /evolve run on a schedule for days without a babysitter?*
Seven fix PRs (#41–#47) later, the answer is designed to be yes — and every
failure mode now converges on the HALT file (the loop fails **stopped**, never
runaway).

### Fixed — autonomy blockers (evolve)
- **Lock leaks**: the 0-D min-interval skip and the 4-A HALT re-check both
  EXITed without deleting the lock created in 0-B — under /loop or cron, every
  early tick (or any mid-cycle HALT) blocked the next on-time run for up to
  30 minutes. The 0-B pseudocode also contradicted its own stale-lock rule
  (unconditional EXIT ⇒ one crash = permanent block until manual `rm`).
  Staleness is now checked inline, stale locks fall through to crash recovery,
  and every early-exit path releases the lock. **Crashes self-heal.**
- **Saturation breaker**: evaluated the current cycle's outputs before Act ran
  (always empty ⇒ counter crept up wrongly) and silently no-oped when the
  counter field was missing. Now evaluates the previous completed cycle and
  initializes the field.
- **`max_silent_failures`** (declared since v1.1, never enforced): N consecutive
  execution errors now HALT after the cycle completes cleanly.
- **Cost ledger policy**: missing (fresh install) ⇒ initialize at $0 with 6-C8
  gap audit; **corrupt ⇒ fail closed** (backup + HALT) — recreating a corrupt
  ledger at $0.00 mid-day would have defeated the daily cap.

### Fixed — scoring / learning correctness (evolve)
- **3-J score verification** hardcoded linear staleness + omitted
  balance_penalty while 3-A defaults to logarithmic ⇒ a false "[WARN] Score
  mismatch" EVERY cycle that then **replaced the correct score with the wrong
  one** (silent winner swaps). 3-J now re-runs the exact 3-A pipeline.
- Cascades were detected then **never written to disk**, and the +3.0 bonus
  re-applied every cycle while pending (compounding). Persisted + one-shot.
- Contrarian check stored a shape no consumer could read — now a standard
  intervention (+1.0, 3 cycles). Starvation window was 11 cycles (off-by-one).
  Futile-loop count now derived from decision_log (survives restarts).
- Balance penalty read flat `metrics.total_skill_executions` while 6-C5 writes
  nested `counters.*` ⇒ the penalty was silently zero forever. Aligned.
- Episodes: spec schema diverged from fixtures/live shape AND the week
  comparison read a field id-keyed entries don't have ⇒ a duplicate episode
  every cycle after the first week boundary. Canonical = fixture schema
  (`EP-YYYY-Wnn` id) with an existence guard.

### Fixed — Act-path safety enforcement (evolve + dev-cycle)
- **Chains bypassed every 4-A gate** (allowlist, level, implementation) — a
  chain_trigger could run /dev-cycle at Level 2. Chains now pass the same
  SAFETY GATE as the primary skill.
- **`max_prs_per_cycle`** (declared, never enforced): now tracked in 4-C,
  consulted by the chain gate, and any over-limit PR is forced to Tier 3 +
  a safety_violation memo.
- Checkpoints were taken only when `enable_rollback` — with auto-merge on and
  rollback off the agent could self-merge with **no recovery point**. Either
  flag now forces the checkpoint. Auto-rollback handles `git push` failure
  loudly (HALT always created).
- Action lifecycle: orphaned in_progress items re-queue, blocked items move to
  completed[], a partial PR spawns a remainder action, dev-cycle returns to
  main on failure. Nothing jams the queue forever.

### Fixed — cross-skill contracts
- **Every bundled chain_trigger referenced variables its skill never wrote.**
  4-B now defines the evaluation source (skill's contract output file →
  Report variables → false, logged); check-tests writes
  `new_failures`/`coverage_drop`/`previous_status`, scan-health writes top-level
  `consecutive_failures`, plan-backlog writes `actionable_items: 0` on every
  early exit, dev-cycle's Report declares `pr_created`.
- decision_log canonical field names: `selected_domain`/`selected_skill`
  (three writer sites used bare `domain`/`skill` that no reader queried).
- Canonical test marker: `test_status == "passed"` (was "passed" vs "passing"
  vs "green" across three layers — auto-merge could never fire end-to-end).
- ooda-status reads cost from cost_ledger.json (metrics.json never had cost
  fields); Trend computed from data that exists.
- ooda-config: /domain add writes `status:"active"` (CLI-added domains could
  never win); duplicate validate list collapsed (27-check list is canonical);
  lens reset writes the full empty schema; +2 validate checks updated for the
  enabled→status canon.
- **#31 resolved**: state JSONs are deliberately versioned (they're the
  auditable memory); only lock files + HALT stay gitignored; 6-D warns loudly
  if the state path is ignored. ooda-setup initializes reflections.json +
  full-shape memos.json.
- agent/safety/autonomous-mode.md + SECURITY.md + README level tables synced to
  the real engine (Levels 0–2 = no PRs; Level 3 = Draft by default; auto-merge
  opt-in only). skill_gaps capped at 50.

### Added
- **"Run it continuously (unattended operation)"** README section (EN + KO):
  `/loop 4h /evolve`, the cron one-liner, and the six rails that make the loop
  fail stopped.
- Reference scripts hardened: render_cycle_card no longer crashes without
  memos.json (+ canonical-key reads); dryrun_score reads the real
  `confidence_weight` key.

verify.py **38/0** after every one of the seven PRs.

---

## [v1.2.1] — 2026-06-09

Auto-merge finishing touches + deeper verification, from the Tier B+ live-run
side findings. Default behavior is unchanged (auto-merge stays off until opted in).

### Fixed
- **#34** — removed the unreachable Risk Tier 2 ("oversize → ready PR"). evolve
  4-C is now two outcomes: **Tier 1** (auto-merge, all low-risk gates) or
  **Tier 3** (Draft, human review). Oversize changes are simply Tier 3.
- **#35** — a partial change that **skips a protected path** (`protected_blocked`)
  is now forced to Draft / Tier 3 and is never auto-merge-eligible, even when the
  remaining diff is small and green (it may be incomplete/incoherent).

### Verified
- **`scripts/sim_longhorizon.py`** — deterministic reference for the time/cycle
  thresholds a short run can't reach: saturation (warn@5 / boost@10 / HALT@15),
  contrarian cadence (`cycle % 10`), action-queue decay (Step 6-C6). Checked
  against the shipped `config.example.json`.
- **Stack-agnostic auto-merge gate** — `verify.py` asserts a low-risk green change
  is eligible across Go / Rust / Node / Ruby / Java shapes; the gate never reads
  the language. TESTING.md documents `check-tests`' stack coverage.
- `verify.py` **34 → 38 PASS / 0 FAIL**.

---

## [v1.2.0] — 2026-06-09

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
  unless you flip the switch.**
- **Live-verified end-to-end** (Tier B+, throwaway repo): a low-risk PR
  auto-merged; oversize/protected stayed Draft; a failed post-merge health check
  auto-reverted + HALTed; `/ooda-config rollback` worked. The run **found and
  fixed a rollback bug** — auto-merge now uses `gh pr merge --squash` (linear
  `main`) so the 4-C2 / Step-R revert is a clean `git revert HEAD` (a `--merge`
  merge commit needed `-m` and left `main` half-reverted). See TESTING.md.

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
