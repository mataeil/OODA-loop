# CONCEPTS — OODA-loop Glossary & Architecture

This document defines the key terms and architectural patterns used in OODA-loop.
It is intended for solo indie hackers and side project developers who want to understand
how the OODA-based autonomous AI agent engine works before configuring or extending it.

---

## The OODA Loop

Boyd's OODA loop (Observe → Orient → Decide → Act) is the engine behind every autonomous cycle.
In OODA-loop, each `/evolve` run executes one complete loop:

- **Observe** — Collect signals from all configured domains: service health, test results,
  backlog size, GitHub PR status, and any other data sources your config defines.

- **Orient** — Analyze patterns across the collected signals. Update per-domain confidence
  scores based on past outcomes (PR merges, rejections). Build a "world model" — a snapshot
  of what the system knows right now. Apply memo-driven adjustments for cross-domain balance.
  **This is the key differentiator.** Orientation is not just score math; it is pattern
  recognition, confidence calibration, and contextual reasoning.

- **Decide** — Score every domain using the scoring formula. The domain with the highest
  score wins and its primary skill is selected for execution.

- **Act** — Execute the winning skill. Create PRs, update state files, trigger skill chains,
  and write a decision log entry.

---

## Key Concepts

| Term | Definition |
|------|------------|
| **Cycle** | One complete OODA loop execution. Triggered by running `/evolve`. |
| **Domain** | A category of concern (e.g., `service_health`, `test_coverage`, `competitors`). Each domain has a weight, a state file, and a primary skill. Domains are configured in `config.json`. |
| **Skill** | A Claude Code slash command that performs a specific task (e.g., `/scan-health`, `/check-tests`). Skills are registered to domains in `config.json` and can be chained together. |
| **Weight** | A multiplier applied to a domain's staleness score during Decide. Higher weight means the domain gets attention sooner. Example: `service_health` uses `2.0` (critical path), `competitors` uses `0.3` (low frequency). |
| **Confidence** | A per-domain score from `0.1` to `1.0` that tracks how well past actions in that domain have been received. Increases on PR merge (`+0.1`), decreases on PR rejection (`-0.2`). Used in the scoring formula. |
| **Scoring Formula** | `score = staleness + dampened_alert + (goal × goal_weight) + (confidence × conf_weight) + memo + balance_penalty`. Staleness uses logarithmic curve by default: `weight × 10 × ln(1 + hours/4)`. Alert dampener reduces bonus for recently-selected domains. Balance penalty prevents domain monopoly via entropy. Floor clamp: negative scores clamped to `0`. The domain with the highest score wins the cycle. |
| **Implementation Domain** | A special domain that converts queued observations into code changes (PRs). Uses a scoring formula based on action queue pressure rather than staleness. Disabled by default — enabled only at Level 3. |
| **Action Queue** | A prioritized list of pending implementation tasks, each scored by RICE (Reach × Impact × Confidence / Effort). Items lose confidence if left unactioned for 14+ days. |
| **HALT File** | `agent/safety/HALT` — if this file exists when `/evolve` runs, the engine stops immediately before taking any action. The ultimate safety valve. To resume, delete the file. |
| **Safety Levels** | Progressive autonomy tiers. **Level 0**: observe only, 1 domain. **Level 1**: observe + test, 2 domains. **Level 2**: full observation, all domains, draft PRs (human merges). **Level 3**: autonomous, implementation enabled, auto-merge allowed. |
| **Protected Paths** | Files and directories that always require human review, even at Level 3: `agent/safety/*`, `skills/evolve/*`, `agent/contracts/*`. PRs touching these paths cannot be auto-merged at any level. Prevents the agent from rewriting its own safety rules or contracts. |
| **Skill Chain** | A sequence of skills executed after the primary skill completes. Example: after `run-deploy`, chain `scan-health` to verify the deployment succeeded. Defined per-domain in `config.json`. |
| **Contract** | The interface specification that all skills must follow. Defined in `agent/contracts/schema.md`. Ensures consistent input/output shape across the harness. |
| **Memo / Score Adjustment** | Cross-cycle notes that adjust domain scores in the next Orient phase. Example: "3 consecutive `business_strategy` runs → boost `ux_evolution` +1.0 for balance." Memos are consumed after they are applied. |
| **Dry Run** | `/evolve --dry-run` executes Observe → Orient → Decide but skips Act entirely. Prints the full score table and identifies which domain would have won. Safe to run at any time. |
| **First Cycle Observe-Only** | When `first_cycle_observe_only: true` is set in `config.json`, the very first `/evolve` run only observes all domains without executing any action. Builds initial state files safely before autonomous operation begins. |
| **3-Tier Memory** | Working memory (last 20 `decision_log` entries) → Episodes (52 weeks of summaries) → Principles (permanent learnings). Information cascades from short-term to long-term as cycles accumulate. |
| **Contrarian Check** | Every `memory.contrarian_check_interval` cycles (default 10), the engine must generate one counter-argument to its currently dominant strategy. The result is stored as a memo with type `"contrarian"`. Prevents tunnel vision and over-indexing on a single domain. |
| **Implicit Guidance** | Boyd's "Orient feeds directly into Act" shortcut. Before formal scoring, the Decide phase checks for (1) critical alerts that bypass scoring entirely, and (2) stable patterns where the same domain won 3+ consecutive cycles with confidence >= 0.8. Implemented in the evolve engine as Step 3-A0. |
| **Adaptive Lens** | A per-domain learning file (`agent/state/{domain}/lens.json`) that evolves each cycle. Observe skills load their lens to focus on high-variance metrics, learned thresholds, and cross-domain correlations. Bad learning decays 2x faster than good learning grows (asymmetric confidence: +0.1 confirm, -0.2 disconfirm). Max 50 items per lens; items below confidence 0.1 are deprecated. |
| **Domain Status** | A lifecycle field on each domain in `config.json`. Values: `"active"` (fully operational), `"available"` (configured but skill not yet generated -- run `/ooda-skill create`), `"disabled"` (manually paused), `"paused"` (temporarily suspended with resume date), `"degraded"` (active but reduced weight), `"saturated"` (auto-detected, reduced frequency). Only `active` and `degraded` domains participate in scoring. |
| **Graceful Degradation** | If GitHub, CI, or test infrastructure are unavailable, the engine disables dependent features instead of failing hard. The cycle continues with reduced scope. |
| **Logarithmic Staleness** | The staleness term uses `weight × K × ln(1 + hours/T)` (K=10, T=4) instead of linear `hours × weight`. This prevents extreme scores (168h × 2.0 = 336 under linear vs 37.6 under log) that caused domain monopoly in production. Configurable via `config.scoring.staleness_curve`. |
| **Alert Recency Dampener** | Reduces alert bonus for domains that were recently selected. Prevents alert-driven domain monopoly. After `max_consecutive_alert_cycles` (default 3) consecutive alert selections, the bonus auto-acknowledges to 0. Critical alerts bypass the dampener. |
| **Saturation Circuit Breaker** | Detects when the engine runs consecutive observe-only cycles without producing actionable output. Warning at 5 cycles, action queue boost at 10, auto-HALT at 15. Configured via `config.saturation`. |
| **Observation Micro-Adjustments** | At Level < 3, confidence receives small updates from observation results: +0.02 for actionable findings, +0.03 for alerts, -0.01 for no new data. Prevents confidence stagnation in observation-only deployments. |
| **Entropy Balance Penalty** | Penalizes domains that monopolize execution. Formula: `-B × (domain_share - expected_share)` where B=5.0. A domain running 50% of cycles in a 5-domain setup (expected: 20%) gets -1.5 penalty. |
| **Per-Domain Cooldown** | Optional `min_interval_hours` per domain. A domain within its cooldown period gets score 0 regardless of other factors. |
| **Action Queue Workflow** | Human-in-the-loop states: `approved` (priority execution), `deferred` (excluded for N days), `rejected_by_human`, `review_feedback`. Managed via `/ooda-config action` commands. |
| **Season Modes** | Project lifecycle modes (e.g., default, intensive, maintenance) with weight overrides and domain enable/disable rules. Switch via `/ooda-config mode {name}`. |
| **Cross-Domain Cascade** | When a change in one domain affects dependent domains (configured via `config.domain_dependencies`), affected domains receive +3.0 score bonus to ensure they update. Cascade resolves when all affected domains have run. |
| **Extended RICE** | Optional extra dimensions beyond base RICE (Reach×Impact×Confidence/Effort). Projects define extensions in `config.scoring.rice_extensions` with weights. Formula: `base_RICE × (1 + Σ extension_i × weight_i)`. |
| **Risk Tier Classification** | File-pattern-based risk classification for actions. Configurable via `config.safety.risk_rules`. Supplements the default file-count-based tier system. |
| **Data Classification** | Security level for skill data access. `internal` (local files), `api` (first-party APIs), `external` (third-party/web search). External skills at Level < 3 require human approval. |
| **Consensus Execution** | Optional execution mode where a skill runs N times with different perspectives. Items agreed upon by >= threshold fraction of runs are included in output. Defined in skill contracts as `execution_mode: consensus`. |
| **Rollback Protocol** | Pre-action checkpoints (5 retained) for post-merge recovery. Auto-reverts on health failure after auto-merge. Manual rollback via `/ooda-config rollback {cycle}`. Opt-in via `config.safety.enable_rollback`. |

> **Scoring Dynamics.** The logarithmic staleness curve ensures no domain scores above ~40 regardless of how long it has been idle (vs 336+ under the legacy linear curve). Combined with the entropy balance penalty, this prevents domain monopoly — the most common pathology observed in production (36% of 64 cycles taken by a single domain before the fix). Alert dampening adds another layer: even with active alerts, a domain cannot monopolize more than 3 consecutive cycles. These three mechanisms (log staleness, entropy penalty, alert dampener) work together to ensure healthy domain rotation while still responding to genuine urgency.

---

## Architecture Overview

```
User runs /evolve
  → Step 0: Check HALT file
              └─ If HALT exists: stop immediately, log reason

  → Step 1: Observe
              └─ Read all domain state files
              └─ Query GitHub for PR status, CI results
              └─ Collect urgent signals (alerts, error spikes)

  → Step 2: Orient
              └─ Detect patterns across signals
              └─ Update per-domain confidence scores
              └─ Build world model snapshot
              └─ Apply memo adjustments

  → Step 3: Decide
              └─ Implicit Guidance check (critical alerts / stable patterns)
              └─ Score all domains using scoring formula (floor clamp to 0)
              └─ Apply safety level filters (disabled domains)
              └─ Select winning domain and skill

  → Step 4: Act  (skipped in --dry-run mode)
              └─ Execute primary skill
              └─ Execute skill chain (if configured)
              └─ Create PR or update state

  → Step 5: Reflect
              └─ Write decision_log entry
              └─ Update domain state file (last_run timestamp)
              └─ Update Adaptive Lens for observed domains
              └─ Cascade memory (working → episodes → principles)

  → Commit state changes to git
```

---

## File Structure

```
OODA-loop/
├── skills/                 # All SKILL.md files (plugin auto-discovers)
│   ├── evolve/             # Meta-orchestrator (protected)
│   ├── scan-health/        # Observe: HTTP health monitoring
│   ├── check-tests/        # Detect: test coverage tracking
│   ├── plan-backlog/       # Strategize: GitHub Issues RICE scoring
│   ├── run-deploy/         # Execute: GitHub Actions deployment
│   ├── dev-cycle/          # Support: full implementation pipeline
│   ├── ooda-setup/         # Support: setup wizard
│   ├── ooda-config/        # Support: config CLI + action queue management
│   ├── ooda-status/        # Support: status dashboard
│   └── ooda-skill/         # Support: skill generator
├── agent/
│   ├── contracts/          # Skill interface specification (protected)
│   ├── safety/             # Safety policy + HALT file (protected)
│   └── state/              # Runtime state files (generated, gitignored)
│       └── evolve/         # Engine state (decision_log, confidence, etc.)
├── config.json             # Your project config (from config.example.json)
├── config.example.json     # Template — copy this to start
└── .claude-plugin/         # Claude Code plugin manifest
```

Key configuration note: copy `config.example.json` to `config.json` to begin.
Never commit secrets to `config.json` — use `$ENV_VAR` references for tokens and keys.

---

## Further Reading

- **README.md** — Quick start guide: installation, first cycle, configuration basics
- **CONTRIBUTING.md** — How to add domains, write new skills, and extend the harness
- **SECURITY.md** — Safety levels in detail, HALT file usage, and protected path policy
