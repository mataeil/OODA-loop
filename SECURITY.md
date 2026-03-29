# Security Policy — ooda-harness

## Reporting Vulnerabilities

**Do not open public GitHub issues for security bugs.**

Security vulnerabilities in ooda-harness should be reported privately to:

    security@ooda-harness.dev

Include a description of the issue, steps to reproduce, and the potential impact.
We practice responsible disclosure: reporters will receive acknowledgment within
**48 hours** and a resolution timeline within 7 days. We ask that you hold off on
public disclosure until a fix is available.

---

## Threat Model

ooda-harness is an autonomous AI agent that can read your codebase, open pull
requests, run deployment workflows, and at Level 3 merge PRs without human
approval. This capability creates a threat surface that differs from ordinary
software. The threats and mitigations below reflect deliberate design decisions.

### Threat 1: Self-Modification

**Risk.** The agent modifies its own safety rules, contracts, or core engine
(`agent/safety/*`, `agent/skills/meta/*`, `agent/contracts/*`), removing
guardrails that govern its own behavior.

**Mitigation.** Those paths are declared as `protected_paths` in config. Any PR
that touches protected paths requires explicit human review and cannot be
auto-merged, regardless of the current complexity level. The agent cannot
modify its own policy files without human approval.

---

### Threat 2: Secret Exposure

**Risk.** The agent stages API keys, tokens, or other secrets into a git commit
and exposes them in the repository or PR diff.

**Mitigation.**
- `git add -A` is forbidden in all skills. Only explicitly named files may be
  staged.
- `config.json` (which holds runtime config) is in `.gitignore` and must never
  be committed.
- `config.example.json` uses `$ENV_VAR` placeholders for all credentials. The
  runtime config resolves those references from environment variables at load
  time — secrets never appear as literals in config files.

---

### Threat 3: Unbounded Autonomous Action

**Risk.** The agent creates excessive pull requests, deploys broken code
repeatedly, or accumulates large API costs without operator awareness.

**Mitigation.**
- Maximum 1 PR per cycle (`max_prs_per_cycle: 1`).
- Maximum 20 files and 500 lines per PR (`max_files_per_pr`, `max_lines_per_pr`).
  Exceeding either limit forces Level 3 review.
- Minimum 30-minute interval between cycles (`min_cycle_interval_minutes: 30`).
- Daily API cost cap of $10 USD by default (`cost.daily_limit_usd`). A warning
  fires at 80% of the limit; a hard stop fires when the limit is reached.

---

### Threat 4: Confidence Manipulation

**Risk.** The agent inflates its own confidence scores to exceed the
`confidence_threshold`, causing it to act on domains where its track record is
poor.

**Mitigation.** Confidence updates are formula-driven and non-negotiable:
- Merged PR: `+0.1` (`confidence.merge_boost`)
- Rejected PR: `-0.2` (`confidence.reject_penalty`)
- All values are clamped to the range `[0.1, 1.0]`.

The agent cannot set confidence scores directly. The formulas are applied by the
evolve engine after each PR outcome, not by skill logic.

---

### Threat 5: HALT Bypass

**Risk.** The agent ignores the HALT file, overwrites it, or deletes it as part
of cleanup logic, removing the operator's ability to stop the agent immediately.

**Mitigation.**
- The HALT check is **Step 0** of every cycle — it runs before any observation,
  strategy, or action logic. There is no code path that bypasses it.
- The check is a simple file-existence test (`test -f agent/safety/HALT`), not a
  complex condition that could be circumvented by edge cases.
- `agent/safety/*` is a protected path. The agent cannot open a PR that deletes
  or modifies the HALT file without triggering Level 3 review.

---

### Threat 6: Skill Injection

**Risk.** An unregistered or malicious skill is loaded and executed by the evolve
engine, running arbitrary code under the agent's permissions.

**Mitigation.** The `skill_allowlist` in config limits which registered skills
evolve may call. When the allowlist is empty (the default), all currently
registered skills are eligible — but "registered" means explicitly present in the
skills directory with a valid `SKILL.md` contract. Arbitrary shell commands or
unregistered paths cannot be injected.

In production, set `skill_allowlist` to an explicit list of skill names.

---

## Safety Mechanisms

### HALT File

| Property  | Value                     |
|-----------|---------------------------|
| Location  | `agent/safety/HALT`       |
| Trigger   | File exists (any content) |
| Effect    | evolve stops at Step 0, no cycle proceeds |
| Scope     | Protected path — cannot be modified by the agent |

**To stop the agent immediately:**

```
touch agent/safety/HALT
```

**To resume:**

```
rm agent/safety/HALT
```

The HALT file is the "big red button". It requires no config change, no restart,
and no understanding of internal state. Any operator can create the file and the
agent stops on its next heartbeat.

---

### Progressive Complexity Levels

The agent operates at one of four levels. Start at Level 0 and advance only when
you are confident in the agent's behavior.

| Level | Name               | Domains Active | Implementation | Auto-Merge |
|-------|--------------------|----------------|----------------|------------|
| 0     | Just watching      | 1              | No             | No         |
| 1     | Watching + testing | 2              | No             | No         |
| 2     | Full observation   | All            | No             | No         |
| 3     | Autonomous         | All            | Yes            | Yes        |

At Levels 0–2 the agent only observes and proposes. No PRs are merged without
human approval. Level 3 enables auto-merge and is the only level where the agent
can make changes to your codebase without a human click.

Protected paths always require human review, even at Level 3.

---

### Protected Paths

Changes to the following paths always require human review, regardless of the
current complexity level:

| Path                  | Contains                                |
|-----------------------|-----------------------------------------|
| `agent/safety/*`      | Safety policy, HALT file                |
| `agent/skills/meta/*` | Core evolve engine                      |
| `agent/contracts/*`   | Skill interface contracts               |

Any PR touching these paths requires explicit human review and cannot be
auto-merged, regardless of the current complexity level.

---

### PR Limits

| Limit                 | Default | Config Key                   |
|-----------------------|---------|------------------------------|
| PRs per cycle         | 1       | `safety.max_prs_per_cycle`   |
| Files per PR          | 20      | `safety.max_files_per_pr`    |
| Lines per PR          | 500     | `safety.max_lines_per_pr`    |

Exceeding any limit automatically escalates the PR to Level 3 for human review.
Limits can be tightened but should not be loosened without careful consideration.

---

### Confidence Threshold

Actions for a domain are skipped when that domain's confidence score is below
`safety.confidence_threshold` (default `0.6`). Confidence falls when PRs are
rejected, preventing the agent from repeatedly acting on domains where its
judgment is unreliable. Scores recover gradually as PRs are merged.

---

### Cost Controls

| Setting                     | Default | Config Key                       |
|-----------------------------|---------|----------------------------------|
| Daily limit                 | $10 USD | `cost.daily_limit_usd`           |
| Warning threshold           | 80%     | `cost.warning_threshold_pct`     |

At 80% of the daily limit a warning is logged. When the limit is reached the
cycle is halted for the remainder of the day. Adjust the limit in config to match
your budget; setting it to `0` disables the hard stop (not recommended).

---

## Best Practices for Operators

1. **Start at Level 0.** Run at least three cycles and review the decision logs
   before advancing to a higher level.

2. **Keep `first_cycle_observe_only: true`.** The first cycle should never
   produce a PR. Verify that the agent's observations make sense for your project
   before allowing any action.

3. **Use `--dry-run` before enabling autonomous mode.** Run `/evolve --dry-run`
   to see what actions the agent would take without actually creating PRs or
   making changes.

4. **Set an explicit `skill_allowlist` in production.** The default empty list
   permits all registered skills. Lock it down to only the skills your project
   actually needs.

5. **Monitor `agent/state/evolve/state.json` regularly.** Anomalies in domain
   scores, confidence values, or action counts are early indicators of unexpected
   behavior.

6. **Back up state files before major config changes.** State is stored in
   `agent/state/`. Copy it before editing `config.json` or changing complexity
   levels so you can roll back if needed.

7. **Review the first few cycles' decision logs manually.** Even after advancing
   past Level 0, periodic manual review of evolve output keeps you informed of
   what the agent is prioritizing.

8. **Never store secrets in `config.json`.** Use `$ENV_VAR` references and pass
   values through environment variables. Treat `config.json` as you would a
   `.env` file: never commit it.

---

## Supported Versions

Only the **latest release** of ooda-harness receives security patches. If you
are running an older version, upgrade before reporting a vulnerability or
applying a fix.
