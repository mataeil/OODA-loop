# Autonomous Mode — Safety Policy

This document is the runtime safety contract for OODA-loop. Every skill and
the evolve engine MUST read and obey these rules. Violations are bugs.

All thresholds and limits are read from `config.json` at runtime. This document
defines the rules; the config defines the values.

---

## HALT — Emergency Stop [ENFORCED]

Before ANY work, check: `test -f <config.safety.halt_file>`

- File exists: **stop immediately**. Log the reason if the file has content.
  Do not observe, orient, decide, or act.
- File absent: proceed.
- The HALT file is a protected path. The agent MUST NOT create, modify, or
  delete it under normal operation. (The post-merge health check is the sole
  exception — see below.)

Stop: `touch agent/safety/HALT` | Resume: `rm agent/safety/HALT`

---

## Progressive Complexity Levels [ENFORCED]

Read from `config.progressive_complexity.current_level`. Only a human may change it.

| Level | Observe | Create PRs | Auto-Merge | Implementation |
|-------|---------|------------|------------|----------------|
| 0     | 1 domain  | No  | No  | No  |
| 1     | 2 domains | No  | No  | No  |
| 2     | All       | Draft only | No  | No  |
| 3     | All       | Yes | Yes | Yes |

- **Level 0-1**: Observe only. State file updates and decision logs permitted.
- **Level 2**: Draft PRs allowed. Human must approve and merge.
- **Level 3**: Full autonomy. Auto-merge permitted for non-protected paths.

First cycle is observe-only when `config.safety.first_cycle_observe_only` is
true, regardless of level.

---

## Protected Paths — Self-Modification Ban [ENFORCED]

Paths in `config.safety.protected_paths` cannot be auto-merged at any level.
Any PR touching a protected path:

1. Requires human review — cannot be auto-merged, even at Level 3.
2. Must be flagged with `[PROTECTED PATH]` in the PR description.

Default: `agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*`.

The agent cannot remove paths from this list. Only human edits to `config.json`
can change protected paths.

---

## Skill Allowlist [ENFORCED]

Evolve may only invoke skills in `config.safety.skill_allowlist`. If non-empty,
calling an unlisted skill MUST be blocked and logged as a safety violation.

Empty allowlist = all registered skills eligible. Set an explicit list in production.

---

## PR Size Limits [ENFORCED]

Every agent-created PR must respect:
- `config.safety.max_files_per_pr` — max files changed
- `config.safety.max_lines_per_pr` — max lines changed (additions + deletions)
- `config.safety.max_prs_per_cycle` — max PRs per evolve cycle

Exceeding limits: split into smaller PRs, or escalate to human review.

---

## Cost Hard Gate [ENFORCED]

Tracks estimated API cost against `config.cost.daily_limit_usd`.

- At `config.cost.warning_threshold_pct`: log warning in decision log.
- At 100%: **stop the cycle gracefully**. Complete in-progress git operations
  (no dirty state), write decision log, halt. No new cycles until next UTC day.
- `daily_limit_usd: 0` disables the gate (not recommended).

---

## Post-Merge Health Check [ENFORCED at Level 3]

When auto-merge is active, every merged PR triggers verification:

1. Wait for CI/deploy propagation (duration is implementation-defined).
2. Run health check (`config.test_command` / `config.health_endpoints`).
3. **Pass**: cycle completes normally.
4. **Fail**:
   a. `git revert --no-edit <merge-sha>` and push.
   b. Create HALT file with the failure reason as content.
   c. Notify operator if notifications are configured.
   d. Log the incident.

No second merge attempt after failure. HALT ensures human intervention.

---

## Confidence Gate [ENFORCED]

A domain is skipped during Act if its confidence score is below
`config.safety.confidence_threshold`. Confidence updates follow formulas in
`config.confidence`, applied only by the evolve engine after PR outcomes.
The agent cannot set confidence scores directly.

---

## Cycle Interval [ENFORCED]

Minimum time between cycles: `config.safety.min_cycle_interval_minutes`.
Request before interval elapsed = wait or decline. Prevents runaway loops.

---

## Git Hygiene [ENFORCED]

- **No `git add -A` or `git add .`**. Stage files by explicit path only.
- Autonomous branches: `auto/<skill-name>/<description>`.
- State files (`agent/state/*`): direct commit to default branch allowed.
- Code changes: branch + PR required.

---

## Secret Management [RECOMMENDED]

- `config.json` is gitignored — never commit it.
- Credentials use `$ENV_VAR` references, resolved at runtime.
- Before staging, verify files do not contain tokens, keys, or passwords.

---

## Notifications [RECOMMENDED]

Notify operator on: HALT creation, health check failure, cost warning, PR events.
Notification delivery failure is non-fatal — the cycle continues regardless.

---

## Branch Strategy [RECOMMENDED]

- Prefer draft PRs over direct commits for code changes.
- Branch naming: `auto/<skill-name>/<date>-<description>`.
- State file updates are exempt from branching requirements.

---

## Operator Checklist

Before advancing complexity level:

- [ ] Ran at least 3 cycles at current level
- [ ] Reviewed decision logs for unexpected behavior
- [ ] Confirmed `skill_allowlist` is explicit in config
- [ ] Confirmed `protected_paths` covers safety, meta, and contracts
- [ ] Tested HALT file (create, verify stop, remove, verify resume)
- [ ] Set `daily_limit_usd` appropriate for your budget
